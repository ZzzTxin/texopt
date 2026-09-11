# -*- coding: utf-8 -*-
r"""执行层：白名单动作集。

铁律：
  1. 动作只能落在排版面（preamble 参数、页边距、字号、浮动体位置参数、
     图片宽度、documentclass 选项）；
  2. 正文文字 / 公式 / 引用 / 标签 / 图表内容 一律不碰（core 用 body diff
     机器校验）；
  3. 全部动作幂等、可回滚（core 在应用前备份）。

动作（参数化、双向，或一次性规范化）：
  set_margin             把等效单边页边距设为指定值（可收可放，带下限保护）
  set_fontsize           把文档字号设为指定值（10/11/12 档）
  normalize_fig_width    数值宽度超阈值的插图归一化到 \linewidth（全量）
  set_fig_width          定点设置某一张插图宽度（模型在环 Level-3 动作）
  sanitize_float_specs   不稳定的浮动体位置参数（如 [h]/[h!]）规范为要求档（全量）
  set_float_spec         定点设置某一个浮动体位置参数（模型在环 Level-3 动作）
  drop_fleqn             移除 documentclass 的 fleqn 选项（公式恢复居中）
  inject_quality_macros  注入断行/孤行寡行质量宏（幂等）

所有这些动作都只落在排版面（preamble 参数/页边距/字号/浮动体位置参数/
图片宽度/documentclass 选项），不触及正文文字/公式/引用/图表内容。
"""

from __future__ import annotations

import re

from .perceive import (parse_source as _parse_source, text_area_mm,
                       _len_to_mm, _fmt_mm, DOC_CLASS_RE, GEOMETRY_USE_RE,
                       READING_AID_RE, WARNING_RE, CALLOUT_ENVS,
                       ANY_ENV_RE, SIZE_ORDER, HEADING_SIZE_CAP, SIZE_CMD_RE,
                       LIST_ENV_RE, LIST_SPACING_KEYS, _len_to_pt,
                       _env_ranges, tex_braced_arg, _LONG_URL_RE)

# ---------------------------------------------------------------- 质量宏注入

QUALITY_MACROS = r"""
% ===== texopt: 排版质量宏（自动注入，仅影响断行质量，不改内容） =====
\emergencystretch=1.5em
\clubpenalty=10000
\widowpenalty=10000
\displaywidowpenalty=10000
\doublehyphendemerits=5000
\finalhyphendemerits=5000
% ===== texopt end =====
"""


def inject_quality_macros(src: str) -> tuple[str | None, bool, str]:
    if "texopt: 排版质量宏" in src:
        return src, False, "质量宏已注入，跳过"
    m = re.search(r"\\begin\{document\}", src)
    if not m:
        return None, False, "找不到 \\begin{document}，无法注入"
    new = src[: m.start()] + QUALITY_MACROS + "\n" + src[m.start():]
    return new, True, "注入断行质量宏（禁孤行寡行/连字符堆叠/紧急伸缩）"


# ---------------------------------------------------------------- 页边距

def _split_geometry_options(opt_str: str) -> tuple[list, list]:
    """把 geometry 选项拆成 (非边距项, 边距项)。"""
    plain, sides = [], []
    for o in [x.strip() for x in opt_str.split(",") if x.strip()]:
        k, _, v = o.partition("=")
        if k.strip() in ("margin", "top", "bottom", "left", "right"):
            sides.append(o)
        else:
            plain.append(o)
    return plain, sides


def _scaled_sides(sides: list[str], factor: float) -> str:
    """把 top/bottom/left/right 各项按 factor 缩放，保持原有版面比例。"""
    out = []
    for o in sides:
        k, _, v = o.partition("=")
        mm = _len_to_mm(v)
        if mm is None:
            out.append(o)
            continue
        nv = max(mm * factor, 8.0)  # 任何单边不低于 8mm（绝对底线）
        out.append(f"{k.strip()}={_fmt_mm(nv)}")
    return ",".join(out)


def set_margin(src: str, to_mm: float, min_mm: float = 18.0,
               cur_mm: float | None = None) -> tuple[str | None, bool, str, float]:
    """把页边距设为 to_mm（夹在 [min_mm, ∞)）。返回 (新src, applied, note, 实际新值)。"""
    target = max(float(to_mm), min_mm)
    if cur_mm is not None and abs(target - cur_mm) < 0.01:
        return src, False, f"页边距已是 {target:g}mm，无需改动", cur_mm
    factor = target / cur_mm if cur_mm else 1.0

    m = GEOMETRY_USE_RE.search(src)
    if not m:
        dc = DOC_CLASS_RE.search(src)
        if not dc:
            return None, False, "找不到 \\documentclass", cur_mm or target
        insert_at = dc.end()
        new = (src[:insert_at] + "\n"
               + f"\\usepackage[margin={_fmt_mm(target)}]{{geometry}}"
               + src[insert_at:])
        return new, True, f"无 geometry 包，插入 margin={_fmt_mm(target)}", target

    opt_str = m.group(1) if m.group(1) is not None else m.group(2)
    plain, sides = _split_geometry_options(opt_str or "")
    margin_item = next((s for s in sides if s.startswith("margin")), None)
    if margin_item is not None:
        new_sides = [s if not s.startswith("margin")
                     else f"margin={_fmt_mm(target)}" for s in sides]
    elif sides:
        new_sides = [_scaled_sides(sides, factor)]
    else:
        new_sides = [f"margin={_fmt_mm(target)}"]

    new_opts = ",".join([o for o in plain] + new_sides)
    full = m.group(0)
    if m.group(1) is not None:
        replacement = f"\\usepackage[{new_opts}]{{geometry}}"
    else:
        replacement = f"\\RequirePackage[{new_opts}]{{geometry}}"
    note = (f"页边距 {cur_mm:g}mm -> {target:g}mm（等效单边）" if cur_mm
            else f"页边距设为 {target:g}mm（等效单边）")
    return src.replace(full, replacement, 1), True, note, target


# ---------------------------------------------------------------- 字号

FONT_STEPS = (10, 11, 12)  # 标准 LaTeX 字号档


def _current_font_pt(src: str) -> tuple[int | None, str | None]:
    dc = DOC_CLASS_RE.search(src)
    if not dc:
        return None, None
    for o in [x.strip() for x in (dc.group(1) or "").split(",") if x.strip()]:
        m = re.fullmatch(r"(\d+)pt", o)
        if m:
            return int(m.group(1)), dc.group(0)
    return 10, dc.group(0)  # 标准类缺省 10pt


def set_fontsize(src: str, to_pt: int) -> tuple[str | None, bool, str, int | None]:
    cur, dc_full = _current_font_pt(src)
    if cur is None:
        return None, False, "找不到 \\documentclass", None
    if to_pt not in FONT_STEPS:
        return src, False, f"字号 {to_pt}pt 不在标准档位 {FONT_STEPS} 中", cur
    if to_pt == cur:
        return src, False, f"字号已是 {cur}pt", cur
    if cur not in FONT_STEPS:
        return src, False, f"当前字号 {cur}pt 非标准档，不做自动调整", cur

    dc = DOC_CLASS_RE.search(src)
    opts = (dc.group(1) or "")
    items = [o.strip() for o in opts.split(",") if o.strip()]
    new_items = []
    replaced = False
    for o in items:
        m = re.fullmatch(r"(\d+)pt", o)
        if m:
            new_items.append(f"{to_pt}pt")
            replaced = True
        else:
            new_items.append(o)
    if not items:
        new_items = [f"{to_pt}pt"]
        replaced = True
    new_dc = (dc.group(0).replace(f"[{opts}]", f"[{','.join(new_items)}]", 1)
              if opts else
              dc.group(0).replace("\\documentclass",
                                  f"\\documentclass[{to_pt}pt]", 1))
    return src.replace(dc.group(0), new_dc, 1), True, \
        f"文档字号 {cur}pt -> {to_pt}pt", to_pt


# ---------------------------------------------------------------- 图片宽度归一

_INC_RE = re.compile(r"(\\includegraphics)(?:\[([^\]]*)\])?(\{)")


def normalize_fig_width(src: str, threshold_mm: float = 150.0
                        ) -> tuple[str | None, bool, str]:
    r"""宽度超阈值的插图归一化到 \\linewidth。

    两类超宽写法都覆盖（修复 2026-09-11：旧版只认数值宽度，导致
    `width=1.18\linewidth` 这类相对超宽永远修不了）：
      * 数值宽度 `width=170mm` -> 超过 threshold_mm 即归一；
      * 相对宽度 `width=1.18\linewidth` / `1.2\textwidth` -> 系数 > 1 即归一。
    对 0.92\\textwidth 这类合理尺寸不改（只有确实超出版心的才动）。

    覆盖 [width=170mm] 与 [trim=...,width=170mm] 两类写法：解析 options 内
    width 键，只替换其值，其余选项与内容不动。"""
    hits = []

    def _sub(m):
        head, opt, brace = m.group(1), m.group(2) or "", m.group(3)
        wm = re.search(r"(width\s*=\s*)([^,\]]+)", opt)
        if not wm:
            return m.group(0)
        expr = wm.group(2).strip()
        mm = _len_to_mm(expr)
        if mm is not None:
            over = mm > threshold_mm
        else:
            rm = re.fullmatch(
                r"([0-9]*\.?[0-9]+)\s*\\(?:linewidth|textwidth|"
                r"columnwidth|hsize)", expr)
            over = bool(rm and float(rm.group(1)) > 1.0)
        if not over:
            return m.group(0)
        hits.append(m.group(0)[:70])
        new_opt = opt[:wm.start(2)] + r"\linewidth" + opt[wm.end(2):]
        return f"{head}[{new_opt}]{brace}"

    new = _sub_code(src, _INC_RE, _sub)
    if hits:
        return new, True, \
            f"归一 {len(hits)} 处超宽图片到 \\linewidth（{hits[0]}…）"
    return src, False, "无超宽图片（宽度表达式类型或阈值内），跳过"


# ---------------------------------------------------------------- 浮动体位置参数

FLOAT_BEGIN_RE = re.compile(
    r"(\\begin\{(figure|table)(\*?)\})(?:\[([^\]]*)\])?")


def _unstable_spec(spec: str | None) -> bool:
    """spec 是否不稳定：无参数(默认 tbp)稳定；[H]（float 宏包强排）保留；
    其余仅靠 h 系（无 t/b/p 兜底）的写法 TeX 会自行改写，视为不稳定。"""
    if not spec:
        return False
    s = spec.strip()
    letters = set(re.findall(r"[htbp!H]", s))
    if letters == {"H"}:
        return False                       # \usepackage{float} 的强排，尊重作者
    return not ({"t", "b", "p"} & letters)


def sanitize_float_specs(src: str, req_spec: str = "tbp",
                         include_H: bool = False
                         ) -> tuple[str | None, bool, str]:
    """把不稳定的浮动体位置参数（[h]/[h!] 等）规范为 req_spec（默认 tbp）。

    原理：\begin{figure}[h] 在 LaTeX 里几乎总被改成 'ht'，作者意图落空且
    浮动体可能乱序（“位置被 TeX 强改”也是日志 float 警告的来源之一）。
    规范为含 t/b/p 的稳定档后由 LaTeX 全局最优放置。只改参数，不动内容。

    include_H=True 时连 [H]（float 宏包的“强制就位”）也一并规范为
    [tbp]——它会把图/表钉死在本行，是页面失衡与大块留白的常见来源；
    是否保留由 core 的全局评分仲裁（变差即回滚）。默认 False（尊重作者）。
    """
    hits = []

    def _sub(m):
        head, kind, starred, spec = m.group(1), m.group(2), m.group(3), m.group(4)
        s = (spec or "").strip()
        bad = _unstable_spec(spec)
        if include_H and s == "H":
            bad = True
        if bad:
            hits.append(f"{kind}{'*' if starred else ''}[{s}]")
            return f"{head}[{req_spec}]"
        return m.group(0)

    new = _sub_code(src, FLOAT_BEGIN_RE, _sub)
    if hits:
        return new, True, \
            f"{len(hits)} 处浮动体位置参数不稳定（{', '.join(hits)}）规范为 [{req_spec}]"
    return src, False, "浮动体位置参数均已稳定（含 t/b/p 或 [H] 强排），跳过"


# ---------------------------------------------------------------- 定点浮动体 / 图宽
# 说明：sanitize_float_specs / normalize_fig_width 是「全量」动作；
# 下面两个是「定点」动作——按 1-based 序号只改某一个浮动体/插图，
# 供模型在环（LLM proposal）做 Level-3 「这一张图让它浮到页顶/缩到
# 0.8 行宽」之类的局部判断。两者都只动排版参数，内容零改动。

_FLOAT_SPEC_SAFE_RE = re.compile(r"^[htbp!H]{1,5}$")


def _safe_float_spec(spec: str) -> str | None:
    s = (spec or "").strip()
    return s if _FLOAT_SPEC_SAFE_RE.fullmatch(s) else None


def list_float_targets(src: str) -> list[dict]:
    """列出正文里可被定点修改的浮动体：[{index, kind, spec, line}]。"""
    mask = _code_mask(src)
    out = []
    for i, m in enumerate(FLOAT_BEGIN_RE.finditer(mask), start=1):
        out.append({"index": i, "kind": m.group(2),
                    "spec": (m.group(4) or "").strip() or None,
                    "line": src.count("\n", 0, m.start()) + 1})
    return out


def _sub_code_indexed(src: str, regex, make) -> str:
    """与 _sub_code 同源，但给 make(match, index) 传 1-based 正序序号。

    _sub_code 自后向前替换（索引不漂移），无法直接用于「第 N 个」语义；
    本函数先按正序编号（与 list_*_targets 一致），再自后向前落地。
    """
    mask = _code_mask(src)
    matches = list(regex.finditer(mask))
    out = src
    for i in range(len(matches) - 1, -1, -1):
        m = matches[i]
        out = out[:m.start()] + make(m, i + 1) + out[m.end():]
    return out


def set_float_spec(src: str, spec: str = "tbp",
                   target: str | int | None = None
                   ) -> tuple[str | None, bool, str, int]:
    """定点设置浮动体位置参数。

    target: None 或 'all' = 所有浮动体；数字/'#N'/'figure#N' = 第 N 个。
    只改 \begin{figure}[...] 的位置参数，不动环境内容。返回 (src, ok, note, n)。
    """
    s = _safe_float_spec(spec)
    if s is None:
        return None, False, f"非法浮动体参数 '{spec}'（仅允许 h/t/b/p/!/H 组合）", 0
    idx = _parse_target_index(target)
    hits = []

    def _make(m, i):
        if idx is not None and i != idx:
            return m.group(0)
        head, kind, starred, cur = m.group(1), m.group(2), m.group(3), m.group(4)
        if (cur or "").strip() == s:
            return m.group(0)
        hits.append(f"{kind}{'*' if starred else ''}#{i}[{cur or '-'}]")
        return f"{head}[{s}]"

    new = _sub_code_indexed(src, FLOAT_BEGIN_RE, _make)
    if not hits:
        return src, False, "目标浮动体位置参数已是目标值，跳过", 0
    return new, True, f"定点浮动体参数 -> [{s}]（{', '.join(hits)}）", len(hits)


_FIG_WIDTH_SAFE_RE = re.compile(
    r"^(?:[0-9]*\.?[0-9]+\s*)?"
    r"(?:\\(?:linewidth|textwidth|columnwidth|hsize)|[0-9.]+\s*(?:mm|cm|pt|in|em|ex|\\textwidth))"
    r"$")


def _safe_width(expr: str) -> str | None:
    e = (expr or "").strip()
    # 统一把 \textwidth 尾缀换成允许形式；禁止任何花括号/控制序列注入
    if "{" in e or "}" in e or e.count("\\") > 1:
        return None
    return e if _FIG_WIDTH_SAFE_RE.fullmatch(e) else None


def list_fig_targets(src: str) -> list[dict]:
    """列出插图及其宽度表达式：[{index, width, line}]。"""
    mask = _code_mask(src)
    out = []
    for i, m in enumerate(_INC_RE.finditer(mask), start=1):
        opt = m.group(2) or ""
        wm = re.search(r"width\s*=\s*([^,\]]+)", opt)
        out.append({"index": i, "width": wm.group(1).strip() if wm else None,
                    "line": src.count("\n", 0, m.start()) + 1})
    return out


def set_fig_width(src: str, width: str = r"\linewidth",
                  target: str | int | None = None
                  ) -> tuple[str | None, bool, str, int]:
    """定点设置插图宽度（只改 width= 值，不动图片文件/内容）。

    target: None 或 'all' = 所有插图；数字/'#N'/'fig#N' = 第 N 个 inclusive
    graphics。width 仅允许安全长度表达式（如 \\linewidth / 0.8\\linewidth /
    120mm），以防注入任意 LaTeX。
    """
    w = _safe_width(width)
    if w is None:
        return None, False, \
            f"非法宽度表达式 '{width}'（仅允许 \\linewidth、0.8\\linewidth、120mm 等）", 0
    idx = _parse_target_index(target)
    hits = []

    def _make(m, i):
        if idx is not None and i != idx:
            return m.group(0)
        head, opt, brace = m.group(1), m.group(2) or "", m.group(3)
        wm = re.search(r"(width\s*=\s*)([^,\]]+)", opt)
        if not wm:
            return m.group(0)
        if wm.group(2).strip() == w:
            return m.group(0)
        hits.append(f"#{i}:{wm.group(2).strip()}->{w}")
        new_opt = opt[:wm.start(2)] + w + opt[wm.end(2):]
        return f"{head}[{new_opt}]{brace}"

    new = _sub_code_indexed(src, _INC_RE, _make)
    if not hits:
        return src, False, "目标插图宽度已是目标值，跳过", 0
    return new, True, f"定点插图宽度（{', '.join(hits)}）", len(hits)


def _parse_target_index(target) -> int | None:
    """'all'/None -> None；2 / '#2' / 'figure#2' / 'fig2' -> 2（1-based）。"""
    if target is None or (isinstance(target, str)
                          and target.strip().lower() in ("", "all", "*")):
        return None
    if isinstance(target, int):
        return target if target > 0 else None
    m = re.search(r"(\d+)", str(target))
    return int(m.group(1)) if m else None


# ---------------------------------------------------------------- 公式居中（fleqn）


def drop_fleqn(src: str) -> tuple[str | None, bool, str]:
    """移除 documentclass 选项中的 fleqn（公式从左侧对齐恢复为居中）。

    期刊/会议默认要求公式居中（Basic 模块），fleqn 属于作者误留或
    双栏草稿习惯，移除只改 documentclass 选项，不碰任何公式内容。
    """
    dc = DOC_CLASS_RE.search(src)
    if not dc:
        return None, False, "找不到 \\documentclass"
    opts = dc.group(1)
    if not opts or "fleqn" not in opts:
        return src, False, "文档类无 fleqn 选项，公式本就居中，跳过"
    items = [o.strip() for o in opts.split(",")
             if o.strip() and o.strip() != "fleqn"]
    new_opts = ",".join(items)
    new_dc = (dc.group(0).replace(f"[{opts}]", f"[{new_opts}]", 1)
              if opts else dc.group(0))
    return src.replace(dc.group(0), new_dc, 1), True, \
        "移除 documentclass 的 fleqn 选项（公式恢复居中）"


# ---------------------------------------------------------------- 裸数学归一

def _code_mask(src: str) -> str:
    r"""把注释部分抹成等长空白（保留索引），% 前带反斜杠（\%）的不算注释。"""
    out = []
    for ln in src.split("\n"):
        m = re.search(r"(?<!\\)%", ln)
        if m:
            ln = ln[:m.start()] + " " * (len(ln) - m.start())
        out.append(ln)
    return "\n".join(out)




def _sub_code(src: str, regex, make) -> str:
    r"""只在非注释代码区执行替换：在注释掩码上匹配，对原文同步替换。

    注释里的代码示例（如 % \begin{figure}[h]）属于作者说明文字，
    不是排版面，任何动作都不得改写 —— 这是“内容零改动”的注释级保证。
    """
    mask = _code_mask(src)
    out = src
    for m in reversed(list(regex.finditer(mask))):
        out = out[:m.start()] + make(m) + out[m.end():]
    return out

def normalize_dollar_math(src: str) -> tuple[str | None, bool, str]:
    r"""把 TeX 原语裸数学 $$..$$ 归一为 LaTeX \[..\]（排版等价）。

    $$ 是 TeX 原语（间距/断行行为与 \[..\] 有细微差异，且不支持
    \qedhere 等），规范要求一律用 \[..\] 或 equation 环境。
    只在注释掩码后成对出现时执行（注释里的 $$ 文本不受影响）。
    """
    mask = _code_mask(src)
    pairs = list(re.finditer(r"\$\$(.+?)\$\$", mask, re.S))
    if not pairs:
        return src, False, "无 $$..$$ 裸数学，跳过"
    new = src
    for m in reversed(pairs):          # 从后往前替换，索引不漂移
        new = (new[:m.start()] + "\\[" + new[m.start() + 2:m.end() - 2]
               + "\\]" + new[m.end():])
    return new, True, \
        f"{len(pairs)} 处裸 $$..$$ 改为 \\[..\\]（排版等价，规范写法）"


# =====================================================================
# 确定性排版修复动作（2026-09-11 新增）
#
# 背景（根因修复）：感知层早就检测出「手动分页/过大的手动垂直间距/行内
# 字号乱标/超长不可断词/列表间距过大/标题字号过大」等问题（见
# perceive.scan_hygiene），但没有任何动作能修它们 —— 检测结果进不了 Act，
# 闭环于是无事可做，A 分永远停在原地。下面这组动作把「检测 -> 修改」
# 这条链路补齐；每个动作只落在排版面，不碰正文文字/公式/引用/图表内容，
# 幂等且可回滚，最终一律由 core 整篇重编译后全局评分验收。
# =====================================================================

_BODY_BEGIN_RE = re.compile(r"\\begin\{document\}")
_SUBFIG_W_ARG_RE = re.compile(
    r"\\begin\{(?:subfigure|subfloat|minipage)\}\s*\{([0-9]*\.?[0-9]+)\s*\\"
    r"(?:textwidth|linewidth|columnwidth)")


def _source_of(src: str) -> dict:
    """当前源码的解析快照（供需要版心尺寸的动作复用）。"""
    return _parse_source(src)
_BODY_END_RE = re.compile(r"\\end\{document\}")

# verbatim / 数学 / 表格环境内部：这些区域的排版命令不自动改写（保护内容）
_PROTECTED_ENVS = {
    "verbatim", "verbatim*", "lstlisting", "minted", "comment",
    "tabular", "tabular*", "tabularx", "longtable", "array",
    "align", "align*", "alignat", "alignat*", "flalign", "flalign*",
    "gather", "gather*", "multline", "multline*", "eqnarray", "eqnarray*",
    "aligned", "alignedat", "gathered", "split", "cases", "matrix",
    "pmatrix", "bmatrix", "Bmatrix", "vmatrix", "Vmatrix", "smallmatrix",
}


def _body_span(src: str) -> tuple[int, int]:
    """正文（document 环境内部）的字符区间；找不到 document 返回 (-1,-1)。"""
    mb = _BODY_BEGIN_RE.search(src)
    if not mb:
        return -1, -1
    me = _BODY_END_RE.search(src, mb.end())
    return mb.end(), (me.start() if me else len(src))


def _protected_ranges(src: str) -> list:
    """verbatim/数学/表格环境的字符区间（这些位置不自动改）。"""
    ranges = _env_ranges(src, _PROTECTED_ENVS)
    for m in re.finditer(r"\\\[.*?\\\]|\\\(.*?\\\)", src, re.S):
        ranges.append((m.start(), m.end()))
    return ranges


def _sub_body(src: str, regex, extra_skip=None):
    """只在正文区（document 内、非 verbatim/数学/表格）定位匹配。

    返回 (匹配列表, 掩码)。匹配位置与 src 一致（掩码等长），调用方
    自行重建字符串（从后往前替换，索引不漂移）。
    """
    mask = _code_mask(src)
    b0, b1 = _body_span(src)
    if b0 < 0:
        return [], mask
    protected = _protected_ranges(mask)
    hits = []
    for m in regex.finditer(mask):
        if not (b0 <= m.start() < b1):
            continue
        if any(a <= m.start() < b for a, b in protected):
            continue
        if extra_skip is not None and extra_skip(m, mask):
            continue
        hits.append(m)
    return hits, mask


def _apply(src: str, edits: list) -> str:
    """按 (start, end, text) 列表重建字符串（从后往前，索引不漂移）。"""
    out = src
    for s, e, txt in sorted(edits, key=lambda t: t[0], reverse=True):
        out = out[:s] + txt + out[e:]
    return out


# ---------------------------------------------------------------- 1) 手动分页

_PAGEBREAK_RE = re.compile(r"\\(?:newpage|clearpage|pagebreak)\*?"
                           r"(?:\s*\[[^\]]*\])?")


def remove_manual_pagebreak(src: str) -> tuple[str | None, bool, str]:
    """删除正文里的手动分页（\\newpage/\\clearpage/\\pagebreak）。

    手动分页会把图/表与正文钉死在作者猜的位置，是页面失衡与大块留白的
    首要来源（参见 chaos 靶稿的“最后一页只剩两行”）。交给 LaTeX 全局
    最优断页；是否真的变好由整篇重编译后的全局评分决定（变差即回滚）。
    """
    hits, _mask = _sub_body(src, _PAGEBREAK_RE)
    if not hits:
        return src, False, "正文无手动分页，跳过"
    new = _apply(src, [(m.start(), m.end(), "") for m in hits])
    kinds = ", ".join(sorted({m.group(0).split("[")[0] for m in hits}))
    return new, True, \
        f"删除 {len(hits)} 处正文手动分页（{kinds}），交回 LaTeX 全局断页"


# ---------------------------------------------------------------- 2) 过大垂直间距

_VSPACE_RE = re.compile(r"\\vspace\*?\s*\{([^}]*)\}")


def remove_excessive_vspace(src: str, min_pt: float = 28.35
                            ) -> tuple[str | None, bool, str]:
    """删除正文里明显过大的 \\vspace{...}（默认 ≥ 10mm = 28.35pt）。

    只删“异常大”的显式垂直间距；正常数学/标题/浮动体间距（TeX 自动的）
    以及小数値（如 \\vspace{2pt}）不动。需要统一段距应由 preamble 的
    \\parskip 定义，而非逐处硬塞。
    """
    def _skip(m, mask):
        pt = _len_to_pt(m.group(1))
        return pt is None or pt < min_pt

    hits, _mask = _sub_body(src, _VSPACE_RE, extra_skip=_skip)
    if not hits:
        return src, False, "无异常过大的手动垂直间距，跳过"
    new = _apply(src, [(m.start(), m.end(), "") for m in hits])
    vals = ", ".join(m.group(1).strip() for m in hits[:4])
    return new, True, \
        f"删除 {len(hits)} 处过大的手动垂直间距（{vals}）"


# ---------------------------------------------------------------- 3) 行内字号乱标


def normalize_local_font_size(src: str) -> tuple[str | None, bool, str]:
    """删除正文里孤立的行内字号切换（如 {\\Large ...} / {\\tiny ...}）。

    字号应交给全局样式/宏（section/subsection 的层级由文档类或 titlesec
    定义），行内手改字号会打乱整个页面的密度节奏。删除字号命令后，花括号
    分组保留（分组本身无影响），不涉及任何文字。

    保护：数学/表格/verbatim 区域内的字号命令不处理（如矩阵里的 \\small），
    避免误伤合法特殊内容。
    """
    hits, _mask = _sub_body(src, SIZE_CMD_RE)
    if not hits:
        return src, False, "正文无行内字号乱标，跳过"
    new = _apply(src, [(m.start(), m.end(), "") for m in hits])
    kinds = ", ".join(sorted({m.group(0) for m in hits}))
    return new, True, f"删除正文 {len(hits)} 处行内字号切换（{kinds}）"


# ---------------------------------------------------------------- 4) 标题字号


def _heading_arg_spans(mask: str) -> list:
    """(level, (arg_start, arg_end))：\\titleformat / \\xxxfont 的样式参数。"""
    from .perceive import _HEADING_FORMAT_RE, _SECTIONFONT_RE
    spans = []
    for m in _HEADING_FORMAT_RE.finditer(mask):
        got = tex_braced_arg(mask, m.end())
        if got:
            spans.append((m.group(1), (got[1], got[2])))
    for m in _SECTIONFONT_RE.finditer(mask):
        got = tex_braced_arg(mask, m.end())
        if got:
            spans.append((m.group(1), (got[1], got[2])))
    return spans


def normalize_heading_size(src: str) -> tuple[str | None, bool, str]:
    """把超出层级上限的标题字号压回上限（\\Huge section -> \\Large）。

    规则（与 perceive.heading_size_violations 同源）：section/chapter 不超
    \\Large，subsection 不超 \\large，subsubsection 不超 \\normalsize。
    只改 \\titleformat/\\sectionfont 这类标题样式声明里的字号命令，不碰
    标题文字（标题文字仍在参数里原样保留）。
    """
    mask = _code_mask(src)
    edits, notes = [], []
    for level, (a0, a1) in _heading_arg_spans(mask):
        cap = HEADING_SIZE_CAP.get(level)
        if not cap:
            continue
        for sm in SIZE_CMD_RE.finditer(mask, a0, a1):
            cmd = sm.group(1)
            if SIZE_ORDER.index(cmd) > SIZE_ORDER.index(cap):
                edits.append((sm.start(), sm.end(), "\\" + cap))
                notes.append(f"{level}:{cmd}->{cap}")
    if not edits:
        return src, False, "标题字号未见异常（均 ≤ 层级上限），跳过"
    return _apply(src, edits), True, \
        f"规范化 {len(edits)} 处标题字号（{', '.join(notes[:4])}）"


# ---------------------------------------------------------------- 5) 列表间距


def reduce_list_spacing(src: str, max_pt: float = 8.0
                        ) -> tuple[str | None, bool, str]:
    """删除列表环境里明显过大的垂直间距选项（itemsep/topsep/parsep/partopsep）。

    只删「大于 max_pt 的间距键」，回到文档类默认的列表间距；列表结构、
    条目内容、label 等一律不动（左侧缩进等其它选项也保留）。
    """
    mask = _code_mask(src)
    b0, b1 = _body_span(src)
    edits, notes = [], []
    for m in LIST_ENV_RE.finditer(mask):
        if not (b0 <= m.start() < b1):
            continue
        keep, dropped = [], []
        for opt in m.group(2).split(","):
            k, _, v = opt.partition("=")
            if k.strip() in LIST_SPACING_KEYS:
                pt = _len_to_pt(v)
                if pt is not None and pt > max_pt:
                    dropped.append(f"{k.strip()}={v.strip()}")
                    continue
            keep.append(opt)
        if not dropped:
            continue
        notes += dropped
        if [x for x in keep if x.strip()]:
            edits.append((m.start(2), m.end(2),
                          ",".join(x for x in keep if x.strip())))
        else:                                     # 选项全删 -> 去掉空的 []
            edits.append((m.start(), m.end(),
                          "\\begin{" + m.group(1) + "}"))
    if not edits:
        return src, False, "列表间距正常，跳过"
    return _apply(src, edits), True, \
        f"收紧列表间距 {len(notes)} 处（{', '.join(notes[:4])}）"


# ---------------------------------------------------------------- 6) 超长不可断词

_LONG_WORD_RE = re.compile(r"[A-Za-z]{%d,}" % 40)


def add_hyphenation_points(src: str, min_chars: int = 80, step: int = 12
                           ) -> tuple[str | None, bool, str]:
    """给正文里超长不可断词插入 \\- 断词点（TeX 合法断行机制）。

    超长单词（默认 ≥ 80 字符）无法断行，是 Overfull \\hbox 的典型来源。
    \\- 是“可选断点”（discretionary hyphen）：只在需要时才以连字符断开，
    不改变任何字符/语义，也不改变未断行时的外观。
    """
    def _skip(m, mask):
        w = m.group(0)
        if len(w) < min_chars:
            return True
        if m.start() > 0 and mask[m.start() - 1] == "\\":
            return True                     # 宏名的一部分，不动
        if "\\" in w:
            return True
        return False

    hits, _mask = _sub_body(src, _LONG_WORD_RE, extra_skip=_skip)
    if not hits:
        return src, False, "无超长不可断词，跳过"
    edits = []
    for m in hits:
        w = m.group(0)
        pieces = []
        for i, ch in enumerate(w):
            pieces.append(ch)
            if (i + 1) % step == 0 and i != len(w) - 1:
                pieces.append("\\-")
        edits.append((m.start(), m.end(), "".join(pieces)))
    return _apply(src, edits), True, \
        f"为 {len(hits)} 个超长词插入 \\- 断词点（最长 {max(len(m.group(0)) for m in hits)} 字符）"


# ---------------------------------------------------------------- 6b) 超长 URL

def break_long_urls(src: str) -> tuple[str | None, bool, str]:
    r"""给超长 URL 注入 \usepackage{xurl}（允许 URL 在任意位置断行）。

    放在 preamble 末尾（\begin{document} 之前），因此在 hyperref 之后加载，
    不影响正文文字本身；xurl 是 URL 断行的标准合法机制（比手工插入
    断词点更安全，不会把 \url{} 的参数改坏）。仅当正文里存在
    \url{}/\href{}/\path{} 形式的长 URL 时启用。
    """
    mask = _code_mask(src)
    b0, b1 = _body_span(src)
    hits = [m for m in _LONG_URL_RE.finditer(mask) if b0 <= m.start() < b1]
    if not hits:
        return src, False, "正文无超长 URL（\\url/\\href/\\path 形式），跳过"
    if "\\usepackage{xurl}" in src or "\\usepackage{url}" in src:
        return src, False, "已加载 xurl/url，跳过"
    new = _preamble_insert(src, "\\usepackage{xurl}  % texopt: 允许超长 URL 断行")
    return new, True, \
        f"注入 \\usepackage{{xurl}}（{len(hits)} 个超长 URL 可在任意位置断行）"


# ---------------------------------------------------------------- 7) 超宽表格

# 只匹配环境名；列格式用 tex_braced_arg 取（可能含 p{2cm} 这类嵌套花括号）
_TAB_BEGIN_RE = re.compile(r"\\begin\{(tabular)\}\s*(?=\{)")
_PWIDTH_COL_RE = re.compile(r"[pmb]\s*\{[^{}]*\}")
_SIMPLE_COLS_RE = re.compile(r"^[\s|lcr]*$")


def _xify_cols(spec: str) -> str | None:
    r"""把列格式改成含 X 列（tabularx 自适应列）；无法安全转换时 None。

    两类输入：
      * 纯 l/c/r 组合（如 {lrrrr}）-> 首列（或末列）换 X；
      * p{2cm}/m{...}/b{...} 固定窄列（如 {p{2cm}p{2cm}}）-> 全部换 X，
        配合 tabularx{\linewidth} 让窄表撑满版心（Phase 2）。
    """
    inner = spec.strip()
    if inner.startswith("{") and inner.endswith("}"):   # 去掉最外层花括号
        inner = inner[1:-1].strip()
    if _SIMPLE_COLS_RE.fullmatch(inner) and re.search(r"[lcr]", inner):
        if "l" in inner:                   # 首列常为文字列 -> 换成自适应 X
            return inner.replace("l", "X", 1)
        return inner[:-1] + "X"            # 否则末列换 X
    if _PWIDTH_COL_RE.search(inner):       # p/m/b{...} 固定窄列
        new = _PWIDTH_COL_RE.sub("X", inner)
        return new if re.fullmatch(r"[X\s|]*", new) else None
    return None


def fix_table_width(src: str, lines: list | None = None
                    ) -> tuple[str | None, bool, str]:
    """超宽表格改用 tabularx（\\linewidth 自适应列宽）。

    优先靠列宽自适应（tabularx 的 X 列）而不是 \\resizebox 这类“压缩式
    伪修复”：表格数据/顺序/内容一律不动，只改环境名与列格式（属排版面）。

    仅处理列格式简单的（l/c/r 组合）tabular；p{...}/已 tabularx/longtable
    等复杂情形不自动改（列宽策略需作者决定）。
    lines 给出具体行号（编译报出的超宽行，或源码层判定的窄表行）时只改
    覆盖这些行的表格；缺省则处理所有列格式简单的 tabular。
    Phase 2：同时覆盖 p{2cm} 这类**明显窄于版心**的固定列宽表格。
    """
    mask = _code_mask(src)
    edits, n, notes = [], 0, []
    for a, b in _env_ranges(mask, {"tabular"}):
        bm = _TAB_BEGIN_RE.match(mask, a)
        if not bm:
            continue
        # 列格式可能含嵌套花括号（p{2cm}），用括号感知取参
        got = tex_braced_arg(mask, bm.end())
        if not got:
            continue
        spec, _s0, _s1 = got
        if lines:
            l0 = mask.count("\n", 0, a) + 1
            l1 = mask.count("\n", 0, b) + 2      # b 为 \end{tabular} 起始
            if not any(l0 <= ln <= l1 for ln in lines):
                continue
        cols = _xify_cols(spec)
        if cols is None:
            continue
        # 注意：perceive._env_ranges 返回的 b 是 \end{tabular} 的“起始”位置
        e = mask.find("\\end{tabular}", a, b + 20)
        if e < 0:
            continue
        # 只替换环境名与列格式：\begin{tabular}{spec} -> \begin{tabularx}{\linewidth}{cols}
        edits.append((bm.start(), got[2] + 1,
                      "\\begin{tabularx}{\\linewidth}{" + cols + "}"))
        edits.append((e, e + len("\\end{tabular}"), "\\end{tabularx}"))
        notes.append(spec.strip()[:24] + " -> " + cols[:24])
        n += 1
    if not n:
        return src, False, "无超宽/窄表可换算的 tabular，跳过"
    new = _apply(src, edits)
    if "\\usepackage{tabularx}" not in new \
            and not re.search(r"\{tabularx\}", new.split("\\begin{document}")[0]):
        new = _preamble_insert(new, "\\usepackage{tabularx}")
    return new, True, \
        f"{n} 个表格改用 tabularx（\\linewidth 自适应列宽）：{'; '.join(notes[:3])}"


# ---------------------------------------------------------------- 8) 页面平衡

RAGGED_BOTTOM_BLOCK = (r"""% ===== texopt: 页面平衡 ====
% 浮动体放置与页面平衡调优（只影响浮动体分配/底部对齐，不改内容）
\raggedbottom
\setcounter{topnumber}{3}
\setcounter{bottomnumber}{2}
\setcounter{totalnumber}{4}
\renewcommand{\topfraction}{0.8}
\renewcommand{\bottomfraction}{0.7}
\renewcommand{\textfraction}{0.08}
\renewcommand{\floatpagefraction}{0.7}
% ===== texopt end ====
""")


def balance_pages(src: str) -> tuple[str | None, bool, str]:
    r"""注入页面平衡块：\raggedbottom + 浮动体放置比例调优。

    解决两类**页面级**视觉缺陷（量自 PDF）：
      * 页面底部大面积空白 / 内容孤零零（浮动体被挤成半空浮动页）；
      * 页面为凑满而垂直拉伸（Underfull \vbox）。
    手段：\raggedbottom（短页自然收底）+ \floatpagefraction/\topfraction/
    \textfraction（不给“半空的浮动页”留机会）。不删内容、不手动分页凑页；
    是否真的改善由整篇重编译后的视觉/全局评分仲裁（变差即回滚）。
    """
    if "texopt: 页面平衡" in src or "\\raggedbottom" in src:
        return src, False, "已是 raggedbottom 或已注入，跳过"
    body = _BODY_BEGIN_RE.search(src)
    if not body:
        return None, False, "找不到 \\begin{document}"
    new = src[:body.start()] + RAGGED_BOTTOM_BLOCK + "\n" + src[body.start():]
    return new, True, "注入 \\raggedbottom（页面底部自然收底，减少留白/拉伸）"


# =====================================================================
# Phase 2（2026-09-11）动作：把「页面级视觉缺陷 / 版面级问题」落到源码
#   normalize_title          \\title{\\Huge ...} 压回层级上限
#   normalize_parskip        过大的 \\parskip 收敛
#   normalize_header         过长/无意义页眉内容清空
#   remove_mid_multicols     正文中途的局部双栏（保留内容，只去环境）
#   reduce_oversized_figures 过大图片高度 / 子图并排超版心
#   fix_table_width 扩展      p{2cm} 窄表格 -> tabularx 自适应列宽
# 全部仍走「应用→整篇重编译→视觉/全局重评→接受或回滚」。
# =====================================================================

_TITLE_ARG_RE = re.compile(r"\\title\s*(?=\{)")
_PARSKIP_SET_RE = re.compile(r"\\setlength\s*(\{\s*\\parskip\s*\})\s*(\{([^}]*)\})")
_PARSKIP_EQ_RE = re.compile(r"(\\parskip\s*=\s*)([0-9]*\.?[0-9]+)\s*(pt|mm|cm|in)")
_HEADER_CMD_ARG_RE = re.compile(
    r"\\(?:lhead|rhead|chead|fancyhead(?:\s*\[[^\]]*\])?)\s*(?=\{)")
_MULTICOLS_END_RE = re.compile(r"\\end\{multicols\*?\}")


def normalize_title(src: str, cap: str = "LARGE") -> tuple[str | None, bool, str]:
    r"""把 \title{...} 里超限的字号压回上限（\Huge -> \LARGE）。

    标题字号应交给文档类；这里只改字号命令，标题文字一字不动。
    """
    m = _TITLE_ARG_RE.search(src)
    if not m:
        return src, False, "无 \\title，跳过"
    got = tex_braced_arg(src, m.end())
    if not got:
        return src, False, "\\title 参数解析失败，跳过"
    body, a0, _a1 = got
    edits = []
    for sm in SIZE_CMD_RE.finditer(body):
        cmd = sm.group(1)
        if SIZE_ORDER.index(cmd) > SIZE_ORDER.index(cap):
            edits.append((a0 + sm.start(), a0 + sm.end(), "\\" + cap))
    if not edits:
        return src, False, f"标题字号未见异常（≤ {cap}），跳过"
    return _apply(src, edits), True, \
        f"标题字号规范化 {len(edits)} 处（-> \\{cap}）"


def normalize_parskip(src: str, max_pt: float = 8.0
                      ) -> tuple[str | None, bool, str]:
    r"""把过大的 \parskip 收敛到合理值（默认上限 8pt）。

    \parskip 是**整篇**段落间距，过大时每一页都会显得松散、留白过多；
    正文里没有额外段距需求时应收回到接近默认。只改长度值，不动任何文字。
    """
    for m in _PARSKIP_SET_RE.finditer(src):
        val = m.group(3)
        pt = _len_to_pt(val)
        if pt is not None and pt > max_pt:
            new = src[:m.start(2)] + ("{%gpt}" % max_pt) + src[m.end(2):]
            return new, True, \
                f"\\parskip {val.strip()} -> {max_pt:g}pt（整篇段距收敛）"
    for m in _PARSKIP_EQ_RE.finditer(src):
        pt = _len_to_pt(f"{m.group(2)}{m.group(3)}")
        if pt is not None and pt > max_pt:
            new = src[:m.start(2)] + f"{max_pt:g}pt" + src[m.end(3):]
            return new, True, \
                f"\\parskip {m.group(2)}{m.group(3)} -> {max_pt:g}pt"
    return src, False, "\\parskip 未设置或已在合理范围，跳过"


def normalize_header(src: str, max_chars: int = 40
                     ) -> tuple[str | None, bool, str]:
    r"""清空过长/无意义的页眉内容（保留 fancyhdr 设置本身）。

    页眉超过 max_chars 字符时既挤占版心又无信息价值（如整句说明文字）；
    这里只把该页眉的参数置空，不改文档其它任何部分。
    """
    edits, notes = [], []
    for m in _HEADER_CMD_ARG_RE.finditer(src):
        got = tex_braced_arg(src, m.end())
        if not got:
            continue
        arg, a0, a1 = got
        if len(arg.strip()) > max_chars:
            edits.append((a0, a1, ""))
            notes.append(f"{src[m.start():m.end()].strip()}({len(arg.strip())}字)")
    if not edits:
        return src, False, "页眉未见异常，跳过"
    return _apply(src, edits), True, f"清空 {len(edits)} 处过长页眉（{', '.join(notes)}）"


def remove_mid_multicols(src: str) -> tuple[str | None, bool, str]:
    r"""删除正文中途的局部双栏（multicols），内容原样保留。

    文档中途切双栏会让版面节奏断裂（栏宽骤变、断行噪声、图表错位）；
    只删 \begin{multicols}{N}/\end{multicols} 标记，中间内容不变。
    """
    from .perceive import multicols_local_spans
    spans = multicols_local_spans(src)
    if not spans:
        return src, False, "无正文中途双栏，跳过"
    mask = _code_mask(src)
    edits = []
    for a, b in _env_ranges(mask, {"multicols", "multicols*"}):
        bm = re.match(r"\\begin\{multicols\*?\}(\s*\{[^}]*\})?", mask[a:a + 60])
        if not bm:
            continue
        edits.append((a, a + bm.end(), ""))
        em = _MULTICOLS_END_RE.search(mask, max(b - 40, 0))
        if em:
            edits.append((em.start(), em.end(), ""))
    if not edits:
        return src, False, "无正文中途双栏，跳过"
    return _apply(src, edits), True, \
        f"移除 {len(spans)} 处正文中途双栏（内容保留，交回单栏版心）"


def reduce_oversized_figures(src: str, max_height_frac: float = 0.40,
                             subfig_max_sum: float = 0.95
                             ) -> tuple[str | None, bool, str]:
    r"""收敛过大的图片：高度超限 -> 压到上限；子图并排超版心 -> 等比缩小。

    只改 \includegraphics 的 height 值与 \begin{subfigure}{0.49\textwidth}
    这类相对宽度，图片文件、题注、内容一律不动。
    """
    edits, notes = [], []
    # (a) 过大的 height
    for m in _INC_RE.finditer(_code_mask(src)):
        opt = m.group(2) or ""
        hm = re.search(r"(height\s*=\s*)([^,\]]+)", opt)
        if not hm:
            continue
        expr = hm.group(2).strip()
        frac = None
        rm = re.fullmatch(r"([0-9]*\.?[0-9]+)\s*\\"
                          r"(?:textheight|paperheight|pageheight)", expr)
        if rm:
            frac = float(rm.group(1))
        else:
            mm = _len_to_mm(expr)
            if mm is not None:
                frac = mm / text_area_mm(_source_of(src))[1]
        if frac is not None and frac > max_height_frac:
            new_opt = (opt[:hm.start(2)]
                       + ("%g\\textheight" % max_height_frac) + opt[hm.end(2):])
            edits.append((m.start(2), m.end(2), new_opt))
            notes.append(f"height {expr} -> {max_height_frac:g}\\textheight")
    # (b) 子图并排宽度之和超版心 -> 等比缩小
    for a, b in _env_ranges(_code_mask(src), {"figure", "figure*"}):
        seg = src[a:b]
        ms = list(_SUBFIG_W_ARG_RE.finditer(seg))
        vals = [float(x.group(1)) for x in ms]
        if len(vals) >= 2 and sum(vals) > subfig_max_sum:
            factor = (subfig_max_sum - 0.01) / sum(vals)
            for x in ms:
                nv = float(x.group(1)) * factor
                edits.append((a + x.start(1), a + x.end(1), f"{nv:.3f}"))
            notes.append(f"{len(vals)} 子图 x{factor:.2f}")
    if not edits:
        return src, False, "无过大图片/超版心子图，跳过"
    return _apply(src, edits), True, f"收敛图片尺寸 {len(notes)} 处（{'; '.join(notes[:3])}）"


def shrink_oversized_figures(src: str, factor: float = 0.85,
                             min_frac: float = 0.5
                             ) -> tuple[str | None, bool, str]:
    r"""按视觉信号缩小「满宽级」图片（width=\linewidth / 0.9\textwidth 且无高度约束）。

    页面级视觉量发现「巨大内容块」（单块 ≥ 40% 页高）时，最有效的确定性手段
    是把该图的相对宽度降一档（等比缩小 -> 高度同步下降）。
    只改 width= 的系数；子图/小页内部的 \includegraphics 由父容器定宽，不动。
    是否真的改善由整篇重编译后的视觉/全局评分仲裁（变差即回滚）。
    """
    mask = _code_mask(src)
    protected = []
    for a, b in _env_ranges(mask, {"subfigure", "subfloat", "minipage"}):
        protected.append((a, b))
    edits, notes = [], []
    for m in _INC_RE.finditer(mask):
        if any(a <= m.start() < b for a, b in protected):
            continue
        opt = m.group(2) or ""
        if re.search(r"(?:^|,)\s*height\s*=", opt):        # 已有高度约束，跳过
            continue
        wm = re.search(r"(width\s*=\s*)([^,\]]+)", opt)
        if not wm:
            continue
        expr = wm.group(2).strip()
        rm = re.fullmatch(r"(?:([0-9]*\.?[0-9]+))?\s*\\"
                          r"(?:linewidth|textwidth|columnwidth|hsize)", expr)
        if not rm:
            continue
        f = float(rm.group(1)) if rm.group(1) else 1.0
        if f < 0.8:                                        # 本来就不大
            continue
        nf = max(f * factor, min_frac)
        if abs(nf - f) < 1e-6:
            continue
        unit = re.search(r"\\(?:linewidth|textwidth|columnwidth|hsize)",
                         expr).group(0)
        val = ("%g" % nf) + unit
        new_opt = opt[:wm.start(2)] + val + opt[wm.end(2):]
        edits.append((m.start(2), m.end(2), new_opt))
        notes.append(f"{expr} -> {val}")
    if not edits:
        return src, False, "无「满宽且无高度约束」的图片可缩，跳过"
    return _apply(src, edits), True, \
        f"缩小满宽图片 {len(edits)} 处（{'; '.join(notes[:3])}）"


# =====================================================================
# 前置结构 / 版面规范（2026-09-10 新增）
#   insert_toc           插入目录页（\tableofcontents），幂等
#   add_header           注入页眉（fancyhdr）
#   color_headings       标题着色突出（xcolor + sectsty）
#   strip_reading_aids   删除阅读辅助内容（"START READING HERE" 等）
#   remove_warning_boxes 删除 WARNING 类告示块
# 前两者落在 preamble/body 结构位；后两者属于「元信息/编辑性内容」的
# 定点删除，只匹配已知模式（绝不匹配正文句子），删除后由 score 的
# 元信息归一器豁免，保证『正文内容零改动』铁律不被破坏。
# =====================================================================

TOC_MACROS = ("% ===== texopt: 目录页（自动插入） =====\n"
              "\\tableofcontents\n\\newpage\n"
              "% ===== texopt end =====\n")

HEADER_MACROS_TMPL = r"""
% ===== texopt: 页眉（自动注入） =====
\usepackage{fancyhdr}
\makeatletter
@@CAPTURE@@
\pagestyle{fancy}
\fancyhf{}
\fancyhead[L]{\small\itshape @@LEFT@@}
\fancyhead[R]{\small @@RIGHT@@}
\renewcommand{\headrulewidth}{0.4pt}
\makeatother
% ===== texopt end =====
"""

# \maketitle 会把 \@title 清空，所以页眉里不能直接用 \@title；
# 在 \begin{document} 钩子里先存一份标题（未定义时置空）。
_TITLE_CAPTURE = (r"\AtBeginDocument{\ifdefined\@title"
                  r"\let\texopttitle\@title\else\def\texopttitle{}\fi}%")

COLOR_MACROS_TMPL = r"""
% ===== texopt: 标题着色（自动注入） =====
\usepackage{xcolor}
\usepackage{sectsty}
@@DECL@@
\sectionfont{\color{texopthead}}
\subsectionfont{\color{texopthead!85!black}}
\subsubsectionfont{\color{texopthead!85!black}\itshape}
% ===== texopt end =====
"""

_PREAMBLE_ANCHOR = re.compile(r"\\begin\{document\}")
_FIRST_SECTION = re.compile(r"\\section\*?\s*\{")


def _preamble_insert(src: str, block: str) -> str:
    """把一段宏定义插到 \\begin{document} 之前（preamble 末尾）。"""
    m = _PREAMBLE_ANCHOR.search(src)
    if not m:
        return src
    return src[:m.start()] + block.strip() + "\n\n" + src[m.start():]


def insert_toc(src: str) -> tuple[str | None, bool, str]:
    """在正文首个 \\section 前插入目录页（幂等）。"""
    if "\\tableofcontents" in src:
        return src, False, "已存在 \\tableofcontents，跳过"
    body_m = _PREAMBLE_ANCHOR.search(src)
    if not body_m:
        return None, False, "找不到 \\begin{document}"
    sec = _FIRST_SECTION.search(src, body_m.end())
    if not sec:
        return src, False, "正文内没有 \\section，无法确定目录位置"
    new = src[:sec.start()] + TOC_MACROS + src[sec.start():]
    return new, True, "插入目录页 \\tableofcontents（置于正文首节之前）"


def add_header(src: str, left: str | None = None,
               right: str | None = None) -> tuple[str | None, bool, str]:
    """注入页眉（左：简短标题；右：页码）。幂等。"""
    if "texopt: 页眉" in src:
        return src, False, "页眉已注入，跳过"
    if "\\fancyhead" in src or "\\pagestyle{fancy}" in src:
        return src, False, "源码已有 fancyhdr 页眉设置，尊重视为已满足"
    if left is None:
        left = r"\texopttitle"
        capture = _TITLE_CAPTURE
    else:
        capture = ""
    left = left.replace("%", r"\%")
    right = (right or r"\thepage").replace("%", r"\%")
    block = HEADER_MACROS_TMPL.replace("@@CAPTURE@@", capture) \
                                .replace("@@LEFT@@", left) \
                                .replace("@@RIGHT@@", right)
    body_m = _PREAMBLE_ANCHOR.search(src)
    if not body_m:
        return None, False, "找不到 \\begin{document}"
    return _preamble_insert(src, block), True, "注入页眉（fancyhdr：左标题 / 右页码）"


def color_headings(src: str, color: str = "0,62,120"
                   ) -> tuple[str | None, bool, str]:
    """标题着色（section/subsection 用同一强调色）。幂等。"""
    if "texopt: 标题着色" in src:
        return src, False, "标题着色已注入，跳过"
    if "\\usepackage{sectsty}" in src and "\\sectionfont" in src:
        return src, False, "源码已有 sectsty 标题字体设置，看似已着色，跳过"
    if "\\usepackage{titlesec}" in src:
        return src, False, "源码使用 titlesec，自动着色可能与已有 \\titleformat 冲突，跳过（建议手工用 titlesec 着色）"
    if re.fullmatch(r"[0-9]+\s*,\s*[0-9]+\s*,\s*[0-9]+", color):
        decl = f"\\definecolor{{texopthead}}{{RGB}}{{{color}}}"
    elif color.startswith("RGB:"):
        decl = f"\\definecolor{{texopthead}}{{RGB}}{{{color[4:]}}}"
    elif color.startswith("HTML:"):
        decl = f"\\definecolor{{texopthead}}{{HTML}}{{{color[5:]}}}"
    else:
        decl = f"\\colorlet{{texopthead}}{{{color}}}"      # 颜色名/表达式
    block = COLOR_MACROS_TMPL.replace("@@DECL@@", decl)
    return _preamble_insert(src, block), True, \
        f"标题着色（section/subsection -> {color}）"


# ---------------------------------------------------------------- 元信息定点删除

_ANY_ENV = ANY_ENV_RE



def _code_lines(src: str) -> list[str]:
    """注释剥离（行内 % 前无反斜杠）后的代码行，行数不变。"""
    return [re.sub(r"(?<!\\)%.*$", "", ln) for ln in src.split("\n")]


def _env_at(code: str, pos: int):
    """pos 处所处的最内层环境 (name, begin_line, end_line)（1-based，含）。"""
    stack = []
    for m in _ANY_ENV.finditer(code):
        if m.start() >= pos:
            break
        if m.group(1) == "begin":
            stack.append((m.group(2), m.start()))
        elif stack and stack[-1][0] == m.group(2):
            stack.pop()
    if not stack:
        return None
    name, b0 = stack[-1]
    end = None
    depth = 0
    for m in _ANY_ENV.finditer(code, b0):
        if m.group(1) == "begin":
            depth += 1
        else:
            if m.group(2) == name:
                depth -= 1
                if depth == 0:
                    end = m
                    break
    if end is None:
        return None
    l0 = code.count("\n", 0, b0) + 1
    l1 = code.count("\n", 0, end.end()) + 1
    return name, l0, l1


def _block_span(lines: list[str], code: str, idx: int,
                max_env_lines: int = 40) -> tuple[int, int]:
    """返回包含第 idx 行（0-based）的可删除块行区间 (start, end)（0-based 含）。"""
    # 行号 -> 字符位置
    pos = sum(len(l) + 1 for l in lines[:idx])
    env = _env_at(code, pos)
    if env and env[0] in CALLOUT_ENVS and (env[2] - env[1]) <= max_env_lines:
        return env[1] - 1, env[2] - 1
    # 段落：向上/下扩展到空行
    s = idx
    while s > 0 and lines[s - 1].strip() and not lines[s - 1].lstrip().startswith(
            ("\\section", "\\subsection", "\\chapter")):
        s -= 1
    e = idx
    while e + 1 < len(lines) and lines[e + 1].strip():
        e += 1
    return s, e


def _remove_matching_blocks(src: str, match) -> tuple[str, list[int]]:
    """删除所有命中 match 的「块」（告示/段落/调用环境），返回 (新源, 行号)。"""
    lines = src.split("\n")
    code = "\n".join(_code_lines(src))
    hits = [i for i, ln in enumerate(_code_lines(src)) if match(ln)]
    drop: set = set()
    removed_lines: list[int] = []
    for i in hits:
        if i in drop:
            continue
        s, e = _block_span(lines, code, i)
        # 连带吞掉尾随空行，避免留出双倍空行
        while e + 1 < len(lines) and not lines[e + 1].strip():
            e += 1
        drop.update(range(s, e + 1))
        removed_lines.append(i + 1)
    if not drop:
        return src, []
    kept = [ln for i, ln in enumerate(lines) if i not in drop]
    # 清理空环境残留（\begin{center}\end{center} 之类）
    out = "\n".join(kept)
    out = re.sub(r"\\begin\{([a-zA-Z*]+)\}\s*\\end\{\1\}", "", out)
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out, removed_lines


def strip_reading_aids(src: str) -> tuple[str | None, bool, str]:
    """删除阅读辅助内容（"START READING HERE" / "document order was not
    finalized" 等明确非论文内容）。只匹配已知模式，绝不触碰正文句子。"""
    new, lines = _remove_matching_blocks(src, lambda ln: bool(READING_AID_RE.search(ln)))
    if not lines:
        return src, False, "未发现阅读辅助内容，跳过"
    return new, True, f"删除 {len(lines)} 处阅读辅助内容（第 {lines} 行）"


def remove_warning_boxes(src: str) -> tuple[str | None, bool, str]:
    """删除 WARNING/CAUTION/ATTENTION 类告示块（整段或整个调用环境）。

   只认「行首附近」的标记（前 60 字符内），避免误删正文里顺带提到
    “WARNING” 的句子。"""
    new, lines = _remove_matching_blocks(
        src, lambda ln: bool(WARNING_RE.search(ln.strip()[:60])))
    if not lines:
        return src, False, "未发现 WARNING 类告示，跳过"
    return new, True, f"删除 {len(lines)} 处 WARNING 类告示（第 {lines} 行）"
