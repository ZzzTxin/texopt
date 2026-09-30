# -*- coding: utf-8 -*-
"""阶段 7：审美权重校准（方案 10.3 步骤二/三）。

方案原文（10.3 权重确定路径）：

| 步骤 | 做法 | 产出 |
|---|---|---|
| 一（当前） | 等权 / 带外距离，仅用于排序 | 可复现的排序 |
| 二（校准） | 构造可控退化集，用「退化幅度 → A 单调上升」的约束做消融拟合 | 各指标方向与相对权重 |
| 三（标定） | 小规模人类成对比较 → Bradley–Terry / 偏好学习拟合权重 | 带置信区间的权重 |

本模块实现：

* `ablation_weights()` —— **步骤二**：在真实页上做可控退化（复用阶段 5 的
  `pick_degradation` / `inject_doc`），对每个维度同时量两件事：
  - **信号** `signal_d`：该维被注入退化时，它的归一化带外损失的增量（中位数）；
  - **噪声** `noise_d`：**别的**维被退化时，该维自己乱动的幅度（中位数，截断 ≥0）。
  信噪比 `SN_d = signal_d / (noise_d + eps)` 就是相对权重（再裁剪 + 归一化到均值 1）。
  理由：一个指标要当判定维度，必须「该动的时候动、不该动的时候不动」。
* `bootstrap_ci()` —— 论文聚类的 bootstrap（重采样**论文**而不是页，同阶段 2 口径）。
* `fit_bradley_terry()` —— **步骤三**：成对比较的 Bradley–Terry 逻辑回归
  （纯 Python 梯度上升 + 朝等权收缩的 L2），带 bootstrap 置信区间；
  人类数据未采集时如实返回 `None`（不包装成「已标定」）。
* `accept_verdict()` —— 验收：校准后的权重只有在**不劣化** 12.1 单调性、
  且**中位判别间隔**严格变大时才被接受，否则保留等权（`applied=false`）。

诚实边界：本模块给出的是「相对权重 + 置信区间」，不是绝对分数量纲；
λ 仍为 0（`shadow.LAMBDA`），权重只改变 `A_profile` 的**排序口径**，
不参与优化验收 —— 启用 λ>0 属阶段 7 之后的人工决策（见
`docs/stage7_weight_calibration.md`）。
"""
from __future__ import annotations

import json
import math
import os
import random

from . import aesthetic as AE

WEIGHTS_SCHEMA = "aesthetic_weights.v1"
EPS_NOISE = 0.05          # 噪声下限：避免 SN 爆到无穷（该维在对照里纹丝不动的极端情形）
W_MIN, W_MAX = 0.25, 4.0  # 权重裁剪区间（相对权重，均值归一到 1）
RANK_DIMS_KEY = "dims"


# ---------------------------------------------------------------- 消融（步骤二）

def _paper_of(rows: list[dict]) -> dict:
    by = {}
    for r in rows:
        by.setdefault(r["paper"], []).append(r)
    return by


def ablation_trials(rows: list[dict], profile: dict, *, dims=None, n_pages: int = 60,
                    seed: int = 17, gate_drop=None, step_frac: float = 0.55) -> list[dict]:
    """构造可控退化试验：每次挑一页、一个维度、按「推离本档常态」方向退化一档。

    每次试验记录：**基线**与**退化后**的逐维归一化带外损失（Δ），
    其中「被注入维」的 Δ 是信号，「其它维」的 Δ 是噪声（对照）。
    """
    from . import evalproto as EP
    rnd = random.Random(seed)
    by_paper = _paper_of(rows)
    papers = sorted(by_paper)
    rnd.shuffle(papers)
    drop = set(gate_drop or ())
    cand = list(dims or [])
    out = []
    for pid in papers:
        if len(out) >= n_pages:
            break
        rs = by_paper[pid]
        fl = [r["metrics"] for r in rs]
        roles = [r["role"] for r in rs]
        if len(fl) < 3:
            continue
        venue = rs[0].get("venue")
        layout = rs[0].get("layout")
        target = rnd.randrange(len(fl))
        role = roles[target]
        det, level, key = AE.pick_detector(profile, venue, role, layout, drop=drop)
        if not det:
            continue
        pool = [d for d in (cand or det.dims) if d in det.dims]
        if not pool:
            continue
        dim = rnd.choice(pool)
        base = dict(fl[target])
        if base.get(dim) is None:
            continue
        sign, lad, _dvals = EP.pick_degradation(det, dim, base, role)
        if sign is None:
            continue
        sc = EP._dim_scale(det, dim)
        # 取阶梯中段（既不是「毫厘之差」也不是「推到底」，避免饱和）
        alphas = [a for a, _ in lad] or [step_frac]
        alpha = alphas[min(len(alphas) - 1, max(0, int(round(step_frac * len(alphas))) - 1))]
        doc0 = EP.inject_doc(fl, target, dim, 0.0, sc, sign, roles, venue=venue, layout=layout)
        doc1 = EP.inject_doc(fl, target, dim, alpha, sc, sign, roles, venue=venue, layout=layout)
        r0 = AE.evaluate_doc(doc0, profile, venue=venue)
        r1 = AE.evaluate_doc(doc1, profile, venue=venue)
        d0, d1 = _loss_by_dim(r0), _loss_by_dim(r1)
        delta = {k: round((d1.get(k, 0.0) or 0.0) - (d0.get(k, 0.0) or 0.0), 6)
                 for k in set(d0) | set(d1)}
        out.append({"paper": pid, "page": target + 1, "role": role, "dim": dim,
                    "sign": sign, "alpha": alpha, "stratum": f"{level}:{key}",
                    "delta": delta, "a0": r0["paper"]["a_profile"],
                    "a1": r1["paper"]["a_profile"],
                    "w_used": (dict(r1["paper"].get("weights_used") or {})
                               if r1["paper"].get("weights_used") else {}),
                    "parts0": _parts_of(r0), "parts1": _parts_of(r1)})
    return out


def _loss_by_dim(rep: dict) -> dict:
    """evaluate_doc 的逐维**归一化**损失（dim_norm_top 与 dim_norm_p90 同源）。"""
    return ((rep.get("paper") or {}).get("dim_norm_top") or {})


def _parts_of(rep: dict) -> dict:
    """a_profile 的**可重算分量**（阶段 7 加权口径必须与之同式，才能公平比较）。

    优先用报告里的 `paper.parts`（未四舍五入，可逐位复现 a_profile）；
    旧报告没有该字段时回退到 `dim_norm_top` + `norm_d2_p90`（四舍五入过）。
    """
    p = rep.get("paper") or {}
    parts = p.get("parts")
    if isinstance(parts, dict) and parts.get("dims"):
        return {"dims": dict(parts.get("dims") or {}), "d2": parts.get("d2")}
    return {"dims": dict(p.get("dim_norm_top") or {}),
            "d2": p.get("norm_d2_p90")}


def a_profile_from_parts(parts: dict | None, weights: dict | None = None,
                         *, w_d2: float | None = None) -> float | None:
    """与 `aesthetic.evaluate_doc` 同式：Σ w·v / Σ w（含 D² 项，权重 W_D2）。"""
    if not parts:
        return None
    w_d2 = AE.W_D2 if w_d2 is None else w_d2
    num = den = 0.0
    for d, v in (parts.get("dims") or {}).items():
        if v is None:
            continue
        wd = float((weights or {}).get(d, 1.0))
        num += wd * v
        den += wd
    if parts.get("d2") is not None:
        num += w_d2 * parts["d2"]
        den += w_d2
    return (num / den) if den > 0 else None


def _median(v):
    v = sorted(x for x in v if x is not None)
    if not v:
        return None
    n = len(v)
    m = n // 2
    return v[m] if n % 2 else (v[m - 1] + v[m]) / 2.0


def _sn_from_trials(trials: list[dict], dim: str) -> dict:
    """一个维度的信号 / 噪声 / 信噪比（由试验集算出）。

    * 信号：该维被注入退化时的损失增量（中位数）；
    * 噪声：对照试验里该维在**未退化的原页**上的自发损失（P90）——
      「这个维在正常页上自己有多吵」。用分位而不是中位：多数正常页该维损失为 0，
      中位恒 0 会让信噪比退化成「只看信号」（先把它当成噪声试过，实测如此）。
      这一项直接对应阶段 12.2 关心的东西：在正常页上乱报的维应该降权。
    """
    sig = [_t.get("delta", {}).get(dim) for _t in trials if _t.get("dim") == dim]
    noise = []
    for t in trials:
        if t.get("dim") == dim:
            continue
        v = ((t.get("parts0") or {}).get("dims") or {}).get(dim)
        if v is None:                       # 老数据回退：用 Δ 的正增量
            v = max(0.0, (t.get("delta", {}).get(dim) or 0.0))
        noise.append(max(0.0, v))
    s, nz = _median(sig), _p90(noise)
    sn = None
    if s is not None:
        sn = s / ((nz or 0.0) + EPS_NOISE)
    return {"dim": dim, "signal": s, "noise": nz, "sn": sn,
            "n_signal": len([x for x in sig if x is not None]),
            "n_noise": len(noise)}


def _p90(values):
    v = sorted(x for x in values if x is not None)
    if not v:
        return None
    i = min(len(v) - 1, int(round(0.90 * (len(v) - 1))))
    return v[i]


def _clip_norm(sn_map: dict[str, float], dims: list[str]) -> dict[str, float]:
    """信噪比 -> 权重：裁剪 [W_MIN, W_MAX] → 归一到**均值 1** → 再裁剪（保证不越界）。

    注意顺序：先归一（相对权重才有意义）再裁剪；反过来的话归一化会把值推回
    区间外（实测踩到：clip 后除均值，`alignment.center_var` 掉到 0.12）。
    """
    raw = {}
    for d in dims:
        sn = sn_map.get(d)
        raw[d] = W_MAX if (sn is None or not math.isfinite(sn)) \
            else max(W_MIN, min(W_MAX, sn))
    m = sum(raw.values()) / len(raw) if raw else 1.0
    if m <= 0:
        return {d: 1.0 for d in dims}
    return {d: round(max(W_MIN, min(W_MAX, raw[d] / m)), 4) for d in dims}


def bootstrap_ci(trials: list[dict], dims: list[str], *, n_boot: int = 200,
                 seed: int = 29) -> dict:
    """论文聚类的 bootstrap：重采样**论文**（不是页），给权重的 5%/95% 区间。"""
    rnd = random.Random(seed)
    by_paper = _paper_of(trials) if trials else {}
    papers = sorted(by_paper)
    if not papers:
        return {}
    out = {d: [] for d in dims}
    for _ in range(int(n_boot)):
        pick = [papers[rnd.randrange(len(papers))] for _ in range(len(papers))]
        sample = [t for p in pick for t in by_paper[p]]
        sn_map = {d: (_sn_from_trials(sample, d) or {}).get("sn") for d in dims}
        w = _clip_norm(sn_map, dims)
        for d in dims:
            out[d].append(w[d])
    ci = {}
    for d in dims:
        vals = sorted(out[d])
        if vals:
            ci[d] = [round(vals[int(0.05 * (len(vals) - 1))], 4),
                     round(vals[int(0.95 * (len(vals) - 1))], 4)]
    return ci


def weights_from_trials(trials: list[dict], dims: list[str], *, n_boot: int = 200,
                        seed: int = 17, gate_drop=None) -> dict:
    """由试验集算出权重块（信号/噪声/SN + bootstrap CI）；未验收（applied=False）。"""
    drop = list(gate_drop or ())
    stats = [_sn_from_trials(trials, d) for d in dims]
    sn_map = {s["dim"]: s["sn"] for s in stats}
    w = _clip_norm(sn_map, dims)
    ci = bootstrap_ci(trials, dims, n_boot=n_boot, seed=seed + 7)
    by_dim = {}
    for s in stats:
        d = s["dim"]
        by_dim[d] = {"w": w[d], "ci": ci.get(d), "signal": s["signal"],
                     "noise": s["noise"], "sn": (None if s["sn"] is None
                                                 else round(s["sn"], 4)),
                     "n_signal": s["n_signal"], "n_noise": s["n_noise"],
                     "source": "ablation"}
    return {"schema": WEIGHTS_SCHEMA, "version": "w1", "method": "ablation",
            "by_dim": by_dim, "excluded_dims": drop, "n_trials": len(trials),
            "n_boot": int(n_boot),
            "applied": False,        # 由 accept_verdict() 决定
            "note": "相对权重（均值 1），只改变 A_profile 的排序口径；λ 仍为 0"}


def ablation_weights(rows: list[dict], profile: dict, *, dims=None, n_pages: int = 60,
                     seed: int = 17, gate_drop=None, n_boot: int = 200) -> dict:
    """步骤二全流程：试验 -> 信噪比权重 -> bootstrap CI -> 权重块（未验收）。"""
    drop = list(gate_drop or ())
    dims = [d for d in (dims or _default_dims(profile)) if d not in drop]
    trials = ablation_trials(rows, profile, dims=dims, n_pages=n_pages,
                             seed=seed, gate_drop=drop)
    return weights_from_trials(trials, dims, n_boot=n_boot, seed=seed,
                               gate_drop=drop)


def _default_dims(profile: dict) -> list:
    mh = profile.get("mahalanobis") or {}
    lv = (mh.get("level") or {}).get("venue_role") or {}
    for blk in lv.values():
        return list(blk.get("dims") or [])
    return list(AE.DEFAULT_DIMS)


# ---------------------------------------------------------------- 验收（不劣化才启用）

def margin_stats(trials: list[dict], weights: dict | None = None) -> dict:
    """判别间隔：退化后 A_profile − 基线 A_profile。

    **两边必须同式**（阶段 7 实测踩到）：等权与校准权重都用
    `a_profile_from_parts` 重算，而不是「等权用记录值、校准用加权值」——
    后者会把 D² 项与 pool 口径的差异也算进「权重带来的变化」，结论不可信。
    """
    outs, mismatch = [], 0
    for t in trials:
        p0, p1 = t.get("parts0"), t.get("parts1")
        if p0 and p1:
            a0 = a_profile_from_parts(p0, weights)
            a1 = a_profile_from_parts(p1, weights)
            # 自检：试验时的记录值必须能用**当时用的权重**（w_used）从分量复现
            # （否则说明合成口径变了，后面「权重带来的变化」就不可信）
            wu = t.get("w_used") if "w_used" in t else weights
            if t.get("a0") is not None:
                b0 = a_profile_from_parts(p0, wu)
                b1 = a_profile_from_parts(p1, wu)
                if abs(b0 - t["a0"]) > 1e-4 or abs(b1 - t["a1"]) > 1e-4:
                    mismatch += 1
        else:                                  # 老数据回退：只有记录值
            a0, a1 = t.get("a0"), t.get("a1")
        if a0 is not None and a1 is not None:
            outs.append(a1 - a0)
    if not outs:
        return {"n": 0, "median": None, "positive_rate": None}
    pos = sum(1 for x in outs if x > 1e-12)
    return {"n": len(outs), "median": round(_median(outs), 6),
            "positive_rate": round(pos / len(outs), 4),
            "recompute_mismatch": mismatch}


def accept_verdict(equal_stats: dict, cal_stats: dict, *, weights: dict | None = None,
                   tol: float = 1e-9) -> dict:
    """验收规则：权重只有在「不劣化 + 判别间隔严格改善」时才 applied。

    * 判据 1：退化后 A 上升的比例不得下降（方案 12.1 单调性的必要条件）；
    * 判据 2：中位判别间隔严格变大（权重真的让信号更清楚）；
    * 判据 3：权重有限且在裁剪区间内。
    """
    reasons = []
    pr0, pr1 = equal_stats.get("positive_rate"), cal_stats.get("positive_rate")
    if pr0 is None or pr1 is None:
        reasons.append("样本不足")
    elif pr1 < pr0 - tol:
        reasons.append(f"单调性劣化（正向率 {pr0} → {pr1}）")
    m0, m1 = equal_stats.get("median"), cal_stats.get("median")
    if m0 is None or m1 is None:
        reasons.append("间隔不可比")
    elif m1 <= m0 + tol:
        reasons.append(f"中位判别间隔未改善（{m0} → {m1}）")
    if weights:
        bad = [d for d, w in weights.items()
               if w is None or not math.isfinite(w) or not (W_MIN - 1e-9 <= w <= W_MAX + 1e-9)]
        if bad:
            reasons.append(f"权重越界：{bad}")
    return {"applied": not reasons, "reasons": reasons,
            "equal": equal_stats, "calibrated": cal_stats}


# ---------------------------------------------------------------- 步骤三：Bradley–Terry

def fit_bradley_terry(pairs: list[dict], dims: list[str], *, l2: float = 1.0,
                      iters: int = 400, lr: float = 0.5, seed: int = 3) -> dict | None:
    """成对比较 -> 权重（方案 10.3 步骤三）。

    `pairs` 每项：`{"a": {dim: norm_loss}, "b": {...}, "winner": "a"|"b"}`
    （loss 越大越差；模型用 x = −loss 作为「更好」的得分向量）。
    目标：P(a≻b) = σ(w·(x_a − x_b))，L2 朝**等权**收缩（保证小样本下不跑飞）。

    数据未采集（`pairs` 为空/None）时返回 `None` —— 如实说明「未标定」，
    不把消融权重包装成人类标定结果。
    """
    if not pairs:
        return None
    w = [1.0] * len(dims)
    idx = {d: i for i, d in enumerate(dims)}
    data = []
    for p in pairs:
        try:
            xa = [-float((p.get("a") or {}).get(d) or 0.0) for d in dims]
            xb = [-float((p.get("b") or {}).get(d) or 0.0) for d in dims]
            y = 1.0 if str(p.get("winner")) in ("a", "A") else 0.0
            if str(p.get("winner")) not in ("a", "A", "b", "B"):
                continue
        except Exception:
            continue
        data.append((xa, xb, y))
    if len(data) < 8:                       # 与 spearman 同口径：<8 对不给结论
        return None
    for _ in range(int(iters)):
        g = [-l2 * (w[i] - 1.0) for i in range(len(dims))]   # 朝等权收缩
        for xa, xb, y in data:
            d = [xa[i] - xb[i] for i in range(len(dims))]
            z = sum(w[i] * d[i] for i in range(len(dims)))
            p = 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, z))))
            err = (y - p)
            for i in range(len(dims)):
                g[i] += err * d[i]
        w = [w[i] + lr * g[i] / len(data) for i in range(len(dims))]
    w = _clip_norm({d: w[idx[d]] for d in dims}, dims)
    # 拟合优度：成对准确率（重采样论文/对做 CI 略；这里给点估计）
    correct = 0
    for xa, xb, y in data:
        z = sum(w[d] * (xa[i] - xb[i]) for i, d in enumerate(dims))
        pred = 1.0 if z > 0 else 0.0
        correct += int(pred == y)
    return {"by_dim": {d: w[d] for d in dims}, "n_pairs": len(data),
            "pair_accuracy": round(correct / len(data), 4),
            "method": "bradley-terry", "l2": l2}


def load_pairs(path: str) -> list[dict]:
    """读人类成对比较数据（JSON 数组）；缺文件返回 []（不伪造数据）。"""
    if not path or not os.path.isfile(path):
        return []
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return []
    if isinstance(data, dict):
        data = data.get("pairs") or []
    return [p for p in data if isinstance(p, dict)] if isinstance(data, list) else []


def merge_human(base: dict, bt: dict | None) -> dict:
    """人类标定结果并入权重块（步骤三优先；无数据则保持步骤二并如实标注）。"""
    if not bt:
        base["human_calibration"] = None
        return base
    for d, w in (bt.get("by_dim") or {}).items():
        if d in base.get("by_dim", {}):
            base["by_dim"][d]["w_human"] = w
            base["by_dim"][d]["w"] = w
            if base["by_dim"][d].get("source") == "ablation":
                base["by_dim"][d]["source"] = "ablation+human"
    base["human_calibration"] = {"n_pairs": bt.get("n_pairs"),
                                 "pair_accuracy": bt.get("pair_accuracy"),
                                 "method": bt.get("method")}
    base["method"] = "ablation+human"
    return base


def save(block: dict, path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(block, f, ensure_ascii=False, indent=1)


def apply_to_profile(profile: dict, block: dict) -> dict:
    """把权重块挂到 profile（供 `aesthetic.Detector` 读取）；不改变 profile 统计本身。"""
    profile = dict(profile)
    profile["weights"] = block
    return profile
