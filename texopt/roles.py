# -*- coding: utf-8 -*-
"""页面角色标注器（阶段 1）：把每页判为 title / section-head / body / math-heavy /
figure-page / table-page / references / appendix / last-page / unknown。

设计要点（对应设计方案第五章 5.1）：
  * **规则优先、可解释**：每个判定都带 `role_reason`，便于人工抽检与误差上报；
    阶段 2 若需要再叠加学习式分类器，但规则结果永远是兜底。
  * 只依赖**页级信号**（由 `extract.py` 从 PDF 文本行/图框算出），不依赖像素层，
    因此同一份信号可以离线复算、可复现。
  * `role` 是**单一主标签**；正交信息（是否末页/是否章节起始页/是否整页浮动）
    放在 `role_flags` 里，避免主标签把互相独立的属性压成一个枚举。
  * 参考文献/附录是**跨页状态**：一旦出现 References 标题，其后各页都算 references，
    直到出现 Appendix 标题转 appendix。状态机在 `classify_pages()` 里。

阈值（THRESH）为阶段 1 初值，来源是"明显如此/明显不是"的粗档；阶段 2 拿到 608 篇
的分布后再校准，并在报告中记录校准前后差异。
"""
from __future__ import annotations

import re

# 主标签判定优先级（先命中者胜）
#
# 2026-09-28 阶段 2 校准：把整页图/表提到**参考文献/附录之前**。理由：
#   * 角色的作用是让"同类可比"。整页图/表的密度、重心与文字页完全不可比；
#   * 而"这是参考文献页/附录页"的结构信息不丢——落在 `role_flags` 的
#     `in-references` / `in-appendix` 上（状态照样继续传递）。
#   实测：旧优先级下全库只判出 3 页 figure-page（大量整页图落在附录里被吞）。
ROLE_PRIORITY = ("title", "figure-page", "table-page", "references", "appendix",
                 "math-heavy", "section-head", "last-page", "body", "unknown")

# 阈值来自 608 篇 / 10538 页的**实测分布**（见 docs/stage2_profile.md）：
#   coverage_figure 的 P95 = 0.36；coverage_table 的 P99 = 0.16；
#   同时要求正文覆盖 < 0.30（整页图页的文字应该明显偏少）。
# 之前的拍脑袋值（0.50 / 0.40）分别落在 P99 / P99.5 之外，导致几乎不触发。
THRESH = {
    "fig_page_cov": 0.36,
    "fig_page_text": 0.30,
    "tab_page_cov": 0.16,
    "math_ratio": 0.35,
    "head_top_frac": 0.30,      # 章节标题位于版心顶部 30% 内 → section-head
}

REFERENCES_RE = None          # 见 detect_headings()（避免 import re 时机问题）
APPENDIX_RE = None


REFERENCES_RE = re.compile(r"^\s*(?:\d+\.?\s*)?(references|bibliography|"
                           r"参考文献)\s*$", re.I)
APPENDIX_RE = re.compile(
    r"^\s*(appendix|appendices|supplementary|supplemental|"
    r"supporting\s+information|附录)\b(?:(?-i:\s*[A-Z0-9:.\-])|\s*$)", re.I)
SECTION_RE = re.compile(
    r"^(?:\d+(?:\.\d+)*\.?\s+\S"                     # 1 / 1.2 / 3.4.5
    r"|[IVX]+\.\s+\S"                                 # I. / II.
    r"|[A-Z]\.\s+\S"                                  # A. （附录小节）
    r"|(abstract|introduction|related\s+work|background|preliminaries"
    r"|method(?:s|ology)?|approach|experiments?|evaluation|results?"
    r"|analysis|discussion|conclusions?|limitations|future\s+work"
    r"|acknowledge?ments?|contributions?)\b)", re.I)


def norm_head(t: str) -> str:
    """标题文本归一（去页码/编号噪声、压缩空白）。"""
    return " ".join((t or "").split()).strip(" .·•—-")


def is_references_head(text: str) -> bool:
    return bool(REFERENCES_RE.match(norm_head(text)))


def is_appendix_head(text: str) -> bool:
    return bool(APPENDIX_RE.match(norm_head(text)))


def is_section_head(text: str, *, size: float, body_pt: float,
                    bold: bool, col_width_pt: float | None) -> bool:
    """章节标题判定：短、比正文大（或加粗）、且形如编号标题/常见标题词。

    标题样式在会议间差异大，所以只用"弱证据组合"：字号或加粗任一成立，
    再叠加"短 + 无句末标点"这条硬约束。
    """
    s = norm_head(text)
    if not s or len(s) > 90 or s.endswith((".", "。", ",", "，")):
        return False
    big = col_width_pt is not None and len(s) * size * 0.5 > col_width_pt
    if big and len(s) > 60:
        return False
    style = (size >= body_pt + 0.4) or bold
    return bool(style and SECTION_RE.match(s))


def classify_page(sig: dict, state: dict) -> dict:
    """单页判定。state 是跨页状态（refs/appendix 是否已开始），就地更新。"""
    role, conf, reason = "body", 0.5, "默认：普通正文页"
    flags: list[str] = []

    n_lines = sig.get("n_lines") or 0
    n_chars = sig.get("n_chars") or 0
    if n_lines == 0 and n_chars == 0:
        return {"role": "unknown", "role_confidence": 0.9,
                "role_reason": "无可抽取文本（扫描页/整页图/空白页）",
                "role_flags": []}

    if sig.get("is_last"):
        flags.append("last-page")
    if sig.get("section_head"):
        flags.append("section-start")
    if (sig.get("fig_coverage") or 0) + (sig.get("tab_coverage") or 0) >= 0.5:
        flags.append("float-dominated")
    if sig.get("refs_heading"):
        state["refs"] = True
    if sig.get("appendix_heading"):
        state["appendix"] = True
        state["refs"] = False
    if state.get("appendix"):
        flags.append("in-appendix")
    elif state.get("refs"):
        flags.append("in-references")

    # ---- 判定：先看整页浮动，再看结构状态，最后看内容形态
    fig_cov = sig.get("fig_coverage") or 0.0
    tab_cov = sig.get("tab_coverage") or 0.0
    txt_cov = sig.get("text_coverage") or 0.0
    math_r = sig.get("math_ratio") or 0.0
    if sig.get("is_first"):
        role, conf, reason = "title", 0.95, "第 1 页（标题/摘要/作者）"
    elif fig_cov >= THRESH["fig_page_cov"] and txt_cov < THRESH["fig_page_text"]:
        role, conf = "figure-page", 0.75
        reason = (f"浮动体覆盖 {fig_cov:.0%} 版心、正文仅 {txt_cov:.0%}（整页/近整页图）"
                  + ("；位于" + ("附录" if state.get("appendix") else "参考文献")
                     if state.get("appendix") or state.get("refs") else ""))
    elif tab_cov >= THRESH["tab_page_cov"]:
        role, conf = "table-page", 0.7
        reason = f"表格覆盖 {tab_cov:.0%} 版心（表格主导页）"
    elif state.get("appendix"):
        role, conf = "appendix", 0.85
        reason = ("附录区（自出现 Appendix/Supplementary 标题起）"
                  if not sig.get("appendix_heading") else "本页出现附录标题")
    elif state.get("refs"):
        role, conf = "references", 0.85
        reason = ("参考文献区（自出现 References 标题起）"
                  if not sig.get("refs_heading") else "本页出现参考文献标题")
    elif math_r >= THRESH["math_ratio"]:
        role, conf = "math-heavy", 0.6
        reason = f"数学字形占比 {math_r:.0%}（公式密集页）"
    elif sig.get("section_head"):
        role, conf = "section-head", 0.6
        reason = f"章节标题位于版心顶部（{str(sig.get('section_head_text') or '')[:24]}）"
    elif sig.get("is_last"):
        role, conf, reason = "last-page", 0.5, "正文最后一页且无更强结构信号"
    else:
        role, conf, reason = "body", 0.5, "默认：普通正文页"
    return {"role": role, "role_confidence": conf, "role_reason": reason,
            "role_flags": flags}


def classify_pages(signals: list[dict]) -> list[dict]:
    """按顺序标注整篇（含跨页状态）。signals 见 extract.page_signals()。"""
    state: dict = {"refs": False, "appendix": False}
    out = []
    for sig in signals:
        r = classify_page(sig, state)
        r["page"] = sig.get("page")
        out.append(r)
    return out


def hist(roles: list[dict]) -> dict:
    h: dict = {}
    for r in roles:
        h[r["role"]] = h.get(r["role"], 0) + 1
    return h
