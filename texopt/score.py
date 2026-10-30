# -*- coding: utf-8 -*-
"""全局量化层（2026-10-14 v3 结构）：**底层逻辑门** + **model1** + **model2**。

  ┌── 底层逻辑 gate（不是公式，是「必须满足」的前置条件）
  │     编译成功 / 产出 PDF、页数≤上限（有要求时）、图表保真、
  │     字号、页边距、fleqn·目录·页眉（要求点名时）
  │     —— 任一项不满足 = 不可行（+∞），不参与打分
  ├── model1（主）：M1 = ρ·P + I
  │     P（页面缺陷，半硬性，带详细比重）：行级 over/underfull、vbox、
  │       浮动体警告与强排、超宽表/图、源码卫生、内容孤立/空白页
  │     I（整体修改情况，越小越好）：I_struct + β·D_content
  ├── model2（审美）：M2 = A_soft + λ·A_profile
  │     A_soft（绝对软指标）：灰度/墨迹密度、留白、图表占比、上下均衡
  │     A_profile（相对偏离）：与同会议·同角色·同栏数语料档案比，λ 默认 0
  └── 排序：字典序 (|gate|, M1, M2)

设计原则（不变）：一切量都建在 R(x′) 上 —— **先整篇重编译，再全局重评**，
拒绝贪心局部修复。
"""
from __future__ import annotations

import math
import re
from collections import Counter

from . import perceive as P
from . import actions, visual
from .requirements import Requirement

# ============ 模型权重与比重表（2026-10-14 用户重新定义，均可标定） ============
GATE_PENALTY = 1e6       # 底层逻辑违规的权重（远大于 M1/M2，保证 gate 优先）
L_PENALTY = GATE_PENALTY  # 旧名兼容
# ρ：缺陷 → 代价单位 的换算率（model1 里 P 与 I 的汇率）。
# 2026-10-30（用户拍定口径 = **等边际收益**）：ρ = 闭环里**实际付出**的干预代价 ÷
#   实际修掉的缺陷，即 ΔI /(−ΔP)，只统计真的付了代价（ΔI>0）的尝试动作
#   （免费修复不携带汇率信息；按每次尝试而非被接受动作统计，避免 ρ 自我论证）。
#   实测 4 篇真编译闭环（43 次修复动作 / 其中 6 次付费）：
#       ρ 中位 0.341（p25 0.304，p75 0.383），未裁剪。
#   artifact = metrics/rho_exchange_rate.json；工具 = tools/calibrate_rho.py。
# 含义：「修掉 1 个加权缺陷，实际换来约 0.34 个代价单位」——比原先手拍的 2.0 低，
#   因为多数缺陷是零代价修掉的（质量宏/删手动分页/规范浮动体参数）。
# 注意：样本小（6 次付费动作，单人/单语料），后续采到更多闭环数据应重跑。
W_PAGE_DEFECT = 0.341
# β：正文改动幅度的权重（内容保留不再是硬约束，但仍是强偏好；
#   语义抛光阶段另设内容保留率下限 κ 兜底）。
CONTENT_PENALTY = 50.0

# ---- P：页面缺陷比重（半硬性约束，2026-10-30 回填数据来源）----
# 2026-10-30（任务3）：5 项换成**有来源**的值
#   w = 人的严重度（15 题成对比较 → Bradley-Terry） ÷ 语料频率（200 篇/3898 页）
#   再做 sqrt 阻尼 + 缩放到现行权重同量纲；口径见 docs/stage11_severity_sheet_20261028.md，
#   applied artifact = metrics/severity_weights_applied.json（tools/apply_severity_weights.py）。
#   其余 6 项仍是先验：vbox_under/spec_H/tab_overwide/fig_overwide/stranded_block/
#   near_empty 在语料里计数为 0 或无对应字段，作不了分母（不伪造）；warn/macros_missing/
#   unstable_spec 属人眼不可判的技术项，不进标定表。
# 注意：ρ（W_PAGE_DEFECT）是总尺度锚点，这里只改 P 的内部相对结构。
PAGE_DEFECT_WEIGHT = {
    "overfull": 0.33,       # 正文行溢出（右侧超出）        ← human×corpus
    "underfull": 0.273,     # 正文行欠满                    ← human×corpus
    "vbox_over": 2.344,     # 页面垂直盒子溢出              ← human×corpus
    "vbox_under": 1.4,      # 页面垂直盒子欠满（孤行寡行代理）← 先验（语料计数 0）
    "floatwarn": 1.254,     # 浮动体警告（位置/尺寸被强改）  ← human×corpus
    "tab_overwide": 1.2,    # 表格超宽                      ← 先验（语料无字段）
    "fig_overwide": 1.0,    # 图片超宽                      ← 先验（语料无字段）
    "warn": 0.3,            # 其余编译 Warning              ← 先验（人不可判）
    "macros_missing": 2.0,  # 断行质量宏缺失                ← 先验（人不可判）
    "unstable_spec": 0.8,   # 浮动体位置参数不稳定          ← 先验（人不可判）
    "spec_H": 0.5,          # [H] 强排                      ← 先验（语料计数 0）
}
# 页面图像层的缺陷归属：结构/放置类进 model1，软性审美类进 model2。
VISUAL_DEFECT_M1 = {
    "stranded_block": 1.2,  # 内容孤零零 + 大面积留白（放置错误类）
    "near_empty": 0.6,      # 几乎空白页（孤立浮动体/手动分页等结构问题）
}

# ---- model2：A_soft 参考带 (lo, hi, w)（2026-10-28 起**只用于报告口径**）----
# 打分不再用「带内=0 / 带外线性罚」，改用下面的 SOFT_SPEC 平滑目标形式：
# 人工排序验收（workbench-detector/rank_analysis_20261028.md）显示带内=0 会制造
# 大量并列（20 页里 8 页总分恰为 0），把排序信号抹平，且 ink_ratio 上界与人的偏好相反。
SOFT_BANDS = {
    "ink_ratio": (0.020, 0.150, 1.0),         # 灰度 / 墨迹密度
    "bottom_blank": (0.000, 0.220, 1.5),      # 页底留白
    "top_blank": (0.000, 0.120, 0.6),         # 页首留白
    "max_gap": (0.000, 0.150, 1.2),           # 页内连续空洞
    "band": (0.050, 0.350, 3.0),              # 图表/公式块占页高（图表占比代理）
    "left_blank": (0.000, 0.180, 0.6),        # 左侧留白
    "right_blank": (0.000, 0.180, 0.6),       # 右侧留白
    "top_bottom_ratio": (0.700, 1.400, 0.8),  # 上下半页墨迹均衡
}
W_SOFT_LOW, W_SOFT_HIGH = 1.2, 1.0   # 旧带形式的系数，仅兼容保留
# ---- model2：A_soft 平滑目标形式（2026-10-28 起实际打分口径）----
# 每个指标给一个**目标 t**（取已录用语料中位数，3898 页，见 detector_check.json）
# 和两侧尺度 s（取 t 到 p5 / p95 的距离），损失为**无平台区**的平滑核：
#
#     d = |x - t| / s_side        loss = w · (1 - exp(-d²/2))   ≤ w
#
# 性质：① 目标处损失为 0、两侧严格单调增（无并列平台）；② 有界（w 封顶），
# 极端页不吃掉全部权重；③ 单侧指标把某一侧 s 设 None 即该侧不罚。
# 单侧设定依据人工排序结果：人偏好“更满”的页面（ink_ratio 原始值 ρ=+0.50）、
# 不惩罚页底留白（bottom_blank ρ=+0.42），真正刺眼的是**大片空洞**与**上下失衡**。
SOFT_SPEC = {
    # metric            t(目标)  s_low  s_high  w     说明
    "ink_ratio":        dict(t=0.120, s_low=0.076, s_high=None,  w=1.0,  # 只罚过空
                             note="上侧不罚：满版/整页图不是缺陷"),
    "bottom_blank":     dict(t=0.066, s_low=0.025, s_high=None,  w=0.8,  # 只罚贴边
                             note="多留白不罚，失衡交给 tbr/max_gap"),
    "top_blank":        dict(t=0.079, s_low=0.047, s_high=0.039, w=0.5),
    "max_gap":          dict(t=0.100, s_low=None,  s_high=0.244, w=1.4,  # 只罚大洞
                             note="小空洞无所谓，唯一人工验证有效的量"),
    "band":             dict(t=0.004, s_low=0.030, s_high=0.051, w=0.0,  # 暂缓
                             note="Step2 判暂缓：语料 5% 在带内，量本身不可用"),
    "left_blank":       dict(t=0.091, s_low=0.022, s_high=0.130, w=0.4),
    "right_blank":      dict(t=0.115, s_low=0.036, s_high=0.100, w=0.4),
    "top_bottom_ratio": dict(t=1.031, s_low=0.515, s_high=1.292, w=1.0,  # 对数空间
                             log=True, note="比值量取对数后对称"),
}
SOFT_LOSS_CAP = 3.0
SOFT_METRIC_CLIP = {"top_bottom_ratio": (0.05, 5.0)}

# 源码卫生问题在 P 里的比重（按「能否被确定性动作修复 × 影响程度」定）：
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


# ---- 底层逻辑门：结构化描述（2026-10-30 任务1：一票否决 + 直接退出 + 建议）----
# code → 是否**可被白名单确定性动作修复**。不可修复项一旦出现，闭环不再打分、
# 不再试动作，直接退出（BLOCKED_GATE）并给修改建议。
GATE_REPAIRABLE = {
    "compile": False,   # 编译错误（缺宏包/语法错误）：不在排版动作面内
    "pdf": False,       # 产不出 PDF
    "content": False,   # content_hard=True 时正文被改
    "figures": False,   # 图形/表格指纹变化（保真底线）
    "pages": True,      # 可压页（margin_cut / font_cut）
    "font": True,       # font_spec / font_cut
    "margin": True,     # margin_spec
    "fleqn": True,      # drop_fleqn
    "toc": True,        # insert_toc
    "header": True,     # 页眉动作
}
GATE_SUGGEST = {
    "compile": "先修 .tex 的编译错误（看日志第一条 Error），或换成可编译的模板/宏包组合",
    "pdf": "确认引擎真的产出 PDF（不是只有 DVI）；缺字体/宏包先补齐",
    "content": "content_hard=True：正文必须逐字保留，把改动的正文还原",
    "figures": "图形/表格内容不得重绘或替换，只允许改宽度：恢复原内容",
    "pages": "页数超限：先用纯排版压（收边距/降字号/修浮动体/缩图宽）；仍超再删减内容或换图表",
    "font": "把 \\documentclass 字号选项改到要求档位（10/11/12pt），局部字号不算",
    "margin": "用 geometry 把页边距调到要求值（会议模板以下限口径判）",
    "fleqn": "去掉 \\documentclass 的 fleqn 选项，让公式回到居中",
    "toc": "要求目录：加 \\tableofcontents，并连编两遍让页码稳定",
    "header": "要求页眉：加 fancyhdr/pagestyle 页眉，并检查首页样式",
}


def gate_issues(per: P.Perception, req: Requirement,
                orig_body: str, orig_source: dict | None = None) -> list[dict]:
    """底层逻辑（可行性门）的结构化违规清单。空列表 = 这些「必须满足」的条件全部满足。

    2026-10-14 用户重新定义：这里不再是「一个可打分的模型」，而是**底层逻辑**——
    编译/产出 PDF、页数上限（有要求时）、图表保真、字号/边距/fleqn/目录/页眉
    （要求点名时）这些是「硬性必须满足」，任一项不满足即不可行，不参与打分。

    2026-10-30（任务1）：每项带 code / repairable / suggestion。调用方据此决定
    「直接退出（不可修复）」还是「先跑 gate 定向修复（可修复）」。
    """
    out: list[dict] = []

    def add(code: str, text: str):
        out.append({"code": code, "text": text,
                    "repairable": bool(GATE_REPAIRABLE.get(code, False)),
                    "suggestion": GATE_SUGGEST.get(code, "")})

    if not per.ok:
        add("compile", f"编译失败/无法渲染 PDF（{per.compile.first_error}）")
    elif per.compile.pdf_path is None:
        add("pdf", "未生成 PDF")
    # 2026-10-14：正文内容完整保留默认**不再**是硬约束（语义抛光阶段要合法改正文）。
    # 默认走软项 CONTENT_PENALTY·D_content（见 total_score）；
    # 需要旧口径时把 Requirement.content_hard 置 True。
    if getattr(req, "content_hard", False) \
            and _norm_body(content_body(per.src), req) != _norm_body(orig_body, req):
        add("content", "正文内容被改动（content_hard=True：违反内容完整保留）")
    if req.page_limit:
        st = page_status(per, req)
        if st["over_strict"]:
            if st.get("first_ref_page"):
                add("pages", f"正文页数 {st['strict']}–{st['judge']}（参考文献之前）"
                             f"超出限制 {req.page_limit}（PDF 共 {st['total']} 页）")
            else:
                add("pages", f"页数 {st['judge']} 超出限制 {req.page_limit}")
        elif st["scope"] == "content" and st["content_upper"] is None \
                and per.pages is not None and per.pages > req.page_limit:
            add("pages", f"页数 {per.pages} 超出限制 {req.page_limit}"
                         "（未能区分正文页，按总页数判定）")
    # 硬性规范（期刊/会议/自定义要求明确指定的，属 L 而非审美项）
    if req.font_pt and per.source["font_pt"] != req.font_pt:
        add("font", f"字号 {per.source['font_pt']}pt 不符合要求 {req.font_pt}pt")
    if req.margin_mm and per.source.get("geometry_margin_mm") is not None:
        cur_mm = per.source["geometry_margin_mm"]
        if getattr(req, "margin_is_floor", False):
            # 会议模板：官方边距是下限（模板 json 里的 margin_floor_mm）——
            # 低于下限才不合规；高于下限不干预（不得把合法的宽/不对称边距改小）。
            if cur_mm < req.margin_mm - 0.5:
                add("margin", f"页边距 {cur_mm:g}mm 低于要求下限 {req.margin_mm:g}mm")
        elif abs(cur_mm - req.margin_mm) > 0.5:
            add("margin", f"页边距 {cur_mm:g}mm 不符合要求 {req.margin_mm:g}mm")
    if req.eq_fleqn_allowed is False and per.source["fleqn"]:
        add("fleqn", "文档类带 fleqn 选项，公式未居中")
    # 结构规范：目录 / 页眉（要求明确指定才算硬约束）
    if req.toc and per.source.get("sections", 0) >= req.toc_min_sections \
            and not per.source.get("has_toc"):
        add("toc", "缺少目录页（要求 toc=True）")
    if req.running_header and not per.source.get("has_header"):
        add("header", "缺少页眉（要求 running_header=True）")
    # 图形保真：图表内容不得重绘/改写（多源判断的图像层底线）
    if req.preserve_figures and orig_source is not None:
        cur_f = [(f.get("kind"), f.get("fingerprint"))
                 for f in per.source.get("figures", [])]
        org_f = [(f.get("kind"), f.get("fingerprint"))
                 for f in orig_source.get("figures", [])]
        if cur_f != org_f:
            add("figures", f"图形/表格内容被改动（原稿 {len(org_f)} 处，"
                           f"现 {len(cur_f)} 处，指纹不一致）")
    return out


def gate_violations(per: P.Perception, req: Requirement,
                    orig_body: str, orig_source: dict | None = None) -> list[str]:
    """兼容接口：只返回 gate 违规的文字清单（空 = 可行）。"""
    return [d["text"] for d in gate_issues(per, req, orig_body, orig_source)]


def soft_metric_loss(metric: str, x) -> float | None:
    """单页单指标的 A_soft 损失（平滑目标形式，无平台区、有界）。

    x 为渲染层原始量；缺失返回 None。一侧 s 为 None 表示该侧不罚。
    """
    spec = SOFT_SPEC.get(metric)
    if spec is None or not spec.get("w") or x is None:
        return None
    clip = SOFT_METRIC_CLIP.get(metric)
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    if clip:
        x = min(max(x, clip[0]), clip[1])
    t = spec["t"]
    if spec.get("log"):
        eps = 1e-6
        x, t = math.log(max(x, eps)), math.log(max(t, eps))
    s = spec["s_low"] if x < t else spec["s_high"]
    if not s:
        return 0.0                        # 单侧：该方向不罚
    d = abs(x - t) / max(s, 1e-6)
    return min(SOFT_LOSS_CAP, spec["w"] * (1.0 - math.exp(-0.5 * d * d)))


def aesthetic_score(per: P.Perception, req: Requirement) -> float:
    """model2 · A_soft：**绝对软指标**的审美量化（越低越好）。

    2026-10-14 用户重新定义：审美层面只看软性约束——页面灰度/墨迹密度、
    留白情况、图表占比、上下半页密度均衡等；而「浮动体错位/孤行寡行」这类
    页面缺陷已归入 model1 的 P（见 PAGE_DEFECT_WEIGHT / VISUAL_DEFECT_M1）。

    量来自渲染页图（`per.visual` 的页级 page_metrics）。2026-10-28 起每个软指标
    用**平滑目标形式**（见 SOFT_SPEC）：
        d = |x - t| / s_side,   loss = w · (1 - exp(-d²/2))
    目标 t 与尺度 s 由 3898 页已录用语料的中位数/p5/p95 定出，侧别可单侧关闭；
    目标处为 0、两侧严格单调、有界，**没有“带内一律 0”的平台区**
    （旧带形式导致 20 页里有 8 页总分为 0，人工排序 Spearman 只有 0.31）。
    再按 CVaR 式做「页 → 文档」聚合：0.5·前k大均值 + 0.5·全体均值，
    k = max(1, round(5%·页数))（对局部异常页敏感，又不被单页主导）。

    注：这里的 t/s 是先验（语料标定，可再标），只读渲染层原始量；
    与同档语料的相对偏离由 A_profile 负责（shadow 模式，λ 默认 0）。
    无渲染信息时返回 0（与旧行为一致，报告里会标出视觉缺失）。
    """
    pages = ((getattr(per, "visual", None) or {}).get("pages")) or []
    pages = [p for p in pages
             if isinstance(p, dict) and "error" not in p
             and p.get("ink_ratio") is not None]
    if not pages:
        return 0.0
    k = max(1, int(round(0.05 * len(pages))))
    total = 0.0
    for metric, spec in SOFT_SPEC.items():
        if not spec.get("w"):
            continue                      # 暂缓/停用的指标不进分
        losses = [soft_metric_loss(metric, p.get(metric)) for p in pages]
        losses = [x for x in losses if x is not None]
        if not losses:
            continue
        losses.sort(reverse=True)
        top = sum(losses[:k]) / k
        mean = sum(losses) / len(losses)
        total += 0.5 * top + 0.5 * mean   # soft_metric_loss 已含权重 w
    return round(total, 3)


def page_defect_score(per: P.Perception, req: Requirement) -> float:
    """model1 · P：**页面缺陷分**（半硬性约束，越低越好）。

    组成：TeX/日志侧的行页缺陷、浮动体放置缺陷、源码卫生问题、
    以及渲染层里属于「结构/放置错误」的页面缺陷（内容孤立、空白页）。
    权重见 PAGE_DEFECT_WEIGHT / HYGIENE_WEIGHT / VISUAL_DEFECT_M1。
    """
    iss = per.issues
    w = PAGE_DEFECT_WEIGHT
    p = (w["overfull"] * len(iss["overfull"])
         + w["underfull"] * len(iss["underfull"])
         + w["vbox_over"] * sum(1 for v in iss["vbox"] if v["kind"] == "Overfull")
         + w["vbox_under"] * sum(1 for v in iss["vbox"] if v["kind"] == "Underfull")
         + w["floatwarn"] * len(iss["floats"])
         + w["tab_overwide"] * len(iss["tables_overwide"])
         + w["warn"] * len(iss.get("warnings", [])))
    p += w["fig_overwide"] * len(_overwide_figs(per, req))
    if req.enable_quality_macros and "texopt: 排版质量宏" not in per.src:
        p += w["macros_missing"]
    for fe in per.source.get("float_envs", []):
        spec = (fe.get("spec") or "").strip()
        if spec and actions._unstable_spec(spec):
            p += w["unstable_spec"]
        elif spec == "H":
            p += w["spec_H"]
    p += sum(HYGIENE_WEIGHT.get(h["kind"], DEFAULT_HYGIENE_WEIGHT)
             for h in per.issues.get("hygiene", []))
    for d in visual.visual_defects(getattr(per, "visual", None)):
        wt = VISUAL_DEFECT_M1.get(d.get("kind"))
        if wt:
            p += wt * visual.SEVERITY_FACTOR.get(d.get("severity"), 0.6)
    return round(p, 3)


def _as_body(s: str) -> str:
    """容忍两种入参：完整源码（含 \\begin{document}）或已被 content_body 抽出的正文。"""
    return content_body(s) if "\\begin{document}" in s else s


def _content_text(src_or_body: str, req=None) -> str:
    """内容面文本：抽正文 -> 扩展归一（排版命令可动面不计）-> 空白归一。"""
    b = _as_body(src_or_body)
    return "".join(_norm_body_ext(b, req).split())


def content_deviation(per: P.Perception, req: Requirement, orig_body: str) -> float:
    """D_content：正文偏差率（0 = 内容面完全一致，越大改动越多）。

    2026-10-14 用户指定：内容保留从 L 硬约束降级为软项，用于软性惩罚 +
    阶段报告 + 后续语义抛光阶段的「内容保留率下限 κ」约束。
    口径：内容面（_norm_body_ext 归一、空白折叠）字符多重集的
    **Jaccard 重合率** Keep = Σmin/Σmax，D = 1 - Keep（增删都计偏差）；
    排版命令可动面（浮动体参数/图宽/
ewpage/\noindent 等）不计。
    这是**改动幅度代理**，不是语义等价证明（与项目一贯的诚实边界一致）。
    """
    a = _content_text(per.src, req)
    b = _content_text(orig_body, req)
    if not a and not b:
        return 0.0
    ca, cb = Counter(a), Counter(b)
    inter = sum((ca & cb).values())
    union = sum((ca | cb).values())
    return round(max(0.0, 1.0 - (inter / union if union else 1.0)), 6)


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
    """完整评分（v4 结构，2026-10-30 起**两线分离**）：

        gate : 底层逻辑违规清单 + 结构化明细（空 = 可行，才进入打分）
        P    : model1 · 页面缺陷分
        I    : model1 · 整体修改情况（I_struct + β·D_content）
        M1   : model1 总分 = ρ·P + I
        A    : model2 · A_soft（软性审美）
        M2   : model2 总分 = A_soft + λ·A_profile（λ 由 shadow 侧给出）

    两条线**并行、不相加**：不再有 total。验收为严格字典序
    (gate, M1, M2)，M2 只在 M1 完全持平时作 tie-break。
    gate 未过时 scored=False —— M1/M2 仍算出来仅供诊断，**不参与任何判定**。
    """
    gd = gate_issues(per, req, content_body(orig.src), orig.source)
    gv = [d["text"] for d in gd]
    p = page_defect_score(per, req)
    istr = intervention_cost(per, orig)
    d = 0.0 if getattr(req, "content_hard", False) \
        else content_deviation(per, req, content_body(orig.src))
    i = round(istr + CONTENT_PENALTY * d, 3)
    m1 = round(W_PAGE_DEFECT * p + i, 3)
    a = aesthetic_score(per, req)          # model2 · A_soft
    m2 = a
    return {"l": gv, "gate": gd, "scored": not gv,
            "p": p, "i_struct": istr, "d_content": d, "i": i,
            "m1": m1, "a": a, "m2": m2, "ok": not gv,
            "content_preserved": d <= 0.0}


# 旧名兼容（2026-10-14 前的调用点/文档仍可用）
l_violations = gate_violations


def visual_defects(per: P.Perception) -> list:
    """当前文档的页面级视觉缺陷清单（无视觉信息时为空）。"""
    return visual.visual_defects(getattr(per, "visual", None))
