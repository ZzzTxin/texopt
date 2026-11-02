#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P 权重统一标定表：把「人眼可判的缺陷」全部换成同一把尺子（边距 mm）。

背景（2026-11-01）：
    ρ 已经用无差异点钉住（15），但 P 的内部结构还是两张皮：
      * 5 项来自「人判严重度 ÷ 语料频率」（overfull / underfull / vbox_over / floatwarn / tab_overwide）
      * 其余是**先验拍值**（vbox_under / fig_overwide / spec_H / warn / macros_missing / unstable_spec）
    第一轮 ρ 标定的 per-defect 汇率（overfull ≈ 32–38、widetable ≈ 5–7，中位 15）说明
    这套结构确实偏了：overfull 的权重偏低约 2×，tab_overwide 偏高约 2.5×。

方法（与 ρ 标定同一套机制，只是反过来用）：
    对每个缺陷单独问「缺陷保留 vs 缺陷修掉 + 页边距 +c mm」，求出无差异点 c*。
    在等边际收益口径下，若所有缺陷共用同一个 ρ，则应有
        w_i = c*_i / ρ
    ——即「留 1 个该缺陷」正好等于「人愿意付出的边距代价」。这就是本表要回填的权重。

题目（12 题 + 2 道空题 = 14 题）：
    * 4 类缺陷 × 2 档代价（边距 +16mm / +30mm，I = 8 / 15）：underfull 松弛行、
      vbox_under 页底大片留白、vbox_over 文字压进下边距、spec_H 浮动体钉死留洞
    * 2 题边界复核：overfull（I ≈ 12.5）、widetable（I ≈ 8）用第二轮 c* 附近复测
    * 2 题空题（左右同页）：测注意力/位置偏差

构造说明（2026-11-02 补齐 vbox_over / spec_H）：
    * vbox_over：整页文字 + \enlargethispage{20mm}，末几行压进 25.4mm 的下边距
      （墨迹剖面 last≈0.964，版心底 0.914）。语料里的 Overfull \vbox 多数由此类
      「多塞一行」造成；该构造**不产生日志告警**，warn_re=None。
    * spec_H：8 段文字后接 figure[H]（高 0.45\textheight，本页放不下 → 整页留洞 41%），
      修法同内容改 [tbp]（浮动体走开、文字填满，洞消失）。同样无日志告警。

用法：
    python3 tools/make_pweight_sheet.py --build
    python3 tools/make_pweight_sheet.py --import answers.json
"""

from __future__ import annotations

import argparse
import json
import os
import random
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import make_tradeoff_sheet as T  # noqa: E402  复用编译/定位/渲染/HTML
from texopt import engine, visual  # noqa: E402

WORK = os.path.join(ROOT, "workbench-pweight")
BUILD = os.path.join(WORK, "build")
SHEET = os.path.join(WORK, "sheet")
MARGIN0 = T.MARGIN0
MM_PER_I = T.MM_PER_I
COSTS = [8.0, 15.0]            # 单位 I（边距 +16 / +30 mm）

# 与 texopt/score.PAGE_DEFECT_WEIGHT 的键一一对应
# 设计要点（2026-11-01 修）：
#   1) 货币只动左右边距：top/bottom 固定 25.4mm，否则页数会随代价漂移，A/B 不可比；
#   2) lead 句两版完全一样（含 probe），只有细节构造不同；
#   3) probe 不使用 ~（pdftotext 里 ~ 渲染成空格，会导致匹配失败）。
PREAMBLE = (
    "\\documentclass[10pt,a4paper]{{article}}\n"
    "\\usepackage[top=25.4mm,bottom=25.4mm,left={margin}mm,right={margin}mm]{{geometry}}\n"
    "\\usepackage{{graphicx,booktabs,amsmath,amssymb}}\n"
    "\\usepackage[hidelinks]{{hyperref}}\n"
    "\\usepackage{{float,tabularx}}\n"
    "\\title{{A Manuscript Page Under Two Layout Choices}}\n"
    "\\author{{Sh Lab \\\\ Zhejiang University}}\n"
    "\\date{{}}\n"
    "\\begin{{document}}\n\\sloppy\n"
    "\\maketitle\n"
    "\\begin{{abstract}}\n"
    "This note is a calibration page. The paragraphs around the marked position are "
    "identical in every version; only one construct and the width of the text block change.\n"
    "\\end{{abstract}}\n"
    "\\section{{Introduction}}\n"
)

PROBE = {
    "underfull": "Line looseness is measured on this page",
    "vbox_under": "The closing remark of this section is typeset here",
    "floatwarn": "A large figure is declared at this point in the text",
    "vbox_over": "Spill into the bottom margin is measured on this page",
    "spec_H": "Pinned float placement is measured on this page",
    "overfull": "Identifier stress test",
    "widetable": "compares the three scoring variants",
}

FILLER = [
    "The first remark closes the paragraph that precedes the construct, and it is identical "
    "in both versions of the page.",
    "The second remark keeps the page from ending immediately after the construct, so the "
    "comparison stays on a page that carries real text.",
    "The third remark is short on purpose; the point of the page is the construct, not the "
    "length of the surrounding prose.",
]


def _paras(n: int, start: int = 0) -> str:
    """拿 n 段真文章（PARAS_AFTER 循环），两侧内容完全一致。"""
    ps = T.PARAS_AFTER
    return "".join("\\noindent " + ps[(start + i) % len(ps)] + "\n\n" for i in range(n))


SPEC_H_CAPTION = "A pinned float that cannot fit the remaining space."
SPEC_H_FIG = ("\\begin{figure}[{spec}]\\centering"
               "\\rule{0.8\\linewidth}{0.45\\textheight}"
               "\\caption{" + SPEC_H_CAPTION + "}\\end{figure}\n\n")


def _spec_fig(spec: str) -> str:
    return SPEC_H_FIG.replace("{spec}", spec)

DEFECTS = [
    dict(
        id="underfull", key="underfull", name="正文行欠满（字距被拉得很松）",
        # \hbox to \linewidth 是唯一能稳定逼出「Underfull \hbox (badness 10000)」的写法：
        # 行内文字不足又没有 \hfil 吸收余量，空格被拉开到整行宽。
        defect=("\\noindent " + PROBE["underfull"] + ".\n\n"
                "\\noindent\\hbox to \\linewidth{The line is stretched across the whole "
                "measure, with enormous gaps between the words.}\n\n"),
        fixed=("\\noindent " + PROBE["underfull"] + ".\n\n"
               "\\noindent The line is stretched across the whole measure, with enormous "
               "gaps between the words.\n\n"),
        probe=PROBE["underfull"],
        warn_re="Underfull \\\\hbox",
    ),
    dict(
        id="vbox_under", key="vbox_under", name="页底大片留白（正文提前收尾）",
        # 留小半页而不是整页空白：太干净会变成 near_empty（另一个 P 项），不是要测的东西
        defect=("\\noindent " + PROBE["vbox_under"] + ".\n\n"
                "\\noindent " + FILLER[0] + "\n\n"
"\\noindent " + T.PARAS_AFTER[0] + "\n\n"
                "\\noindent " + T.PARAS_AFTER[1] + "\n\n"
                "\\noindent " + T.PARAS_AFTER[2] + "\n\n"
                "\\noindent " + T.PARAS_AFTER[3] + "\n\n"
                "\\noindent " + T.PARAS_AFTER[4] + "\n\n"
                                "\\newpage\n\n"
                "\\noindent " + FILLER[2] + "\n\n"),
        fixed=("\\noindent " + PROBE["vbox_under"] + ".\n\n"
               "\\noindent " + FILLER[0] + "\n\n"
"\\noindent " + T.PARAS_AFTER[0] + "\n\n"
               "\\noindent " + T.PARAS_AFTER[1] + "\n\n"
               "\\noindent " + T.PARAS_AFTER[2] + "\n\n"
               "\\noindent " + T.PARAS_AFTER[3] + "\n\n"
               "\\noindent " + T.PARAS_AFTER[4] + "\n\n"
                              "\\noindent " + FILLER[2] + "\n\n"),
        probe=PROBE["vbox_under"],
        warn_re=None,
    ),
    dict(
        id="floatwarn", key="floatwarn", name="浮动体过大被推到别处（页面留大洞）",
        defect=("\\noindent " + PROBE["floatwarn"] + ".\n\n"
                "\\begin{figure}[tbp]\\centering\n"
                "\\rule{0.9\\linewidth}{1.05\\textheight}\n"
                "\\caption{An oversized float that no page can hold.}\n"
                "\\end{figure}\n\n"),
        fixed=("\\noindent " + PROBE["floatwarn"] + ".\n\n"
               "\\begin{figure}[tbp]\\centering\n"
               "\\rule{0.9\\linewidth}{0.4\\textheight}\n"
               "\\caption{A float that fits the page.}\n"
               "\\end{figure}\n\n"),
        probe=PROBE["floatwarn"],
        warn_re="Float too large",
    ),
    # ---- vbox_over：整页文字 + \enlargethispage，末几行压进 25.4mm 下边距
    # 语料里的 Overfull \vbox 大多就是「本页多塞了一两行」，用 \enlargethispage 是
    # 最忠实的复现：版心底 0.914，A 版墨迹到 0.964（≈15mm 进下边距）。
    # B 版只拿掉 \enlargethispage（纯排版修复，不动内容）。
    # 注意：该构造不产生日志告警，warn_re=None，不参与告警自检。
    dict(
        id="vbox_over", key="vbox_over", name="文字压进下边距（页面垂直溢出）",
        defect=("\\noindent " + PROBE["vbox_over"] + ".\n\n"
                "\\enlargethispage{20mm}\n\n" + _paras(10)),
        fixed=("\\noindent " + PROBE["vbox_over"] + ".\n\n" + _paras(10)),
        probe=PROBE["vbox_over"],
        warn_re=None,
    ),
    # ---- spec_H：8 段文字后钉一张放不下的图 → 本页留 41% 的洞
    # 修法同内容换 [tbp]：浮动体走开，文字填满本页，洞消失。同样无日志告警。
    dict(
        id="spec_H", key="spec_H", name="浮动体钉死留大洞（[H] 强排）",
        defect=("\\noindent " + PROBE["spec_H"] + ".\n\n" + _paras(8)
                + _spec_fig("H") + _paras(7, start=3)),
        fixed=("\\noindent " + PROBE["spec_H"] + ".\n\n" + _paras(8)
               + _spec_fig("tbp") + _paras(7, start=3)),
        probe=PROBE["spec_H"],
        warn_re=None,
    ),
    # ---- 边界复核：第二轮已测，用其 c* 附近再问一次，检验会不会漂
    dict(
        id="overfull", key="overfull", name="正文行溢出（右侧戳出版心）",
        cost_override=[12.5],
        defect=("\\noindent " + PROBE["overfull"] + ": \\mbox{\\texttt{perceive\\_score"
                "\\_act\\_loop\\_with\\_global\\_recompilation\\_and\\_rollback"
                "\\_trajectory\\_audit\\_for\\_every\\_accepted\\_and\\_rejected"
                "\\_candidate\\_action}}.\n\n"),
        fixed=("\\noindent " + PROBE["overfull"] + ": \\texttt{perceive\\-score"
               "\\-act\\-loop\\-with\\-global\\-recompilation\\-and\\-rollback"
               "\\-trajectory\\-audit\\-for\\-every\\-accepted\\-and\\-rejected"
               "\\-candidate\\-action}.\n\n"),
        probe=PROBE["overfull"],
        warn_re="Overfull \\\\hbox",
    ),
    dict(
        id="widetable", key="tab_overwide", name="表格超宽（压出版心）",
        cost_override=[8.0],
        defect=("\\noindent Table~1 " + PROBE["widetable"] + ".\n\n"
                "\\noindent\\begin{tabular}{p{4.2cm}p{4.2cm}p{4.2cm}p{4.2cm}}\n"
                "\\hline\nVariant & Feasibility & Primary model & Quality model \\\\\n"
                "\\hline\ngate first & hard reject & separate & separate \\\\\n"
                "\\hline\\end{tabular}\n\n"),
        fixed=("\\noindent Table~1 " + PROBE["widetable"] + ".\n\n"
               "\\noindent\\begin{tabularx}{\\linewidth}{XXXX}\n\\hline\n"
               "Variant & Feasibility & Primary model & Quality model \\\\\n"
               "\\hline\ngate first & hard reject & separate & separate \\\\\n"
               "\\hline\\end{tabularx}\n\n"),
        probe=PROBE["widetable"],
        warn_re="Overfull \\\\hbox",
    ),
]


def _variant_src(snippet: str, margin_mm: float) -> str:
    body = PREAMBLE.format(margin=margin_mm)
    for p in T.PARAS:
        body += p + "\n\n"
    body += "\\clearpage\n\n"
    body += T.LEAD_IN + "\n\n"
    body += snippet + "\n"
    for p in T.PARAS_AFTER + T.PARAS_AFTER[:2]:
        body += p + "\n\n"
    body += "\\end{document}\n"
    return body


def _page_of(pdf: str, probe: str):
    """定位包含 probe 的页（空白归一化后匹配，避免 -layout 断行导致漏匹配）。"""
    tool = T._pdftotext()
    if not tool:
        return None
    d = os.path.dirname(os.path.abspath(pdf))
    txt = os.path.join(d, "pages.txt")
    r = __import__("subprocess").run(
        [tool, "-layout", os.path.basename(pdf), "pages.txt"], cwd=d,
        capture_output=True)
    if r.returncode != 0 or not os.path.isfile(txt):
        return None
    norm = lambda s: " ".join(s.split())          # noqa: E731
    want = norm(probe)
    pages = open(txt, encoding="utf-8", errors="replace").read().split("\f")
    for i, p in enumerate(pages, start=1):
        if want in norm(p):
            return i
    return None


def _compile(tag: str, src: str) -> dict:
    T.BUILD = BUILD
    return T.compile_variant(tag, src)


def build() -> int:
    for d in (BUILD, SHEET):
        if os.path.isdir(d):
            shutil.rmtree(d)
        os.makedirs(d)

    items, notes = [], []
    for dfx in DEFECTS:
        costs = dfx.get("cost_override") or COSTS
        a = _compile(f"{dfx['id']}-A", _variant_src(dfx["defect"], MARGIN0))
        if not a["ok"]:
            print(f"[跳过] {dfx['id']} A 编译失败：{a.get('err')}")
            continue
        pa = _page_of(a["pdf"], dfx["probe"])
        if pa is None:
            print(f"[跳过] {dfx['id']} 找不到缺陷页")
            continue
        a_png = T.render_page(a["pdf"], pa, SHEET, f"{dfx['id']}-A")
        if not a_png:
            print(f"[跳过] {dfx['id']} A 渲染失败")
            continue
        ma = T.metrics_of(a["pdf"], pa)
        warn_a = len(__import__("re").findall(dfx["warn_re"], a["log"])) \
            if dfx["warn_re"] else None
        notes.append({"defect": dfx["id"], "key": dfx["key"], "role": "A",
                      "page": pa, "pages": engine.pdf_pages(a["pdf"]),
                      "warn": warn_a,
                      "ink": round(ma.get("ink_ratio", 0), 4),
                      "bottom_blank": round(ma.get("bottom_blank", 0), 4)})

        for cost in costs:
            mm = MARGIN0 + cost * MM_PER_I
            b = _compile(f"{dfx['id']}-B{cost}",
                         _variant_src(dfx["fixed"], mm))
            if not b["ok"]:
                print(f"[跳过] {dfx['id']}@{cost} B 编译失败：{b.get('err')}")
                continue
            pb = _page_of(b["pdf"], dfx["probe"])
            if pb is None:
                print(f"[跳过] {dfx['id']}@{cost} 找不到对应页")
                continue
            b_png = T.render_page(b["pdf"], pb, SHEET, f"{dfx['id']}-B{cost}")
            if not b_png:
                continue
            mb = T.metrics_of(b["pdf"], pb)
            warn_b = len(__import__("re").findall(dfx["warn_re"], b["log"])) \
                if dfx["warn_re"] else None
            notes.append({"defect": dfx["id"], "key": dfx["key"], "role": "B",
                          "cost": cost, "margin_mm": mm, "page": pb,
                          "pages": engine.pdf_pages(b["pdf"]), "warn": warn_b,
                          "ink": round(mb.get("ink_ratio", 0), 4),
                          "bottom_blank": round(mb.get("bottom_blank", 0), 4)})
            left_is = "A" if random.random() < 0.5 else "B"
            items.append({"A": os.path.basename(a_png),
                          "B": os.path.basename(b_png),
                          "left": os.path.basename(a_png if left_is == "A" else b_png),
                          "right": os.path.basename(b_png if left_is == "A" else a_png),
                          "title": dfx["name"], "defect": dfx["id"],
                          "key": dfx["key"],
                          "defect_name": dfx["name"], "cost": cost,
                          "margin_mm": mm, "left_is": left_is})

    # 空题：左右同一张图（注意力自检）
    nulls = [it for it in items if it["defect"] in ("underfull", "vbox_under")]
    for it in nulls[:2]:
        items.append({"A": it["A"], "B": it["A"], "left": it["A"],
                      "right": it["A"], "title": "对照题", "defect": "null",
                      "key": None,
                      "defect_name": "对照题（左右同页）", "cost": 0.0,
                      "margin_mm": MARGIN0, "left_is": "B"})

    random.shuffle(items)
    cards, key = [], []
    for i, it in enumerate(items, start=1):
        cards.append({"q": i, "left": it["left"], "right": it["right"],
                      "title": it["title"]})
        key.append({"q": i, "defect": it["defect"], "key": it["key"],
                    "defect_name": it["defect_name"],
                    "cost": it["cost"], "margin_mm": it["margin_mm"],
                    "left_is": it["left_is"], "A": it["A"], "B": it["B"]})

    with open(os.path.join(WORK, "key.json"), "w", encoding="utf-8") as f:
        json.dump({"schema": "texopt.pweight/v1", "margin0_mm": MARGIN0,
                   "mm_per_I": MM_PER_I, "costs": COSTS,
                   "questions": key, "variants": notes},
                  f, ensure_ascii=False, indent=2)
    with open(os.path.join(SHEET, "sheet.html"), "w", encoding="utf-8") as f:
        f.write(T._html(cards).replace("等边际收益标定（ρ）：缺陷 vs 干预代价",
                                       "P 权重标定：缺陷 vs 干预代价（同一把尺子）"))
    print(f"{len(cards)} 题 -> {os.path.join(SHEET, 'sheet.html')}")
    print(f"答案映射（不要给打分人）-> {os.path.join(WORK, 'key.json')}")

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
    print("自检明细见 key.json.variants（ink / bottom_blank / warn / pages）")
    return 0


def import_answers(path: str, out_metrics: str | None = None) -> int:
    from texopt import score as S

    key = json.load(open(os.path.join(WORK, "key.json"), encoding="utf-8"))
    qs = {q["q"]: q for q in key["questions"]}
    ans = json.load(open(path, encoding="utf-8"))
    got = {int(a["q"]): a["choice"] for a in ans.get("answers", [])}

    rows, null_ok, null_n = [], 0, 0
    for qid, q in qs.items():
        ch = got.get(qid)
        if ch is None:
            continue
        if q["defect"] == "null":
            null_n += 1
            null_ok += (ch == "same")
            continue
        b = 0.5 if ch == "same" else (
            1.0 if ((ch == "left") == (q["left_is"] == "B")) else 0.0)
        rows.append({"q": qid, "defect": q["defect"], "key": q["key"],
                     "cost": q["cost"], "b": b})

    per = {}
    for d in sorted({r["defect"] for r in rows}):
        pts = sorted([r for r in rows if r["defect"] == d], key=lambda r: r["cost"])
        cstar, prev = None, None
        for p in pts:
            if p["b"] <= 0.5:
                if prev is None or prev["b"] == p["b"]:
                    cstar = p["cost"]
                else:
                    t = (prev["b"] - 0.5) / max(1e-9, prev["b"] - p["b"])
                    cstar = prev["cost"] + t * (p["cost"] - prev["cost"])
                break
            prev = p
        if cstar is None:
            cstar = max(p["cost"] for p in pts)
        per[d] = {"key": pts[0]["key"],
                  "points": [[p["cost"], p["b"]] for p in pts],
                  "cstar": round(cstar, 3)}

    rho = S.W_PAGE_DEFECT
    proposed, current = {}, dict(S.PAGE_DEFECT_WEIGHT)
    for d, v in per.items():
        proposed[v["key"]] = round(v["cstar"] / rho, 3)

    diffs = []
    for k in sorted(set(proposed) | set()):
        old = current.get(k)
        new = proposed[k]
        diffs.append({"key": k, "old": old, "new": new,
                      "ratio": None if not old else round(new / old, 3)})
    measured = set(proposed)
    untouched = {k: v for k, v in current.items() if k not in measured}

    report = {
        "schema": "texopt.p_weight_tradeoff.v1",
        "method": "同一把尺子：c* = 人判无差异点（边距 mm），w = c* / ρ（等边际收益自洽）",
        "rho_used": rho,
        "costs_probed": COSTS,
        "work_dir": os.path.basename(WORK),
        "n_answers": len(rows),
        "null_questions": {"n": null_n, "correct": null_ok},
        "per_defect": per,
        "proposed_weights": proposed,
        "diffs": diffs,
        "untouched_priors": untouched,
        "sum_old_measured": round(sum(current[k] for k in measured if k in current), 3),
        "sum_new_measured": round(sum(proposed.values()), 3),
        "warnings": [],
    }
    if null_n and null_ok < null_n:
        report["warnings"].append(
            f"空题 {null_ok}/{null_n}：没全部选「差不多」，说明有注意力/位置偏差，结果需打折看")
    if per and any(v["cstar"] == max(p[0] for p in v["points"]) for v in per.values()):
        report["warnings"].append("有关键缺陷在最高代价档仍偏好「修好版」：c* 只是下界")
    import re as _re
    tag = _re.sub(r"[^0-9a-zA-Z]", "", WORK.rsplit("-", 1)[-1]) or "round"
    name = out_metrics or f"p_weight_tradeoff_{tag}.json"
    out = os.path.join(ROOT, "metrics", name)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\n-> {out}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--import", dest="imp", default=None)
    ap.add_argument("--costs", default=None,
                    help="代价阶梯（I 单位），逗号分隔；默认 8,15")
    ap.add_argument("--work", default="workbench-pweight",
                    help="产物目录（相对仓库根），默认 workbench-pweight")
    ap.add_argument("--out-metrics", default=None,
                    help="metrics 文件名，默认 p_weight_tradeoff_<workdir 尾巴>.json")
    a = ap.parse_args()

    global WORK, BUILD, SHEET, COSTS
    WORK = os.path.join(ROOT, a.work)
    BUILD = os.path.join(WORK, "build")
    SHEET = os.path.join(WORK, "sheet")
    if a.costs:
        COSTS = [float(x) for x in a.costs.split(",") if x.strip()]

    if a.imp:
        return import_answers(a.imp, a.out_metrics)
    if a.build:
        return build()
    ap.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
