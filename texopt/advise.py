# -*- coding: utf-8 -*-
"""建议层：把闭环修不干净的问题转成结构化建议，供「模型在环」消费。

定位（2026-09-09，参考 workspace-latex-mcp 的模型在环形态）：
  texopt 确定性闭环能自动修白名单内的排版问题；其余问题（卫生类、
  结构类、语义类）涉及作者意图或内容理解，交给 LLM 逐条决策执行。
  本模块为每条残余问题生成：
    id / line / kind / severity / issue / suggestion / edit_hint
  其中 edit_hint 给出可直接落地的 TeX 改法示例（模型照做即可）。

severity 分级：
    cosmetic   —— 纯外观/规范，改动零风险或极低
    moderate   —— 可能影响上下文观感，需模型看上下文决定
    content    —— 涉及内容理解/增删（如补题注、超宽表改列），
                  模型必须谨慎并遵守内容红线
"""
from __future__ import annotations

import re

from . import perceive as P, score as S
from .requirements import Requirement

SEVERITY = {"cosmetic": 0, "moderate": 1, "content": 2}

# 每条残余问题可关联的白名单动作（供 LLM 把「问题」直接映射为「可执行提案」）。
# 为空 = 该问题需内容/作者决策，不在程序可执行白名单内。
SUGGESTED_ACTIONS = {
    "manual_pagebreak": ["remove_manual_pagebreak"],
    "manual_vspace": ["remove_excessive_vspace"],
    "underline_abuse": [],
    "noindent": [],
    "size_switch": ["normalize_local_font_size"],
    "heading_size": ["normalize_heading_size"],
    "list_spacing": ["reduce_list_spacing"],
    "hard_linebreak": [],
    "center_text": [],
    "missing_caption": [],
    "unbreakable": ["add_hyphenation_points"],
    "long_url": ["break_long_urls", "add_hyphenation_points"],
    "title_size": ["normalize_title"],
    "parskip": ["normalize_parskip"],
    "header_abnormal": ["normalize_header"],
    "multicols_mid": ["remove_mid_multicols"],
    "fig_oversized": ["reduce_oversized_figures", "set_fig_width"],
    "subfig_overfull": ["reduce_oversized_figures"],
    "table_narrow": ["fix_table_width"],
    "dollar_math": [],
    "overfull_hbox": ["normalize_fig_width", "set_fig_width",
                      "add_hyphenation_points", "fix_table_width",
                      "sanitize_float_specs"],
    "page_break_quality": ["sanitize_float_specs", "set_float_spec",
                           "balance_pages"],
    "table_overwide": ["fix_table_width"],
    "reading_aid": ["strip_reading_aids"],
    "warning_box": ["remove_warning_boxes"],
    "missing_toc": ["insert_toc"],
    "missing_header": ["add_header"],
    "heading_plain": ["color_headings"],
    "page_limit": [],
    "figure_unpreserved": [],
}

# kind -> (severity, 通用建议模板)  ；行号/细节动态拼
HYGIENE_ADVICE = {
    "dollar_math": ("cosmetic",
                    "裸 $$..$$ 数学应使用 \\[\\] 或 equation 环境；闭环已自动修复，如仍存在说明成对异常，请人工检查"),
    "manual_pagebreak": ("cosmetic",
                         "删除该处手动分页（\\newpage/\\clearpage），让浮动体与断页交给 LaTeX 全局最优放置；若删除后某图表位置明显变差，再考虑用浮动体参数而非硬分页"),
    "manual_vspace": ("cosmetic",
                      "删除或收敛该处手动垂直间距；若确需段落间距，应在 preamble 统一定义 \\parskip 而不是逐处 \\vspace"),
    "underline_abuse": ("cosmetic",
                        "\\underline 在投稿中通常禁用；若意在强调请改 \\emph{...}，若只是下划线装饰请删除"),
    "noindent": ("cosmetic",
                 "删除该 \\noindent，让段落缩进交给文档全局样式（除非紧跟在定理类环境后需抑制缩进）"),
    "size_switch": ("moderate",
                    "行内字号切换通常是手工模拟结构层次；若它本意是标题/小标题，请改用 \\section/\\subsection 等语义结构，否则删除（闭环已自动删除正文行内字号乱标，如仍存在说明它在数学/表格等保护区）"),
    "heading_size": ("cosmetic",
                     "标题字号超出层级上限（section ≤ \\Large、subsection ≤ \\large、"
                     "subsubsection ≤ \\normalsize）；建议把标题层级交给文档类或 "
                     "titlesec 统一定义（闭环已自动把超限字号压回上限）"),
    "list_spacing": ("cosmetic",
                     "列表的 itemsep/topsep/parsep/partopsep 过大，会打乱页面密度节奏；"
                     "建议删除这些选项、回到文档类默认间距（闭环已自动收紧）"),
    "hard_linebreak": ("moderate",
                       "行尾 \\\\ 硬换行会破坏 Knuth–Plass 断行优化；把这几行合并成自然段落（删掉 \\\\，让文字自然回流），除非是诗歌/地址等必须换行的内容"),
    "center_text": ("moderate",
                    "center 环境包裹了整段正文；请去掉 \\begin{center}/\\end{center} 使其成为普通左对齐段落（center 只用于图/表内部）"),
    "missing_caption": ("content",
                        "该浮动体缺 \\caption：请根据图表内容补一句题注（figure 用 'Figure N: ...' 形式由 \\caption 自动编号），注意不要改动图表本身内容"),
    "long_url": ("cosmetic",
                 "超长 URL 默认断行点少，容易顶出版心；建议用 \\url{} 包裹并加载 "
                 "xurl 允许任意位置断行（闭环已自动注入 xurl），不要手工拆 URL 文字"),
    "title_size": ("cosmetic",
                   "文档标题字号超出层级上限；标题字号应交给文档类"
                   "（闭环已自动压回上限）"),
    "parskip": ("moderate",
                "\\parskip 过大（整篇段距）——每页都会显得松散、留白偏多；"
                "建议收敛到 ≤ 8pt 或交给文档类默认（闭环已自动收敛）"),
    "header_abnormal": ("cosmetic",
                        "页眉内容过长/无信息价值（挤占版心且不美观）；"
                        "建议只保留短标题或页码（闭环已自动清空过长部分）"),
    "multicols_mid": ("moderate",
                      "正文中途切换双栏会打断版面节奏（栏宽骤变、图表错位）；"
                      "若非必要建议移除（闭环已自动移除，内容保留）"),
    "fig_oversized": ("moderate",
                      "图片高度占页高比例过大，会把整页撑成“图占满”的版面；"
                      "建议压到 ≤ 40% 版心高（闭环已自动收敛）"),
    "subfig_overfull": ("moderate",
                        "并排子图宽度之和超过版心（含间距），容易被挤成畸形行；"
                        "建议等比缩小（闭环已自动等比缩放）"),
    "table_narrow": ("moderate",
                     "表格列宽合计明显小于版心，页面留白突兀；建议改用 "
                     "tabularx 自适应列宽（闭环已自动改用 tabularx）"),
    "unbreakable": ("moderate",
                    "超长不可断词造成溢出；可在合适位置插入断词点（URL 用 \\url 或 \\path 宏包），或改写为可断行的表述"),
    "reading_aid": ("cosmetic",
                    "该行是阅读辅助/校对提示（如 START READING HERE），不属于论文正文；要求开启 strip_reading_aids 时闭环自动删除，如仍存在请手工删除"),
    "warning_box": ("cosmetic",
                    "WARNING/CAUTION/ATTENTION 类告示块属编辑性提示，非论文正文；要求开启 remove_warning_boxes 时闭环自动删除"),
}


def _line_text(src: str, line: int) -> str:
    lines = src.split("\n")
    return lines[line - 1].strip() if 0 < line <= len(lines) else ""


def build_advisory(orig_src: str, per: P.Perception,
                   req: Requirement) -> list[dict]:
    """生成残余问题建议清单（按 severity 排序）。"""
    out: list[dict] = []
    iss = per.issues

    def add(kind: str, line: int, issue: str, suggestion: str,
            severity: str, hint: str = "", location: str = ""):
        out.append({
            "id": f"{kind}-{line}",
            "kind": kind, "line": line, "severity": severity,
            "location": location,
            "issue": issue, "suggestion": suggestion, "edit_hint": hint,
            "suggested_actions": SUGGESTED_ACTIONS.get(kind, []),
            "source_line": _line_text(per.src, line),
        })

    # 1) 卫生类（源码静态检测，line 精确）
    for h in iss.get("hygiene", []):
        kind = h["kind"]
        sev, tmpl = HYGIENE_ADVICE.get(kind, ("cosmetic", "人工复核该行"))
        add(kind, h["line"], h["detail"], tmpl, sev)

    # 2) 表格超宽（content：改法涉及列格式/内容布局）
    for t in iss.get("tables_overwide", []):
        add("table_overwide", t.get("line", 0),
            f"表格超宽 {t['detail']}（第 {t.get('lines')} 行）",
            "超宽表需要结构性处理：改用 tabularx/tabular* 让列宽按 \\textwidth "
            "自适应、缩短表头/单元格文本，或把表格拆分为两段（带重复表头）。"
            "任何修改都不得改变数据与含义。",
            "content")

    # 3) 正文溢出（overfull 常在长词/长 URL/公式行）
    for o in iss.get("overfull", [])[:10]:
        add("overfull_hbox", o.get("line", 0),
            f"正文行溢出 {o['detail']}（第 {o.get('lines')} 行）",
            "定位到该行的长词/长公式：允许断词（插入 \\- 或 hyphenat 规则）、"
            "把长 URL 换 \\url{...}、或轻微改写该句（保义）让断行点更多。",
            "moderate")

    # 4) 页面垂直质量（vbox，孤行寡行代理）
    for v in iss.get("vbox", [])[:10]:
        add("page_break_quality", 0,
            f"{v['kind']} vbox（badness {v['detail']}）——页面断点质量/孤行寡行代理信号",
            "在该页附近微调：给前一段末尾换词（避免孤行）或调整浮动体位置；"
            "注意每步都重新编译验证全局分，不要顾此失彼。",
            "moderate")

    # 5) L 未达标（超页等）→ 语义层兜底建议
    lv = S.l_violations(per, req, S.content_body(orig_src),
                        P.parse_source(orig_src))
    # 模型在环阶段：若正文语义保留（仅排版命令级变化），"正文内容被改动"
    # 项不构成违规，不进入建议清单
    if S.semantic_diff(orig_src, per.src, req)["preserved"]:
        lv = [v for v in lv if "正文内容被改动" not in v]
    for v in lv:
        if "页数" in v:
            add("page_limit", 0, v,
                "纯排版手段已穷尽仍超页。可选：① 作者精简（删除冗余句/合并段落，"
                "保义）；② 压缩合并图表（两图并排/删次要子图）；③ 语义保意缩行"
                "（SRTP 第三期 LLM 能力）。此步必须经用户确认，Agent 不擅自删内容。",
                "content")
        else:
            add("l_violation", 0, v, "该硬约束项需要人工介入（见 issue）。",
                "content")

    # 6) 结构规范（目录/页眉/标题着色）——要求未落实时给建议
    if req.toc and not per.source.get("has_toc") \
            and per.source.get("sections", 0) >= req.toc_min_sections:
        add("missing_toc", 0, "缺少目录页（要求 toc）",
            "在正文首节前插入 \\tableofcontents（可配 \\newpage 使目录单独成页）。",
            "cosmetic", "\\tableofcontents\n\\newpage")
    if req.running_header and not per.source.get("has_header"):
        add("missing_header", 0, "缺少页眉（要求 running_header）",
            "引入 fancyhdr，设置 \\pagestyle{fancy} 与 \\fancyhead[L/R]{...}。",
            "cosmetic",
            "\\usepackage{fancyhdr}\\pagestyle{fancy}"
            "\\fancyhead[L]{短标题}\\fancyhead[R]{\\thepage}")
    if req.heading_color and not per.source.get("has_heading_color"):
        add("heading_plain", 0, "标题未着色（要求 heading_color）",
            "用 sectsty 给 \\section/\\subsection 标题着色，以颜色建立层级突出；"
            "若已用 titlesec 请在 \\titleformat 里加 \\color。",
            "cosmetic",
            "\\usepackage{sectsty}\\sectionfont{\\color{texopthead}}")

    # 7) 图形保真（图不得重绘/改写；多源判断的图像层底线）
    for v in lv:
        if "图形/表格内容被改动" in v:
            add("figure_unpreserved", 0, v,
                "图不得重绘或改写：应从原 PDF 裁切原图原样嵌入（保留原作者作图），"
                "不要用 TikZ 重画，也不得换算/重标轴。",
                "content",
                "python3 optimize.py --extract-fig 原稿.pdf "
                "--page 3 --box x0,y0,x1,y1 --out figs/fig1.png")

    # 4) 排序：severity 升序（cosmetic 先做，风险低）
    out.sort(key=lambda x: (SEVERITY[x["severity"]], x["line"]))
    # 去重（同 kind+line 只留一条；table_overwide 与 hygiene 无重叠，安全）
    seen, dedup = set(), []
    for item in out:
        key = (item["kind"], item["line"])
        if key in seen:
            continue
        seen.add(key)
        dedup.append(item)
    return dedup


def summary_lines(advisory: list[dict]) -> list[str]:
    """人读摘要（模型在环汇报用）。"""
    lines = []
    for it in advisory:
        hint = f"  改法示例：{it['edit_hint']}" if it["edit_hint"] else ""
        loc = f"（第 {it['line']} 行）" if it["line"] else ""
        lines.append(f"[{it['severity']}] {it['kind']}{loc}: {it['issue']}")
        lines.append(f"  建议：{it['suggestion']}")
        if hint:
            lines.append(hint)
    return lines
