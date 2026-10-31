#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一致性复核（6 题）：回答两个问题——

  1) 位置偏差 / 注意力：3 题左右完全相同，正确答案只能是「差不多」。
  2) 大差异是否看得见：3 题代价拉到转折点的 2 倍（明显过头），
     此时正确答案是「缺陷版更好」——若仍选修复版，说明没在比较版面。

产物：workbench-tradeoff-check/sheet/sheet.html + key.json（含标准答案）
用法：
    python3 tools/make_tradeoff_check.py --build
    python3 tools/make_tradeoff_check.py --import answers.json
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

import make_tradeoff_sheet as M
import make_tradeoff_v2 as V2
from texopt import engine  # noqa: E402

WORK = os.path.join(ROOT, "workbench-tradeoff-check")
BUILD = os.path.join(WORK, "build")
SHEET = os.path.join(WORK, "sheet")

# 第二轮得到的转折点（I 单位）
CSTAR = {"vspace": 8.0, "widefig": 13.0, "widetable": 6.0}


def build() -> int:
    for d in (BUILD, SHEET):
        if os.path.isdir(d):
            shutil.rmtree(d)
    os.makedirs(BUILD)
    os.makedirs(SHEET)

    items = []

    # ---- 3 题：完全相同（正确 = 差不多）
    for did in ("overfull", "vspace", "widefig"):
        dfx = {d["id"]: d for d in M.DEFECTS}[did]
        tag = f"null-{did}"
        a = V2.compile_one(tag, V2.base_doc(M.MARGIN0, dfx["fixed"]))
        if not a["ok"]:
            print(f"[跳过] null {did}: {a['err']}")
            continue
        pa = M.page_of(a["pdf"], dfx["probe"])
        png = M.render_page(a["pdf"], pa, SHEET, tag)
        if not png:
            continue
        items.append({"kind": "null", "defect": dfx["id"], "cost": 0,
                      "expect": "same", "A": png, "B": png})

    # ---- 3 题：代价 2 倍（明显过头，正确 = 缺陷版更好）
    for did, cstar in CSTAR.items():
        dfx = {d["id"]: d for d in M.DEFECTS}[did]
        c = min(2.0 * cstar, 26.0)
        mm = M.MARGIN0 + c * M.MM_PER_I
        a = V2.compile_one(f"ext-{did}-A", V2.base_doc(M.MARGIN0, dfx["defect"]))
        b = V2.compile_one(f"ext-{did}-B", V2.base_doc(mm, dfx["fixed"]))
        if not (a["ok"] and b["ok"]):
            print(f"[跳过] ext {did}")
            continue
        pa = M.page_of(a["pdf"], dfx["probe"])
        pb = M.page_of(b["pdf"], dfx["probe"])
        a_png = M.render_page(a["pdf"], pa, SHEET, f"ext-{did}-A")
        b_png = M.render_page(b["pdf"], pb, SHEET, f"ext-{did}-B")
        if not (a_png and b_png):
            continue
        items.append({"kind": "extreme", "defect": did, "cost": c,
                      "margin_mm": mm, "expect": "defect",
                      "A": a_png, "B": b_png})

    random.shuffle(items)
    cards, key = [], []
    for i, it in enumerate(items, start=1):
        it["left_is"] = "A" if random.random() < 0.5 else "B"
        left = it["A"] if it["left_is"] == "A" else it["B"]
        right = it["B"] if it["left_is"] == "A" else it["A"]
        cards.append({"q": i, "left": os.path.basename(left),
                      "right": os.path.basename(right)})
        key.append({"q": i, "kind": it["kind"], "defect": it["defect"],
                    "cost": it["cost"], "left_is": it["left_is"],
                    "expect": it["expect"],
                    "margin_mm": it.get("margin_mm", M.MARGIN0),
                    "A": os.path.basename(it["A"]), "B": os.path.basename(it["B"])})

    json.dump({"schema": "texopt.tradeoff/check", "margin0_mm": M.MARGIN0,
               "questions": key},
              open(os.path.join(WORK, "key.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    open(os.path.join(SHEET, "sheet.html"), "w", encoding="utf-8").write(_html(cards))
    print(f"{len(cards)} 题 -> {os.path.join(SHEET, 'sheet.html')}")
    return 0


def _html(cards):
    import html as H
    rows = [f"""
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
  </div>""" for c in cards]
    return f"""<!doctype html><html lang="zh"><meta charset="utf-8">
<title>一致性复核（{len(cards)} 题）</title>
<style>
 body{{font-family:system-ui,sans-serif;margin:20px;background:#f6f6f7;color:#1d1d1f}}
 h1{{font-size:18px;margin:0 0 6px}} p.lead{{font-size:13px;color:#555;max-width:900px;line-height:1.65}}
 .pair{{background:#fff;border:1px solid #ddd;border-radius:10px;padding:10px;margin:14px 0}}
 .ph{{font-size:12px;color:#888;margin-bottom:6px}}
 .two{{display:grid;grid-template-columns:1fr 1fr;gap:8px}}
 .side{{background:#fafafa;border:1px solid #eee;padding:4px}}
 .side img{{width:100%;display:block}}
 .opts{{display:flex;gap:22px;margin-top:8px;font-size:14px}}
 .bar{{position:sticky;top:0;background:#fff;border:1px solid #ddd;border-radius:8px;
      padding:8px 10px;display:flex;align-items:center;gap:12px;z-index:9}}
 button{{padding:7px 14px;font-size:14px}} #prog{{font-size:13px;color:#444}}
</style>
<h1>一致性复核（{len(cards)} 题）</h1>
<p class="lead">6 题，1 分钟。这轮的目的不是测你的偏好，而是检查前两轮的判断稳定性：
其中<b>有题目左右完全一样</b>，也有题目<b>差异非常明显</b>。规则不变：只看版面，
哪页整体更好；分不出来就选「差不多」。请按平常速度做，不要回头检查。</p>
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
  const data={{ranker:'user',task:'rho_tradeoff_check',ts:new Date().toISOString(),
    answers:Object.keys(o).map(k=>({{q:+k,choice:o[k]}}))}};
  const blob=new Blob([JSON.stringify(data,null,2)],{{type:'application/json'}});
  const a=document.createElement('a');a.href=URL.createObjectURL(blob);
  a.download='answers.json';a.click();
  document.getElementById('msg').textContent='已导出 answers.json';
}}
</script></html>"""


def import_answers(path: str) -> int:
    key = json.load(open(os.path.join(WORK, "key.json"), encoding="utf-8"))
    qs = key["questions"]
    got = {int(a["q"]): a["choice"] for a in json.load(open(path, encoding="utf-8"))["answers"]}
    rows, ok = [], 0
    for q in qs:
        ch = got.get(q["q"])
        if q["expect"] == "same":
            good = ch == "same"
        else:
            # 期望选「缺陷版」：B 是修复版，所以不能选 B 那一侧
            chosen_b = (ch == "left") == (q["left_is"] == "B") if ch != "same" else None
            good = (ch != "same") and (chosen_b is False)
        ok += int(bool(good))
        rows.append({"q": q["q"], "kind": q["kind"], "defect": q["defect"],
                     "cost": q["cost"], "choice": ch, "expected": q["expect"],
                     "correct": bool(good)})
    nulls = [r for r in rows if r["kind"] == "null"]
    exts = [r for r in rows if r["kind"] == "extreme"]
    out = {"schema": "texopt.tradeoff/check_result",
           "total_correct": f"{ok}/{len(rows)}",
           "null_correct": f"{sum(r['correct'] for r in nulls)}/{len(nulls)}",
           "extreme_correct": f"{sum(r['correct'] for r in exts)}/{len(exts)}",
           "position": {"left": sum(1 for v in got.values() if v == "left"),
                        "right": sum(1 for v in got.values() if v == "right"),
                        "same": sum(1 for v in got.values() if v == "same")},
           "rows": rows,
           "verdict": ("可用：位置与注意力检查通过" if ok >= 5
                       else "需重测：至少一项目检失败，前两轮 ρ 的置信区间要放宽")}
    json.dump(out, open(os.path.join(WORK, "check_result.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(json.dumps({k: out[k] for k in
                      ("total_correct", "null_correct", "extreme_correct",
                       "position", "verdict")}, ensure_ascii=False, indent=2))
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
