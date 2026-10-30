# -*- coding: utf-8 -*-
"""Step 2 验收：20 页人工排序表 + 排序一致性（Spearman）。

为什么需要：合成图只证明「量得准」，语料分位只证明「人口径是什么」，
但**指标排序是否跟人眼一致**只能问人。口径：Spearman ≥ 0.6 才算这个指标能进 model2。

用法：
  python3 tools/make_detector_sheet.py --build        # 生成打分表（20 页）
  python3 tools/make_detector_sheet.py --import answers.json
  python3 tools/make_detector_sheet.py --stats

产物：
  workbench-detector/sheet/sheet.html      离线打分表（含 20 张页图）
  workbench-detector/sheet/pages.json      选页与逐页指标
  workbench-detector/human_rank.json       导入后的排序与相关系数
"""
from __future__ import annotations

import argparse
import json
import os
import random
import shutil
import sys

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJ)

from texopt import score as S, visual  # noqa: E402

ROWS = "/mnt/d/texopt-corpus/rows_originals.jsonl"
PDFDIR = "/mnt/d/texopt-corpus/pdf"
WORK = os.path.join(PROJ, "workbench-detector")
SHEET = os.path.join(WORK, "sheet")
N = 20
# 人的验收只看「会进 model2 的软指标」；band 已被 Step 2 判为暂缓（w=0），不参与排序
RANK_METRICS = [m for m, sp in S.SOFT_SPEC.items() if sp.get("w")]


def _page_loss(m: dict, metric: str) -> float:
    """与 score.aesthetic_score 同一口径的**逐页**损失（2026-10-28 平滑目标形式）。"""
    v = S.soft_metric_loss(metric, m.get(metric))
    return 0.0 if v is None else v


def page_score(m: dict) -> float:
    return sum(_page_loss(m, k) for k in RANK_METRICS)   # 损失已含权重


def _select() -> list[dict]:
    """按「模型自己算的逐页 A_soft 损失」分三档抽页（低/中/高各约 1/3）。

    为什么不按墨迹分：墨迹只反映页面内容多少，不反映排版好坏；
    要验收的是「模型的排序和人眼是否一致」，样本必须覆盖模型判断的整个好坏区间，
    否则 Spearman 无从谈起。每篇论文最多出 1 页，避免同一模板风格主导。
    """
    pool, seen = [], set()
    for line in open(ROWS, encoding="utf-8"):
        r = json.loads(line)
        if r["paper_id"] in seen:
            continue
        pages = r.get("page_metrics") or []
        cand = [(i + 1, p) for i, p in enumerate(pages)
                if 1 < i + 1 <= max(2, len(pages) - 1) and p.get("band", 0) < 0.40]
        if not cand:
            continue
        idx, p = random.choice(cand)          # 每篇随机一页
        pool.append({"case_id": r["case_id"], "paper_id": r["paper_id"],
                     "venue": r["venue"], "column": r["column"],
                     "page": idx, "m": p, "score": page_score(p)})
        seen.add(r["paper_id"])
    pool.sort(key=lambda x: x["score"])
    n = min(N, len(pool))
    thirds = [pool[: len(pool) // 3], pool[len(pool) // 3: 2 * len(pool) // 3],
              pool[2 * len(pool) // 3:]]
    want = [n // 3, n // 3, n - 2 * (n // 3)]
    picked = []
    for seg, k in zip(thirds, want):
        if not seg or not k:
            continue
        step = max(1, len(seg) // k)
        picked += seg[::step][:k]
    return picked


def build() -> int:
    os.makedirs(SHEET, exist_ok=True)
    pages = _select()
    cards = []
    for i, it in enumerate(pages, 1):
        pdf = os.path.join(PDFDIR, it["case_id"].replace("/", "__") + ".pdf")
        imgs, err = visual.render_pages(pdf, SHEET, dpi=100,
                                        first=it["page"], last=it["page"],
                                        prefix=f"p{i:02d}")
        if err or not imgs:
            print("render fail", pdf, err)
            continue
        img = imgs[0]
        # render_pages 会重命名成 pXX-1.png，卡片编号用文件序号
        cards.append({
            "id": i, "img": os.path.basename(img),
            "case_id": it["case_id"], "venue": it["venue"], "column": it["column"],
            "page": it["page"], "score": round(page_score(it["m"]), 4),
            "metrics": {k: it["m"].get(k) for k in S.SOFT_BANDS},
        })
    cards.sort(key=lambda c: c["id"])
    html = _html(cards)
    with open(os.path.join(SHEET, "sheet.html"), "w", encoding="utf-8") as f:
        f.write(html)
    with open(os.path.join(SHEET, "pages.json"), "w", encoding="utf-8") as f:
        json.dump(cards, f, ensure_ascii=False, indent=2)
    print(f"{len(cards)} 页 -> {os.path.join(SHEET, 'sheet.html')}")
    return 0


def _html(cards: list[dict]) -> str:
    import html as H
    rows = []
    for c in cards:
        rows.append(f"""
  <div class="card" id="c{c['id']}">
    <div class="hd"><b>#{c['id']}</b>
      <input class="rk" data-id="{c['id']}" type="number" min="1" max="{len(cards)}"
             placeholder="排名"> </div>
    <img src="{H.escape(c['img'])}">
    <div class="meta">{H.escape(c['venue'])} · {H.escape(c['column'])} · 第 {c['page']} 页</div>
  </div>""")
    return f"""<!doctype html><html lang="zh"><meta charset="utf-8">
<title>排版排序验收（{len(cards)} 页）</title>
<style>
 body{{font-family:system-ui,sans-serif;margin:24px;background:#fafafa;color:#222}}
 h1{{font-size:18px}} p{{font-size:13px;color:#555;max-width:900px}}
 .grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:16px}}
 .card{{background:#fff;border:1px solid #ddd;border-radius:8px;padding:8px}}
 .card img{{width:100%;display:block;border:1px solid #eee}}
 .hd{{display:flex;justify-content:space-between;align-items:center;margin-bottom:6px}}
 .rk{{width:70px;padding:4px}}
 .meta{{font-size:12px;color:#777;margin-top:6px}}
 button{{padding:8px 14px;font-size:14px;margin:16px 8px 0 0}}
</style>
<h1>排版排序验收（Step 2）</h1>
<p>给下面 {len(cards)} 页按「排版好坏」排名：<b>1 = 最好，{len(cards)} = 最差</b>，每页填一个不重复的数字。判断只看版面本身：
留白是否得当、有没有大片空洞、图/表是否孤立或超宽、上下半页是否失衡。不用管内容质量、不用管颜色。
填完点「导出答案」，把下载的 answers.json 发回给助手。</p>
<div class="grid">{''.join(rows)}
</div>
<button onclick="exp()">导出答案</button>
<button onclick="show()">看看还缺哪些</button>
<pre id="out"></pre>
<script>
function vals(){{return [...document.querySelectorAll('.rk')].map(e=>({{id:+e.dataset.id,rank:+e.value||0}}))}}
function exp(){{
  const v=vals(), used=v.map(x=>x.rank).filter(r=>r>0);
  const dup=used.filter((r,i)=>used.indexOf(r)!==i);
  if(dup.length){{alert('有重复排名：'+[...new Set(dup)].join(','));return}}
  const miss=v.filter(x=>!x.rank).map(x=>'#'+x.id);
  const data={{ranker:'user',ts:new Date().toISOString(),ranks:v}};
  const blob=new Blob([JSON.stringify(data,null,2)],{{type:'application/json'}});
  const a=document.createElement('a');a.href=URL.createObjectURL(blob);
  a.download='answers.json';a.click();
  document.getElementById('out').textContent='已导出。未填：'+(miss.join(' ')||'无');
}}
function show(){{const v=vals();document.getElementById('out').textContent=
  '未填：'+(v.filter(x=>!x.rank).map(x=>'#'+x.id).join(' ')||'无')}}
</script></html>"""


def spearman(a: list[float], b: list[float]) -> float | None:
    """秩相关（并列取平均秩）。"""
    n = len(a)
    if n < 3:
        return None

    def rank(xs):
        order = sorted(range(n), key=lambda i: xs[i])
        r = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and xs[order[j + 1]] == xs[order[i]]:
                j += 1
            avg = (i + j) / 2 + 1
            for k in range(i, j + 1):
                r[order[k]] = avg
            i = j + 1
        return r

    ra, rb = rank(a), rank(b)
    ma, mb = sum(ra) / n, sum(rb) / n
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    den = (sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb)) ** 0.5
    return round(num / den, 4) if den else None


def import_answers(path: str) -> int:
    pages = json.load(open(os.path.join(SHEET, "pages.json"), encoding="utf-8"))
    ans = json.load(open(path, encoding="utf-8"))
    rk = {int(r["id"]): int(r["rank"]) for r in ans["ranks"] if int(r["rank"]) > 0}
    use = [p for p in pages if p["id"] in rk]
    if len(use) < 8:
        print(f"只填了 {len(use)} 页，至少要 8 页才有结论（不伪造数据）")
        return 1
    human = [rk[p["id"]] for p in use]
    # 口径随 score.py 走：从 pages.json 的原始指标**重算**，不用建表时的缓存分
    scores = [page_score(p["metrics"]) for p in use]
    out = {"n": len(use), "rank_metrics": RANK_METRICS, "overall": {},
           "per_metric": {}, "form": "soft_metric_loss(2026-10-28)"}
    # 人对 = 排名数字小更好；指标 = 损失小更好 → 取负号使两列“大=好”
    out["overall"]["spearman"] = spearman([-h for h in human], [-s for s in scores])
    for mt in RANK_METRICS:
        losses = [-_page_loss(p["metrics"], mt) for p in use]
        out["per_metric"][mt] = spearman([-h for h in human], losses)
    out["raw"] = {"human": human, "metric_score": scores,
                  "ids": [p["id"] for p in use],
                  "cached_score_at_build": [p["score"] for p in use]}
    with open(os.path.join(WORK, "human_rank.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(json.dumps({k: v for k, v in out.items() if k != "raw"},
                     ensure_ascii=False, indent=2))
    return 0


def stats() -> int:
    p = os.path.join(WORK, "human_rank.json")
    if not os.path.isfile(p):
        print("还没有 human_rank.json（先 --import answers.json）")
        return 1
    print(open(p, encoding="utf-8").read())
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--import", dest="imp")
    ap.add_argument("--stats", action="store_true")
    a = ap.parse_args()
    if a.build:
        return build()
    if a.imp:
        return import_answers(a.imp)
    if a.stats:
        return stats()
    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
