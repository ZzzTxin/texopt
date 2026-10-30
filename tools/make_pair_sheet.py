# -*- coding: utf-8 -*-
"""Step 2-c：**成对比较**验收表（12 对，每对只点一次），替代整页排序。

为什么换：20 页全序排名要人一次性排 20 个名次，认知负担大（用户 2026-10-28 明确
反馈“不想要排序的打分表，工作量太大”）。成对比较每题只判断「左/右哪页排版更好」，
一题一次点击，且对噪声更鲁棒（不需要维持全局一致的名次）。

设计要点：
  * 每对两页来自**不同论文**，模型给出的总分差足够大（|Δ| ≥ 0.30）；
  * 每对尽量只由**一个维度**主导（主导维占总差 ≥ 50%），这样一次判断
    同时验收「总分方向」和「该维度方向」；
  * 左右位置随机，避免位置偏差；提供「差不多」选项（计为并列，不进准确率）；
  * 准确率 = 人的选择与模型判断一致的比例；再用二项检验给出显著性。

用法：
  python3 tools/make_pair_sheet.py --build            # 选页 + 渲染 + 生成 HTML
  python3 tools/make_pair_sheet.py --import answers.json
  python3 tools/make_pair_sheet.py --stats
  python3 tools/make_pair_sheet.py --selftest         # 用“模型永远对”的假答案自检口径

产物：
  workbench-pairs/sheet.html      离线成对比较表（24 张页图内联）
  workbench-pairs/pairs.json      选页、逐维损失、左右映射
  workbench-pairs/result.json     导入后的准确率与逐维拆解
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import sys

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJ)

from texopt import score as S, visual  # noqa: E402

ROWS = "/mnt/d/texopt-corpus/rows_originals.jsonl"
PDFDIR = "/mnt/d/texopt-corpus/pdf"
WORK = os.path.join(PROJ, "workbench-pairs")
SHEET = os.path.join(WORK, "sheet")
N_PAIRS = 12
MIN_GAP = 0.40          # 模型总分差下限（0.30 太小：12 对里出现 4 次“差不多”）
SAME_COLUMN = True      # 只配同栏数（单栏 vs 双栏）的页，避免模板混淆
SAME_VENUE_FIRST = True # 优先同会议（留白/页边距口径一致）
DOMINANCE = 0.50        # 主导维占总差的下限
METRICS = [m for m, sp in S.SOFT_SPEC.items() if sp.get("w")]


def page_losses(m: dict) -> dict[str, float]:
    out = {}
    for k in METRICS:
        v = S.soft_metric_loss(k, m.get(k))
        out[k] = 0.0 if v is None else round(v, 4)
    return out


def page_score(m: dict) -> float:
    return round(sum(page_losses(m).values()), 4)


def _used_papers() -> set[str]:
    p = os.path.join(WORK, "used_papers.json")
    if not os.path.isfile(p):
        return set()
    try:
        return set(json.load(open(p, encoding="utf-8")))
    except Exception:
        return set()


def _pool() -> list[dict]:
    """每篇论文随机取一页（首末页与 band 高的页跳过），排除往轮用过的论文。"""
    pool, seen = [], _used_papers()
    for line in open(ROWS, encoding="utf-8"):
        r = json.loads(line)
        if r["paper_id"] in seen:
            continue
        pages = r.get("page_metrics") or []
        cand = [(i + 1, p) for i, p in enumerate(pages)
                if 1 < i + 1 <= max(2, len(pages) - 1) and (p.get("band") or 0) < 0.40]
        if not cand:
            continue
        idx, p = random.choice(cand)
        pool.append({"case_id": r["case_id"], "paper_id": r["paper_id"],
                     "venue": r["venue"], "column": r["column"], "page": idx,
                     "m": p, "loss": page_losses(p), "score": page_score(p)})
        seen.add(r["paper_id"])
    return pool


def _pick_pairs(pool: list[dict], n: int) -> list[dict]:
    """按主导维轮转配对：每个维度最多 2 对，同维里挑差额最大的，覆盖面与强度兼顾。"""
    lo_pool = sorted(pool, key=lambda x: x["score"])
    n_lo = max(1, len(lo_pool) * 2 // 3)
    cands: dict[str, list[tuple]] = {}
    for hi in lo_pool[len(lo_pool) // 3:]:
        for lo in lo_pool[:n_lo]:
            if lo["paper_id"] == hi["paper_id"]:
                continue
            if SAME_COLUMN and lo["column"] != hi["column"]:
                continue
            gap = hi["score"] - lo["score"]
            if gap < MIN_GAP:
                continue
            diffs = {k: hi["loss"][k] - lo["loss"][k] for k in METRICS}
            dim = max(diffs, key=lambda k: diffs[k])
            share = diffs[dim] / gap
            if share < DOMINANCE:
                continue
            same_venue = 1 if lo["venue"] == hi["venue"] else 0
            pref = (0 if (SAME_VENUE_FIRST and same_venue) else 1, -gap)
            cands.setdefault(dim, []).append((pref, -gap, -share, lo, hi, dim,
                                              min(1.0, share), gap))
    for dim in cands:
        cands[dim].sort(key=lambda t: t[0])

    used, pairs, taken = set(), [], {}
    order = sorted(cands, key=lambda d: len(cands[d]))
    while len(pairs) < n:
        progressed = False
        for dim in order:
            if len(pairs) >= n:
                break
            if taken.get(dim, 0) >= 3:
                continue
            while cands.get(dim):
                _pref, _ng, _ns, lo, hi, d, share, gap = cands[dim].pop(0)
                if lo["paper_id"] in used or hi["paper_id"] in used:
                    continue
                used.update({lo["paper_id"], hi["paper_id"]})
                taken[d] = taken.get(d, 0) + 1
                diffs = {k: hi["loss"][k] - lo["loss"][k] for k in METRICS}
                pairs.append({"lo": lo, "hi": hi, "dim": d,
                              "gap": round(gap, 4), "share": round(share, 3),
                              "diffs": diffs})
                progressed = True
                break
        if not progressed:
            break
    return pairs


def build(n: int = N_PAIRS) -> int:
    random.seed(20261028)
    os.makedirs(SHEET, exist_ok=True)
    pairs = _pick_pairs(_pool(), n)
    if not pairs:
        print("选不出满足条件的页对")
        return 1
    cards, out = [], []
    for i, pr in enumerate(pairs, 1):
        imgs = {}
        for side, item in (("a", pr["lo"]), ("b", pr["hi"])):
            pdf = os.path.join(PDFDIR, item["case_id"].replace("/", "__") + ".pdf")
            got, err = visual.render_pages(pdf, SHEET, dpi=90,
                                           first=item["page"], last=item["page"],
                                           prefix=f"q{i:02d}{side}")
            if err or not got:
                print("render fail", pdf, err)
                break
            imgs[side] = os.path.basename(got[0])
        if len(imgs) < 2:
            continue
        # 左右随机：left/right 与 a/b 的映射独立随机
        flip = random.random() < 0.5
        left, right = ("a", "b") if not flip else ("b", "a")
        cards.append({"pair": i, "left": imgs[left], "right": imgs[right]})
        out.append({"pair": i, "left_side": left, "right_side": right,
                    "a": {"case_id": pr["lo"]["case_id"], "venue": pr["lo"]["venue"],
                          "column": pr["lo"]["column"],
                          "page": pr["lo"]["page"], "score": pr["lo"]["score"],
                          "loss": pr["lo"]["loss"]},
                    "b": {"case_id": pr["hi"]["case_id"], "venue": pr["hi"]["venue"],
                          "column": pr["hi"]["column"],
                          "page": pr["hi"]["page"], "score": pr["hi"]["score"],
                          "loss": pr["hi"]["loss"]},
                    "dominant_dim": pr["dim"], "gap": pr["gap"],
                    "dominance": pr["share"]})
    with open(os.path.join(WORK, "pairs.json"), "w", encoding="utf-8") as f:
        json.dump({"n": len(out), "metrics": METRICS, "form": "soft_metric_loss(2026-10-28)",
                   "pairs": out}, f, ensure_ascii=False, indent=2)
    with open(os.path.join(SHEET, "sheet.html"), "w", encoding="utf-8") as f:
        f.write(_html(cards))
    print(f"{len(cards)} 对 -> {os.path.join(SHEET, 'sheet.html')}")
    used = {p["paper_id"] for pr in pairs for p in (pr["lo"], pr["hi"])}
    up = os.path.join(WORK, "used_papers.json")
    prev = sorted(_used_papers() | set(used))
    with open(up, "w", encoding="utf-8") as f:
        json.dump(prev, f, ensure_ascii=False, indent=2)
    dims = {}
    for c in out:
        dims[c["dominant_dim"]] = dims.get(c["dominant_dim"], 0) + 1
    print("主导维分布:", dims)
    return 0


def _html(cards: list[dict]) -> str:
    import html as H
    rows = []
    for c in cards:
        rows.append(f"""
  <div class="pair" id="q{c['pair']}">
    <div class="ph">第 {c['pair']} 对 / 共 {len(cards)} 对</div>
    <div class="two">
      <div class="side"><img src="{H.escape(c['left'])}"></div>
      <div class="side"><img src="{H.escape(c['right'])}"></div>
    </div>
    <div class="opts">
      <label><input type="radio" name="q{c['pair']}" value="left">左页更好</label>
      <label><input type="radio" name="q{c['pair']}" value="right">右页更好</label>
      <label><input type="radio" name="q{c['pair']}" value="same">差不多</label>
    </div>
  </div>""")
    return f"""<!doctype html><html lang="zh"><meta charset="utf-8">
<title>排版成对比较（{len(cards)} 对）</title>
<style>
 body{{font-family:system-ui,sans-serif;margin:20px;background:#f6f6f7;color:#1d1d1f}}
 h1{{font-size:18px;margin:0 0 6px}} p.lead{{font-size:13px;color:#555;max-width:880px}}
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
<h1>排版成对比较（Step 2-c）</h1>
<p class="lead">每题左右各一页，点一个即可：哪一页**排版**更好？只看版面——留白是否得当、
有没有大片空洞、图文是否孤立或挤成一片、上下是否失衡。不用管内容质量、不用管颜色深浅、
不用管页边距宽窄是否与别的会议不同。拿不准就选「差不多」，也算有效回答。</p>
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
  const data={{ranker:'user',ts:new Date().toISOString(),
    answers:Object.keys(o).map(k=>({{pair:+k,choice:o[k]}}))}};
  const blob=new Blob([JSON.stringify(data,null,2)],{{type:'application/json'}});
  const a=document.createElement('a');a.href=URL.createObjectURL(blob);
  a.download='answers.json';a.click();
  document.getElementById('msg').textContent='已导出 answers.json';
}}
</script></html>"""


def _binom_one_sided(hits: int, n: int) -> float:
    """P(X >= hits | p=0.5)，精确二项尾部。"""
    if n <= 0:
        return 1.0
    tail = sum(math.comb(n, k) for k in range(hits, n + 1)) / (2 ** n)
    return round(min(1.0, tail), 4)


def import_answers(path: str, out_name: str = "result.json") -> int:
    pj = json.load(open(os.path.join(WORK, "pairs.json"), encoding="utf-8"))
    ans = json.load(open(path, encoding="utf-8"))
    got = {int(a["pair"]): a["choice"] for a in ans.get("answers", [])}
    use = [p for p in pj["pairs"] if p["pair"] in got]
    if not use:
        print("答案里没有可用配对")
        return 1
    hits = ties = 0
    per_dim: dict[str, list[int]] = {}
    detail = []
    for p in use:
        ch = got[p["pair"]]
        model_better = "a" if p["a"]["score"] < p["b"]["score"] else "b"
        rec = {"pair": p["pair"], "choice": ch, "model_better": model_better,
               "dominant_dim": p["dominant_dim"], "gap": p["gap"]}
        if ch == "same":
            ties += 1
            rec["agree"] = None
        else:
            human_better = p["left_side"] if ch == "left" else p["right_side"]
            ok = human_better == model_better
            rec["agree"] = ok
            hits += 1 if ok else 0
            per_dim.setdefault(p["dominant_dim"], []).append(1 if ok else 0)
        detail.append(rec)
    n = hits + sum(1 for d in detail if d["agree"] is False)
    res = {"n_pairs": len(use), "n_decided": n, "n_tied": ties,
           "accuracy": round(hits / n, 4) if n else None,
           "binom_p_one_sided": _binom_one_sided(hits, n),
           "per_dim": {k: {"n": len(v), "acc": round(sum(v) / len(v), 3)}
                       for k, v in sorted(per_dim.items())},
           "form": pj.get("form"), "detail": detail}
    with open(os.path.join(WORK, out_name), "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    print(json.dumps({k: v for k, v in res.items() if k != "detail"},
                     ensure_ascii=False, indent=2))
    return 0


def stats() -> int:
    p = os.path.join(WORK, "result.json")
    if not os.path.isfile(p):
        print("还没有 result.json（先 --import answers.json）")
        return 1
    print(open(p, encoding="utf-8").read())
    return 0


def selftest() -> int:
    """口径自检：模型永远对的假答案 -> 准确率必须 1.0；反着选 -> 0.0。"""
    pj = json.load(open(os.path.join(WORK, "pairs.json"), encoding="utf-8"))
    good, bad = [], []
    for p in pj["pairs"]:
        better = "a" if p["a"]["score"] < p["b"]["score"] else "b"
        # left_side/right_side 记的是“该位置放的是 a 还是 b”
        side = "left" if p["left_side"] == better else "right"
        other = "right" if side == "left" else "left"
        good.append({"pair": p["pair"], "choice": side})
        bad.append({"pair": p["pair"], "choice": other})
    for name, arr, want in (("good", good, 1.0), ("bad", bad, 0.0)):
        tmp = os.path.join(WORK, f"_selftest_{name}.json")
        json.dump({"ranker": "selftest", "answers": arr}, open(tmp, "w", encoding="utf-8"))
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()):
            import_answers(tmp, out_name="_selftest_result.json")
        acc = json.load(open(os.path.join(WORK, "_selftest_result.json"),
                             encoding="utf-8"))["accuracy"]
        os.remove(tmp)
        os.remove(os.path.join(WORK, "_selftest_result.json"))
        print(f"selftest/{name}: accuracy={acc} (期望 {want})")
        if acc != want:
            return 1
    print("selftest ok")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--n", type=int, default=N_PAIRS)
    ap.add_argument("--import", dest="imp")
    ap.add_argument("--stats", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.build:
        return build(a.n)
    if a.imp:
        return import_answers(a.imp)
    if a.stats:
        return stats()
    if a.selftest:
        return selftest()
    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
