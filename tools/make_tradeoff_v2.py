#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ρ 第二轮（强化版）：把无差异点钉准，并校准 I 的内部系数。

第一轮（+12/+20/+30mm）已经把每个缺陷的转折点框在 8–15 I 单位之间。
这一轮做四件事：

  Block A（10 题）边界加密：每个缺陷在上一轮转折点 ±2 I 单位各问一次，
                  把 c* 从"两档之间"收敛到更窄区间。
  Block B（8 题）第二种货币：同样的缺陷，代价改成「字号升 1 档 / 升 2 档」
                  （I = 3.0 / 6.0）。用它与 Block A 对比，就能直接读出
                  「1 档字号在观感上等于多少 mm 边距」——这是 I 内部系数
                  （字号 3.0、边距 0.5/mm）目前完全没有证据的地方。
  Block C（4 题）一致性自检：2 题左右两页完全相同（正确回答必须是"差不多"），
                  2 题是已出过的题左右对调（回答应该不变）——用来估计
                  你自己的前后一致率，也让 ρ 的置信区间有依据。

用法：
    python3 tools/make_tradeoff_v2.py --build
    python3 tools/make_tradeoff_v2.py --import answers.json
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import random
import re
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import make_tradeoff_sheet as M  # 复用编译/定位/渲染/指标
from texopt import engine, visual  # noqa: E402

WORK = os.path.join(ROOT, "workbench-tradeoff2")
BUILD = os.path.join(WORK, "build")
SHEET = os.path.join(WORK, "sheet")
MARGIN0 = M.MARGIN0
MM_PER_I = M.MM_PER_I          # 0.5 / mm -> 1 I = 2mm

FONT_COST_PER_STEP = 3.0       # score.intervention_cost：字号每偏离 1 档 = 3.0


def base_doc(margin_mm: float, snippet: str, font_pt: int = 10) -> str:
    """基准稿：与第一轮同一批段落，可指定字号档（代价货币 B）。"""
    body = M.PREAMBLE.format(margin=margin_mm).replace(
        "\\documentclass[10pt,a4paper]", "\\documentclass[%dpt,a4paper]" % font_pt)
    for p in M.PARAS:
        body += p + "\n\n"
    body += "\\clearpage\n\n"
    body += M.LEAD_IN + "\n\n"
    body += snippet
    for p in M.PARAS_AFTER + M.PARAS_AFTER[:4]:
        body += p + "\n\n"
    body += "\\end{document}\n"
    return body


def compile_one(tag: str, src: str) -> dict:
    d = os.path.join(BUILD, tag)
    os.makedirs(d, exist_ok=True)
    tex = os.path.join(d, "main.tex")
    open(tex, "w", encoding="utf-8").write(src)
    r = engine.compile_tex(tex, passes=1, timeout=120)
    return {"tag": tag, "ok": r.ok, "pdf": r.pdf_path, "log": r.log or "",
            "err": r.first_error}


DEF_BY_ID = {d["id"]: d for d in M.DEFECTS}

# 上一轮的转折点（I 单位），用于加密
PREV_CSTAR = {"overfull": 12.5, "vspace": 10.0, "narrowtable": 10.0,
              "widefig": 15.0, "widetable": 8.0}

BLOCK_B_DEFECTS = ["overfull", "vspace", "widefig", "narrowtable"]


def build() -> int:
    for d in (BUILD, SHEET):
        if os.path.isdir(d):
            shutil.rmtree(d)
    os.makedirs(BUILD)
    os.makedirs(SHEET)

    items, log = [], []

    # ---------- Block A：边界加密（margin 货币）
    for did, cstar in PREV_CSTAR.items():
        dfx = DEF_BY_ID[did]
        a = compile_one(f"A-{did}", base_doc(MARGIN0, dfx["defect"]))
        if not a["ok"]:
            print(f"[跳过] {did} A: {a['err']}")
            continue
        pa = M.page_of(a["pdf"], dfx["probe"])
        a_png = M.render_page(a["pdf"], pa, SHEET, f"A-{did}")
        if not a_png:
            continue
        for c in (max(1.0, cstar - 2.0), cstar + 2.0):
            mm = MARGIN0 + c * MM_PER_I
            b = compile_one(f"A-{did}-c{c}", base_doc(mm, dfx["fixed"]))
            if not b["ok"]:
                print(f"[跳过] {did}@{c}: {b['err']}")
                continue
            pb = M.page_of(b["pdf"], dfx["probe"])
            b_png = M.render_page(b["pdf"], pb, SHEET, f"A-{did}-c{c}")
            if not b_png:
                continue
            items.append({"kind": "tradeoff", "currency": "margin",
                          "defect": did, "defect_name": dfx["name"],
                          "cost": c, "margin_mm": mm, "font_pt": 10,
                          "A": os.path.basename(a_png), "B": os.path.basename(b_png)})

    # ---------- Block B：字号货币（1 档 / 2 档）
    for did in BLOCK_B_DEFECTS:
        dfx = DEF_BY_ID[did]
        a_png = os.path.join(SHEET, f"A-{did}.png")
        if not os.path.exists(a_png):
            a = compile_one(f"B-{did}", base_doc(MARGIN0, dfx["defect"]))
            if not a["ok"]:
                continue
            pa = M.page_of(a["pdf"], dfx["probe"])
            p = M.render_page(a["pdf"], pa, SHEET, f"A-{did}")
            if not p:
                continue
            a_png = p
        for step in (1, 2):
            font_pt = 10 + step
            cost = FONT_COST_PER_STEP * step
            b = compile_one(f"B-{did}-f{step}",
                            base_doc(MARGIN0, dfx["fixed"], font_pt=font_pt))
            if not b["ok"]:
                print(f"[跳过] {did} font{step}: {b['err']}")
                continue
            pb = M.page_of(b["pdf"], dfx["probe"])
            b_png = M.render_page(b["pdf"], pb, SHEET, f"B-{did}-f{step}")
            if not b_png:
                continue
            items.append({"kind": "tradeoff", "currency": "font",
                          "defect": did, "defect_name": dfx["name"],
                          "cost": cost, "margin_mm": MARGIN0, "font_pt": font_pt,
                          "font_step": step,
                          "A": os.path.basename(a_png), "B": os.path.basename(b_png)})

    # ---------- Block C：一致性自检
    # C1/C2：两页完全相同（正确 = 差不多）
    for i, did in enumerate(["overfull", "widetable"], start=1):
        dfx = DEF_BY_ID[did]
        a = compile_one(f"C-null{i}", base_doc(MARGIN0, dfx["fixed"]))
        if not a["ok"]:
            continue
        pa = M.page_of(a["pdf"], dfx["probe"])
        png = M.render_page(a["pdf"], pa, SHEET, f"C-null{i}")
        if not png:
            continue
        items.append({"kind": "null", "currency": "none", "defect": did,
                      "defect_name": dfx["name"], "cost": 0, "margin_mm": MARGIN0,
                      "font_pt": 10,
                      "A": os.path.basename(png), "B": os.path.basename(png)})

    # C3/C4：与 Block A 重复、左右对调（回答应不变）
    dup_src = [it for it in items if it["kind"] == "tradeoff"
               and it["currency"] == "margin"][:2]
    for i, it in enumerate(dup_src, start=3):
        items.append({"kind": "mirror", "currency": it["currency"],
                      "defect": it["defect"], "defect_name": it["defect_name"],
                      "cost": it["cost"], "margin_mm": it["margin_mm"],
                      "font_pt": it["font_pt"], "of_q": None,
                      "A": it["A"], "B": it["B"],
                      "mirror_of": (it["defect"], it["currency"], it["cost"])})

    # 左右随机 + 打乱题序（分块内打乱，保证三种块都有代表）
    for it in items:
        it["left_is"] = "A" if random.random() < 0.5 else "B"
    random.shuffle(items)
    # 自检题强制各一：null 题必须是同一张图；mirror 题稍后回填 of_q
    cards, key = [], []
    for i, it in enumerate(items, start=1):
        left = it["A"] if it["left_is"] == "A" else it["B"]
        right = it["B"] if it["left_is"] == "A" else it["A"]
        cards.append({"q": i, "left": left, "right": right,
                      "kind": it["kind"], "title": it["defect_name"]})
        key.append({"q": i, **{k: it[k] for k in
                               ("kind", "currency", "defect", "defect_name",
                                "cost", "margin_mm", "font_pt", "left_is",
                                "A", "B")}})
    # mirror 题的 of_q：同 defect/currency/cost 的第一题
    for k in key:
        if k["kind"] == "mirror":
            k["of_q"] = next((x["q"] for x in key
                              if x["kind"] == "tradeoff"
                              and (x["defect"], x["currency"], x["cost"])
                              == (k["defect"], k["currency"], k["cost"])), None)

    json.dump({"schema": "texopt.tradeoff/v2", "margin0_mm": MARGIN0,
               "mm_per_I": MM_PER_I, "font_cost_per_step": FONT_COST_PER_STEP,
               "prev_cstar": PREV_CSTAR, "questions": key},
              open(os.path.join(WORK, "key.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    open(os.path.join(SHEET, "sheet.html"), "w", encoding="utf-8").write(_html(cards))
    n = {k: sum(1 for c in key if c["kind"] == k)
         for k in ("tradeoff", "null", "mirror")}
    print(f"{len(cards)} 题（tradeoff {n['tradeoff']} / null {n['null']} / mirror {n['mirror']}）"
          f" -> {os.path.join(SHEET, 'sheet.html')}")
    print(f"答案映射 -> {os.path.join(WORK, 'key.json')}")
    return 0


def _html(cards: list[dict]) -> str:
    import html as H
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
<title>等边际收益标定 · 第二轮强化（{len(cards)} 题）</title>
<style>
 body{{font-family:system-ui,sans-serif;margin:20px;background:#f6f6f7;color:#1d1d1f}}
 h1{{font-size:18px;margin:0 0 6px}}
 p.lead{{font-size:13px;color:#555;max-width:920px;line-height:1.65}}
 ul.lead{{font-size:13px;color:#555;max-width:920px;line-height:1.65}}
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
<h1>等边际收益标定 · 第二轮强化（{len(cards)} 题）</h1>
<p class="lead">规则和上次一样：左右是同一篇论文的同一页内容，只差「缺陷在不在」和「代价付不付」。
请只看版面，选哪一页整体更好；分不出来就选「差不多」。</p>
<ul class="lead">
<li>这一轮有三种代价：<b>页面边距变宽</b>、<b>正文字号变大</b>（整篇都会变），以及<b>完全相同的两页</b>。</li>
<li>看到两页一模一样、或者差异小到说不清，请一定选「差不多」——这正是我们要的数据。</li>
<li>字号变大不是"更好"，它是代价：纸张、页数、与图表的比例都会变。</li>
<li>同一道题可能出现两次（左右可能对调），按你当时的判断填就行。</li>
</ul>
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
  const data={{ranker:'user',task:'rho_tradeoff_v2',ts:new Date().toISOString(),
    answers:Object.keys(o).map(k=>({{q:+k,choice:o[k]}}))}};
  const blob=new Blob([JSON.stringify(data,null,2)],{{type:'application/json'}});
  const a=document.createElement('a');a.href=URL.createObjectURL(blob);
  a.download='answers.json';a.click();
  document.getElementById('msg').textContent='已导出 answers.json';
}}
</script></html>"""


def import_answers(path: str) -> int:
    key = json.load(open(os.path.join(WORK, "key.json"), encoding="utf-8"))
    qs = {q["q"]: q for q in key["questions"]}
    got = {int(a["q"]): a["choice"] for a in json.load(open(path, encoding="utf-8"))["answers"]}

    def b_wins(q, ch):
        if ch == "same":
            return 0.5
        return 1.0 if ((ch == "left") == (q["left_is"] == "B")) else 0.0

    # 一致性
    nulls = [q for q in qs.values() if q["kind"] == "null"]
    null_ok = sum(1 for q in nulls if got.get(q["q"]) == "same")
    mirrors = [q for q in qs.values() if q["kind"] == "mirror"]
    mir_ok = 0
    for q in mirrors:
        base = qs.get(q["of_q"])
        if not base:
            continue
        a1, a2 = b_wins(base, got.get(base["q"])), b_wins(q, got.get(q["q"]))
        mir_ok += int(abs(a1 - a2) < 1e-9)

    out = {"schema": "texopt.rho_tradeoff/v2",
           "consistency": {"null_correct": f"{null_ok}/{len(nulls)}",
                           "mirror_agree": f"{mir_ok}/{len(mirrors)}"},
           "by_currency": {}}
    for cur in ("margin", "font"):
        res = {}
        for d in sorted({q["defect"] for q in qs.values()
                         if q["kind"] == "tradeoff" and q["currency"] == cur}):
            pts = sorted([(q["cost"], b_wins(q, got.get(q["q"])))
                          for q in qs.values()
                          if q["kind"] == "tradeoff" and q["currency"] == cur
                          and q["defect"] == d], key=lambda x: x[0])
            cstar, prev = None, None
            for c, b in pts:
                if b <= 0.5:
                    if prev is None or prev[1] == b:
                        cstar = c
                    else:
                        t = (prev[1] - 0.5) / max(1e-9, prev[1] - b)
                        cstar = prev[0] + t * (c - prev[0])
                    break
                prev = (c, b)
            if cstar is None:
                cstar = pts[-1][0]
            res[d] = {"points": pts, "cstar_I": round(cstar, 3)}
        out["by_currency"][cur] = res

    # ρ（每缺陷 I 单位 / P 权重）——ω 用 score 里的现行权重
    from texopt import score as S
    W = dict(S.PAGE_DEFECT_WEIGHT)
    hy = dict(S.HYGIENE_WEIGHT)
    wmap = {"overfull": W["overfull"], "vspace": hy["manual_vspace"],
            "narrowtable": hy["table_narrow"], "widefig": W["fig_overwide"],
            "widetable": W["tab_overwide"]}
    rho = {}
    for d, v in out["by_currency"].get("margin", {}).items():
        rho[d] = round(v["cstar_I"] / wmap[d], 2)
    vals = sorted(rho.values())
    out["rho_margin"] = rho
    out["rho_median"] = vals[len(vals) // 2] if vals else None

    # 字号货币 -> 多少 mm 边距
    conv = {}
    for d, v in out["by_currency"].get("font", {}).items():
        m = out["by_currency"]["margin"].get(d)
        if not m:
            continue
        conv[d] = {"font_I": v["cstar_I"], "margin_I_at_cstar": m["cstar_I"],
                   "font_steps_per_2mm": round(v["cstar_I"] / FONT_COST_PER_STEP, 3)}
    out["font_vs_margin"] = conv

    json.dump(out, open(os.path.join(WORK, "rho_estimate_v2.json"), "w",
                        encoding="utf-8"), ensure_ascii=False, indent=2)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--import", dest="imp")
    a = ap.parse_args()
    if a.imp:
        return import_answers(a.imp)
    if a.build:
        return build()
    ap.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
