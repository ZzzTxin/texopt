#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""等边际收益标定表（ρ）—— 生成「缺陷 vs 干预代价」的 15 道二选一题。

背景（用户 2026-10-30/31 定义）：
    ρ 是**边际替代率**：在无差异点上
        「修 1 单位缺陷的质量收益」= 「省 1 单位干预代价的保真收益」
    因此 ρ 不能由「已发生的付费修复取中位数」估计（那是效率统计量），
    必须直接问出**人判的无差异点**。

题目构造（每题两页，同一篇论文、同一处内容，只差两件事）：
    A 页：缺陷保留，版心不动            （I = 0）
    B 页：缺陷修掉，页边距偏离 c mm      （I = 0.5·c）

    1 单位 I 的换算（与 score.intervention_cost 一致）：边距 0.5 / mm
        I = 0.5  → 边距 +1 mm
        I = 1.5  → 边距 +3 mm
        I = 3.0  → 边距 +6 mm

5 类缺陷 × 3 档代价 = 15 题。左右位置随机，页面不标 A/B。

用法：
    python3 tools/make_tradeoff_sheet.py --build      # 生成 sheet.html + key.json
    python3 tools/make_tradeoff_sheet.py --import answers.json   # 解出 ρ
"""

from __future__ import annotations

import argparse
import glob
import html as H
import json
import os
import random
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from texopt import engine, visual  # noqa: E402

BASE_TEX = None   # 由 PARAS 现场拼装（见 _base_doc），不再依赖 examples/demo.tex
WORK = os.path.join(ROOT, "workbench-tradeoff")
BUILD = os.path.join(WORK, "build")
SHEET = os.path.join(WORK, "sheet")

# 基准稿：同一批段落，缺陷插在中间，前后都有足够文字（保证两版都落在有内容的页上）
PARAS = [
 "Layout optimization for academic manuscripts is a constrained problem: the visual result "
 "of a document is a global property of the whole file, while most editing actions are local. "
 "A change that removes one bad line can push a float to the next page and create a much "
 "larger gap, so an optimizer must always recompile and re-evaluate the entire document "
 "before accepting an edit.",
 "The scoring model used here separates feasibility from quality. Feasibility asks whether "
 "the file compiles, whether the rendered PDF keeps the body text unchanged, and whether the "
 "requested hard constraints such as font size, margins and page limits are satisfied. "
 "Quality collects measurable layout defects that a reader can point at on the page.",
 "Intervention cost makes the optimizer conservative. Every edit that is applied to the "
 "source increases the intervention score, so a repair is only kept when the objective "
 "improves after a full recompilation. This is what prevents the system from grooming its "
 "own score with edits that no human would ever make.",
 "Perception is layered. The source layer parses the file and looks for patterns that are "
 "known to be unstable, such as manual page breaks, manual vertical spacing and float "
 "specifications that pin a float to its declaration point. The log layer reads the compiler "
 "log and counts overfull boxes, underfull boxes and badness warnings.",
 "The rendered layer measures the PDF itself. Page images give coverage statistics, the "
 "vertical position of ink, and the size of the largest empty band on each page. Those "
 "numbers are coarse on purpose: they are used as evidence that something looks wrong, not "
 "as a model of human taste.",
 "Float placement is the hardest part of the problem. A figure that is referenced in one "
 "paragraph may be typeset several pages later, and the quality of the page depends on "
 "whether the top, bottom and text fraction constraints of the float mechanism are balanced. "
 "Sanitising the float specification is a cheap first step.",
 "An optimizer that only looks at the source file is blind to the page. The same paragraph "
 "can end a page cleanly or leave a two-line orphan at the top of the next one, and nothing "
 "in the source distinguishes the two cases. Measurement therefore has to come from the "
 "rendered result, not from the intent of the edit.",
 "The visual evidence is deliberately coarse. Coverage, ink balance and the largest empty "
 "band are cheap to compute, hard to argue with, and stable across renderers. They will "
 "never describe taste, but they do describe the failures that readers complain about in "
 "review, which is the part of layout quality that can be measured without a human in the loop.",
 "A single page carries a limited amount of information. When a page is full, every "
 "additional element has to go somewhere: it either displaces text, changes the width of the "
 "text block, or moves to the next page and leaves a hole behind. Most layout defects are "
 "visible consequences of that competition for space.",
 "Readers are remarkably tolerant of dense pages and remarkably sensitive to broken ones. A "
 "line that sticks into the margin, a table that crosses the page boundary, or a half-empty "
 "page in the middle of a section will be noticed immediately, even by readers who could not "
 "say which rule was violated.",
]
LEAD_IN = (
    "The remainder of this page shows the construct under study. The paragraph immediately "
    "before it, and every paragraph after it, are identical in both versions of the page."
)

PARAS_AFTER = [
 "Quality macros are injected before any structural edit. Penalties for widows and orphans, "
 "limits on consecutive hyphenated lines and a small emergency stretch are enough to remove "
 "a large fraction of the visual defects that a raw manuscript shows, and they do not change "
 "a single character of the body text.",
 "Reporting matters as much as repair. Every run writes a machine readable trace and a human "
 "readable report. The report lists the residual problems that the system deliberately left "
 "alone, together with the reason, so that an author can decide whether to rewrite a "
 "sentence, move a figure or accept the page as it is.",
 "Determinism matters for reproducibility. Given the same source file, the same requirement "
 "specification and the same toolchain, the system produces the same trace of candidate "
 "actions, the same accept and rollback decisions, and the same final document. That is what "
 "makes an audit trail trustworthy rather than decorative.",
 "Page limits deserve special care. Compressing a document by shrinking its margins changes "
 "the relationship between floats and the text that refers to them, and the resulting layout "
 "often looks wrong even though every number in the report is legal. For that reason the "
 "default policy refuses to touch the global text block.",
 "The experiment reported here compares two kinds of cost. Leaving a visible defect in place "
 "costs quality, while repairing it by changing the shape of the text block costs fidelity "
 "to the author's original design. Neither cost is zero, and the exchange rate between them "
 "is exactly what the calibration below tries to measure.",
 "A calibration of this kind is only meaningful if both alternatives are real documents. The "
 "pages shown to the annotator therefore differ in exactly two respects: the defect is "
 "present or absent, and the text block is untouched or narrower. Everything else is fixed.",
]

MARGIN0 = 25.4                 # demo.tex 原始边距（mm）
MM_PER_I = 2.0                 # 边距 0.5/mm  -> 1 单位 I = 2mm
COSTS = [1.5, 3.0, 4.5]        # 单位：I（边距 +3/+6/+9mm）

# ---------------------------------------------------------------- 缺陷定义
# 每条：id / 名称 / 插在哪（唯一锚点）/ 缺陷版片段 / 修复版片段 / 期望的编译告警
DEFECTS = [
    dict(
        id="overfull", name="正文行溢出（右侧戳出版心）",
        defect=(
            "\\begin{sloppypar}\\noindent Identifier stress test: "
            "\\mbox{\\texttt{perceive\\_score\\_act\\_loop\\_with\\_global\\_"
            "recompilation\\_and\\_rollback\\_trajectory\\_audit\\_"
            "for\\_every\\_accepted\\_and\\_rejected\\_candidate\\_action}}"
            ".\\end{sloppypar}\n\n"
        ),
        fixed=(
            "\\begin{sloppypar}\\noindent Identifier stress test: "
            "\\texttt{perceive\\-score\\-act\\-loop\\-with\\-global\\-"
            "recompilation\\-and\\-rollback\\-trajectory\\-audit\\-"
            "for\\-every\\-accepted\\-and\\-rejected\\-candidate\\-action}"
            ".\\end{sloppypar}\n\n"
        ),
        probe="Identifier stress test",
        warn_re="Overfull \\\\hbox",
    ),
    dict(
        id="vspace", name="过大的手动垂直间距（页面中部空洞）",
        defect=(
            "\\vspace*{30mm}\n"
            "\\noindent The paragraph after an oversized manual vertical space.\n\n"
        ),
        fixed="\\noindent The paragraph after an oversized manual vertical space.\n\n",
        probe="oversized manual vertical space",
        warn_re=None,
    ),
    dict(
        id="widefig", name="图片超宽（宽于版心、戳出页边）",
        defect=(
            "\\noindent Figure~1 illustrates the measurement pipeline.\n\n"
            "\\noindent\\includegraphics[width=1.18\\linewidth]{example-image}\n\n"
        ),
        fixed=(
            "\\noindent Figure~1 illustrates the measurement pipeline.\n\n"
            "\\noindent\\includegraphics[width=\\linewidth]{example-image}\n\n"
        ),
        probe="illustrates the measurement pipeline",
        warn_re="Overfull \\\\hbox",
    ),
    dict(
        id="widetable", name="表格超宽（压出版心）",
        defect=(
            "\\noindent Table~1 compares the three scoring variants.\n\n"
            "\\noindent\\begin{tabular}{p{4.2cm}p{4.2cm}p{4.2cm}p{4.2cm}}\n\\hline\n"
            "Variant & Feasibility & Primary model & Quality model \\\\\n"
            "\\hline\n"
            "single total & folded into score & fused with cost & fused with cost \\\\\n"
            "gate first & hard reject & separate & separate \\\\\n"
            "\\hline\n\\end{tabular}\n\n"
        ),
        fixed=(
            "\\noindent Table~1 compares the three scoring variants.\n\n"
            "\\noindent\\begin{tabularx}{\\linewidth}{XXXX}\n\\hline\n"
            "Variant & Feasibility & Primary model & Quality model \\\\\n"
            "\\hline\n"
            "single total & folded into score & fused with cost & fused with cost \\\\\n"
            "gate first & hard reject & separate & separate \\\\\n"
            "\\hline\n\\end{tabularx}\n\n"
        ),
        probe="compares the three scoring variants",
        warn_re="Overfull \\\\hbox",
    ),
    dict(
        id="narrowtable", name="表格明显窄于版心（列被压扁）",
        defect=(
            "\\noindent Table~2 lists residual defects by frequency.\n\n"
            "\\noindent\\begin{tabular}{p{2.0cm}p{2.0cm}p{2.0cm}p{2.0cm}}\n\\hline\n"
            "Defect & Papers & Per page & Action \\\\\n\\hline\n"
            "overfull & 142 & 0.251 & fix width \\\\\n"
            "underfull & 147 & 0.585 & tolerance \\\\\n"
            "float warning & 94 & 0.101 & sanitise \\\\\n"
            "\\hline\n\\end{tabular}\n\n"
        ),
        fixed=(
            "\\noindent Table~2 lists residual defects by frequency.\n\n"
            "\\noindent\\begin{tabularx}{\\linewidth}{lXXX}\n\\hline\n"
            "Defect & Papers & Per page & Action \\\\\n\\hline\n"
            "overfull & 142 & 0.251 & fix width \\\\\n"
            "underfull & 147 & 0.585 & tolerance \\\\\n"
            "float warning & 94 & 0.101 & sanitise \\\\\n"
            "\\hline\n\\end{tabularx}\n\n"
        ),
        probe="lists residual defects by frequency",
        warn_re=None,
    ),
]

PREAMBLE = (
    "\\documentclass[10pt,a4paper]{{article}}\n"
    "\\usepackage[margin={margin}mm]{{geometry}}\n"
    "\\usepackage{{graphicx,booktabs,amsmath,amssymb}}\n"
    "\\usepackage[hidelinks]{{hyperref}}\n"
    "\\usepackage{{float,tabularx}}\n"
    "\\title{{A Manuscript Page Under Two Layout Choices}}\n"
    "\\author{{Sh Lab \\\\ Zhejiang University}}\n"
    "\\date{{}}\n"
    "\\begin{{document}}\n"
    "\\maketitle\n"
    "\\begin{{abstract}}\n"
    "This note is a calibration page. The paragraphs around the marked position are "
    "identical in every version; only one construct and the width of the text block change.\n"
    "\\end{{abstract}}\n"
    "\\section{{Introduction}}\n"
)


def _base_doc(margin_mm: float, snippet: str) -> str:
    """拼装基准稿：前 6 段 + 缺陷槽 + 后 6 段。"""
    body = PREAMBLE.format(margin=margin_mm)
    for p in PARAS:
        body += p + "\n\n"
    # 固定版式：缺陷区永远落在第 2 页（先强制换页 + 一段引导文字），
    # 这样 A/B 两版的对比页都是"有正文的第 2 页"，不会出现半空页。
    body += "\\clearpage\n\n"
    body += (LEAD_IN + "\n\n")
    body += snippet
    # 第 2 页要写满：缺陷之后的段落重复一轮（同一批文字，不影响对比）
    for p in PARAS_AFTER + PARAS_AFTER[:4]:
        body += p + "\n\n"
    body += "\\end{document}\n"
    return body


def _variant_src(snippet: str, margin_mm: float) -> str:
    return _base_doc(margin_mm, snippet)


def compile_variant(tag: str, src: str) -> dict:
    d = os.path.join(BUILD, tag)
    os.makedirs(d, exist_ok=True)
    tex = os.path.join(d, "main.tex")
    with open(tex, "w", encoding="utf-8") as f:
        f.write(src)
    res = engine.compile_tex(tex, passes=1, timeout=120)
    out = {"tag": tag, "ok": res.ok, "pdf": res.pdf_path, "log": res.log or "",
           "dir": d}
    if not res.ok:
        out["err"] = res.first_error
    return out


def _pdftotext() -> str | None:
    for pat in ("/mnt/c/texlive/*/bin/windows/pdftotext.exe",
                "/mnt/c/texlive/*/bin/*/pdftotext"):
        hit = sorted(glob.glob(pat))
        if hit:
            return hit[-1]
    return shutil.which("pdftotext")


def page_of(pdf: str, probe: str) -> int | None:
    """找到包含 probe 的页码（1 起）。"""
    tool = _pdftotext()
    if not tool:
        return None
    d = os.path.dirname(os.path.abspath(pdf))
    txt = os.path.join(d, "pages.txt")
    r = subprocess.run([tool, "-layout", os.path.basename(pdf), "pages.txt"],
                       cwd=d, capture_output=True)
    if r.returncode != 0 or not os.path.isfile(txt):
        return None
    pages = open(txt, encoding="utf-8", errors="replace").read().split("\f")
    for i, p in enumerate(pages, start=1):
        if probe in p:
            return i
    return None


def render_page(pdf: str, page: int, out_png_dir: str, name: str) -> str | None:
    files, err = visual.render_pages(pdf, out_png_dir, dpi=110, first=page, last=page)
    if err or not files:
        return None
    dst = os.path.join(out_png_dir, name + ".png")
    shutil.move(files[0], dst)
    return dst


def metrics_of(pdf: str, page: int) -> dict:
    """灰度页指标（用于自检：A 应比 B 更差）。"""
    tmp = os.path.join(os.path.dirname(pdf), "_gray")
    files, err = visual.render_gray(pdf, tmp, dpi=50, prefix="g")
    if err or not files or page > len(files):
        return {}
    try:
        return visual.page_metrics(files[page - 1])
    except Exception:
        return {}


def build() -> int:
    os.makedirs(SHEET, exist_ok=True)
    os.makedirs(BUILD, exist_ok=True)
    for d in (BUILD, SHEET):
        for p_ in glob.glob(os.path.join(d, "*")):
            shutil.rmtree(p_) if os.path.isdir(p_) else os.remove(p_)
    os.makedirs(SHEET, exist_ok=True)

    items, notes = [], []
    for dfx in DEFECTS:
        a = compile_variant(f"{dfx['id']}-A",
                            _variant_src(dfx["defect"], MARGIN0))
        if not a["ok"]:
            print(f"[跳过] {dfx['id']} A 编译失败：{a.get('err')}")
            continue
        pa = page_of(a["pdf"], dfx["probe"])
        if pa is None:
            print(f"[跳过] {dfx['id']} 找不到缺陷页")
            continue
        a_png = render_page(a["pdf"], pa, SHEET, f"{dfx['id']}-A")
        if not a_png:
            print(f"[跳过] {dfx['id']} A 渲染失败")
            continue
        ma = metrics_of(a["pdf"], pa)
        a_pages = engine.pdf_pages(a["pdf"])
        a_warn = len(re.findall(dfx["warn_re"], a["log"])) if dfx["warn_re"] else None
        notes.append({"defect": dfx["id"], "role": "A", "page": pa,
                      "pages": a_pages, "warn": a_warn,
                      "ink": round(ma.get("ink_ratio", 0), 4),
                      "bottom_blank": round(ma.get("bottom_blank", 0), 4),
                      "max_gap": round(ma.get("max_gap", 0), 4)})

        for cost in COSTS:
            mm = MARGIN0 + cost * MM_PER_I
            b = compile_variant(f"{dfx['id']}-B{cost}",
                                _variant_src(dfx["fixed"], mm))
            if not b["ok"]:
                print(f"[跳过] {dfx['id']}@{cost} B 编译失败：{b.get('err')}")
                continue
            pb = page_of(b["pdf"], dfx["probe"])
            if pb is None:
                print(f"[跳过] {dfx['id']}@{cost} 找不到对应页")
                continue
            b_png = render_page(b["pdf"], pb, SHEET, f"{dfx['id']}-B{cost}")
            if not b_png:
                continue
            mb = metrics_of(b["pdf"], pb)
            b_warn = len(re.findall(dfx["warn_re"], b["log"])) if dfx["warn_re"] else None
            notes.append({"defect": dfx["id"], "role": "B", "cost": cost,
                          "margin_mm": mm, "page": pb,
                          "pages": engine.pdf_pages(b["pdf"]), "warn": b_warn,
                          "ink": round(mb.get("ink_ratio", 0), 4),
                          "bottom_blank": round(mb.get("bottom_blank", 0), 4),
                          "max_gap": round(mb.get("max_gap", 0), 4)})

            left_is = "A" if random.random() < 0.5 else "B"
            items.append({
                "left": os.path.basename(a_png if left_is == "A" else b_png),
                "right": os.path.basename(b_png if left_is == "A" else a_png),
                "title": dfx["name"], "defect": dfx["id"], "defect_name": dfx["name"],
                "cost": cost, "margin_mm": mm, "left_is": left_is,
                "A": os.path.basename(a_png), "B": os.path.basename(b_png),
            })

    random.shuffle(items)
    cards, key = [], []
    for i, it in enumerate(items, start=1):
        cards.append({"q": i, "left": it["left"], "right": it["right"],
                      "title": it["title"]})
        key.append({"q": i, "defect": it["defect"], "defect_name": it["defect_name"],
                    "cost": it["cost"], "margin_mm": it["margin_mm"],
                    "left_is": it["left_is"], "A": it["A"], "B": it["B"]})

    with open(os.path.join(WORK, "key.json"), "w", encoding="utf-8") as f:
        json.dump({"schema": "texopt.tradeoff/v1", "margin0_mm": MARGIN0,
                   "mm_per_I": MM_PER_I, "costs": COSTS,
                   "questions": key, "variants": notes},
                  f, ensure_ascii=False, indent=2)
    with open(os.path.join(SHEET, "sheet.html"), "w", encoding="utf-8") as f:
        f.write(_html(cards))
    print(f"{len(cards)} 题 -> {os.path.join(SHEET, 'sheet.html')}")
    print(f"答案映射（不要给打分人）-> {os.path.join(WORK, 'key.json')}")

    # 自检：A 必须比 B 差（告警更多 / 空洞更大 / 密度更低），且页数不因代价而变
    for dfx in DEFECTS:
        a = next((n for n in notes if n["defect"] == dfx["id"] and n["role"] == "A"), None)
        if not a:
            continue
        for b in [n for n in notes if n["defect"] == dfx["id"] and n["role"] == "B"]:
            flags = []
            if a["warn"] is not None and b["warn"] is not None and a["warn"] <= b["warn"]:
                flags.append(f"告警 A={a['warn']} B={b['warn']}")
            if a["pages"] and b["pages"] and a["pages"] != b["pages"]:
                flags.append(f"页数 A={a['pages']} B={b['pages']}")
            if flags:
                print(f"[自检] {dfx['id']}@{b['cost']}: " + "；".join(flags))
    print("自检明细见 key.json.variants（ink / bottom_blank / max_gap）")
    return 0


def _html(cards: list[dict]) -> str:
    rows = []
    for c in cards:
        rows.append(f"""
  <div class="pair" id="q{c['q']}">
    <div class="ph">第 {c['q']} 题 / 共 {len(cards)} 题</div>
    <div class="two">
      <div class="side"><img src="{H.escape(c['left'])}"></div>
      <div class="side"><img src="{H.escape(c['right'])}"></div>
    </div>
    <div class="opts">
      <label><input type="radio" name="q{c['q']}" value="left">左页更好</label>
      <label><input type="radio" name="q{c['q']}" value="right">右页更好</label>
      <label><input type="radio" name="q{c['q']}" value="same">差不多（无差异）</label>
    </div>
  </div>""")
    return f"""<!doctype html><html lang="zh"><meta charset="utf-8">
<title>等边际收益标定（{len(cards)} 题）</title>
<style>
 body{{font-family:system-ui,sans-serif;margin:20px;background:#f6f6f7;color:#1d1d1f}}
 h1{{font-size:18px;margin:0 0 6px}}
 p.lead{{font-size:13px;color:#555;max-width:900px;line-height:1.6}}
 .pair{{background:#fff;border:1px solid #ddd;border-radius:10px;padding:10px;margin:14px 0}}
 .ph{{font-size:12px;color:#888;margin-bottom:6px}}
 .two{{display:grid;grid-template-columns:1fr 1fr;gap:8px}}
 .side{{background:#fafafa;border:1px solid #eee;padding:4px}}
 .side img{{width:100%;display:block}}
 .opts{{display:flex;gap:22px;margin-top:8px;font-size:14px}}
 .bar{{position:sticky;top:0;background:#fff;border:1px solid #ddd;border-radius:8px;
      padding:8px 10px;display:flex;align-items:center;gap:12px;z-index:9}}
 button{{padding:7px 14px;font-size:14px}}
 #prog{{font-size:13px;color:#444}}
</style>
<h1>等边际收益标定（ρ）：缺陷 vs 干预代价</h1>
<p class="lead">
每题左右是**同一篇论文的同一页**，只差两件事中的一个组合：一边是「缺陷还在、版心完全没动」，
另一边是「缺陷修掉了、但页边距被改宽了」。请只看版面判断：<b>哪一页整体更好看</b>？
<ul style="font-size:13px;color:#555;max-width:900px">
<li>缺陷常见的有：某一行戳出版心、页底一大片空白、图被钉死在段落中间、表格/图比版心宽。</li>
<li>另一边的代价是页边距变宽（版心变窄），这不违反规则，但和图表的对应关系、纸张利用率会变差。</li>
<li>如果两边看起来差不多、你分不出哪个更好，请选「差不多（无差异）」——这个答案最有价值，
  它直接告诉我们你的无差异点在哪里。</li>
<li>不用管内容、不用管字体、不用管是哪一页；拿不准就选「差不多」。</li>
</ul></p>
<div class="bar"><button onclick="exp()">导出答案</button>
  <span id="prog">已完成 0 / {len(cards)}</span><span id="msg"></span></div>
{''.join(rows)}
<script>
const N={len(cards)};
function picked(){{const o={{}};for(let i=1;i<=N;i++){{const e=document.querySelector('input[name="q'+i+'"]:checked');if(e)o[i]=e.value;}}return o;}}
function upd(){{document.getElementById('prog').textContent='已完成 '+Object.keys(picked()).length+' / '+N;}}
document.addEventListener('change',upd);upd();
function exp(){{
  const o=picked(),miss=[];for(let i=1;i<=N;i++)if(!o[i])miss.push('#'+i);
  if(miss.length){{document.getElementById('msg').textContent='还缺：'+miss.join(' ');return;}}
  const data={{ranker:'user',task:'rho_tradeoff',ts:new Date().toISOString(),
    answers:Object.keys(o).map(k=>({{q:+k,choice:o[k]}}))}};
  const blob=new Blob([JSON.stringify(data,null,2)],{{type:'application/json'}});
  const a=document.createElement('a');a.href=URL.createObjectURL(blob);
  a.download='answers.json';a.click();
  document.getElementById('msg').textContent='已导出 answers.json';
}}
</script></html>"""


# ---------------------------------------------------------------- 解 ρ

def import_answers(path: str) -> int:
    key = json.load(open(os.path.join(WORK, "key.json"), encoding="utf-8"))
    qs = {q["q"]: q for q in key["questions"]}
    ans = json.load(open(path, encoding="utf-8"))
    got = {int(a["q"]): a["choice"] for a in ans.get("answers", [])}

    # 统一成「修好版是否更好」：B 更好 = 1，A 更好 = 0，same = 0.5
    rows = []
    for qid, q in qs.items():
        ch = got.get(qid)
        if ch is None:
            continue
        if ch == "same":
            b = 0.5
        else:
            b = 1.0 if ((ch == "left") == (q["left_is"] == "B")) else 0.0
        rows.append({"q": qid, "defect": q["defect"], "cost": q["cost"], "b": b})

    out = {}
    for d in sorted({r["defect"] for r in rows}):
        pts = sorted([r for r in rows if r["defect"] == d], key=lambda r: r["cost"])
        # 无差异点：B 的胜率先降到 ≤0.5 的那一档（线性插值）
        rho = None
        prev = None
        for p in pts:
            if p["b"] <= 0.5:
                if prev is None or prev["b"] == p["b"]:
                    rho = p["cost"]
                else:
                    t = (prev["b"] - 0.5) / max(1e-9, prev["b"] - p["b"])
                    rho = prev["cost"] + t * (p["cost"] - prev["cost"])
                break
            prev = p
        if rho is None:
            rho = max(p["cost"] for p in pts)          # 一直偏好"修好"：取上界
        out[d] = {"points": [(p["cost"], p["b"]) for p in pts],
                  "rho": round(rho, 3)}

    vals = sorted(v["rho"] for v in out.values())
    med = vals[len(vals) // 2] if vals else None
    # I 单位 -> 边距 mm（便于人核对）
    report = {"schema": "texopt.rho_tradeoff/v1", "per_defect": out,
              "rho_median": med,
              "rho_median_margin_mm": None if med is None else round(med * MM_PER_I, 2),
              "n_answers": len(rows)}
    with open(os.path.join(WORK, "rho_estimate.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\n-> {os.path.join(WORK, 'rho_estimate.json')}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true", help="生成 15 题")
    ap.add_argument("--import", dest="imp", default=None, help="读 answers.json 解 ρ")
    a = ap.parse_args()
    if a.imp:
        return import_answers(a.imp)
    if a.build:
        return build()
    ap.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
