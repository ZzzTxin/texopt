# -*- coding: utf-8 -*-
"""阶段 4：多维异常检测（马氏距离，方案 9.3）与非单调带外损失 A_profile（方案 10.1-10.3）。

定位与诚实标注：
  * 本模块量化的是**页面级「常态偏离」**，不是人类审美评分；
  * 默认**影子模式**（lambda = 0）：只报告、不参与验收，A 分口径不变：
        A = A_defect + lambda * A_profile        （方案 13.1）
    A_defect 仍是 score.py 里那套确定性缺陷加权计数，回归测试不受影响；
  * 权重采用方案 10.3「步骤一：等权」，只保证**排序可复现**，
    不主张绝对分数跨模型可比。

三个量：
  1) D^2（马氏距离）——回答「是否异常」。在 role 分层内，用稳健中心 + 收缩协方差。
  2) band loss（带外损失）——回答「哪里异常」。非单调：只有落到目标区间外才罚。
  3) A_profile = sum w_i*norm(loss_i) + w_M*norm(D^2)（阶段一等权 w=1）。

稳健化（本机无 numpy/scipy，全部手写）：
  * 标准化：中位数 / IQR（分位来自档案，天然抗离群）；
  * 截断：|z| > Z_CLIP 截断，限制单页对协方差的影响；
  * 收缩：Sigma = (1-delta)*R + delta*I，delta 用 Ledoit-Wolf 解析式估计，
    n 小 / 维高时自动加大收缩，避免 Sigma^-1 不稳定（方案 9.3 明确要求）；
  * 求逆：Cholesky（对称正定）→ 失败逐级加 jitter → 再失败退 Gauss-Jordan。

依赖：仅标准库。
"""
from __future__ import annotations

import json
import math
import os

from . import profile as PROF

SCHEMA = "aesthetic_eval.v1"
PROFILE_SCHEMA = "aesthetic_profile.v1"   # 结构兼容；版本看顶层 profile_version

# ---------------------------------------------------------------- 常量（可复算）

BAND_Q = (0.25, 0.75)        # 默认目标区间 [P25, P75]（方案 10.1）
WIDE_Q = (0.10, 0.90)        # 区间过窄时的回退（方案 10.1「宽区间用 [P10,P90]」）
WIDE_MIN_RATIO = 0.10        # IQR < 10%*(P90-P10) 视为「窄到不可用」→ 回退宽区间
Z_CLIP = 4.0                 # 标准化后的截断
W_LOW = 1.2                  # 低于下界的权重（版面偏空通常比偏满更刺眼，方案 10.1）
W_HIGH = 1.0                 # 高于上界的权重
W_D2 = 1.0                   # D^2 项权重（阶段一等权）
MIN_CONF_TIER = "medium"     # 低于此可信度的档不参与异常判定（方案 5.3），回退 role 层
ANOM_P = 0.05               # 页级「异常」判定阈值（卡方上尾概率）     # 低于此可信度的档不参与异常判定（方案 5.3），回退 role 层
JITTER = 1e-8
LOW_DIR_MAX_Q = 0.75         # direction=low 的指标：以 P75 为「上界」
LOG1P_DIMS = ("ratio.fig_text", "ratio.figtab_text")
#   正比率、重尾（分母趋零时会爆）→ 在 log1p 域做区间/尺度/标准化
MODE_FRAC_MAX = 0.5          # 众数占比 ≥ 此值视为零膨胀/常数维 → 不参与判定
LOSS_CAP = 20.0              # 单维归一化损失上限（防残余重尾指标主导）

# 默认维度（去冗余后的代表清单；构建期由相关性聚类结果覆盖）。
# 选取原则：每个现象族保留一个代表（密度/留白/图文比/平衡/行距/对齐/一致性/图件）。
DEFAULT_DIMS = (
    "density.coverage_text",
    "whitespace.total_ratio",
    "balance.visual_centroid_y",
    "ratio.fig_text",
    "readability.leading_ratio",
    "alignment.center_var",
    "consistency.figure_width_cv",
    "figure_quality.aspect_outliers",
)

CONF_ORDER = {"low": 0, "medium": 1, "high": 2}


# ---------------------------------------------------------------- 小工具

def _q(v_sorted, q: float) -> float:
    n = len(v_sorted)
    if not n:
        raise ValueError("empty")
    if n == 1:
        return float(v_sorted[0])
    pos = (n - 1) * q
    lo = int(pos)
    hi = min(lo + 1, n - 1)
    return float(v_sorted[lo] + (v_sorted[hi] - v_sorted[lo]) * (pos - lo))


def percentile(values, q: float):
    """分位数（线性插值）。"""
    v = sorted(float(x) for x in values if x is not None)
    if not v:
        return None
    return _q(v, q)


def topk_mean(values, k: int = 1):
    """前 k 大均值（CVaR 式聚合）：对「局部单页异常」敏感，又不被单个离群页完全主导。"""
    v = sorted((float(x) for x in values if x is not None), reverse=True)
    if not v:
        return None
    k = max(1, min(int(k), len(v)))
    return round(sum(v[:k]) / k, 6)


W_TOPK = 0.5          # 页→文档聚合：严重性项（前 k 大均值）权重


def pooled_agg(values, k: int = 1):
    """页级值 -> 文档级值：`W_TOPK·前k大均值 + (1-W_TOPK)·均值`。

    为什么不能只用 max / 前-k 均值（阶段 5 实测）：只要**别的页**在当前维上值更大，
    被注入页的退化就不会改变聚合值，12.1 单调性直接失败（实测 6/81 例）。
    均值项保证「任何一页变差都会抬高文档级值」，前-k 项保留「严重性」的敏感度。
    """
    v = [float(x) for x in values if x is not None]
    if not v:
        return None
    tk = topk_mean(v, k)
    mean = sum(v) / len(v)
    return round(W_TOPK * tk + (1.0 - W_TOPK) * mean, 6)


def _tf(dim: str, v) -> float:
    """指标值 -> 判定域（重尾正比率走 log1p）。"""
    x = float(v)
    return math.log1p(x) if dim in LOG1P_DIMS and x > -1 else x


def _isnan(v) -> bool:
    return isinstance(v, float) and math.isnan(v)


def _median(values):
    vals = sorted(values)
    return vals[len(vals) // 2] if len(vals) % 2 else \
        0.5 * (vals[len(vals) // 2 - 1] + vals[len(vals) // 2])


# ---------------------------------------------------------------- 线性代数 / 统计

def corr_from_z(z_rows: list[list[float]]) -> list[list[float]]:
    """标准化行 -> 相关矩阵（对角=1）。z_rows 假定每行等长、无缺失。"""
    n = len(z_rows)
    k = len(z_rows[0]) if n else 0
    if n < 2 or k < 1:
        return [[1.0 if i == j else 0.0 for j in range(k)] for i in range(k)]
    mean = [sum(r[j] for r in z_rows) / n for j in range(k)]
    sd = []
    for j in range(k):
        var = sum((r[j] - mean[j]) ** 2 for r in z_rows) / (n - 1)
        sd.append(math.sqrt(var) if var > 0 else 0.0)
    R = [[0.0] * k for _ in range(k)]
    for i in range(k):
        for j in range(i, k):
            if i == j:
                R[i][i] = 1.0
                continue
            if sd[i] == 0 or sd[j] == 0:
                R[i][j] = R[j][i] = 0.0
                continue
            c = sum((a[i] - mean[i]) * (a[j] - mean[j]) for a in z_rows) \
                / ((n - 1) * sd[i] * sd[j])
            R[i][j] = R[j][i] = max(-1.0, min(1.0, c))
    return R


def lw_delta(z_rows: list[list[float]], R: list[list[float]]) -> float:
    """Ledoit-Wolf 收缩强度（相关矩阵版，解析式）。

    delta = clip( pi / (n * gamma), 0, 1 )
      gamma = ||R - I||_F^2                      （偏离单位阵的程度）
      pi    = sum_{i != j} Var_n(r_hat_ij)       （样本相关的方差和）
    样本越大、指标越独立 → delta 越小；反之自动加大收缩。
    """
    n = len(z_rows)
    k = len(R)
    if n < 2 or k < 2:
        return 1.0
    gamma = sum(R[i][j] ** 2 for i in range(k) for j in range(k) if i != j)
    if gamma <= 0:
        return 0.0
    pi_sum = 0.0
    for i in range(k):
        for j in range(k):
            if i == j:
                continue
            vals = []
            for row in z_rows:
                vals.append(row[i] * row[j])
            m = sum(vals) / n
            var = sum((v - m) ** 2 for v in vals) / max(1, n - 1)
            pi_sum += var
    d = pi_sum / (n * gamma) if gamma else 0.0
    return max(0.0, min(1.0, d))


def shrink(R: list[list[float]], delta: float) -> list[list[float]]:
    """Sigma = (1-delta)*R + delta*I。"""
    k = len(R)
    return [[((1.0 - delta) * R[i][j] + (delta if i == j else 0.0))
             for j in range(k)] for i in range(k)]


def chol(A: list[list[float]]):
    """Cholesky 分解（对称正定）。失败返回 None。"""
    n = len(A)
    L = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1):
            s = A[i][j] - sum(L[i][m] * L[j][m] for m in range(j))
            if i == j:
                if s <= 0:
                    return None
                L[i][j] = math.sqrt(s)
            else:
                if L[j][j] == 0:
                    return None
                L[i][j] = s / L[j][j]
    return L


def inv_spd(A: list[list[float]]):
    """对称正定矩阵求逆（Cholesky + 前代/回代）。失败返回 None。"""
    n = len(A)
    L = chol(A)
    if L is None:
        return None
    # 求 L^-1（下三角）
    Linv = [[0.0] * n for _ in range(n)]
    for i in range(n):
        Linv[i][i] = 1.0 / L[i][i]
        for j in range(i):
            Linv[i][j] = -sum(L[i][m] * Linv[m][j] for m in range(j, i)) / L[i][i]
    # A^-1 = Linv^T Linv
    return [[sum(Linv[m][i] * Linv[m][j] for m in range(n)) for j in range(n)]
            for i in range(n)]


def inv_gj(A: list[list[float]]):
    """Gauss-Jordan 求逆（含部分选主元），作为兜底。"""
    n = len(A)
    M = [list(map(float, A[i])) + [1.0 if i == j else 0.0 for j in range(n)]
         for i in range(n)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(M[r][col]))
        if abs(M[piv][col]) < 1e-14:
            return None
        M[col], M[piv] = M[piv], M[col]
        pv = M[col][col]
        M[col] = [v / pv for v in M[col]]
        for r in range(n):
            if r == col:
                continue
            f = M[r][col]
            if f:
                M[r] = [a - f * b for a, b in zip(M[r], M[col])]
    return [row[n:] for row in M]


def invert(A: list[list[float]]):
    """稳健求逆：Cholesky → 加 jitter → Gauss-Jordan。"""
    inv = inv_spd(A)
    if inv is not None:
        return inv, "cholesky"
    k = len(A)
    for scale in (1e-9, 1e-7, 1e-5, 1e-3):
        B = [row[:] for row in A]
        for i in range(k):
            B[i][i] += scale
        inv = inv_spd(B)
        if inv is not None:
            return inv, f"cholesky+jitter({scale:g})"
    inv = inv_gj(A)
    return (inv, "gauss-jordan") if inv is not None else (None, "singular")


def chi2_sf(x: float, k: int) -> float:
    """卡方上尾概率 P(X > x)，自由度 k。用正则化不完全 gamma（连分式）。"""
    if x <= 0:
        return 1.0
    if k <= 0:
        return 1.0
    a = k / 2.0
    xx = x / 2.0
    # P(a, x) 的下/上分支（Numerical Recipes 风格）
    if xx < a + 1.0:
        # 级数
        ap = a
        s = 1.0 / a
        d = s
        for _ in range(200):
            ap += 1.0
            d *= xx / ap
            s += d
            if abs(d) < abs(s) * 1e-12:
                break
        p = s * math.exp(-xx + a * math.log(xx) - math.lgamma(a))
        return max(0.0, min(1.0, 1.0 - p))
    # 连分式
    tiny = 1e-300
    b = xx + 1.0 - a
    c = 1.0 / tiny
    d = 1.0 / b
    h = d
    for i in range(1, 200):
        an = -i * (i - a)
        b += 2.0
        d = an * d + b
        if abs(d) < tiny:
            d = tiny
        c = b + an / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        de = d * c
        h *= de
        if abs(de - 1.0) < 1e-12:
            break
    q = math.exp(-xx + a * math.log(xx) - math.lgamma(a)) * h
    return max(0.0, min(1.0, q))


def chi2_isf(p: float, k: int) -> float:
    """卡方分位（上尾 p 对应的 x），二分搜索。用于缺参照时兜底。"""
    lo, hi = 0.0, 1.0
    while chi2_sf(hi, k) > p and hi < 1e6:
        hi *= 2
    for _ in range(200):
        mid = (lo + hi) / 2
        if chi2_sf(mid, k) > p:
            lo = mid
        else:
            hi = mid
    return hi


# ---------------------------------------------------------------- 档（判定模型）

class Detector:
    """一个分层（venue|role 或 role）上的判定模型：D^2 + 带外损失。

    `drop`：阶段 5（方案 12.6）未通过门槛的指标清单 —— 被剔除的维**不参与判定**，
    只在报告里保留（不物理删数据，只在这里过滤，可逆、可审计）。
    """

    def __init__(self, block: dict, label: str = "", drop=None, weights=None):
        self.label = label
        all_dims = list(block.get("dims") or [])
        drop_set = {d for d in (drop or ()) if d in all_dims}
        keep = [i for i, d in enumerate(all_dims) if d not in drop_set]
        self.dropped_dims = sorted(drop_set)
        self.dims = [all_dims[i] for i in keep]
        # 阶段 7：审美权重（方案 10.3）—— 未标定/未启用时全为 1.0（与等权完全等价）
        wb = (weights or {})
        self.weights_version = wb.get("version")
        self.weights_applied = bool(wb.get("applied"))
        by_dim = wb.get("by_dim") or {}
        self.weights = {d: (float(by_dim[d]["w"]) if self.weights_applied
                            and isinstance(by_dim.get(d), dict)
                            and by_dim[d].get("w") is not None else 1.0)
                        for d in self.dims}
        self.center = [list(block.get("center") or [])[i] for i in keep]
        self.scale = [list(block.get("scale") or [])[i] for i in keep]
        self.bands = {k: v for k, v in (block.get("bands") or {}).items()
                      if k in self.dims}
        self.directions = {k: v for k, v in (block.get("directions") or {}).items()
                           if k in self.dims}
        C = block.get("corr") or []
        self.corr = [[C[i][j] for j in keep] for i in keep] if C else []
        self.delta = float(block.get("delta") or 0.0)
        self.d2_ref = block.get("d2_ref")
        self.loss_ref = dict(block.get("loss_ref") or {})
        self.n_pages = block.get("n_pages") or 0
        self.confidence = block.get("confidence")
        self.notes = list(block.get("notes") or [])
        self._inv_cache: dict = {}

    # -- 维度取值
    def vector(self, page: dict):
        items = dict(PROF.page_metric_items(page))
        vals = []
        for d in self.dims:
            v = items.get(d)
            vals.append(_tf(d, v) if isinstance(v, (int, float))
                        and not isinstance(v, bool) else None)
        return vals

    def _z(self, vals):
        return [max(-Z_CLIP, min(Z_CLIP, (v - c) / s)) if v is not None else None
                for v, c, s in zip(vals, self.center, self.scale)]

    def _sub_inv(self, idx):
        key = tuple(idx)
        if key in self._inv_cache:
            return self._inv_cache[key]
        k = len(idx)
        if k == 1:
            out = ([[1.0]], "identity-1d")
        else:
            R = [[self.corr[i][j] for j in idx] for i in idx]
            A = shrink(R, self.delta)
            out = invert(A)
            if out[0] is None:
                out = ([[1.0 if a == b else 0.0 for b in range(k)] for a in range(k)],
                       "fallback-identity")
        self._inv_cache[key] = out
        return out

    # -- 是否异常
    def mahalanobis(self, vals):
        """-> (D2, k_used, p_value, how)。可用维 < 1 时 None。"""
        idx = [i for i, v in enumerate(vals) if v is not None]
        if not idx:
            return None, 0, None, "no-data"
        z = self._z(vals)
        zi = [z[i] for i in idx]
        inv, how = self._sub_inv(idx)
        d2 = sum(zi[a] * inv[a][b] * zi[b] for a in range(len(idx))
                 for b in range(len(idx)))
        d2 = max(0.0, d2)
        return round(d2, 6), len(idx), round(chi2_sf(d2, len(idx)), 6), how

    # -- 哪里异常
    def band_loss(self, vals) -> dict:
        out = {}
        for d, v in zip(self.dims, vals):
            if v is None:
                continue
            s = 0.0
            try:
                s = float(self.scale[self.dims.index(d)])
            except Exception:
                pass
            if s <= 0:
                s = 1.0
            direction = self.directions.get(d, "band")
            if direction == "low":
                hi = (self.bands.get(d) or [None, None])[1]
                if hi is None:
                    continue
                out[d] = round(max(0.0, v - hi) / s, 6)
                continue
            lo, hi = (self.bands.get(d) or [None, None])[:2]
            if lo is None or hi is None:
                continue
            loss = 0.0
            if v < lo:
                loss += (lo - v) / s * W_LOW
            elif v > hi:
                loss += (v - hi) / s * W_HIGH
            out[d] = round(loss, 6)
        return out

    def norm_loss(self, dim: str, loss: float) -> float:
        """把带外损失换算成「相对该档语料 P90 损失」的倍率（归一化口径，方案 10.2）。"""
        ref = self.loss_ref.get(dim)
        v = loss / ref if ref and ref > 0 else loss
        return min(v, LOSS_CAP)

    def norm_d2(self, d2: float, k_used: int) -> float:
        ref = self.d2_ref if self.d2_ref else chi2_isf(0.10, max(1, k_used))
        if not ref or ref <= 0:
            return d2
        return d2 / ref

    # -- 单页
    def score_page(self, page: dict) -> dict:
        vals = self.vector(page)
        d2, k, p, how = self.mahalanobis(vals)
        losses = self.band_loss(vals)
        tail = {"d2": d2, "p_value": p, "k_used": k, "solver": how,
                "losses": losses,
                "n_dims_missing": sum(1 for v in vals if v is None)}
        if losses:
            worst = max(losses.items(), key=lambda kv: kv[1])
            tail["worst_dim"], tail["worst_loss"] = worst[0], worst[1]
        tail["z"] = {d: (None if z is None else round(z, 3))
                     for d, z in zip(self.dims, self._z(vals))}
        return tail


# ---------------------------------------------------------------- 档案扩展（构建期）

def build_block(rows: list[dict], dims, *, min_pages: int = 30,
                confidence: str | None = None) -> dict | None:
    """用同一档的页级 rows 生成马氏判定块（构建期算，在线只查表）。

    rows: [{"metrics": {...}}]（与 profile.build_stratum 的输入同构）
    """
    cand = [d for d in dims]
    # 缺值过多的维度先剔除（完整样本太少时协方差不可靠）
    while len(cand) > 1:
        complete = [r for r in rows
                    if all(r["metrics"].get(d) is not None for d in cand)]
        if len(complete) >= min_pages:
            break
        # 丢掉缺失最多的那一维
        miss = {d: sum(1 for r in rows if r["metrics"].get(d) is None) for d in cand}
        cand.remove(max(miss, key=lambda d: (miss[d], -cand.index(d))))
    if not cand:
        return None
    complete = [r for r in rows if all(r["metrics"].get(d) is not None for d in cand)]
    if len(complete) < max(5, min_pages // 4):
        return None

    # 维度有效性：常数 / 零膨胀维不参与判定（例如正文页的 coverage_table 常为 0，
    # IQR=0 → 任何非零都会算成「巨大超界」，会把分布判定带偏）
    notes, valid = [], []
    for d in cand:
        raw = [r["metrics"][d] for r in rows if r["metrics"].get(d) is not None]
        if not raw:
            continue
        cnt = {}
        for v in raw:
            cnt[v] = cnt.get(v, 0) + 1
        mode_frac = max(cnt.values()) / len(raw)
        tvs = sorted(_tf(d, v) for v in raw)
        wide_t = _q(tvs, 0.90) - _q(tvs, 0.10)
        if mode_frac >= MODE_FRAC_MAX:
            notes.append(f"{d}: 零膨胀/常数（众数占比 {mode_frac:.2f}）")
            continue
        if wide_t <= 1e-9:
            notes.append(f"{d}: 退化为常数（P90-P10={wide_t:.3g}）")
            continue
        valid.append(d)
    cand = valid
    if not cand:
        return None

    center, scale, bands, directions = [], [], {}, {}
    for d in cand:
        vals = [r["metrics"][d] for r in rows if r["metrics"].get(d) is not None]
        vs = sorted(_tf(d, v) for v in vals)
        p10, p25, p50, p75, p90 = (_q(vs, q) for q in (0.10, 0.25, 0.50, 0.75, 0.90))
        iqr = p75 - p25
        wide = p90 - p10
        s = iqr
        if s <= 0:
            s = wide / 2.563 if wide > 0 else 0.0
        if s <= 0:
            s = 1e-6
        center.append(round(p50, 6))
        scale.append(round(s, 6))
        direction = PROF.DIRECTION.get(d, PROF.DEFAULT_DIRECTION)
        directions[d] = direction
        if direction == "low":
            bands[d] = [None, round(p75, 6)]                    # 只罚「过大」
        elif iqr < WIDE_MIN_RATIO * wide:
            bands[d] = [round(p10, 6), round(p90, 6)]           # 区间过窄 → 用宽区间
        else:
            bands[d] = [round(p25, 6), round(p75, 6)]

    z_rows = []
    for r in complete:
        z = []
        for i, d in enumerate(cand):
            z.append(max(-Z_CLIP, min(Z_CLIP,
                                      (_tf(d, r["metrics"][d]) - center[i]) / scale[i])))
        z_rows.append(z)
    R = corr_from_z(z_rows)
    delta = lw_delta(z_rows, R)
    Sigma = shrink(R, delta)
    inv, how = invert(Sigma)
    if inv is None:
        return None

    prot = {"dims": cand, "center": center, "scale": scale, "bands": bands,
            "directions": directions, "corr": [[round(v, 6) for v in row] for row in R],
            "delta": round(delta, 6), "n_pages": len(rows),
            "n_complete": len(complete), "confidence": confidence,
            "solver": how, "notes": notes, "log1p_dims": list(LOG1P_DIMS)}

    # 参照值：同档页自身的 P90（归一化口径的基准）
    det = Detector(prot, label="build")
    d2s, loss_pool = [], {d: [] for d in cand}
    for r in rows:
        vals = det.vector(_metrics_as_page(r["metrics"]))
        d2, k, _, _ = det.mahalanobis(vals)
        if d2 is not None:
            d2s.append(d2)
        for d, l in det.band_loss(vals).items():
            loss_pool[d].append(l)
    prot["d2_ref"] = round(percentile(d2s, 0.90) or 0.0, 6)
    prot["loss_ref"] = {d: round(percentile(v, 0.90) or 0.0, 6)
                        for d, v in loss_pool.items() if v}
    if not d2s:
        prot["notes"].append("no-d2")
    return prot


def _metrics_as_page(flat: dict) -> dict:
    """把 flat 指标 dict 还原成 page 结构（供 Detector.vector 复用同一口径）。"""
    page: dict = {}
    for k, v in flat.items():
        if "." not in k:
            continue
        g, name = k.split(".", 1)
        page.setdefault(g, {})[name] = v
    return page


# ---------------------------------------------------------------- 在线评估

def _tier_ok(conf) -> bool:
    return CONF_ORDER.get(conf or "low", 0) >= CONF_ORDER.get(MIN_CONF_TIER, 1)


def pick_detector(profile: dict, venue, role: str, layout: str | None = None,
                  drop=None):
    """按 venue|role → role|layout → role 顺序挑档；低可信度档跳过（方案 5.3）。

    `drop`（方案 12.6）：未通过阶段 5 门槛的指标，不参与判定。

    `role|layout` 层存在的理由（实测）：小样本会议（n<16）的 venue 档可信度低
    只能回退到 role 层，而 role 层是**跨栏数混合**的 —— 单栏论文在混合档里必然
    离群，假阳率一度到 40%+。按栏数条件化（方案 5.2）后回到可用水平。
    """
    mh = (profile.get("mahalanobis") or {}).get("level") or {}
    order = []
    if venue:
        order.append(("venue_role", f"{venue}|{role}"))
    if layout:
        order.append(("role_layout", f"{role}|{layout}"))
    order.append(("role", role))
    for level, key in order:
        blk = (mh.get(level) or {}).get(key)
        if blk and _tier_ok(blk.get("confidence")):
            det = Detector(blk, label=f"{level}:{key}", drop=drop,
                           weights=profile.get("weights"))
            if not det.dims:                 # 全被剔除 → 等价于无档
                continue
            return det, level, key
    return None, None, None


def evaluate_doc(doc: dict, profile: dict, *, venue: str | None = None,
                 lambda_: float = 0.0, top_n: int = 10, drop_dims=None) -> dict:
    """一篇文档的页级指标 + 档案 -> 影子评估报告（不改任何分数）。

    `drop_dims`：未通过阶段 5 门槛的维度（方案 12.6，只报告不参与判定）。
    """
    drop = list(drop_dims or ())
    meta = doc.get("doc") or doc.get("meta") or {}
    venue = venue or meta.get("venue")
    layout = meta.get("layout")
    pages = doc.get("pages") or []
    per_page, used = [], {}
    dicts = {}
    for p in pages:
        role = p.get("role") or "unknown"
        det = dicts.get(role)
        if role not in dicts:
            det, level, key = pick_detector(profile, venue, role, layout, drop=drop)
            dicts[role] = det
            if det:
                used[role] = f"{level}:{key}"
        if not det:
            per_page.append({"page": p.get("page"), "role": role,
                             "status": "no-stratum"})
            continue
        s = det.score_page(p)
        s.update({"page": p.get("page"), "role": role, "status": "ok",
                  "stratum": det.label})
        per_page.append(s)

    ok_pages = [s for s in per_page if s.get("status") == "ok"]
    # 阶段 7：审美权重（方案 10.3）——用**全局权重表**（不是某个档的 dims 子集），
    # 否则同一维在不同角色下会拿到不同权重（同一份报告里两套口径，实测踩到）。
    wb = profile.get("weights") or {}
    w_applied = bool(wb.get("applied"))
    w_version = wb.get("version")
    w_map = {}
    if w_applied:
        for _d, _x in (wb.get("by_dim") or {}).items():
            if isinstance(_x, dict) and _x.get("w") is not None:
                w_map[_d] = float(_x["w"])
    report = {
        "schema": SCHEMA, "profile_version": profile.get("profile_version"),
        "profile_schema": profile.get("schema"), "venue": venue,
        "weights_version": w_version, "weights_applied": bool(w_applied),
        "lambda": lambda_, "mode": "shadow" if not lambda_ else "active",
        "dropped_dims": drop,
        "levels_used": used, "n_pages": len(pages), "n_pages_scored": len(ok_pages),
        "per_page": per_page,
    }
    # 论文级聚合（阶段 5 修订，见 docs/stage5_eval_protocol.md F1）：
    #   * 旧口径「按 role 取 P90 再跨 role 取 max」有两个真问题：
    #     ① 某个 role 的单页大损失会**遮住**其它页/其它 role 的变化；
    #     ② 长文里单页退化在 P90 分位上几乎不可见 —— 12.1 单调性直接失败。
    #   * 新口径：逐页先按**本页所属档**归一化（loss/ref、D²/d2_ref），再把该维所有页的
    #     归一化值做「前 k 大均值」（k = max(1, round(5%·页数))）——CVaR 式聚合，
    #     既对局部单页异常敏感，又不被单个离群页完全主导。
    k_top = max(1, int(round(0.05 * len(ok_pages)))) if ok_pages else 1
    dims_norm, dim_loss_pool = {}, {}
    d2_norm_pool = []
    for s in ok_pages:
        det = dicts.get(s["role"])
        if not det:
            continue
        if s.get("d2") is not None:
            d2_norm_pool.append(det.norm_d2(s["d2"], s.get("k_used") or 1))
        for d, l in (s.get("losses") or {}).items():
            dim_loss_pool.setdefault(d, []).append(l)
            dims_norm.setdefault(d, []).append(det.norm_loss(d, l))
    dims_norm = {d: pooled_agg(v, k_top) for d, v in dims_norm.items()}
    dim_loss_top = {d: topk_mean(v, k_top) for d, v in dim_loss_pool.items()}
    d2s = [s["d2"] for s in ok_pages if s.get("d2") is not None]
    d2_p90, d2_max = percentile(d2s, 0.90), (max(d2s) if d2s else None)
    norm_d2 = pooled_agg(d2_norm_pool, k_top)
    # 阶段 7：若档案挂了**已验收**的权重（方案 10.3 步骤二/三），按 Σw·v / Σw 合成；
    # 等权（未标定/未启用）时与旧口径逐位相同（分子分母同为 1.0 权重）。
    num, den = 0.0, 0.0
    w_used = {}
    for d, v in dims_norm.items():
        if v is None:
            continue
        wd = float(w_map.get(d, 1.0))
        w_used[d] = wd
        num += wd * v
        den += wd
    if norm_d2 is not None:
        num += W_D2 * norm_d2
        den += W_D2
    a_profile = round(num / den, 6) if den > 0 else None

    anomalies = sorted([s for s in ok_pages if s.get("d2") is not None],
                       key=lambda s: -s["d2"])[:top_n]
    report["paper"] = {
        "status": "ok" if a_profile is not None else "insufficient",
        "a_profile": a_profile,
        "median_d2": percentile(d2s, 0.50), "d2_p90": d2_p90, "d2_max": d2_max,
        "norm_d2_top": None if norm_d2 is None else round(norm_d2, 6),
        "norm_d2_p90": None if norm_d2 is None else round(norm_d2, 6),
        "topk": k_top,
        "dim_norm_top": {d: round(v, 6) for d, v in sorted(dims_norm.items())},
        "dim_norm_p90": {d: round(v, 6) for d, v in sorted(dims_norm.items())},
        "dim_loss_top": {d: round(v, 6) for d, v in sorted(dim_loss_top.items())},
        "dim_loss_p90": {d: round(v, 6) for d, v in sorted(dim_loss_top.items())},
        "weights_used": (w_used if w_applied else None),
        # a_profile 的可重算分量（阶段 7 的口径自检与权重校准都用它，不四舍五入）
        "parts": {"dims": dict(dims_norm), "d2": norm_d2},
        "n_anomalous_pages": sum(1 for s in ok_pages
                              if (s.get("p_value") if s.get("p_value") is not None else 1.0) < ANOM_P),
        "top_anomalous": [{"page": s.get("page"), "role": s.get("role"),
                           "d2": s.get("d2"), "p_value": s.get("p_value"),
                           "worst_dim": s.get("worst_dim"),
                           "stratum": s.get("stratum")} for s in anomalies],
        "note": "A_profile 为排序量（方案 10.3）；影子模式下不参与验收；"
                "页→文档聚合为「0.5·前k大均值 + 0.5·均值」(k=max(1,5%页数))，"
                "维度合成按 Σw·v/Σw（未标定时 w≡1，与等权等价），见阶段 5 文档 F1 与阶段 7 文档",
    }
    return report


# ---------------------------------------------------------------- 维度选择（去冗余）

def select_dims(rows: list[dict], redundancy: dict, *, max_dims: int = 8,
                min_cov: float = 0.5, max_per_group: int = 2) -> list[str]:
    """选判定维度：优先 DEFAULT_DIMS，且同一高相关族只留一个代表。

    redundancy 用 profile.correlation_and_groups 的输出（groups 为高相关簇）。
    """
    n = len(rows) or 1
    keys = sorted({k for r in rows for k in r["metrics"]})
    cov = {k: sum(1 for r in rows if r["metrics"].get(k) is not None) / n for k in keys}
    fam = {}
    for i, g in enumerate(redundancy.get("groups") or []):
        for k in g:
            fam[k] = i
    used, grp_cnt, out = set(), {}, []

    def take(k):
        f = fam.get(k, "alone:" + k)
        grp = k.split(".", 1)[0]
        if f in used or grp_cnt.get(grp, 0) >= max_per_group:
            return False
        used.add(f)
        grp_cnt[grp] = grp_cnt.get(grp, 0) + 1
        out.append(k)
        return True

    for d in DEFAULT_DIMS:
        if cov.get(d, 0.0) >= min_cov:
            take(d)
    if len(out) < max_dims:
        # 补充：覆盖达标、族未代表、且该指标组未超额的其它指标（按覆盖降序）
        for k in sorted(keys, key=lambda k: -cov.get(k, 0)):
            if len(out) >= max_dims:
                break
            if cov.get(k, 0.0) < min_cov or k in out:
                continue
            take(k)
    return out[:max_dims]
