#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""make_pairs.py —— 阶段 7 步骤三：生成「人类成对比较」采集包（方案 10.3）。

为什么需要这个工具：步骤三要有**人来判「哪页更顺眼」**，但每对比较必须附上
两侧的**逐维归一化带外损失**（`aesthetic_weights.json` 的那 6 个维），否则
Bradley-Terry 拟合不了。人工去翻指标既费时又容易错，所以这里：

  1. 从缓存页指标里按角色（默认 body）挑页，算好逐维归一化损失；
  2. 配对时保证「**可分性**」：一侧主导维明显、其余维接近（否则权重不可辨识），
     并混合「都不错」与「都差」两类（防止退化成「谁最烂」检测器）；
  3. 把两页渲染成 PNG，生成一个**离线 HTML 打分表**（左右随机，避免位置偏差）；
  4. 人只填「左 / 右 / 看不出」→ `--import` 把答案合回 `human/pairs.json`。

用法：

    python3 tools/make_pairs.py --sheet          # 生成打分表（默认 30 对）
    # 人在浏览器里打开 workbench-eval/pairs_sheet/sheet.html 填写，复制出 answers JSON
    python3 tools/make_pairs.py --import <answers.json>   # 写 human/pairs.json
    python3 tools/make_pairs.py --stats          # 看覆盖度（对数/论文数/维分布）
    python3 tools/calibrate_weights.py --pairs human/pairs.json --apply

诚实边界：本工具只**准备与整理**数据；判断必须来自人。未采集时
`human/pairs.json` 不存在，`calibrate_weights.py` 如实记 null，不伪造。
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DS = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(DS))
sys.path.insert(0, ROOT)

PAGES = os.path.join(DS, "metrics", "pages")
PDFS = os.path.join(DS, "sources", "raw", "pdfs")
HUMAN = os.path.join(DS, "human")
SHEET = os.path.join(DS, "workbench-eval", "pairs_sheet")
OUT_PAIRS = os.path.join(HUMAN, "pairs.json")


def _p(m):
    print(m, flush=True)


def weight_dims() -> list[str]:
    from texopt import shadow as SH
    b = (SH.load_profile() or {}).get("weights") or {}
    dims = sorted((b.get("by_dim") or {}).keys())
    return dims


def collect_pages(dims, role="body"):
    """缓存页指标 -> [{sid, venue, layout, pdf, page, dims:{...}, total}]（只取指定角色）。"""
    from texopt import aesthetic as AE
    from texopt import shadow as SH
    prof = SH.load_profile()
    rows = []
    for fn in sorted(os.listdir(PAGES)):
        if not fn.endswith(".json"):
            continue
        try:
            with open(os.path.join(PAGES, fn), encoding="utf-8") as f:
                doc = json.load(f)
        except Exception:
            continue
        meta = doc.get("doc") or {}
        pdf = meta.get("pdf")
        venue, layout = meta.get("venue"), meta.get("layout")
        if not pdf or not os.path.isfile(os.path.join(PDFS, pdf)):
            continue
        det = None
        for p in doc.get("pages") or []:
            if (p.get("role") or "") != role:
                continue
            if det is None:
                picked = AE.pick_detector(prof, venue, role, layout, drop=[])
                det = picked[0] if picked else None
                if det is None:
                    break
            s = det.score_page(p)
            losses = s.get("losses") or {}
            vals = {}
            for d in dims:
                if d in losses:
                    vals[d] = round(float(det.norm_loss(d, losses[d])), 4)
            if len(vals) < 3:
                continue
            rows.append({"sid": fn[:-5], "venue": venue, "layout": layout, "pdf": pdf,
                         "page": p.get("page"), "dims": vals,
                         "total": round(sum(vals.values()), 4)})
    return rows


def _score_pair(a, b, dims, min_delta):
    """可分性打分：主导维差 Δ1 要够大，且与次大差 Δ2 拉开。"""
    ds = sorted(((d, abs(a["dims"].get(d, 0.0) - b["dims"].get(d, 0.0))) for d in dims),
                key=lambda x: -x[1])
    d1, delta1 = ds[0]
    _, delta2 = ds[1] if len(ds) > 1 else ("", 0.0)
    if delta1 < min_delta:
        return None
    if delta2 > 0.5 * delta1 and (delta1 - delta2) < 0.35:
        return None                       # 两个维同时大差 → 权重不可辨识
    return {"lead_dim": d1, "lead_delta": round(delta1, 4),
            "second_delta": round(delta2, 4)}


def pick_pairs(rows, dims, *, n_pairs=30, max_per_paper=6, min_papers=6,
               min_delta=0.6, seed=7):
    """同一篇论文内配对（同 venue/版面，判的是版面质量），控制多样性。"""
    rnd = random.Random(seed)
    by_sid = {}
    for r in rows:
        by_sid.setdefault(r["sid"], []).append(r)
    totals = sorted(r["total"] for r in rows)
    thr = totals[len(totals) // 2] if totals else 0.0
    cands = []
    for sid, group in by_sid.items():
        if len(group) < 4:
            continue
        pair = []
        seen = set()
        idxs = [(i, j) for i in range(len(group)) for j in range(i + 1, len(group))]
        rnd.shuffle(idxs)
        for i, j in idxs:
            a, b = group[i], group[j]
            if a["page"] in seen or b["page"] in seen:
                continue
            sc = _score_pair(a, b, dims, min_delta)
            if not sc:
                continue
            good = (a["total"] < thr and b["total"] < thr)
            bad = (a["total"] >= thr and b["total"] >= thr)
            # 两侧是否都有非零偏差：全零（完全在带内）的一侧对权重标定贡献很小，
            # 所以把 “一侧干净” 单独标出来，选对时优先让**两侧都有偏差**。
            ma = max(a["dims"].values()) if a["dims"] else 0.0
            mb = max(b["dims"].values()) if b["dims"] else 0.0
            if ma < 0.05 and mb < 0.05:
                continue
            if ma < 0.05 or mb < 0.05:
                kind = "one-clean"
            elif good or bad:
                kind = "both-good" if good else "both-bad"
            else:
                kind = "mixed"
            sc.update({"sid": sid, "a": a, "b": b, "kind": kind})
            pair.append(sc)
            seen.add(a["page"])
            seen.add(b["page"])
            if len(pair) >= max_per_paper:
                break
        pair.sort(key=lambda x: -x["lead_delta"])
        cands.extend(pair)

    rnd.shuffle(cands)
    # 三类尽量均衡（方案 10.3 采集建议：既要有“都不错”，也要有“都差”）；
    # 优先两侧都有偏差的（信息量最大），再按 one-clean 补齐。
    both = [c for c in cands if c["kind"] != "one-clean"]
    bad = [c for c in both if c["kind"] == "both-bad"]
    good = [c for c in both if c["kind"] == "both-good"]
    mix = [c for c in both if c["kind"] == "mixed"]
    one_clean = [c for c in cands if c["kind"] == "one-clean"]
    third = max(1, n_pairs // 3)
    chosen = bad[:third] + good[:third] + mix[:third]
    for pool in (bad[third:], mix[third:], good[third:], one_clean):
        if len(chosen) >= n_pairs:
            break
        chosen += pool[: n_pairs - len(chosen)]
    chosen = chosen[:n_pairs]
    while len({c["sid"] for c in chosen}) < min_papers and len(chosen) < len(cands):
        for c in cands:
            if c in chosen:
                continue
            if c["sid"] not in {x["sid"] for x in chosen}:
                chosen.append(c)
                break
        else:
            break
    return chosen


def render_pair(i, c, dpi=72):
    """渲两页成 PNG。注意：Windows 原生 pdftoppm 只认**真实盘符路径**，
    所以必须在 PDF 所在目录下用**文件名**调用，再把产物搬回来（同 visual.py 的做法）。"""
    from texopt import engine
    ppm = engine.pdftoppm_path()
    os.makedirs(SHEET, exist_ok=True)
    out = {}
    for tag, side in (("a", c["a"]), ("b", c["b"])):
        dst = os.path.join(SHEET, f"p{i}_{tag}.png")
        if not os.path.isfile(dst):
            src_dir = os.path.dirname(os.path.join(PDFS, side["pdf"]))
            name = os.path.basename(side["pdf"])
            tmp = f"_pairsheet_tmp_{i}{tag}"
            cmd = [ppm, "-f", str(side["page"]), "-l", str(side["page"]),
                   "-r", str(dpi), "-png", "-singlefile", name, tmp]
            try:
                subprocess.run(cmd, cwd=src_dir, check=False,
                               capture_output=True, timeout=180)
            except Exception:
                pass
            made = os.path.join(src_dir, tmp + ".png")
            if os.path.isfile(made):
                shutil.move(made, dst)
            elif os.path.isfile(made + ".pgm"):
                os.remove(made + ".pgm")
        if os.path.isfile(dst):
            out[tag] = os.path.basename(dst)
    return out


def write_sheet(pairs, dims, path):
    rows_html = []
    for i, c in enumerate(pairs, 1):
        disp = "ab" if i % 2 else "ba"          # 左右随机，避免位置偏差
        left, right = ("a", "b") if disp == "ab" else ("b", "a")
        img = render_pair(i, c)
        if len(img) < 2:
            continue
        fn = lambda k: img[k]                           # noqa: E731
        rows_html.append(f"""
 <section class="pair" data-pair="p{i}" data-disp="{disp}">
  <h3>第 {i} 对　<span class="meta">{c['sid']}　主导维 {c['lead_dim']}　Δ={c['lead_delta']}</span></h3>
  <div class="imgs">
   <figure><img src="{fn(left)}"><figcaption>左</figcaption></figure>
   <figure><img src="{fn(right)}"><figcaption>右</figcaption></figure>
  </div>
  <div class="opts">
   <label><input type="radio" name="p{i}" value="L"> 左边更顺眼</label>
   <label><input type="radio" name="p{i}" value="R"> 右边更顺眼</label>
   <label><input type="radio" name="p{i}" value="?"> 看不出差别 / 跳过</label>
   <input class="note" name="note{i}" placeholder="可选：理由（如“左页下半空太多”）">
  </div>
 </section>""")
    html = """<!doctype html><html lang="zh"><meta charset="utf-8">
<title>阶段 7 步骤三 · 人类成对比较</title>
<style>
 body{font-family:system-ui,-apple-system,"Noto Sans CJK SC",sans-serif;margin:24px;background:#fafafa;color:#222}
 .pair{background:#fff;border:1px solid #e3e3e3;border-radius:10px;padding:14px 16px;margin:18px 0}
 .imgs{display:flex;gap:14px;align-items:flex-start}
 figure{margin:0;flex:1;text-align:center}
 img{width:100%;border:1px solid #ddd;border-radius:6px;background:#fff}
 figcaption{font-size:12px;color:#666;margin-top:4px}
 .opts{margin-top:10px;display:flex;gap:18px;flex-wrap:wrap;align-items:center;font-size:14px}
 .note{flex:1;min-width:220px;padding:4px 6px;border:1px solid #ccc;border-radius:6px}
 .meta{color:#888;font-weight:400;font-size:12px}
 textarea{width:100%;height:180px;font-family:ui-monospace,monospace;font-size:12px}
</style>
<h1>阶段 7 步骤三 · 人类成对比较（谁更顺眼）</h1>
<p>每对是同一篇论文里的两页。请只看<strong>版面</strong>（留白/密度/上下平衡/对齐），
不要考虑内容对错。选完所有对你觉得有把握的，然后把下面框里的 JSON 复制出来，
存成文件后再 <code>python3 tools/make_pairs.py --import &lt;该文件&gt;</code>。</p>
""" + "".join(rows_html) + """
<h2>结果 JSON（复制到 answers.json）</h2>
<textarea id="out" readonly></textarea>
<script>
function refresh(){
  const o={};
  document.querySelectorAll('section.pair').forEach(s=>{
    const picked=s.querySelector('input[type=radio]:checked');
    if(!picked||picked.value==='?') return;
    const n=s.querySelector('.note');
    o[s.dataset.pair]={side:picked.value, note:(n&&n.value)||''};
  });
  document.getElementById('out').value=JSON.stringify(o,null,1);
}
document.addEventListener('change',refresh);
document.addEventListener('keyup',refresh);
refresh();
</script>
</html>"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    # 侧车：每对的真实顺序 + 逐维损失（导入时用，不给人看）
    side = {"schema": "stage7.pairs_sheet.v1", "dims": dims, "dpi": 72, "pairs": {}}
    for i, c in enumerate(pairs, 1):
        side["pairs"][f"p{i}"] = {
            "sid": c["sid"], "kind": c["kind"], "lead_dim": c["lead_dim"],
            "display": "ab" if i % 2 else "ba",
            "a": {"page": c["a"]["page"], "pdf": c["a"]["pdf"], "dims": c["a"]["dims"]},
            "b": {"page": c["b"]["page"], "pdf": c["b"]["pdf"], "dims": c["b"]["dims"]},
        }
    with open(os.path.join(SHEET, "sheet.json"), "w", encoding="utf-8") as f:
        json.dump(side, f, ensure_ascii=False, indent=1)


def do_import(answers_path):
    """answers: {"p1": {"side":"L"|"R", "note": "..."} , ...} -> human/pairs.json"""
    with open(os.path.join(SHEET, "sheet.json"), encoding="utf-8") as f:
        sheet = json.load(f)
    with open(answers_path, encoding="utf-8") as f:
        ans = json.load(f)
    if isinstance(ans, dict) and "answers" in ans:
        ans = ans["answers"]
    out = []
    for pid, rec in (ans or {}).items():
        c = (sheet["pairs"] or {}).get(pid)
        if not c:
            _p(f"  （跳过 {pid}：打分表里没有这一对）")
            continue
        side = str((rec or {}).get("side") or "").strip().upper()
        if side not in ("L", "R"):
            continue
        # L/R 是**显示**位置 -> 映射回 a/b
        order = {"ab": {"L": "a", "R": "b"}, "ba": {"L": "b", "R": "a"}}[c["display"]]
        winner = order[side]
        out.append({"a": c["a"]["dims"], "b": c["b"]["dims"], "winner": winner,
                    "note": (rec or {}).get("note") or "",
                    "_sid": c["sid"], "_pages": [c["a"]["page"], c["b"]["page"]]})
    n = len(out)
    if n == 0:
        _p("没有有效答案（side 必须是 L 或 R）——未写出 pairs.json")
        return 1
    os.makedirs(HUMAN, exist_ok=True)
    with open(OUT_PAIRS, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    _p(f"写出 {OUT_PAIRS}：{n} 对（论文 {len({x['_sid'] for x in out})} 篇）")
    if n < 8:
        _p("  注意：样本 < 8 对，Bradley-Terry 按口径**不给结论**（会记 null）")
    _p("下一步：cd datasets/conf-specs && python3 tools/calibrate_weights.py "
       "--pairs human/pairs.json --apply")
    return 0


def do_stats():
    if not os.path.isfile(OUT_PAIRS):
        _p(f"{OUT_PAIRS} 不存在 —— 还没采集（工具不会伪造数据）")
        return 0
    with open(OUT_PAIRS, encoding="utf-8") as f:
        rows = json.load(f)
    sids = {r.get("_sid") for r in rows if r.get("_sid")}
    dims = sorted({d for r in rows for d in (r.get("a") or {})})
    win = {"a": 0, "b": 0}
    for r in rows:
        win[r.get("winner")] = win.get(r.get("winner"), 0) + 1
    _p(f"对数 {len(rows)}　论文 {len(sids)} 篇　维 {dims}")
    _p(f"胜负分布 {win}")
    for d in dims:
        da = [abs((r.get("a") or {}).get(d, 0) - (r.get("b") or {}).get(d, 0)) for r in rows]
        _p(f"  {d:32s} 两侧差值 中位 {sorted(da)[len(da)//2]:.4f}")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sheet", action="store_true", help="生成打分表")
    ap.add_argument("--import", dest="import_path", default=None, help="导入答案 -> human/pairs.json")
    ap.add_argument("--stats", action="store_true", help="看已采集数据的覆盖度")
    ap.add_argument("--pairs", type=int, default=30)
    ap.add_argument("--role", default="body")
    ap.add_argument("--min-delta", type=float, default=0.6)
    ap.add_argument("--max-per-paper", type=int, default=6)
    ap.add_argument("--dpi", type=int, default=72)
    args = ap.parse_args()
    if args.import_path:
        return do_import(args.import_path)
    if args.stats:
        return do_stats()
    if not args.sheet:
        ap.print_help()
        return 0
    dims = weight_dims()
    if not dims:
        _p("档案里没有已启用的权重维（aesthetic_weights.json）——先跑阶段 7 步骤二")
        return 1
    _p(f"取页（角色 {args.role}）… 判定维 {len(dims)} 个")
    rows = collect_pages(dims, role=args.role)
    _p(f"  候选页 {len(rows)} 页 / {len({r['sid'] for r in rows})} 篇")
    pairs = pick_pairs(rows, dims, n_pairs=args.pairs,
                       max_per_paper=args.max_per_paper, min_delta=args.min_delta)
    _p(f"  选中 {len(pairs)} 对（论文 {len({c['sid'] for c in pairs})} 篇）")
    write_sheet(pairs, dims, os.path.join(SHEET, "sheet.html"))
    _p(f"打分表：{os.path.join(SHEET, 'sheet.html')}")
    _p("在浏览器里打开它（Windows 侧：D:\\桌面\\texopt\\datasets\\conf-specs\\"
       "workbench-eval\\pairs_sheet\\sheet.html）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
