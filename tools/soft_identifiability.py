#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A_soft 指标**可辨识性体检**（阶段 16，2026-11-02）。

回答一个问题：现在 A_soft 的 8 个指标里，哪些真的在区分「排版好坏」，
哪些只是在量「这页是什么类型」，哪些根本是常量。

判据（全部可复现，不掺主观）：
  1. 单篇内变异：同一篇论文内该指标的取值是否有变化（无变化 → 死数）
  2. 跨篇变异：不同论文之间是否有差别（只在篇间变、篇内不变的 → 文档指纹，不是页质量）
  3. 冗余：与其它指标的 Spearman |ρ| ≥ 0.8 → 同一件事算两遍
  4. 角色混淆：按像素角色分层后，若变异主要来自「页类型」（整页图/空白页）
     而不是同类型页内部差异 → 这个指标需要分层，否则在量页类型

用法：
    python3 tools/soft_identifiability.py --papers 90
    python3 tools/soft_identifiability.py --papers 90 --no-cache   # 重新渲染
产物：
    metrics/soft_identifiability_<date>.json     原始统计
    metrics/soft_identifiability_<date>.md       判定表（人读）
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import glob
import json
import os
import statistics as st
import sys
import tempfile
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from texopt import score as S  # noqa: E402
from texopt import visual  # noqa: E402

PDF_DIR = os.path.join(ROOT, "datasets", "conf-specs", "sources", "raw", "pdfs")
CACHE_DIR = os.path.join(ROOT, "datasets", "conf-specs", "workbench-soft", "cache")
METRICS = ["ink_ratio", "max_gap", "top_bottom_ratio", "top_blank",
           "bottom_blank", "left_blank", "right_blank", "band"]


# ------------------------------------------------------------------ 基础统计

def spearman(a: list, b: list) -> float:
    n = len(a)
    if n < 3:
        return float("nan")

    def rank(v):
        order = sorted(range(n), key=lambda i: v[i])
        r = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and v[order[j + 1]] == v[order[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1
            for k in range(i, j + 1):
                r[order[k]] = avg
            i = j + 1
        return r

    ra, rb = rank(a), rank(b)
    ma, mb = sum(ra) / n, sum(rb) / n
    sa = sum((x - ma) ** 2 for x in ra) ** 0.5
    sb = sum((x - mb) ** 2 for x in rb) ** 0.5
    if sa == 0 or sb == 0:
        return float("nan")
    return sum((x - ma) * (y - mb) for x, y in zip(ra, rb)) / (sa * sb)


def cv(vals: list) -> float:
    vals = [v for v in vals if v is not None]
    if len(vals) < 2:
        return 0.0
    m = st.mean(vals)
    if m == 0:
        return 0.0
    return st.pstdev(vals) / abs(m)


# ------------------------------------------------------------------ 采样渲染

def pick_papers(n: int) -> list:
    pdfs = sorted(glob.glob(os.path.join(PDF_DIR, "*.pdf")))
    if not pdfs:
        return []
    if len(pdfs) <= n:
        return pdfs
    step = len(pdfs) / float(n)
    return [pdfs[int(i * step)] for i in range(n)]


def paper_rows(pdf: str, dpi: int, use_cache: bool) -> list:
    os.makedirs(CACHE_DIR, exist_ok=True)
    key = os.path.basename(pdf).replace(".pdf", "")[:120]
    cache = os.path.join(CACHE_DIR, f"{key}.json")
    if use_cache and os.path.isfile(cache):
        try:
            return json.load(open(cache, encoding="utf-8"))
        except Exception:
            pass
    with tempfile.TemporaryDirectory() as td:
        res = visual.analyze_pdf(pdf, td, dpi=dpi)
    pages = [p for p in (res.get("pages") or []) if "error" not in p]
    total = len(pages)
    inks = sorted(p.get("ink_ratio") for p in pages if p.get("ink_ratio") is not None)
    med = inks[len(inks) // 2] if inks else None
    rows = []
    for i, p in enumerate(pages, start=1):
        role = visual.pixel_role(p, i, total, doc_median_ink=med)
        rows.append({**{k: p.get(k) for k in METRICS},
                     "page": i, "role": role["role"], "flags": role["flags"]})
    if rows:
        with open(cache, "w", encoding="utf-8") as f:
            json.dump(rows, f)
    return rows


# ------------------------------------------------------------------ 统计与判定

def analyse(per_paper: dict, strata_role: str = "body") -> dict:
    out = {"papers": len(per_paper), "pages": sum(len(v) for v in per_paper.values())}
    # 1) 单篇内变异（每篇各算一次，取中位）
    within_cv, within_range = {}, {}
    for m in METRICS:
        cvs, rngs = [], []
        for rows in per_paper.values():
            vals = [r[m] for r in rows if r.get(m) is not None]
            if len(vals) < 2:
                continue
            cvs.append(cv(vals))
            rngs.append(max(vals) - min(vals))
        within_cv[m] = round(st.median(cvs), 4) if cvs else None
        within_range[m] = round(st.median(rngs), 4) if rngs else None
    # 2) 跨篇变异（每篇均值之间的离散度）
    between = {}
    for m in METRICS:
        means = []
        for rows in per_paper.values():
            vals = [r[m] for r in rows if r.get(m) is not None]
            if vals:
                means.append(st.mean(vals))
        between[m] = round(cv(means), 4) if len(means) >= 2 else None
    # 2.5) **损失极差**：真正决定 A_soft 变化的量（不是原始值，而是 loss）
    loss_range, loss_range_body = {}, {}
    for m in METRICS:
        spec = S.SOFT_SPEC.get(m) or {}
        if not spec.get("w"):
            loss_range[m] = loss_range_body[m] = None
            continue
        rngs, rngs_body = [], []
        for rows in per_paper.values():
            ls = [S.soft_metric_loss(m, r.get(m)) for r in rows]
            ls = [x for x in ls if x is not None]
            if len(ls) >= 2:
                rngs.append(max(ls) - min(ls))
            lsb = [S.soft_metric_loss(m, r.get(m)) for r in rows
                   if r["role"] == strata_role]
            lsb = [x for x in lsb if x is not None]
            if len(lsb) >= 2:
                rngs_body.append(max(lsb) - min(lsb))
        loss_range[m] = round(st.median(rngs), 4) if rngs else None
        loss_range_body[m] = round(st.median(rngs_body), 4) if rngs_body else None
    out.update({"loss_range": loss_range, "loss_range_body": loss_range_body})

    # 3) 角色构成 + 分层后的篇内变异
    role_hist: dict = {}
    for rows in per_paper.values():
        for r in rows:
            role_hist[r["role"]] = role_hist.get(r["role"], 0) + 1
    strat_cv, strat_n = {}, {}
    for m in METRICS:
        cvs = []
        n_pages = 0
        for rows in per_paper.values():
            vals = [r[m] for r in rows
                    if r["role"] == strata_role and r.get(m) is not None]
            n_pages += len(vals)
            if len(vals) >= 2:
                cvs.append(cv(vals))
        strat_cv[m] = round(st.median(cvs), 4) if cvs else None
        strat_n[m] = n_pages
    # 4) 冗余（全体页、按角色分层各算一遍）
    def corr_matrix(rows_all):
        cols = {m: [r[m] for r in rows_all if r.get(m) is not None] for m in METRICS}
        mat = {}
        for i, a in enumerate(METRICS):
            for b in METRICS[i + 1:]:
                if len(cols[a]) != len(cols[b]) or len(cols[a]) < 5:
                    continue
                mat[f"{a}|{b}"] = round(spearman(cols[a], cols[b]), 3)
        return mat

    all_rows = [r for rows in per_paper.values() for r in rows]
    body_rows = [r for r in all_rows if r["role"] == strata_role]
    corr_all = corr_matrix(all_rows)
    corr_body = corr_matrix(body_rows)
    redundant = sorted([k for k, v in corr_body.items()
                        if isinstance(v, float) and abs(v) >= 0.8])
    out.update({
        "within_doc_cv": within_cv,
        "within_doc_range": within_range,
        "between_doc_cv": between,
        "role_hist": role_hist,
        "stratified": {"role": strata_role, "within_doc_cv": strat_cv,
                       "pages": strat_n},
        "corr_all": corr_all,
        "corr_body": corr_body,
        "redundant_pairs_body": redundant,
    })
    # 5) 判定
    verdict = {}
    for m in METRICS:
        w_cv = within_cv.get(m)
        s_cv = strat_cv.get(m)
        b = between.get(m)
        lr = loss_range.get(m)
        lrb = loss_range_body.get(m)
        if m == "band":
            verdict[m] = {"call": "threshold-only",
                          "why": "权重已为 0；但高值端（≥0.40）仍是 giant_content 的判据，"
                                 "属阈值型指标，不应做连续分"}
            continue
        if lr is None or lr < 0.10:
            verdict[m] = {"call": "drop",
                          "why": f"篇内损失极差仅 {lr}（<0.10）→ 近似常数，"
                                 f"同稿比较里自动抵消，只抬高 A 的绝对值"}
            continue
        redundant_with = [p.split("|")[0] if p.split("|")[1] == m else p.split("|")[1]
                          for p in redundant if m in p.split("|")]
        if redundant_with and s_cv is not None and s_cv < 0.05:
            verdict[m] = {"call": "merge",
                          "why": f"与 {redundant_with} 秩相关 ≥0.8，且分层后变异很小"
                                 f"（CV={s_cv}）→ 同一件事算两遍"}
            continue
        if lrb is not None and lr and lrb < 0.5 * lr:
            verdict[m] = {"call": "stratify",
                          "why": f"损失极差 {lr} 里大半来自页类型：只看 "
                                 f"{strata_role} 页只剩 {lrb} → 必须按角色分层"}
            continue
        verdict[m] = {"call": "keep",
                      "why": f"篇内损失极差 {lr}（分层后 {lrb}）：能真正挪动 A"}
    out["verdict"] = verdict
    return out


def md_report(res: dict, args) -> str:
    L = [f"# A_soft 指标可辨识性体检（{date.today()}）\n",
         f"- 样本：**{res['papers']} 篇 / {res['pages']} 页**，dpi={args.dpi}，"
         f"像素层，角色用 pixel-proxy 粗分",
         f"- 角色构成：{', '.join(f'{k}×{v}' for k, v in sorted(res['role_hist'].items()))}",
         "", "## 1　判定表\n",
         "| 指标 | 篇内损失极差 | 分层后(body) | 原始篇内 CV | 跨篇 CV | 判定 | 依据 |",
         "|---|---|---|---|---|---|---|"]
    for m in METRICS:
        v = res["verdict"][m]
        L.append(f"| `{m}` | {res['loss_range'][m]} | {res['loss_range_body'][m]} "
                 f"| {res['within_doc_cv'][m]} | {res['between_doc_cv'][m]} "
                 f"| **{v['call']}** | {v['why']} |")
    L += ["", "## 2　冗余（body 页，Spearman |ρ| ≥ 0.8）\n"]
    red = res["redundant_pairs_body"]
    L.append("- 无" if not red else "\n".join(
        f"- `{p.replace('|', '` × `')}` = {res['corr_body'][p]}" for p in red))
    L += ["", "## 3　全页秩相关矩阵（含页类型混杂）\n",
          "| 对 | ρ |", "|---|---|"]
    for p, v in sorted(res["corr_all"].items(),
                       key=lambda kv: -abs(kv[1]) if isinstance(kv[1], float) else 0)[:12]:
        L.append(f"| `{p.replace('|', '` × `')}` | {v} |")
    L += ["", "## 4　读法\n",
          "- `drop`：篇内几乎不变，同稿比较里是常数 → 只是把 A 的绝对值抬高",
          "- `merge`：与别的指标重复，算两遍等于偷偷加权",
          "- `stratify`：变异主要来自页类型（整页图/空白页），必须按角色分层",
          "- `threshold-only`：连续分没用，但高值端的阈值判据仍有效（门控/报告）",
          "- `keep`：同角色内有连续变异，可进 A_soft 连续分"]
    return "\n".join(L) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--papers", type=int, default=90)
    ap.add_argument("--dpi", type=int, default=50)
    ap.add_argument("--strata-role", default="body")
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--workers", type=int, default=4,
                    help="并行渲染进程数（渲染是子进程，线程池即可）")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    pdfs = pick_papers(args.papers)
    if not pdfs:
        print(f"没有语料 PDF：{PDF_DIR}")
        return 1
    print(f"取样 {len(pdfs)} 篇（共 {len(glob.glob(os.path.join(PDF_DIR, '*.pdf')))} 篇）")
    per_paper = {}
    done = 0
    with cf.ThreadPoolExecutor(max_workers=max(1, args.workers)) as ex:
        futs = {ex.submit(paper_rows, pdf, args.dpi, not args.no_cache): pdf
                for pdf in pdfs}
        for fut in cf.as_completed(futs):
            pdf = futs[fut]
            done += 1
            try:
                rows = fut.result()
            except Exception as exc:
                print(f"  [{done}/{len(pdfs)}] 失败 {os.path.basename(pdf)[:40]}: {exc}")
                continue
            name = os.path.basename(pdf)[:60]
            if rows:
                per_paper[name] = rows
            print(f"  [{done}/{len(pdfs)}] {len(rows):3d} 页  {name}", flush=True)

    res = analyse(per_paper, args.strata_role)
    res.update({"sample_papers": len(pdfs), "dpi": args.dpi,
                "source": PDF_DIR, "role_source": "pixel-proxy"})
    stamp = date.today().strftime("%Y%m%d")
    out_json = args.out or os.path.join(ROOT, "metrics", f"soft_identifiability_{stamp}.json")
    out_md = out_json.replace(".json", ".md")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    with open(out_md, "w", encoding="utf-8") as f:
        f.write(md_report(res, args))
    print("\n" + md_report(res, args))
    print(f"产物：{out_json}\n      {out_md}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
