# -*- coding: utf-8 -*-
"""全局量化层：L（基础逻辑）与 A（审美）两个数学量化的落地实现。

主线定义（2026-09-09 用户重对齐）：
  总目标函数是整篇文档级别、重编译后的全局量 —— 任何候选修复的验收
  都基于『整篇重编译后的评分』，而非『这一处问题修好没有』，
  从而拒绝贪心的局部最优（修了第 3 页孤行却把第 7 页浮动体弄漂了
  的改动会被评分函数判负并回滚）。

评分结构（lexicographic，先保底后求美）：
  total = L_fail * 1e6 + A + I

  L（基础逻辑量化，硬约束，不满足 = 不可接受）：
    - 能否编译通过、能否渲染出 PDF
    - 内容是否完整保留（document body 相对原稿零改动 —— 机器校验）
    - 是否符合页数限制（req.page_limit，若设定）
    - 硬性规范：要求明确指定的字号 / 页边距 / 公式居中（fleqn）
  A（审美量化，越小越好）：可测量代理指标加权 —— 正文 overfull/underfull、
    页面垂直问题 vbox（孤行寡行等断页质量的 TeX 侧代理信号）、浮动体警告、
    超宽图/表。
    *注*：孤行寡行的像素级精确检测与留白审美属于页面图像视觉层
    （advanced 阶段），本版用 vbox 信号 + 断行质量宏缓解作为代理。
  I（干预代价，最小干预原则）：改动离原稿越远分越高 —— 页边距偏离 mm、
    字号降档、浮动体参数/图片宽度被改的处数。松弛动作（往回改）天然降低
    I，因此达标后评分会自动把参数拉回『最宽松且最优』的临界点。
"""
from __future__ import annotations

import re

from . import perceive as P
from . import actions, visual
from .requirements import Requirement

L_PENALTY = 1e6          # L 每项违规的权重（远大于 A/I，保证先满足硬约束）
# 源码卫生问题在 A 分里的权重（按「能否被确定性动作修复 × 影响程度」定）：
# 有对应动作、且直接关联页面质量的高；纯风格、无动作的低。
HYGIENE_WEIGHT = {
    "manual_pagebreak": 1.0,      # remove_manual_pagebreak
    "heading_size": 0.8,          # normalize_heading_size
    "manual_vspace": 0.6,         # remove_excessive_vspace
    "list_spacing": 0.6,          # reduce_list_spacing
    "unbreakable": 0.6,           # add_hyphenation_points
    "long_url": 0.5,               # break_long_urls (xurl)
    # Phase 2：页面/版面级缺陷（有确定性动作，且人眼明显可见）
    "title_size": 0.8,            # normalize_title
    "multicols_mid": 0.8,         # remove_mid_multicols
    "parskip": 0.6,               # normalize_parskip
    "fig_oversized": 0.6,         # reduce_oversized_figures
    "subfig_overfull": 0.6,       # reduce_oversized_figures
    "table_narrow": 0.6,          # fix_table_width
    "header_abnormal": 0.5,       # normalize_header
    "size_switch": 0.5,           # normalize_local_font_size
    "missing_caption": 0.5,
    "dollar_math": 0.4,
    "reading_aid": 0.4,
    "warning_box": 0.4,
    "underline_abuse": 0.3,
    "noindent": 0.3,
    "hard_linebreak": 0.3,
    "center_text": 0.3,
}
DEFAULT_HYGIENE_WEIGHT = 0.4
BODY_RE = re.compile(
    r"\\begin\{document\}(.*)\\end\{document\}", re.S)
# 白名单排版 token（可被修复动作改动，不算内容）：浮动体位置参数、图片宽度
_FLOAT_SPEC_RE = re.compile(
    r"(\\begin\{(figure|table)(\*?)\})(\[[^\]]*\])?")
# 插图长度参数（width/height）——属排版面（缩图动作会改）
_FIG_WIDTH_RE = re.compile(r"(?:width|height)\s*=\s*[^,\]]+")
# 相对长度参数（子图/小页宽度 {0.49\textwidth} 等）——属排版面
_REL_LEN_ARG_RE = re.compile(
    r"\{\s*[0-9]*\.?[0-9]+\s*\\(?:textwidth|linewidth|columnwidth|"
    r"textheight|paperheight|hsize)\s*\}")


# texopt 自己注入的标记块（质量宏/页眉/标题着色/目录页）——内容校验时整体忽略
_TEXOPT_BLOCK_RE = re.compile(r"(?s)% ===== texopt:.*?% ===== texopt end =====[^\n]*\n?")


def _meta_strip(b: str, req) -> str:
    """元信息归一：删除要求允许的「非正文」内容，使两边可对齐。

    阅读辅助内容 / WARNING 告示属编辑性元信息（要求开启时才允许）；
    目录页命令（\tableofcontents）属结构而非内容。两边同时归一后，
    这些定点删除就不会被误算为「正文内容被改动」。
    """
    b = _TEXOPT_BLOCK_RE.sub("", b)
    if req is None:
        return b
    if getattr(req, "strip_reading_aids", False):
        b = actions.strip_reading_aids(b)[0] or b
    if getattr(req, "remove_warning_boxes", False):
        b = actions.remove_warning_boxes(b)[0] or b
    return re.sub(r"\\tableofcontents\s*(?:\\(?:newpage|clearpage))?", "", b)  # 目录页（结构）


# 排版命令可动面（2026-09-11 扩展）：以下 token 属「排版面」而非正文内容，
# 确定性动作可以删/改它们，内容校验因此对它们归一后再比较：
#   * 手动分页 \newpage/\clearpage/\pagebreak（remove_manual_pagebreak）
#   * 过大手动垂直间距 \vspace{...}（remove_excessive_vspace）
#   * 行内字号切换 \Large/\tiny…（normalize_local_font_size）
#   * 断词点 \-（add_hyphenation_points，零宽可选断点，不改语义）
#   * 列表间距选项 itemsep/topsep/parsep/partopsep（reduce_list_spacing）
#   * 表格环境名/列格式（_norm_tabular_envs：fix_table_width 用 tabularx）
# 正文文字/词序/标点/公式/引用/图表内容仍为逐字符严格比较。
_FMT_TOKEN_RES = [
    re.compile(r"\\(?:newpage|clearpage|pagebreak)\*?(?:\s*\[[^\]]*\])?"),
    re.compile(r"\\vspace\*?\{[^}]*\}"),
    re.compile(r"\\(?:tiny|scriptsize|footnotesize|small|normalsize|"
               r"large|Large|LARGE|huge|Huge)\b"),
    re.compile(r"\\-"),
    re.compile(r"\\begin\{multicols\*?\}(\s*\[[^\]]*\])?(\s*\{[^}]*\})?"),
    re.compile(r"\\end\{multicols\*?\}"),
]
_LIST_OPT_RE = re.compile(
    r"(\\begin\{(?:itemize|enumerate|description)\})\s*\[([^\]]*)\]")
_LIST_SPACING_KEY_RE = re.compile(r"\s*(?:itemsep|topsep|parsep|partopsep)\s*=")


def _strip_list_spacing_opts(m) -> str:
    keep = [o for o in m.group(2).split(",")
            if o.strip() and not _LIST_SPACING_KEY_RE.match(o)]
    return m.group(1) + ("[" + ",".join(keep) + "]" if keep else "")


def _norm_body_fmt(b: str) -> str:
    """抹去「排版命令可动面」的 token（见 _FMT_TOKEN_RES 注释）。"""
    for rx in _FMT_TOKEN_RES:
        b = rx.sub("", b)
    b = _LIST_OPT_RE.sub(_strip_list_spacing_opts, b)
    b = _norm_tabular_envs(b)          # 表格环境/列格式属排版面
    return b


def _norm_body(b: str, req=None) -> str:
    """归一正文：抹去白名单排版 token 的值，其余原样保留。

    修复动作允许落在排版面：浮动体位置参数（[h]->[tbp]）、插图宽度
    （170mm->\\linewidth）、手动分页/过大垂直间距/行内字号乱标/断词点/
    列表间距选项/表格列格式（见 _norm_body_fmt）。内容完整性校验因此
    采用『归一化 diff』：这些 token 变化不算内容改动，其余任何字符
    （文字/公式/引用/标签/图表内容）变化一律判为违规。
    """
    b = _meta_strip(b, req)
    b = _FLOAT_SPEC_RE.sub(lambda m: m.group(1), b)   # 抹掉 [h]/[tbp] 等参数
    b = _FIG_WIDTH_RE.sub("width=W", b)              # 抹掉 width/height 的值
    b = _REL_LEN_ARG_RE.sub("{LEN}", b)              # 抹掉相对长度参数
    b = re.sub(r"\$\$.+?\$\$", "MATH", b, flags=re.S)   # 裸 $$ 数学
    b = re.sub(r"\\\[.+?\\\]", "MATH", b, flags=re.S)  # displaymath
    b = _norm_body_fmt(b)                             # 排版命令可动面
    return b


def content_body(src: str) -> str:
    """抽取 document 环境内的正文原文（含注释/空白），用于内容完整性校验。"""
    m = BODY_RE.search(src)
    return m.group(1) if m else ""


# 表格环境/列格式归一：实现已下沉到 perceive（fig_fingerprint 也要用同源规则）
_norm_tabular_envs = P.norm_tabular_specs


def _norm_body_ext(b: str, req=None) -> str:
    """模型在环归一器：引擎白名单 + 模型可改的卫生排版命令。

    引擎闭环只允许白名单排版参数变化（_norm_body）；模型在环阶段还被
    允许删除 \\noindent/\\vspace/\\newpage、\\underline -> \\emph、
    移除 center 环境、字号乱标、段落硬换行等 —— 这些是排版命令而非
    内容。归一后逐字节一致即『正文语义零改动』。
    """
    b = re.sub(r"(?<!\\)%.*$", "", b, flags=re.M)       # 剥行注释（行尾[E]/[H]等）
    b = _norm_body(b, req)
    b = re.sub(r"\\underline", r"\\emph", b)          # 下划线->强调（归一）
    b = re.sub(r"\\vspace\*?\{[^}]*\}", "", b)        # 手动垂直间距
    b = re.sub(r"\\(?:newpage|clearpage|pagebreak)\b", "", b)  # 手动分页
    b = re.sub(r"\\noindent\b", "", b)                 # 取消缩进命令
    b = re.sub(r"\\(?:tiny|scriptsize|footnotesize|small|normalsize|"
               r"large|Large|LARGE|huge|Huge)\b", "", b)  # 行内字号乱标
    b = re.sub(r"\\(?:begin|end)\{center\}", "", b)    # center 环境标记
    b = _norm_tabular_envs(b)             # 表格环境/列格式归一
    b = re.sub('\\\\\\\\\\s*(?:\\[[^\\]]*\\])?', "", b)          # 行尾硬换行 \\（含 [len]）
    b = b.replace("\\-", "")                     # 断词符 \-（零宽排版字符）
    b = re.sub(r"\\hfill\b|\\break\b", "", b)
    b = re.sub(r"\{\}", "", b)                          # 空组（\Large{} 等残留）
    return b


def semantic_diff(orig_src: str, work_src: str, req=None) -> dict:
    """模型在环语义保留：扩展归一 + 空白归一比较。

    排版命令级变化（noindent/vspace/分页/underline/center/字号/硬换行）与
    换行/空格差异不计；正文文字、词序、标点、公式、引用的任何变化都会
    判未通过（空白归一后逐字符比较）。
    """
    def _norm(src: str) -> str:
        b = content_body(src)
        b = _norm_body_ext(b, req)
        return "".join(b.split())          # 空白归一（行/空格差异不计）

    a, b = _norm(orig_src), _norm(work_src)
    preserved = a == b
    return {"preserved": preserved,
            "note": "排版命令与空白差异不计；正文文字/词序/标点/公式/引用"
                    "任何变化都会判未通过"}


def body_unchanged(orig_src: str, work_src: str, req=None) -> bool:
    """机器校验内容零改动：正文区域归一化后必须完全一致。

    全部修复动作只落在 preamble / documentclass 选项 / geometry /
    浮动体位置参数 / 图片宽度上；归一化 diff 为空即『内容完整保留』。
    """
    return _norm_body(content_body(orig_src), req) \
        == _norm_body(content_body(work_src), req)


def _num_width_mm(expr: str) -> float | None:
    m = re.fullmatch(r"\s*([0-9]*\.?[0-9]+)\s*(mm|cm|in|pt)?", expr.strip())
    if not m:
        return None
    val = float(m.group(1))
    unit = (m.group(2) or "pt").lower()
    return val * {"mm": 1.0, "cm": 10.0, "in": 25.4, "pt": 25.4 / 72.27}[unit]


def _overwide_figs(per: P.Perception, req: Requirement) -> list[str]:
    """超宽的插图宽度表达式清单（数值宽度 > 阈值，或相对系数 > 1.0）。

    修复 2026-09-11：旧版只算数值宽度，`width=1.18\\linewidth` 这类
    相对超宽（最常见的 Overfull 来源）根本不计入 A，导致“图明明溢出、
    分数却没反应”。"""
    out = []
    for expr in per.source.get("graphics_width_expr", []):
        mm = _num_width_mm(expr)
        if mm is not None:
            if mm > req.overwide_fig_threshold_mm:
                out.append(expr)
            continue
        m = re.fullmatch(r"\s*([0-9]*\.?[0-9]+)\s*\\(?:linewidth|"
                         r"textwidth|columnwidth|hsize)\s*", expr)
        if m and float(m.group(1)) > 1.0:
            out.append(expr)
    return out


def page_status(per: P.Perception, req: Requirement) -> dict:
    """页数判定口径（会议差异的唯一来源是 req.page_limit_scope）。

    total   —— 传统口径：直接比 PDF 总页数（与以前行为完全一致）；
    content —— 会议口径：上限针对「正文页」（参考文献/附录不计）。
      用 pdftotext 定位参考文献首页 k：
        strict = k-1（完全在参考文献之前的页数）→ 只有它超限才判违规，
                 避免把「正文恰好写到参考文献首页」的合法论文误判；
        judge  = k  （含参考文献首页的上界）→ 用于压页推进/报告展示。
    量不出正文页数时自动退回总页数口径（并在 advisory 里说明）。
    """
    scope = getattr(req, "page_limit_scope", "total") or "total"
    limit = getattr(req, "page_limit", None)
    st = {"scope": scope, "limit": limit, "total": per.pages,
          "content_lower": getattr(per, "content_pages_lower", None),
          "content_upper": getattr(per, "content_pages_upper", None),
          "judge": per.pages, "strict": per.pages, "label": "页数"}
    if scope == "content" and st["content_upper"] is not None:
        st["judge"] = st["content_upper"]
        st["strict"] = st["content_lower"]
        st["first_ref_page"] = (per.content or {}).get("first_ref_page")
        if st["first_ref_page"]:
            st["label"] = "正文页数（参考文献之前，含参考文献首页的上界）"
        else:
            st["label"] = "页数（未检测到参考文献标题，按总页数计）"
    st["over_strict"] = bool(limit and st["strict"] is not None
                             and st["strict"] > limit)
    st["over_soft"] = bool(limit and st["judge"] is not None
                           and st["judge"] > limit)
    return st


def judge_pages(per: P.Perception, req: Requirement) -> int | None:
    """当前用于压页推进的页数（会议口径下为正文页上界）。"""
    return page_status(per, req)["judge"]


def within_limit(per: P.Perception, req: Requirement) -> bool:
    """是否确定满足页数上限（会议口径下用下界，避免临界误判）。"""
    return not page_status(per, req)["over_strict"]


def page_advisory(per: P.Perception, req: Requirement) -> str | None:
    """页数相关的「临界/口径」提示（信息，不是违规）。"""
    st = page_status(per, req)
    if st["over_soft"] and not st["over_strict"]:
        return (f"{st['label']} = {st['judge']}，高于上限 {st['limit']}，"
                f"但完全在参考文献之前的页数 {st['strict']} ≤ {st['limit']}："
                "正文可能恰好写到参考文献首页（临界），不判违规，"
                f"建议人工/视觉确认（PDF 共 {st['total']} 页）")
    if st["scope"] == "content" and st["content_upper"] is None:
        return ("会议页数上限按正文页口径，但未能量出正文页数"
                "（pdftotext 不可用或无参考文献），已退回总页数判定"
                f"（PDF 共 {st['total']} 页）")
    return None


def l_violations(per: P.Perception, req: Requirement,
                 orig_body: str, orig_source: dict | None = None) -> list[str]:
    """L 硬约束违规清单。空列表 = 基础逻辑量化达标。"""
    out: list[str] = []
    if not per.ok:
        out.append(f"编译失败/无法渲染 PDF（{per.compile.first_error}）")
    elif per.compile.pdf_path is None:
        out.append("未生成 PDF")
    if _norm_body(content_body(per.src), req) != _norm_body(orig_body, req):
        out.append("正文内容被改动（违反内容完整保留）")
    if req.page_limit:
        st = page_status(per, req)
        if st["over_strict"]:
            if st.get("first_ref_page"):
                out.append(f"正文页数 {st['strict']}–{st['judge']}（参考文献之前）"
                           f"超出限制 {req.page_limit}（PDF 共 {st['total']} 页）")
            else:
                out.append(f"页数 {st['judge']} 超出限制 {req.page_limit}")
        elif st["scope"] == "content" and st["content_upper"] is None \
                and per.pages is not None and per.pages > req.page_limit:
            out.append(f"页数 {per.pages} 超出限制 {req.page_limit}"
                       "（未能区分正文页，按总页数判定）")
    # 硬性规范（期刊/会议/自定义要求明确指定的，属 L 而非审美项）
    if req.font_pt and per.source["font_pt"] != req.font_pt:
        out.append(f"字号 {per.source['font_pt']}pt 不符合要求 {req.font_pt}pt")
    if req.margin_mm and per.source.get("geometry_margin_mm") is not None:
        cur_mm = per.source["geometry_margin_mm"]
        if getattr(req, "margin_is_floor", False):
            # 会议模板：官方边距是下限（模板 json 里的 margin_floor_mm）——
            # 低于下限才不合规；高于下限不干预（不得把合法的宽/不对称边距改小）。
            if cur_mm < req.margin_mm - 0.5:
                out.append(f"页边距 {cur_mm:g}mm 低于要求下限 "
                           f"{req.margin_mm:g}mm")
        elif abs(cur_mm - req.margin_mm) > 0.5:
            out.append(f"页边距 {cur_mm:g}mm 不符合要求 {req.margin_mm:g}mm")
    if req.eq_fleqn_allowed is False and per.source["fleqn"]:
        out.append("文档类带 fleqn 选项，公式未居中")
    # 结构规范：目录 / 页眉（要求明确指定才算硬约束）
    if req.toc and per.source.get("sections", 0) >= req.toc_min_sections \
            and not per.source.get("has_toc"):
        out.append("缺少目录页（要求 toc=True）")
    if req.running_header and not per.source.get("has_header"):
        out.append("缺少页眉（要求 running_header=True）")
    # 图形保真：图表内容不得重绘/改写（多源判断的图像层底线）
    if req.preserve_figures and orig_source is not None:
        cur_f = [(f.get("kind"), f.get("fingerprint"))
                 for f in per.source.get("figures", [])]
        org_f = [(f.get("kind"), f.get("fingerprint"))
                 for f in orig_source.get("figures", [])]
        if cur_f != org_f:
            out.append(f"图形/表格内容被改动（原稿 {len(org_f)} 处，"
                       f"现 {len(cur_f)} 处，指纹不一致）")
    return out


def aesthetic_score(per: P.Perception, req: Requirement) -> float:
    """A 分：全局审美/质量量化（越低越好），全部为整篇文档统计量。"""
    iss = per.issues
    a = (1.0 * len(iss["overfull"])          # 正文行溢出
         + 0.6 * len(iss["underfull"])       # 正文行欠满（微）
         + 1.0 * sum(1 for v in iss["vbox"] if v["kind"] == "Overfull")
         + 1.4 * sum(1 for v in iss["vbox"] if v["kind"] == "Underfull")
         # Underfull vbox 常与孤行寡行同源（页面垂直断点质量）
         + 1.6 * len(iss["floats"])           # 浮动体警告（尺寸/位置被 TeX 强改）
         + 1.2 * len(iss["tables_overwide"])  # 表格超宽（有 tabularx 修复动作）
         + 0.3 * len(iss.get("warnings", []))  # 其余编译 Warning
         )
    a += 1.0 * len(_overwide_figs(per, req))  # 超宽图（有自动修复动作）
    # 预防性配置缺失惩罚：要求开启却未注入的断行质量宏（防孤行寡行等）
    if req.enable_quality_macros and "texopt: 排版质量宏" not in per.src:
        a += 2.0
    # 不稳定的浮动体位置参数（TeX 会自行改写 [h]->[ht]，属放置质量缺陷）；
    # [H]（float 宏包强排）会把图钉死在本行，是页面失衡/大块留白常见来源
    for fe in per.source.get("float_envs", []):
        spec = (fe.get("spec") or "").strip()
        if spec and actions._unstable_spec(spec):
            a += 0.8
        elif spec == "H":
            a += 0.5
    # 源码层排版卫生问题（各自可被确定性动作修复，权重按可修性与影响度）
    a += sum(HYGIENE_WEIGHT.get(h["kind"], DEFAULT_HYGIENE_WEIGHT)
             for h in per.issues.get("hygiene", []))
    # Phase 2：页面级视觉缺陷（量自实际 PDF：巨大图/大面积空白/空洞/密度失衡…）
    # —— A 不再只是 LaTeX warning 的加权和，而是真的能反映“看起来明显很差”的页面
    a += visual.defect_penalty(visual.visual_defects(getattr(per, "visual", None)))
    # 结构规范：要求目录/页眉/标题着色却未落实
    if req.toc and not per.source.get("has_toc") \
            and per.source.get("sections", 0) >= req.toc_min_sections:
        a += 2.5
    if req.running_header and not per.source.get("has_header"):
        a += 2.5
    if req.heading_color and not per.source.get("has_heading_color"):
        a += 1.5                                 # 标题未着色（审美项）
    return round(a, 3)


def intervention_cost(per: P.Perception, orig: P.Perception) -> float:
    """I 分：干预代价（越小越好）。动作离原稿越远代价越高。"""
    cost = 0.0
    cur_m = per.source.get("geometry_margin_mm")
    org_m = orig.source.get("geometry_margin_mm")
    if cur_m is not None and org_m is not None:
        cost += 0.5 * abs(cur_m - org_m)          # 页边距每偏离 1mm
    cur_f = per.source.get("font_pt") or 10
    org_f = orig.source.get("font_pt") or 10
    cost += 3.0 * abs(cur_f - org_f)              # 字号每偏离 1 档
    # 浮动体位置参数被规范化处数
    cur_specs = [fe.get("spec") for fe in per.source.get("float_envs", [])]
    org_specs = [fe.get("spec") for fe in orig.source.get("float_envs", [])]
    cost += 0.4 * sum(1 for a, b in zip(org_specs, cur_specs) if a != b)
    # 图片宽度表达式被改（归一）处数
    cur_w = per.source.get("graphics_width_expr", [])
    org_w = orig.source.get("graphics_width_expr", [])
    cost += 0.4 * sum(1 for a, b in zip(org_w, cur_w) if a != b)
    return round(cost, 3)


def total_score(per: P.Perception, req: Requirement,
                orig: P.Perception) -> dict:
    """完整评分：返回 {l: [...], a: float, i: float, total: float, ok: bool}。"""
    lv = l_violations(per, req, content_body(orig.src), orig.source)
    a = aesthetic_score(per, req)
    i = intervention_cost(per, orig)
    total = L_PENALTY * len(lv) + a + i
    return {"l": lv, "a": a, "i": i, "total": round(total, 3), "ok": not lv}


def visual_defects(per: P.Perception) -> list:
    """当前文档的页面级视觉缺陷清单（无视觉信息时为空）。"""
    return visual.visual_defects(getattr(per, "visual", None))
