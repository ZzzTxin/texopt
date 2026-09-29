# -*- coding: utf-8 -*-
"""审美档案构建（阶段 2）：把全库 page_metrics.v1 汇总成「正常范围」。

产出 `aesthetic_profile.v1`：

```
levels.venue_role["cvpr|body"] = {
    n_papers, n_pages, confidence,
    metrics: { "density.coverage_text": {p10,p25,p50,p75,p90,mean,n,ci_p50,ci_p90}, ... }
}
levels.role["body"]  = ...   # 全体会议按角色（跨会议通用档）
levels.venue["cvpr"] = ...   # 会议内全角色（仅参考，不比）
```

统计口径（**都要写清楚，否则不可复现**）：

* 分位：按**页**取分位（线性插值），附样本数 n。
* 置信区间：**按论文聚类的 bootstrap** —— 重采样的是**论文**而不是页。
  同一篇论文的页高度相关（同一模板、同一字号），按页重采样会把 CI 假性收窄；
  聚类 bootstrap 是这类层次数据的标准做法。
* 可信度分档：n_papers ≥ 36 → high；16–35 → medium；≤ 15 → low。
  低可信度档**不参与**异常判定（阶段 4），只作参考。

去冗余（`analyze_redundancy`）：

* Spearman 秩相关矩阵（不假设线性、对离群稳健）；
* |ρ| ≥ 阈值（默认 0.8）的指标用并查集聚成一组，每组只保留一个代表；
* PCA（纯 Python Jacobi 特征分解，对标准化后的指标）给出解释方差，
  说明"多少维才够描述版面"。

依赖：仅标准库（本机无 numpy/scipy，全部手写；都是小矩阵，性能无虞）。
"""
from __future__ import annotations

import json
import math
import os
import random
import statistics as st

SCHEMA = "aesthetic_profile.v1"
GROUPS = ("density", "ratio", "balance", "whitespace", "alignment",
          "consistency", "readability", "figure_quality")
SKIP_KEYS = {"status", "regions", "per_column", "legacy", "n_elements",
             "n_full_lines", "n_short_lines"}

# 指标方向（阶段 4 做「带外损失」时用）：band = 双向（有目标区间），low = 越低越好
DIRECTION = {
    "density.coverage_table": "band",
    "density.coverage_figure": "band",
    "density.coverage_text": "band",
    "whitespace.total_ratio": "band",
    "ratio.fig_text": "band",
    "ratio.figtab_text": "band",
    "balance.visual_centroid_y": "band",
    "alignment.left_var": "low",
    "alignment.right_var": "low",
    "alignment.center_var": "low",
    "consistency.figure_width_cv": "low",
    "consistency.caption_style_cv": "low",
    "figure_quality.aspect_outliers": "low",
}
DEFAULT_DIRECTION = "band"

QUANTS = ((0.10, "p10"), (0.25, "p25"), (0.50, "p50"),
          (0.75, "p75"), (0.90, "p90"))


# ---------------------------------------------------------------- 读数据

def page_metric_items(page: dict):
    """一页 -> [(flat_key, value)]，只取数值型、非空、非排除项。"""
    out = []
    for g in GROUPS:
        blk = page.get(g)
        if not isinstance(blk, dict):
            continue
        for k, v in blk.items():
            if k in SKIP_KEYS or isinstance(v, bool):
                continue
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                out.append((f"{g}.{k}", float(v)))
    return out


def load_pages(metrics_dir: str, index_path: str | None = None):
    """读全库 page_metrics -> (rows, papers)。

    rows: [{"paper": sid, "venue": v, "year": y, "layout": l, "role": r,
            "flags": [...], "metrics": {flat: val}}]
    papers: {sid: {"venue","year","layout","pages"}}
    """
    rows, papers, bad = [], {}, []
    for fn in sorted(os.listdir(metrics_dir)):
        if not fn.endswith(".json"):
            continue
        sid = fn[:-5]
        try:
            with open(os.path.join(metrics_dir, fn), encoding="utf-8") as f:
                doc = json.load(f)
        except Exception:                 # 半写/损坏文件（如并发写入时）跳过并记下
            bad.append(fn)
            continue
        d = doc.get("doc") or {}
        papers[sid] = {"venue": d.get("venue"), "year": d.get("year"),
                       "layout": d.get("layout"), "pages": d.get("pages")}
        for p in doc.get("pages") or []:
            rows.append({"paper": sid, "venue": d.get("venue"), "year": d.get("year"),
                         "layout": d.get("layout"), "role": p.get("role") or "unknown",
                         "flags": p.get("role_flags") or [],
                         "metrics": dict(page_metric_items(p))})
    return rows, papers, bad


# ---------------------------------------------------------------- 统计

def quantiles(values, qs=QUANTS) -> dict:
    v = sorted(values)
    n = len(v)
    if not n:
        return {}
    out = {"n": n, "mean": round(sum(v) / n, 6), "min": v[0], "max": v[-1]}
    for q, name in qs:
        out[name] = _q(v, q)
    return out


def _q(v_sorted, q: float):
    n = len(v_sorted)
    if n == 1:
        return v_sorted[0]
    pos = (n - 1) * q
    lo = int(pos)
    hi = min(lo + 1, n - 1)
    return round(v_sorted[lo] + (v_sorted[hi] - v_sorted[lo]) * (pos - lo), 6)


def cluster_bootstrap_ci(by_paper: dict, q: float = 0.5, iters: int = 300,
                         seed: int = 20260928, alpha: float = 0.05):
    """按**论文**聚类的 bootstrap 置信区间（重采样论文，不是页）。

    by_paper: {paper_id: [values]}（该层该指标下，这篇论文各页的值）
    返回 (lo, hi)；样本不足（论文数 < 5）返回 None。
    """
    ids = sorted(by_paper)
    if len(ids) < 5:
        return None
    rnd = random.Random(seed)
    stats = []
    for _ in range(iters):
        pick = [ids[rnd.randrange(len(ids))] for _ in range(len(ids))]
        vals = sorted(v for i in pick for v in by_paper[i])
        if vals:
            stats.append(_q(vals, q))
    if not stats:
        return None
    stats.sort()
    lo = stats[int(len(stats) * (alpha / 2))]
    hi = stats[min(len(stats) - 1, int(len(stats) * (1 - alpha / 2)))]
    return [round(lo, 6), round(hi, 6)]


def confidence_tier(n_papers: int) -> str:
    if n_papers >= 36:
        return "high"
    if n_papers >= 16:
        return "medium"
    return "low"


def build_stratum(rows: list[dict], with_ci: bool = True) -> dict:
    """一组页 -> {n_papers, n_pages, confidence, metrics:{...}}。"""
    by_key: dict = {}
    for r in rows:
        for k, v in r["metrics"].items():
            by_key.setdefault(k, []).append((r["paper"], v))
    metrics = {}
    for k, pairs in by_key.items():
        vals = [v for _, v in pairs]
        agg = quantiles(vals)
        if with_ci:
            bp: dict = {}
            for pid, v in pairs:
                bp.setdefault(pid, []).append(v)
            agg["ci_p50"] = cluster_bootstrap_ci(bp, 0.50)
            agg["ci_p90"] = cluster_bootstrap_ci(bp, 0.90)
        agg["direction"] = DIRECTION.get(k, DEFAULT_DIRECTION)
        metrics[k] = agg
    n_papers = len({r["paper"] for r in rows})
    return {"n_papers": n_papers, "n_pages": len(rows),
            "confidence": confidence_tier(n_papers), "metrics": metrics}


def build_profile(rows: list[dict], *, min_pages: int = 20,
                  with_ci: bool = True) -> dict:
    """主入口：构建 venue×role / role / venue 三档。"""
    vr: dict = {}
    by_role: dict = {}
    by_venue: dict = {}
    for r in rows:
        by_role.setdefault(r["role"], []).append(r)
        if r["venue"]:
            by_venue.setdefault(r["venue"], []).append(r)
            vr.setdefault(f"{r['venue']}|{r['role']}", []).append(r)
    lev = {"venue_role": {}, "role": {}, "venue": {}}
    for k, rs in sorted(vr.items()):
        if len(rs) >= min_pages or True:          # 全保留，但可信度如实标注
            lev["venue_role"][k] = build_stratum(rs, with_ci)
    for k, rs in sorted(by_role.items()):
        lev["role"][k] = build_stratum(rs, with_ci)
    for k, rs in sorted(by_venue.items()):
        lev["venue"][k] = build_stratum(rs, with_ci)
    return {"schema": SCHEMA, "levels": lev}


# ---------------------------------------------------------------- 去冗余

def _rank(vals: list[float]) -> list[float]:
    order = sorted(range(len(vals)), key=lambda i: vals[i])
    ranks = [0.0] * len(vals)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and vals[order[j + 1]] == vals[order[i]]:
            j += 1
        avg = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def spearman(x: list[float], y: list[float]) -> float | None:
    if len(x) != len(y) or len(x) < 8:
        return None
    rx, ry = _rank(x), _rank(y)
    n = len(rx)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    dx = math.sqrt(sum((a - mx) ** 2 for a in rx))
    dy = math.sqrt(sum((b - my) ** 2 for b in ry))
    if dx == 0 or dy == 0:
        return None
    return round(num / (dx * dy), 4)


def jacobi(a: list[list[float]], iters: int = 200, tol: float = 1e-10):
    """对称矩阵特征分解（循环 Jacobi）。返回 (特征值降序, 特征向量列矩阵)。"""
    n = len(a)
    a = [row[:] for row in a]
    v = [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]
    for _ in range(iters):
        off = math.sqrt(sum(a[i][j] ** 2 for i in range(n) for j in range(i + 1, n)))
        if off < tol:
            break
        for p in range(n - 1):
            for q in range(p + 1, n):
                if abs(a[p][q]) < 1e-15:
                    continue
                theta = (a[q][q] - a[p][p]) / (2 * a[p][q])
                t = (1 if theta >= 0 else -1) / (abs(theta) + math.sqrt(theta * theta + 1))
                c = 1 / math.sqrt(t * t + 1)
                s = t * c
                for k in range(n):
                    akp, akq = a[k][p], a[k][q]
                    a[k][p] = c * akp - s * akq
                    a[k][q] = s * akp + c * akq
                for k in range(n):
                    apk, aqk = a[p][k], a[q][k]
                    a[p][k] = c * apk - s * aqk
                    a[q][k] = s * apk + c * aqk
                for k in range(n):
                    vkp, vkq = v[k][p], v[k][q]
                    v[k][p] = c * vkp - s * vkq
                    v[k][q] = s * vkp + c * vkq
    eig = [(a[i][i], [v[k][i] for k in range(n)]) for i in range(n)]
    eig.sort(key=lambda t: -t[0])
    return [e for e, _ in eig], [w for _, w in eig]


def pca(rows: list[dict], keys: list[str], max_comp: int = 8) -> dict:
    """对标准化后的指标做 PCA（纯 Python）。返回解释方差与载荷。"""
    data = {k: [] for k in keys}
    for r in rows:
        vals = [r["metrics"].get(k) for k in keys]
        if any(v is None for v in vals):
            continue
        for k, v in zip(keys, vals):
            data[k].append(v)
    n = len(next(iter(data.values()))) if data else 0
    k = len(keys)
    if n < 20 or k < 2:
        return {"error": "样本不足"}
    mean = {key: sum(data[key]) / n for key in keys}
    sd = {}
    for key in keys:
        m = mean[key]
        var = sum((x - m) ** 2 for x in data[key]) / max(1, n - 1)
        sd[key] = math.sqrt(var) or 1.0
    z = [[(data[key][i] - mean[key]) / sd[key] for key in keys] for i in range(n)]
    corr = [[sum(z[i][a] * z[i][b] for i in range(n)) / (n - 1) for b in range(k)]
            for a in range(k)]
    evals, evecs = jacobi(corr)
    total = sum(e for e in evals if e > 0) or 1.0
    comps = []
    acc = 0.0
    for i in range(min(max_comp, k)):
        acc += evals[i]
        load = sorted(((keys[j], round(evecs[i][j], 3)) for j in range(k)),
                      key=lambda t: -abs(t[1]))[:6]
        comps.append({"pc": i + 1, "explained": round(evals[i] / total, 4),
                      "cumulative": round(acc / total, 4), "top_loadings": load})
    return {"n": n, "n_components": k, "components": comps,
            "k_for_90pct": next((c["pc"] for c in comps if c["cumulative"] >= 0.90), None)}


def correlation_and_groups(rows: list[dict], thr: float = 0.8,
                           min_pairs: int = 50) -> dict:
    """Spearman 相关 + 高相关聚类（并查集）。同一组的指标描述同一现象。"""
    keys = sorted({k for r in rows for k in r["metrics"]})
    cols = {k: [] for k in keys}
    for r in rows:
        for k in keys:
            v = r["metrics"].get(k)
            cols[k].append(v if v is not None else float("nan"))
    pairs, parent = {}, {k: k for k in keys}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            xs, ys = [], []
            for va, vb in zip(cols[a], cols[b]):
                if not (isinstance(va, float) and math.isnan(va)) \
                        and not (isinstance(vb, float) and math.isnan(vb)):
                    xs.append(va)
                    ys.append(vb)
            if len(xs) < min_pairs:
                continue
            rho = spearman(xs, ys)
            if rho is None:
                continue
            pairs[f"{a}|{b}"] = rho
            if abs(rho) >= thr:
                ra, rb = find(a), find(b)
                if ra != rb:
                    parent[rb] = ra
    groups: dict = {}
    for k in keys:
        groups.setdefault(find(k), []).append(k)
    clustered = [sorted(v) for v in groups.values() if len(v) > 1]
    clustered.sort(key=lambda g: (-len(g), g[0]))
    strongest = sorted(pairs.items(), key=lambda kv: -abs(kv[1]))[:15]
    return {"threshold": thr, "n_metrics": len(keys), "groups": clustered,
            "strongest_pairs": strongest}


# ---------------------------------------------------------------- IO

def dump(profile: dict, path: str) -> str:
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(profile, f, ensure_ascii=False, indent=1)
    return path


def load(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)
