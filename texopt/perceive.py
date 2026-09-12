# -*- coding: utf-8 -*-
"""感知层：L1 源码 / L2 编译日志 / L3 PDF（页面图像视觉层在 advanced 阶段）。

L1 源码：文档类与字号、geometry、twocolumn/fleqn、浮动体（含位置参数）、
         插图宽度、tabular 行区间；
L2 日志：页数、overfull/underfull hbox、页面垂直问题 vbox、
         浮动体警告、其余 Warning、首个错误；
L3 PDF ：pdfinfo 真实页数，与 L2 交叉验证。

多源判断（advanced 目标）的代码侧基础：源码结构与编译日志在此交叉，
表格超宽即通过『overfull 行号落在 tabular 区间』判定。
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass

from . import engine, visual

# ---------------------------------------------------------------- 源码解析

DOC_CLASS_RE = re.compile(r"\\documentclass(?:\[([^\]]*)\])?\{([^}]*)\}")
GEOMETRY_USE_RE = re.compile(
    r"\\usepackage(?:\[([^\]]*)\])?\{geometry\}"           # 单次形式
    r"|\\RequirePackage(?:\[([^\]]*)\])?\{geometry\}"      # 类内部形式
)
LEN_UNIT_TO_MM = {"mm": 1.0, "cm": 10.0, "in": 25.4, "pt": 25.4 / 72.27}
FLOAT_ENV_SPEC_RE = re.compile(
    r"\\begin\{(figure|table)(\*?)\}(?:\[([^\]]*)\])?")
INCLUDEGRAPHICS_RE = re.compile(r"\\includegraphics(?:\[([^\]]*)\])?\{")
TABULAR_ENV_RE = re.compile(r"\\begin\{tabular(?:\*)?\}")
TABULAR_END_RE = re.compile(r"\\end\{tabular(?:\*)?\}")

# ---------------------------------------------------------------- 元信息/结构模式
# 阅读辅助内容（明确非论文正文，可直接删除）与告示类块（WARNING 等）。
# 这两个模式同时被 actions（删除）与 perceive（检测）使用，定义在此避免循环导入。
READING_AID_RE = re.compile(
    r"(?i)(START\s+READING\s+HERE|READ\s+ME\s+FIRST)"
    r"|document order was not finalized")
WARNING_RE = re.compile(r"(?i)(?:^|[\s\\{])(?:\\?[a-zA-Z]*\{?){0,2}\s*"
                        r"(WARNING|CAUTION|ATTENTION)\s*:")
CALLOUT_ENVS = {"quote", "quotation", "center", "flushleft", "flushright",
                "minipage", "tcolorbox", "mdframed", "note", "warning",
                "warnbox", "alertbox", "attentionbox", "framed", "shaded",
                "callout", "infobox", "hintbox", "storybox", "asidebox",
                "cautionbox", "notebox", "importantbox"}
ANY_ENV_RE = re.compile(r"\\(begin|end)\{([a-zA-Z*]+)\}")
HEADER_RE = re.compile(
    r"\\fancyhead|\\pagestyle\{fancy\}"
    r"|\\usepackage(?:\[[^\]]*\])?\{fancyhdr\}")
HEADING_COLOR_RE = re.compile(
    r"\\sectionfont\s*\{|\\titleformat|\\addtokomafont|\\chaptertitlefont")

# ---------------------------------------------------------------- 标题字号规范
# 供 actions.normalize_heading_size（修复）与 scan_hygiene（检测）共用，
# 保证「检测到什么」与「能修什么」是同一套规则。
SIZE_ORDER = ["tiny", "scriptsize", "footnotesize", "small", "normalsize",
              "large", "Large", "LARGE", "huge", "Huge"]
# 各层级标题允许的最大字号（超出即视为排版异常，需规范化）
HEADING_SIZE_CAP = {"chapter": "Large", "section": "Large",
                    "subsection": "large", "subsubsection": "normalsize"}
_HEADING_FORMAT_RE = re.compile(
    r"\\titleformat\*?\s*\{\s*\\(chapter|section|subsection|subsubsection)"
    r"\s*\*?\s*\}")
_SECTIONFONT_RE = re.compile(
    r"\\(chapter|section|subsection|subsubsection)font\s*(?=\{)")
SIZE_CMD_RE = re.compile(r"\\(tiny|scriptsize|footnotesize|small|normalsize|"
                         r"large|Large|LARGE|huge|Huge)\b")


def tex_braced_arg(src: str, pos: int) -> tuple[str, int, int] | None:
    r"""从 src[pos] 起跳过空白，取一个花括号参数。

    返回 (内容, 内容起始, 右括号后位置)；花括号感知（\titleformat{\section}
    {\Huge\bfseries\color{red}}{...} 这类参数内部还有嵌套花括号，正则
    [^{}]* 取不全）。
    """
    i = pos
    while i < len(src) and src[i] in " \t\r\n":
        i += 1
    if i >= len(src) or src[i] != "{":
        return None
    depth, j = 0, i
    while j < len(src):
        if src[j] == "{":
            depth += 1
        elif src[j] == "}":
            depth -= 1
            if depth == 0:
                return src[i + 1:j], i + 1, j
        j += 1
    return None


def heading_size_violations(code: str) -> list[dict]:
    """标题字号异常：\\titleformat / \\xxxfont 里超出层级上限的字号。

    返回 [{level, line, cmd, cap}]，line 为设置所在行（1-based）。
    """
    out: list[dict] = []
    anchors: list[tuple[int, str, str]] = []
    for m in _HEADING_FORMAT_RE.finditer(code):
        level = m.group(1)
        arg = tex_braced_arg(code, m.end())     # 第 1 个参数 = 格式（含字号）
        if arg:
            anchors.append((m.start(), level, arg[0]))
    for m in _SECTIONFONT_RE.finditer(code):
        level = m.group(1)
        arg = tex_braced_arg(code, m.end())
        if arg:
            anchors.append((m.start(), level, arg[0]))
    for pos, level, arg in anchors:
        cap = HEADING_SIZE_CAP.get(level)
        if not cap:
            continue
        for sm in SIZE_CMD_RE.finditer(arg):
            cmd = sm.group(1)
            if SIZE_ORDER.index(cmd) > SIZE_ORDER.index(cap):
                out.append({"level": level, "line": code.count("\n", 0, pos) + 1,
                            "cmd": cmd, "cap": cap})
    return out


# 列表环境过大的垂直间距选项（itemsep/topsep/parsep/partopsep），单位->pt
LIST_ENV_RE = re.compile(r"\\begin\{(itemize|enumerate|description)\}\s*"
                         r"\[([^\]]*)\]")
LIST_SPACING_KEYS = ("itemsep", "topsep", "parsep", "partopsep")
_PT_PER_UNIT = {"pt": 1.0, "mm": 72.27 / 25.4, "cm": 72.27 / 2.54,
                "in": 72.27, "em": 10.0, "ex": 4.3, "mu": 0.5}


def _len_to_pt(expr: str) -> float | None:
    m = re.fullmatch(r"\s*(-?[0-9]*\.?[0-9]+)\s*(pt|mm|cm|in|em|ex|mu)?\s*",
                     expr)
    if not m:
        return None
    return float(m.group(1)) * _PT_PER_UNIT.get((m.group(2) or "pt").lower(), 1.0)


def list_spacing_violations(code: str, max_pt: float = 8.0) -> list[dict]:
    """列表环境里明显过大的垂直间距选项（> max_pt）。返回 [{line, key, val}]。"""
    out: list[dict] = []
    for m in LIST_ENV_RE.finditer(code):
        for opt in m.group(2).split(","):
            k, _, v = opt.partition("=")
            k = k.strip()
            if k not in LIST_SPACING_KEYS:
                continue
            pt = _len_to_pt(v)
            if pt is not None and pt > max_pt:
                out.append({"line": code.count("\n", 0, m.start()) + 1,
                            "key": k, "val": v.strip(), "pt": round(pt, 2)})
    return out


def env_spans(src: str, names: set) -> list:
    """栈式配对：返回 src 中指定环境的 (begin_idx, end_idx) 字符区间。"""
    stack, spans = [], []
    for m in ANY_ENV_RE.finditer(src):
        if m.group(1) == "begin":
            stack.append((m.group(2), m.start()))
        elif stack and stack[-1][0] == m.group(2):
            _n, s0 = stack.pop()
            if m.group(2) in names:
                spans.append((s0, m.end()))
    return spans


def norm_tabular_specs(b: str) -> str:
    r"""表格环境归一：\begin{tabular}{...}（可含嵌套 {p{40mm}...} 列格式、
    tabularx 的 {width}{cols}、[..] 参数）整组归为 \begin{TAB}{COLS}；
    \end{tabularx} 等归为 \end{TAB}。列格式属排版面（换 tabularx/调列宽
    允许）；表格内数据词不归一，仍严格比较。
    """
    _TAB_RE = re.compile('\\\\(begin|end)\\{(?:tabularx|tabular\\*?|longtable|array)\\}')
    out, i = [], 0
    while True:
        m = _TAB_RE.search(b, i)
        if not m:
            out.append(b[i:])
            break
        out.append(b[i:m.start()])
        if m.group(1) == "begin":
            j = m.end()
            while j < len(b):
                if b[j] == "[":
                    k = b.find("]", j)
                    j = k + 1 if k >= 0 else j + 1
                elif b[j] == "{":
                    depth, k = 0, j
                    while k < len(b):
                        depth += (b[k] == "{") - (b[k] == "}")
                        if depth == 0:
                            break
                        k += 1
                    j = k + 1
                else:
                    break
            out.append("\\begin{TAB}{COLS}")
            i = j
        else:
            out.append("\\end{TAB}")
            i = m.end()
    return "".join(out)



def fig_fingerprint(inner: str) -> str:
    """图形/表格内容指纹：排版面参数（宽/高/相对长度/浮动参数）归一，其余逐字比较。

    归一的是**尺寸与位置参数**（缩图/改图宽动作会动它们），
    图文件、题注、label、数据、TikZ 代码等仍逐字比较 —— 重绘/改写图
    内容依然会被判为「图形/表格内容被改动」。
    """
    s = re.sub(r"(?<!\\)%.*$", "", inner, flags=re.M)
    s = re.sub(r"(?:width|height)\s*=\s*[^,\]]+", "LEN=W", s)   # 宽/高值
    s = re.sub(r"\{\s*[0-9]*\.?[0-9]+\s*\\(?:textwidth|linewidth|"
               r"columnwidth|textheight|paperheight|hsize)\s*\}", "{LEN}", s)
    s = re.sub(r"(\\begin\{(?:figure|table)\*?\})\[[^\]]*\]", r"\1", s)  # 位置参数
    s = norm_tabular_specs(s)          # 表格环境名/列格式（tabular<->tabularx）
    return re.sub(r"\s+", " ", s).strip()


def _len_to_mm(text: str) -> float | None:
    m = re.fullmatch(r"\s*([0-9]*\.?[0-9]+)\s*(mm|cm|in|pt)?", text.strip())
    if not m:
        return None
    val = float(m.group(1))
    unit = (m.group(2) or "pt").lower()
    return val * LEN_UNIT_TO_MM[unit]


def _fmt_mm(v: float) -> str:
    v = round(v, 1)
    return f"{v:g}mm"


def _lineno(src: str, m) -> int:
    return src.count("\n", 0, m.start()) + 1


def parse_source(src: str) -> dict:
    """返回 L1 源码层结构化快照。"""
    info: dict = {
        "documentclass": None, "class_options": [],
        "font_pt": None,                      # 显式字号，None=默认 10pt
        "geometry": None,                     # 解析出的 geometry 行原文（若有）
        "geometry_margin_mm": None,           # 有效单边 margin（等效 mm）
        "geometry_explicit": False,           # 是否显式写了 margin/边距
        "has_microtype": False, "has_ctex": False,
        "floats": {"figure": 0, "table": 0},
        "float_envs": [],                     # {kind, starred, spec, line}
        "graphics_width_expr": [],            # includegraphics width 表达式
        "tabular_spans": [],                  # (起始行, 结束行) 每个 tabular 行区间
        "twocolumn": False, "fleqn": False,
        "body_start": -1,
        "abstract": False, "sections": 0,
        "lines": 0,
    }
    body_m = re.search(r"\\begin\{document\}", src)
    info["body_start"] = body_m.start() if body_m else -1

    dc = DOC_CLASS_RE.search(src)
    if dc:
        info["documentclass"] = dc.group(2)
        opts = (dc.group(1) or "").split(",")
        info["class_options"] = [o.strip() for o in opts if o.strip()]
        for o in info["class_options"]:
            m = re.fullmatch(r"(\d+)pt", o)
            if m:
                info["font_pt"] = int(m.group(1))
    if info["font_pt"] is None:
        # LaTeX 标准类缺省 10pt（article/report/book）
        info["font_pt"] = 10
    info["twocolumn"] = "twocolumn" in info["class_options"]
    info["fleqn"] = "fleqn" in info["class_options"]

    gm = GEOMETRY_USE_RE.search(src)
    if gm:
        opt_str = gm.group(1) if gm.group(1) is not None else gm.group(2)
        info["geometry"] = gm.group(0)
        opts = [o.strip() for o in (opt_str or "").split(",") if o.strip()]
        margin_val = None
        sides = {}
        for o in opts:
            k, _, v = o.partition("=")
            k = k.strip()
            if k == "margin":
                margin_val = _len_to_mm(v)
            elif k in ("top", "bottom", "left", "right"):
                mm = _len_to_mm(v)
                if mm is not None:
                    sides[k] = mm
        if margin_val is not None:
            info["geometry_margin_mm"] = margin_val
            info["geometry_explicit"] = True
        elif sides:
            info["geometry_margin_mm"] = min(sides.values())  # 保守取最小边
            info["geometry_explicit"] = True
        else:
            info["geometry_margin_mm"] = 25.4  # 显式 geometry 但未写边距 -> 默认 1in
            info["geometry_explicit"] = False
    else:
        info["geometry_margin_mm"] = 25.4      # 无 geometry -> 标准页边距 1in

    info["has_microtype"] = "microtype" in src
    info["has_ctex"] = bool(re.search(r"\\usepackage(?:\[[^\]]*\])?\{ctex\b", src)
                            or "ctexart" in src or "ctexrep" in src)

    for m in FLOAT_ENV_SPEC_RE.finditer(src):
        kind, starred, spec = m.group(1), bool(m.group(2)), m.group(3)
        info["floats"][kind] += 1
        info["float_envs"].append({
            "kind": kind, "starred": starred,
            "spec": spec.strip() if spec else None,
            "line": _lineno(src, m),
        })

    for m in TABULAR_ENV_RE.finditer(src):
        end = TABULAR_END_RE.search(src, m.end())
        e = _lineno(src, end) if end else _lineno(src, m)
        info["tabular_spans"].append((_lineno(src, m), e))

    for m in INCLUDEGRAPHICS_RE.finditer(src):
        opt_str = m.group(1) or ""
        wm = re.search(r"width\s*=\s*([^,\]]+)", opt_str)
        if wm:
            info["graphics_width_expr"].append(wm.group(1).strip())

    info["abstract"] = "\\begin{abstract}" in src
    info["sections"] = len(re.findall(r"\\section\*?\s*\{", src))
    info["lines"] = src.count("\n") + 1
    # ---- 结构规范（目录/页眉/标题着色）与图形保真指纹 ----
    info["has_toc"] = "\\tableofcontents" in src
    info["has_header"] = bool(HEADER_RE.search(src))
    info["has_heading_color"] = bool(HEADING_COLOR_RE.search(src))
    info["figures"] = [
        {"kind": src[a:b].split("{", 1)[1].split("}", 1)[0].rstrip("*"),
         "fingerprint": fig_fingerprint(src[a:b])}
        for a, b in env_spans(src, {"figure", "figure*", "table", "table*"})
    ]
    return info


# ---------------------------------------------------------------- 日志解析

OVERFULL_RE = re.compile(
    r"Overfull \\hbox \(([^)]*)\) in paragraph at lines (\d+)(?:--(\d+))?")
UNDERFULL_RE = re.compile(
    r"Underfull \\hbox \(([^)]*)\) in paragraph at lines (\d+)(?:--(\d+))?")
VBOX_RE = re.compile(
    r"(Overfull|Underfull) \\vbox \(([^)]*)\) has occurred while \\output is active")
FLOAT_WARN_RE = re.compile(r"LaTeX Warning: ([^\n]*[Ff]loat[^\n]*)")


def parse_log(log: str) -> dict:
    issues = {
        "overfull": [],    # {detail, lines, line}（表格内溢出会迁到 tables_overwide）
        "underfull": [],
        "vbox": [],        # {kind: Overfull|Underfull, detail}（页面垂直质量/孤行寡行代理）
        "floats": [],      # 浮动体警告（尺寸过大/位置被改等）
        "tables_overwide": [],
        "warnings": [],    # 其余文本去重后的 LaTeX Warning
        "errors": [],
    }
    for m in OVERFULL_RE.finditer(log):
        issues["overfull"].append({
            "detail": m.group(1).strip(),
            "lines": m.group(2) + ("--" + m.group(3) if m.group(3) else ""),
            "line": int(m.group(2)),
        })
    for m in UNDERFULL_RE.finditer(log):
        issues["underfull"].append({
            "detail": m.group(1).strip(),
            "lines": m.group(2) + ("--" + m.group(3) if m.group(3) else ""),
        })
    for m in VBOX_RE.finditer(log):
        issues["vbox"].append({"kind": m.group(1), "detail": m.group(2).strip()})
    for m in FLOAT_WARN_RE.finditer(log):
        issues["floats"].append(m.group(1).strip())

    seen = set()
    for m in re.finditer(r"LaTeX Warning: ([^\n]+)", log):
        t = m.group(1).strip()
        if "float" in t.lower():
            continue                      # 已入 issues["floats"]
        key = re.sub(r" on input line \d+", "", t)
        if key not in seen:
            seen.add(key)
            issues["warnings"].append(t)
    for m in re.finditer(r"^! (.+)$", log, re.M):
        issues["errors"].append(m.group(1).strip())
    return issues


def split_table_overfull(issues: dict, tabular_spans: list) -> None:
    """overfull 行号落在 tabular 区间内的 -> 归为表格超宽（表超宽只报告不自动改）。"""
    kept, tables = [], []
    for o in issues.get("overfull", []):
        ln = o.get("line")
        hit = bool(ln) and any(s - 1 <= ln <= e + 1 for s, e in tabular_spans)
        if hit:
            tables.append({"detail": o["detail"], "lines": o["lines"],
                           "line": ln})
        else:
            kept.append(o)
    issues["overfull"] = kept
    issues["tables_overwide"] = tables


# ---------------------------------------------------------------- 组合感知

@dataclass
class Perception:
    src: str
    source: dict
    compile: engine.CompileResult
    issues: dict
    pages: int | None          # 交叉验证后的权威页数
    pdf_pages: int | None
    pdf_info: str = ""
    visual: dict | None = None  # Phase 2：页面级视觉量化（来自实际 PDF）
    content: dict | None = None  # 会议口径：正文页数区间（scope=content 时才计算）

    @property
    def ok(self) -> bool:
        return self.compile.ok

    @property
    def content_pages_lower(self) -> int | None:
        """正文页数下界（参考文献之前的完整页数），无信息时为 None。"""
        return (self.content or {}).get("lower")

    @property
    def content_pages_upper(self) -> int | None:
        """正文页数上界（含参考文献首页），无信息时为 None。"""
        return (self.content or {}).get("upper")

    @property
    def overfull_count(self) -> int:
        return len(self.issues["overfull"])


def perceive(tex_path: str, req=None) -> Perception:
    """对给定 tex 执行一次完整感知（L1+L2+L3+页面视觉），返回快照。

    req 可选：用于把「要求规格」里的阈值传给源码层检测（标题字号上限、
    parskip/图高/窄表阈值等）；不传则用与 Requirement 相同的默认值。
    """
    with open(tex_path, encoding="utf-8", errors="replace") as f:
        src = f.read()
    source = parse_source(src)

    result = engine.compile_tex(tex_path)
    issues = parse_log(result.log)
    split_table_overfull(issues, source["tabular_spans"])
    issues["hygiene"] = scan_hygiene(src, **_hygiene_opts(req))

    pdf_pages = None
    if result.pdf_path:
        pdf_pages = engine.pdf_pages(result.pdf_path)

    pages = result.pages_from_log
    cross = ""
    if pages is not None and pdf_pages is not None:
        if pages != pdf_pages:
            cross = f"（警告：日志页数 {pages} 与 PDF 页数 {pdf_pages} 不一致）"
        pages = pdf_pages  # PDF 元数据更权威
    elif pdf_pages is not None:
        pages = pdf_pages

    # Phase 2：页面级视觉量化（来自实际编译后的 PDF；失败则降级为 None）
    vis = None
    want_visual = bool(result.pdf_path) and (
        req is None or getattr(req, "visual_metrics", True))
    if want_visual:
        try:
            tmp = os.path.join(os.path.dirname(os.path.abspath(tex_path)),
                               ".texopt-gray")
            vis = visual.analyze_pdf(result.pdf_path, tmp,
                                     dpi=getattr(req, "visual_dpi", 50) if req else 50)
        except Exception as exc:                      # 视觉层失败不影响主链路
            vis = {"error": f"视觉量化失败：{exc}", "pages": [], "defects": []}

    # 会议口径：页数上限针对「正文页」时，量取正文页数区间（参考文献不计）
    content = None
    if result.pdf_path and req is not None \
            and getattr(req, "page_limit_scope", "total") == "content":
        try:
            content = engine.content_pages(result.pdf_path)
        except Exception:                             # 量取失败不影响主链路
            content = None

    return Perception(
        src=src, source=source, compile=result,
        issues=issues, pages=pages, pdf_pages=pdf_pages,
        pdf_info=cross, visual=vis, content=content,
    )


def _hygiene_opts(req) -> dict:
    """把要求规格里的阈值转成 scan_hygiene 的关键字参数。"""
    g = lambda k, d: getattr(req, k, d) if req is not None else d
    return dict(title_cap=g("title_size_cap", "LARGE"),
                parskip_max_pt=g("parskip_max_pt", 8.0),
                header_max_chars=g("header_max_chars", 40),
                fig_max_height_frac=g("max_fig_height_frac", 0.40),
                narrow_table_min_frac=g("narrow_table_min_frac", 0.6),
                subfig_max_sum=g("subfig_max_sum", 0.95),
                text_width_mm=None)


# ---------------------------------------------------------------- 版心估算
# Phase 2：纸张/版心尺寸（用于判断“巨大图”“窄表格”这类与页面相关的缺陷）。
PAPER_SIZES_MM = {
    "a4paper": (210.0, 297.0), "a5paper": (148.0, 210.0),
    "b5paper": (176.0, 250.0), "letterpaper": (215.9, 279.4),
    "legalpaper": (215.9, 355.6), "executivepaper": (184.15, 266.7),
}


def paper_size_mm(class_options) -> tuple:
    for o in class_options or []:
        if o in PAPER_SIZES_MM:
            return PAPER_SIZES_MM[o]
    return PAPER_SIZES_MM["letterpaper"]      # LaTeX 标准类默认 letterpaper


def text_area_mm(source: dict) -> tuple:
    """估算版心 (width_mm, height_mm) = 纸张 - 页边距。"""
    w, h = paper_size_mm(source.get("class_options") or [])
    m = source.get("geometry_margin_mm")
    if m is None:
        m = 25.4
    return (max(w - 2 * m, 20.0), max(h - 2 * m, 20.0))


# ---------------------------------------------------------------- 新增静态检测
_TITLE_RE = re.compile(r"\\title\s*(?=\{)")
_PARSKIP_RE = re.compile(r"\\setlength\s*\{\s*\\parskip\s*\}\s*\{([^}]*)\}")
_HEADER_CMD_RE = re.compile(
    r"\\(?:lhead|rhead|chead|fancyhead(?:\s*\[[^\]]*\])?)\s*(?=\{)")
_MULTICOLS_RE = re.compile(r"\\begin\{(multicols\*?)\}\s*\{(\d+)\}")
_HEIGHT_OPT_RE = re.compile(r"(?:^|,)\s*height\s*=\s*([^,\]]+)")
_SUBFIG_W_RE = re.compile(
    r"\\begin\{(?:subfigure|subfloat|minipage)\}\s*\{([0-9]*\.?[0-9]+)\s*\\"
    r"(?:textwidth|linewidth|columnwidth)")
_PWIDTH_RE = re.compile(r"[pmb]\s*\{\s*([0-9]*\.?[0-9]+)\s*(mm|cm|in|pt)\s*\}")
_TABSPEC_RE = re.compile(r"\\begin\{(tabular\*?|tabularx|longtable)\}")


def title_size_violations(src: str, cap: str = "LARGE") -> list:
    """\\title{...} 内超出上限的字号命令（{cmd, line, cap}）。"""
    m = _TITLE_RE.search(src)
    if not m:
        return []
    got = tex_braced_arg(src, m.end())
    if not got:
        return []
    body, start = got[0], got[1]
    out = []
    for sm in SIZE_CMD_RE.finditer(body):
        cmd = sm.group(1)
        if SIZE_ORDER.index(cmd) > SIZE_ORDER.index(cap):
            out.append({"cmd": cmd, "cap": cap,
                        "line": src.count("\n", 0, start + sm.start()) + 1})
    return out


def parskip_violation(src: str, max_pt: float = 8.0):
    """\\setlength{\\parskip}{X} 中过大的 X（> max_pt）。"""
    m = _PARSKIP_RE.search(src)
    if not m:
        return None
    pt = _len_to_pt(m.group(1))
    if pt is None or pt <= max_pt:
        return None
    return {"pt": round(pt, 2), "expr": m.group(1).strip(),
            "line": src.count("\n", 0, m.start()) + 1}


def header_arg_violations(src: str, max_chars: int = 40) -> list:
    """页眉命令里过长/无意义的参数（如超长左页眉、\\today 之类）。"""
    out = []
    for m in _HEADER_CMD_RE.finditer(src):
        got = tex_braced_arg(src, m.end())
        if not got:
            continue
        arg = got[0].strip()
        if len(arg) > max_chars:
            out.append({"cmd": src[m.start():m.end()].strip(), "arg": arg,
                        "line": src.count("\n", 0, m.start()) + 1})
    return out


def multicols_local_spans(src: str) -> list:
    """局部（文档中途）双栏：multicols 环境且未覆盖整个正文。"""
    spans = env_spans(src, {"multicols", "multicols*"})
    if not spans:
        return []
    b0, b1 = -1, -1
    mb = re.search(r"\\begin\{document\}", src)
    if mb:
        b0 = mb.end()
        me = re.search(r"\\end\{document\}", src)
        b1 = me.start() if me else len(src)
    body_len = max(b1 - b0, 1)
    out = []
    for a, b in spans:
        if b0 >= 0 and not (b0 <= a < b1):
            continue
        m = _MULTICOLS_RE.search(src, max(a - 8, 0))
        cols = int(m.group(2)) if m else 2
        if (b - a) < 0.8 * body_len:               # 未覆盖正文 -> 局部双栏
            out.append({"line": src.count("\n", 0, a) + 1, "cols": cols})
    return out


def oversized_fig_heights(src: str, max_frac: float = 0.40,
                          text_h_mm: float | None = None) -> list:
    """\\includegraphics 里过大的 height（相对页高比例 > max_frac）。"""
    if text_h_mm is None:
        text_h_mm = text_area_mm(parse_source(src))[1]
    out = []
    for m in INCLUDEGRAPHICS_RE.finditer(src):
        opt = m.group(1) or ""
        hm = _HEIGHT_OPT_RE.search("," + opt)
        if not hm:
            continue
        expr = hm.group(1).strip()
        frac = None
        rm = re.fullmatch(r"([0-9]*\.?[0-9]+)\s*\\"
                          r"(?:textheight|paperheight|pageheight)", expr)
        if rm:
            frac = float(rm.group(1))
        else:
            mm = _len_to_mm(expr)
            if mm is not None:
                frac = mm / text_h_mm
        if frac is not None and frac > max_frac:
            out.append({"expr": expr, "frac": round(frac, 3),
                        "line": _lineno(src, m)})
    return out


def overfull_subfig_rows(src: str, max_sum: float = 0.98) -> list:
    """同一 figure 内多个子图/小页宽度之和超过版心（如 0.49+0.49+hspace）。"""
    out = []
    for a, b in env_spans(src, {"figure", "figure*"}):
        seg = src[a:b]
        vals = [float(m.group(1)) for m in _SUBFIG_W_RE.finditer(seg)]
        if len(vals) >= 2 and sum(vals) > max_sum:
            out.append({"sum": round(sum(vals), 3), "n": len(vals),
                        "line": src.count("\n", 0, a) + 1})
    return out


def narrow_tables(src: str, text_w_mm: float | None = None,
                  min_frac: float = 0.6) -> list:
    """列宽总和明显窄于版心的表格（如 p{2cm}p{2cm}p{2cm}p{2cm}）。"""
    if text_w_mm is None:
        text_w_mm = text_area_mm(parse_source(src))[0]
    out = []
    for m in _TABSPEC_RE.finditer(src):
        got = tex_braced_arg(src, m.end())
        if not got:
            continue
        spec = got[0]
        widths = [_len_to_mm(f"{v}{u}") for v, u in _PWIDTH_RE.findall(spec)]
        widths = [x for x in widths if x]
        if not widths:
            continue
        total = sum(widths)
        if total < min_frac * text_w_mm:
            out.append({"total_mm": round(total, 1), "line": _lineno(src, m),
                        "spec": spec.strip()})
    return out


# ---------------------------------------------------------------- 卫生/风格静态检测
# 结构化问题清单雏形：源码层可判定的「排版卫生」问题。这些大多不自动修
# （改法涉及作者意图/内容结构），进入 A 分并列入报告，让混乱程度可量化。

_SIZE_SWITCH_RE = re.compile(r"\\(?:tiny|scriptsize|footnotesize|small|"
                             r"normalsize|large|Large|LARGE|huge|Huge)\b")
_LINE_BREAK_TAIL_RE = re.compile(r"\\\\\*?\s*(?:\[[^\]]*\])?\s*$")
_DOLLAR_MATH_RE = re.compile(r"\$\$(.+?)\$\$", re.S)
_UNBREAKABLE_RE = re.compile(r"[A-Za-z]{80,}")
# 超长 URL（含 \url{...} 内的）：默认 TeX 只在少数位置断行，易出 Overfull
_LONG_URL_RE = re.compile(r"\\(?:url|href|path)\s*\{\s*https?://\S{40,}")


def _env_ranges(src: str, wanted: set) -> list:
    """通用栈式环境配对：返回 (begin_idx, end_idx) 区间，仅保留 wanted 内环境。

    任意 \\begin{X}/\\end{X} 都参与栈配对（LaTeX 环境严格嵌套），
    因此多个同层同名环境（如连续两个 center）不会错误合并。
    """
    _ANY_ENV_RE = re.compile('\\\\(begin|end)\\{([a-zA-Z*]+)\\}')
    stack: list = []
    ranges = []
    for m in _ANY_ENV_RE.finditer(src):
        kw, name = m.group(1), m.group(2)
        if kw == "begin":
            stack.append((name, m.start()))
        elif stack and stack[-1][0] == name:
            _n, s0 = stack.pop()
            if name in wanted:
                ranges.append((s0, m.start()))
        # 栈顶不匹配（异常输入）则忽略，保持容错
    return ranges


def scan_hygiene(src: str, *, title_cap: str = "LARGE",
                 parskip_max_pt: float = 8.0, header_max_chars: int = 40,
                 fig_max_height_frac: float = 0.40,
                 narrow_table_min_frac: float = 0.6,
                 subfig_max_sum: float = 0.95,
                 text_width_mm: float | None = None) -> list:
    """源码层静态扫描，返回卫生问题清单 [{kind, line, detail}]。

    阈值由要求规格（Requirement）传入；默认值与 Requirement 默认一致。
    """
    out: list = []
    # 去注释后的逐行代码（行数不变，行号映射仍准确；忽略 \% 转义）
    code_lines = [re.sub(r"(?<!\\)%.*$", "", ln) for ln in src.split("\n")]
    code = "\n".join(code_lines)

    def _line(idx: int) -> int:
        return code.count("\n", 0, idx) + 1

    # 表格/数学对齐环境行号（其内部 \\ 属合法行分隔，不算硬换行）
    _MATH_TAB_NAMES = {"tabular", "tabular*", "tabularx", "longtable",
                       "array", "align", "align*", "alignat", "alignat*",
                       "flalign", "flalign*", "gather", "gather*",
                       "multline", "multline*", "eqnarray", "eqnarray*",
                       "aligned", "alignedat", "gathered", "split", "cases",
                       "smallmatrix", "matrix", "pmatrix", "bmatrix",
                       "Bmatrix", "vmatrix", "Vmatrix"}
    skip_lines: set = set()
    for a, b in _env_ranges(code, _MATH_TAB_NAMES):
        skip_lines.update(range(_line(a), _line(b) + 1))

    # 1) 裸 $$ 数学
    for m in _DOLLAR_MATH_RE.finditer(code):
        out.append({"kind": "dollar_math", "line": _line(m.start()),
                    "detail": "裸 $$..$$ 数学（建议 \\[\\] 或 equation 环境，"
                              "间距与编号规范）"})
    # 2) 手动分页
    for m in re.finditer(r"\\(?:newpage|clearpage|pagebreak)\b", code):
        out.append({"kind": "manual_pagebreak", "line": _line(m.start()),
                    "detail": "手动分页 \\" + m.group(0)[1:] +
                              "（破坏浮动体全局最优放置，压缩页数时会挡路）"})
    # 3) 手动垂直间距
    for m in re.finditer(r"\\vspace\*?\s*\{|\\medskip\b|\\bigskip\b|\\smallskip\b",
                         code):
        out.append({"kind": "manual_vspace", "line": _line(m.start()),
                    "detail": "手动垂直间距（建议由 \\parskip 等统一定义）"})
    # 4) 下划线滥用（期刊规范普遍禁用）
    for m in re.finditer(r"\\underline\s*\{", code):
        out.append({"kind": "underline_abuse", "line": _line(m.start()),
                    "detail": "\\underline 强调（投稿通常禁用，建议 \\emph）"})
    # 5) \noindent
    for m in re.finditer(r"\\noindent\b", code):
        out.append({"kind": "noindent", "line": _line(m.start()),
                    "detail": "\\noindent 手工取消缩进（应交给文档全局样式）"})
    # 6) 行内字号开关（只扫正文：preamble 里的 \titleformat/\title 属样式声明，
    #    由 normalize_heading_size 规则单独检测，避免把合法样式误报成行内乱标）
    body_m = re.search(r"\\begin\{document\}", code)
    body_start = body_m.end() if body_m else 0
    for m in _SIZE_SWITCH_RE.finditer(code):
        if m.start() < body_start:
            continue
        out.append({"kind": "size_switch", "line": _line(m.start()),
                    "detail": f"行内字号切换 {m.group(0)}（应交给全局样式/宏）"})
    # 6b) 标题字号异常（preamble 的 \titleformat/\xxxfont 超出层级上限）
    for hv in heading_size_violations(code):
        out.append({"kind": "heading_size", "line": hv["line"],
                    "detail": f"{hv['level']} 标题字号 {hv['cmd']} 过大"
                              f"（建议不超过 {hv['cap']}）"})
    # 6c) 列表垂直间距过大（itemsep/topsep/parsep/partopsep）
    for lv in list_spacing_violations(code):
        out.append({"kind": "list_spacing", "line": lv["line"],
                    "detail": f"列表 {lv['key']}={lv['val']} 过大"
                              f"（{lv['pt']}pt，应交给列表默认间距）"})
    # 7) 段落硬换行 \\（表格/公式环境内除外）
    for idx, ln in enumerate(code_lines, start=1):
        if idx in skip_lines or not _LINE_BREAK_TAIL_RE.search(ln):
            continue
        if ln.strip().startswith("%") or not ln.strip():
            continue
        out.append({"kind": "hard_linebreak", "line": idx,
                    "detail": "段落内行尾 \\\\ 硬换行（破坏断行优化，"
                              "建议重写为自然段落）"})
    # 8) center 大段正文
    for a, b in _env_ranges(code, {"center"}):
        seg = code[a:b]
        if r"\includegraphics" in seg or r"\caption" in seg:
            continue                       # 图/表居中属常见用法，不算
        nlines = len([l for l in seg.split("\n") if l.strip()])
        if nlines > 3:
            out.append({"kind": "center_text", "line": _line(a),
                        "detail": "center 环境包裹整段正文（正文应左对齐，"
                                  "center 只用于图/表）"})
    # 9) 浮动体缺 caption
    for a, b in _env_ranges(code, {"figure", "figure*",
                                        "table", "table*"}):
        if "\\caption" not in code[a:b]:
            m = re.match(r"\\(?:begin)\{(figure|table)(\*?)\}", code[a:a + 40])
            out.append({"kind": "missing_caption", "line": _line(a),
                        "detail": f"{'图' if 'figure' in code[a:a + 40] else '表'}"
                                  f"浮动体缺 \\caption（期刊要求题注）"})
    # 10) 超长不可断词（overfull 常见来源）
    for m in _UNBREAKABLE_RE.finditer(code):
        out.append({"kind": "unbreakable", "line": _line(m.start()),
                    "detail": f"超长不可断词（{len(m.group(0))} 字符，"
                              f"易产生 Overfull；建议允许断词/重写）"})
    # 10b) 超长 URL（\url{} 等命令内的：可加载 xurl 允许任意位置断行）
    #      已加载 xurl 即视为已解决（否则注入 xurl 后问题仍会被反复报出）
    if "\\usepackage{xurl}" not in src:
        for m in _LONG_URL_RE.finditer(code):
            out.append({"kind": "long_url", "line": _line(m.start()),
                        "detail": f"超长 URL（{len(m.group(0))} 字符，"
                                  f"默认断行点少，易出 Overfull）"})
    # 11) 阅读辅助内容（明确非正文，可直接删除）
    for i, ln in enumerate(code_lines, start=1):
        if READING_AID_RE.search(ln):
            out.append({"kind": "reading_aid", "line": i,
                        "detail": f"阅读辅助内容：{ln.strip()[:60]}"
                                  f"（非论文正文，建议删除）"})
    # 12) WARNING/CAUTION 类告示块
    for i, ln in enumerate(code_lines, start=1):
        if ln.strip().startswith("%"):
            continue
        if WARNING_RE.search(ln.strip()[:60]) and "begin{lstlisting}" not in ln:
            out.append({"kind": "warning_box", "line": i,
                        "detail": f"WARNING 类告示：{ln.strip()[:60]}"
                                  f"（编辑性提示，非正文，建议删除）"})

    # 13) 文档标题字号异常（如 \title{\Huge ...}）
    for tv in title_size_violations(src, title_cap):
        out.append({"kind": "title_size", "line": tv["line"],
                    "detail": f"文档标题字号 {tv['cmd']} 过大"
                              f"（建议不超过 {tv['cap']}）"})
    # 14) 过大的段间距 \setlength{\parskip}{...}
    ps = parskip_violation(src, parskip_max_pt)
    if ps:
        out.append({"kind": "parskip", "line": ps["line"],
                    "detail": f"\\parskip={ps['expr']}（{ps['pt']}pt）过大，"
                              f"整篇段落间距失衡"})
    # 15) 异常/超长页眉
    for hv in header_arg_violations(src, header_max_chars):
        out.append({"kind": "header_abnormal", "line": hv["line"],
                    "detail": f"页眉 {hv['cmd']} 内容过长（{len(hv['arg'])} 字符）："
                              f"{hv['arg'][:40]}…"})
    # 16) 文档中途的局部双栏（multicols）
    for mv in multicols_local_spans(src):
        out.append({"kind": "multicols_mid", "line": mv["line"],
                    "detail": f"正文中途进入 {mv['cols']} 栏（multicols），"
                              f"版面节奏被打断"})
    # 17) 过大的图片高度（height=0.48\textheight 等）
    for fv in oversized_fig_heights(src, fig_max_height_frac):
        out.append({"kind": "fig_oversized", "line": fv["line"],
                    "detail": f"图片 height={fv['expr']} 占页高 "
                              f"{fv['frac'] * 100:.0f}%（过大）"})
    # 18) 子图并排宽度之和超版心
    for sv in overfull_subfig_rows(src, subfig_max_sum):
        out.append({"kind": "subfig_overfull", "line": sv["line"],
                    "detail": f"{sv['n']} 个子图宽度之和 {sv['sum']} 行宽，"
                              f"超出/顶满版心"})
    # 19) 明显窄于版心的表格（p{2cm} 之类固定窄列）
    for nv in narrow_tables(src, text_width_mm, narrow_table_min_frac):
        out.append({"kind": "table_narrow", "line": nv["line"],
                    "detail": f"表格列宽合计 {nv['total_mm']}mm，明显窄于版心"
                              f"（{nv['spec'][:30]}）"})

    # texopt 自己注入的块（质量宏/页眉/标题着色/目录页）不算作者卫生问题
    # 注意：标记行是注释行，需用原文（未剔注释）才能识别
    injected: set = set()
    inside = False
    for i, ln in enumerate(src.split("\n"), start=1):
        if "===== texopt" in ln and "end =====" not in ln:
            inside = True
        if inside:
            injected.add(i)
        if "===== texopt end" in ln:
            inside = False
    if injected:
        out = [h for h in out if h["line"] not in injected]
    return out
