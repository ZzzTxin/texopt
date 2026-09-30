# -*- coding: utf-8 -*-
"""阶段 5：评测与验收协议（设计方案 12.1-12.6）。

审美没有客观 ground truth，因此必须用**代理评测**证明模型有效。本模块把方案的
五项强制检验做成可复算的纯逻辑（无 numpy/scipy，全部手写）：

  12.1 负样本注入（构造性验证）  inject_* + monotone_series + localize
  12.2 假阳率（特异性，按 role）  fp_rates + calibrate_threshold
  12.3 会议可分性（有效性 sanity check）  knn_accuracy + permutation_pvalue
  12.4 稳定性与可复现性  stability_{determinism,dpi,recompile}
  12.5 与人类判断的相关性（探索性）  spearman_rank（数据未采集时如实报 None）
  12.6 验收门槛  gate_dim + gate_verdicts（未通过的指标只能作报告项）

诚实边界（写进报告，不许包装）：
  * 本协议检验的是**实现与口径的自洽性**，不是「模型与人类审美一致」；
  * 12.5 需要人类成对比较数据，本阶段**未采集**，如实输出 None；
  * 12.1 分两级：**指标层注入**（快，全库可跑，验证评分函数）+ **渲染层注入**
    （慢，抽检真实 .tex，验证「感知层 -> 评分」整条链路）。

依赖：仅标准库 + texopt 内部模块。
"""
from __future__ import annotations

import json
import math
import os
import random
import time

from . import aesthetic as AE
from . import profile as PROF

SCHEMA = "eval_protocol.v1"

# ---------------------------------------------------------------- 12.1 负样本注入

# 退化类型 -> 被注入的维度（sign = 往目标区间外的方向推：+1 增大 / -1 减小）
# 对应方案 12.1 列举的六类退化：拆段、注入异常空白、缩小图片、打乱对齐、改变密度、移动浮动体。
INJECTIONS = {
    "split_paragraph": {          # 拆段：段落被拆碎 -> 行间空白增多
        "dims": [("whitespace.total_ratio", +1), ("readability.para_lines_mean", -1)],
        "desc": "拆段：段落被拆成多段，行间/段间空白增多",
    },
    "inject_hole": {              # 注入异常空白：正文中间出现无解释空洞
        "dims": [("whitespace.anomalous_ratio", +1), ("whitespace.total_ratio", +1)],
        "desc": "注入异常空白：正文中间出现无结构解释的连续空洞",
    },
    "shrink_figure": {            # 缩小图片：图占比下降、正文占比上升
        "dims": [("ratio.fig_text", -1), ("density.coverage_text", +1)],
        "desc": "缩小图片：图/文比例下降",
    },
    "break_alignment": {          # 打乱对齐：两端对齐被破坏
        "dims": [("alignment.center_var", +1)],
        "desc": "打乱对齐：短行不再居中、两端不再对齐",
    },
    "change_density": {           # 改变密度：正文占比被拉开
        "dims": [("density.coverage_text", +1)],
        "desc": "改变密度：正文覆盖率被推离常态区间",
    },
    "move_float": {               # 强制移动浮动体：视觉重心上下移动、栏内平衡被破坏
        "dims": [("balance.visual_centroid_y", +1), ("balance.d_mid", +1)],
        "desc": "强制移动浮动体：视觉重心下移、上下/栏内平衡被破坏",
    },
}

# 取值域提示（注入时避免越界；越界饱和会污染单调性检验）
UNIT_DIMS = {
    "density.coverage_text", "density.coverage_figure", "density.coverage_table",
    "density.ink_ratio_page", "density.ink_ratio_text",
    "whitespace.total_ratio", "whitespace.structural_ratio", "whitespace.boundary_ratio",
    "whitespace.float_ratio", "whitespace.trailing_ratio", "whitespace.anomalous_ratio",
    "balance.d_top", "balance.d_mid", "balance.d_bot", "balance.visual_centroid_y",
    "balance.left_right",
}
NONNEG_DIMS = {
    "ratio.fig_text", "ratio.figtab_text", "readability.chars_per_line_mean",
    "readability.para_lines_mean", "alignment.left_var", "alignment.right_var",
    "alignment.center_var", "readability.font_pt", "readability.font_pt_page",
}


def _clip_bound(dim: str, sign: int):
    """该维度在 sign 方向上的可达边界；None = 无界。"""
    if dim in UNIT_DIMS:
        return 1.0 if sign > 0 else 0.0
    if dim in NONNEG_DIMS:
        return None if sign > 0 else 0.0
    if dim == "readability.leading_ratio":
        return None if sign > 0 else 1.0
    return None


def build_ladder(dim: str, value: float, scale: float, sign: int,
                 *, n: int = 4, k_max: float = 4.0):
    """退化幅度阶梯（相对于目标区间尺度 scale 的倍率）。

    有界维度：按**剩余空间**的等分（0.25/0.5/0.75/1.0 × headroom），避免越界饱和；
    无界维度：按 scale 的倍率（0.5·2^j）。
    返回 [(alpha, new_value), ...]，严格单调外推，长度为 n；无法注入时返回 []。
    """
    if scale is None or scale <= 0:
        return []
    bound = _clip_bound(dim, sign)
    out = []
    if bound is not None:
        head = (bound - value) if sign > 0 else (value - bound)
        if head <= 1e-9:
            return []
        for i in range(1, n + 1):
            a = head * i / n
            out.append((round(a / scale, 6), round(value + sign * a, 6)))
    else:
        for j in range(n):
            a = scale * 0.5 * (2.0 ** j)          # 0.5x, 1x, 2x, 4x
            if a / scale > k_max:
                break
            out.append((round(a / scale, 6), round(value + sign * a, 6)))
    return out


def inject_value(value: float, dim: str, alpha: float, scale: float, sign: int) -> float:
    """按 alpha×scale 外推一维取值（带域裁剪）。"""
    v = value + sign * alpha * scale
    bound = _clip_bound(dim, sign)
    if bound is not None:
        v = min(v, bound) if sign > 0 else max(v, bound)
    if dim in UNIT_DIMS:
        v = max(0.0, min(1.0, v))
    elif dim in NONNEG_DIMS:
        v = max(0.0, v)
    return v


def _flat_to_page(flat: dict, page_no: int = 1, role: str = "body") -> dict:
    p = AE._metrics_as_page(flat)
    p["page"] = page_no
    p["role"] = role
    return p


def inject_doc(pages_flat: list[dict], target: int, dim: str, alpha: float,
               scale: float, sign: int, roles=None, *, venue=None,
               layout=None) -> dict:
    """把第 target 页的 dim 按 alpha×scale 外推，返回可直接喂 evaluate_doc 的 doc。

    pages_flat: [{flat_key: value}]（每页一条，顺序 = 页码顺序）
    venue/layout 必须带上，否则 evaluate_doc 会退到 role 层，与注入所用档不一致。
    """
    pages = []
    for i, flat in enumerate(pages_flat):
        f = dict(flat)
        if i == target:
            v = f.get(dim)
            if v is not None:
                f[dim] = inject_value(float(v), dim, alpha, scale, sign)
        role = (roles[i] if roles else "body")
        pages.append(_flat_to_page(f, page_no=i + 1, role=role))
    return {"doc": {"venue": venue, "layout": layout}, "pages": pages}


def monotone_series(values: list[float], *, strict: bool = False,
                    tol_rel: float = 1e-3) -> dict:
    """判定序列是否单调上升。

    默认**非递减**（方案 12.1 的「单调上升」）：非单调带外损失在目标区间内恒为 0，
    退化幅度还没跨出区间时 A 本就不该动，严格要求「每档都更大」会把正确行为判成失败。
    判据 = ① 无超过容差的下降 ② 末值确实高于首值（`delta` > 1e-9）。

    `tol_rel`：允许的相对回落容差（默认 0.1%）。为什么需要它：D² 是二次型，
    当 Σ⁻¹ 存在非对角项（维度相关）时，**单维外推可能让 D² 略微下降** —— 这是
    马氏几何的合法行为，不是实现错误（实测最大回落 3e-5，相对 2e-5）。
    `strict_ok` 同时如实报出「零回落」口径，供保守引用。
    """
    vals = [v for v in values if v is not None]
    if len(vals) < 2:
        return {"ok": False, "reason": "样本不足"}
    tol = abs(tol_rel * max(abs(vals[-1]), 1e-9))
    bad_tol = bad_strict = 0
    worst_drop = 0.0
    for a, b in zip(vals, vals[1:]):
        if b < a - 1e-12:
            bad_strict += 1
        if b < a - tol:
            bad_tol += 1
        worst_drop = min(worst_drop, b - a)
    delta = round(vals[-1] - vals[0], 6)
    return {"ok": bad_tol == 0 and delta > 1e-9,
            "strict_ok": bad_strict == 0 and delta > 1e-9,
            "violations": bad_tol, "violations_strict": bad_strict,
            "max_drop": round(worst_drop, 8), "tol": round(tol, 8),
            "n": len(vals), "first": vals[0], "last": vals[-1], "delta": delta}


def injected_dims() -> list[str]:
    return sorted({d for cfg in INJECTIONS.values() for d, _ in cfg["dims"]})


def _dim_scale(det, dim):
    return det.scale[det.dims.index(dim)] if dim in det.dims else None


def _loss_series(det, dim, flat_page, role, ladder, sign):
    """一维在阶梯上的归一化损失序列（首项 = 未注入基线）。"""
    sc = _dim_scale(det, dim)
    v0 = float(flat_page[dim])
    vals = []
    for a, v in [(0.0, v0)] + list(ladder):
        page = _flat_to_page(dict(flat_page, **{dim: v}), role=role)
        vals.append(det.norm_loss(dim, det.band_loss(det.vector(page)).get(dim, 0.0)))
    return vals


def pick_degradation(det, dim, flat_page, role, *, n: int = 4):
    """选定「退化方向」：把值推离**本档常态**（带外）的方向，而不是写死符号。

    为什么：带外损失是双向非单调的，同一维「变小」在某些页上是退化（原本偏小），
    在另一些页上反而是「回到常态」。写死方向会把正确的非单调行为误判为失败。
    规则：分别试两侧，取损失增幅更大的那侧；两侧都无增幅 → 该页该维不可注入。
    返回 (sign, ladder, loss_series) 或 (None, [], [])
    """
    sc = _dim_scale(det, dim)
    v0 = flat_page.get(dim)
    if sc is None or v0 is None or sc <= 0:
        return None, [], []
    cands = []
    for sign in (+1, -1):
        lad = build_ladder(dim, float(v0), sc, sign, n=n)
        if len(lad) < 2:
            continue
        ser = _loss_series(det, dim, flat_page, role, lad, sign)
        ms = monotone_series(ser)
        cands.append((sign, lad, ser, ser[-1] - ser[0], bool(ms["ok"])))
    if not cands:
        return None, [], []
    # 优先取「损失单调不降」的方向；都有则取增幅大者。都不单调时退而取增幅大者（
    # 会被如实记为未通过，不做掩盖）。
    mono = [c for c in cands if c[4] and c[3] > 1e-9]
    pool = mono or [c for c in cands if c[3] > 1e-9]
    if not pool:
        return None, [], []
    sign, lad, ser, _delta, _ok = max(pool, key=lambda c: c[3])
    return sign, lad, ser


def run_injection_trials(rows: list[dict], profile: dict, *, n_pages: int = 40,
                         seed: int = 5, per_paper: int = 1) -> dict:
    """12.1：在真实页面上做指标层注入，检验 A_profile 单调上升 + 定位到被改页。

    每篇论文取 per_paper 页；每页对每种退化类型、每个被注入维度做一次阶梯注入。
    退化方向由 `pick_degradation` 按「推离本档常态」确定（见其 docstring）。
    """
    rnd = random.Random(seed)
    by_paper: dict[str, list[tuple]] = {}
    for r in rows:
        by_paper.setdefault(r["paper"], []).append(r)
    papers = sorted(by_paper)
    rnd.shuffle(papers)
    doc_series, dim_series, saturation = [], [], []
    for pid in papers:
        if len(doc_series) >= n_pages:
            break
        rs = by_paper[pid]
        fl = [r["metrics"] for r in rs]
        roles = [r["role"] for r in rs]
        if len(fl) < 3:
            continue
        for _ in range(per_paper):
            target = rnd.randrange(len(fl))
            role = roles[target]
            det, level, key = AE.pick_detector(profile, rs[0]["venue"], role,
                                               rs[0].get("layout"))
            if not det:
                continue
            base = dict(fl[target])
            for inj, cfg in INJECTIONS.items():
                for dim, _cfg_sign in cfg["dims"]:
                    if dim not in det.dims or base.get(dim) is None:
                        continue
                    sign, lad, dvals = pick_degradation(det, dim, base, role)
                    if sign is None:
                        saturation.append({"paper": pid, "page": target + 1,
                                           "dim": dim, "injection": inj,
                                           "why": "该页此维已无外推空间/无损失可增"})
                        continue
                    sc = _dim_scale(det, dim)
                    alphas = [0.0] + [a for a, _ in lad]
                    docs = []
                    for a in alphas:
                        doc = inject_doc(fl, target, dim, a, sc, sign, roles,
                                         venue=rs[0]["venue"], layout=rs[0].get("layout"))
                        docs.append(AE.evaluate_doc(doc, profile, venue=rs[0]["venue"]))
                    aSer = [d["paper"]["a_profile"] for d in docs]
                    ms = monotone_series(aSer)
                    doc_series.append({"paper": pid, "page": target + 1,
                                       "role": role, "injection": inj, "dim": dim,
                                       "stratum": f"{level}:{key}", "sign": sign,
                                       "alpha": alphas, "a_profile": aSer,
                                       "delta": ms.get("delta"),
                                       "max_drop": ms.get("max_drop"),
                                       "monotone": ms["ok"],
                                       "strict": ms.get("strict_ok"),
                                       "violations": ms["violations"]})
                    dms = monotone_series(dvals)
                    dim_series.append({"dim": dim, "injection": inj, "role": role,
                                       "ok": dms["ok"], "violations": dms["violations"],
                                       "first": dms.get("first"), "last": dms.get("last"),
                                       "delta": dms.get("delta")})
                    top = (docs[-1]["paper"]["top_anomalous"] or [None])[0]
                    if top is not None:
                        # 定位判定：退化页在**全页 D² 排序**中的名次（top-3 记命中）
                        ranked = sorted([s for s in docs[-1]["per_page"]
                                         if s.get("status") == "ok" and s.get("d2") is not None],
                                        key=lambda s: -s["d2"])
                        rank = next((i + 1 for i, s in enumerate(ranked)
                                     if s.get("page") == target + 1), None)
                        doc_series[-1]["rank"] = rank
                        doc_series[-1]["rank1"] = (rank == 1) if rank is not None else None
                        doc_series[-1]["localized"] = (rank is not None and rank <= 3)
                        doc_series[-1]["worst_dim"] = top.get("worst_dim")
    return {"schema": "eval_injection.v1",
            "n_trials": len(doc_series),
            "doc_monotone_rate": _rate(doc_series, "monotone"),
            "doc_strict_rate": _rate(doc_series, "strict"),
            "localized_rate": _rate([d for d in doc_series if "localized" in d],
                                    "localized"),
            "top1_rate": _rate([d for d in doc_series if "rank1" in d], "rank1"),
            "dim_monotone_rate": _rate(dim_series, "ok"),
            "by_injection": _group_rate(doc_series, "injection", "monotone"),
            "by_dim": _group_rate(dim_series, "dim", "ok"),
            "localized_by_role": _group_rate([d for d in doc_series if "localized" in d],
                                             "role", "localized"),
            "median_rank": _median([d["rank"] for d in doc_series
                                    if d.get("rank") is not None]),
            "saturated": saturation[:20], "n_saturated": len(saturation),
            "trials": doc_series}


def _median(values):
    v = sorted(x for x in values if x is not None)
    return v[len(v)//2] if v else None


def _rate(items: list[dict], key: str) -> float | None:
    vals = [bool(i[key]) for i in items if i.get(key) is not None]
    return round(sum(vals) / len(vals), 4) if vals else None


def _group_rate(items: list[dict], group: str, key: str) -> dict:
    out: dict = {}
    for it in items:
        out.setdefault(it[group], []).append(bool(it.get(key)))
    return {k: round(sum(v) / len(v), 4) if v else None for k, v in sorted(out.items())}


def localize(rep: dict, page_no: int) -> bool:
    """12.1 的定位要求：被改页进入 top_anomalous 且确实被判为最异常。"""
    top = (rep.get("paper") or {}).get("top_anomalous") or []
    return bool(top) and top[0].get("page") == page_no


# ---------------------------------------------------------------- 12.2 假阳率

def fold_split(rows: list[dict], *, k: int = 5, seed: int = 13) -> list[dict]:
    """按论文分层（venue 内）切分 k 折；确定性：同 seed 同结果。"""
    by_venue: dict = {}
    for r in rows:
        if r["venue"]:
            by_venue.setdefault(r["venue"], set()).add(r["paper"])
    folds = [{"train": set(), "test": set()} for _ in range(k)]
    for venue, sids in sorted(by_venue.items()):
        ids = sorted(sids)
        random.Random(f"{seed}|{venue}").shuffle(ids)
        for i, sid in enumerate(ids):
            folds[i % k]["test"].add(sid)
    all_sids = {r["paper"] for r in rows}
    for f in folds:
        f["train"] = all_sids - f["test"]
    return folds


def build_fold_profile(rows: list[dict], train: set, *, dims=None,
                       min_pages: int = 30) -> dict:
    """只用训练集论文重建判定档（不动磁盘上的正式档案）。"""
    tr = [r for r in rows if r["paper"] in train]
    red = PROF.correlation_and_groups(tr)
    dims = list(dims or AE.select_dims(tr, red))
    levels = {"venue_role": {}, "role": {}, "role_layout": {}}
    vr, rl, ro = {}, {}, {}
    for r in tr:
        ro.setdefault(r["role"], []).append(r)
        if r["venue"]:
            vr.setdefault(f"{r['venue']}|{r['role']}", []).append(r)
        if r.get("layout"):
            rl.setdefault(f"{r['role']}|{r['layout']}", []).append(r)

    def conf(rs):
        return PROF.confidence_tier(len({r["paper"] for r in rs}))

    for k, rs in sorted(vr.items()):
        b = AE.build_block(rs, dims, min_pages=min_pages, confidence=conf(rs))
        if b:
            levels["venue_role"][k] = b
    for k, rs in sorted(rl.items()):
        b = AE.build_block(rs, dims, min_pages=min_pages, confidence=conf(rs))
        if b:
            levels["role_layout"][k] = b
    for k, rs in sorted(ro.items()):
        b = AE.build_block(rs, dims, min_pages=min_pages, confidence=conf(rs))
        if b:
            levels["role"][k] = b
    return {"schema": PROF.SCHEMA, "profile_version": "eval-fold",
            "mahalanobis": {"level": levels, "dims": dims}}


def docs_from_rows(rows: list[dict]) -> list[dict]:
    """页级 rows -> 文档列表（每篇一个 doc，供 evaluate_doc 使用）。"""
    by_paper: dict = {}
    for r in rows:
        by_paper.setdefault(r["paper"], []).append(r)
    docs = []
    for pid in sorted(by_paper):
        rs = by_paper[pid]
        pages = []
        for i, r in enumerate(rs):
            p = AE._metrics_as_page(r["metrics"])
            p["page"] = i + 1
            p["role"] = r["role"]
            pages.append(p)
        docs.append((pid, rs[0]["venue"], rs[0].get("layout"), {"pages": pages}))
    return docs


def evaluate_fold(rows: list[dict], fold: dict, *, dims=None,
                  min_pages: int = 30) -> dict:
    """在某一折上：训练集建档 -> 在训练页上定阈值 -> 在测试页上测假阳率。"""
    prof = build_fold_profile(rows, fold["train"], dims=dims, min_pages=min_pages)
    train_docs = docs_from_rows([r for r in rows if r["paper"] in fold["train"]])
    test_docs = docs_from_rows([r for r in rows if r["paper"] in fold["test"]])
    train_d2, train_role_d2, train_n = [], {}, 0
    for _pid, venue, layout, doc in train_docs:
        rep = AE.evaluate_doc(doc, prof, venue=venue)
        for s in rep["per_page"]:
            if s.get("status") != "ok" or s.get("d2") is None:
                continue
            train_d2.append(s["d2"])
            train_role_d2.setdefault(s["role"], []).append(s["d2"])
            train_n += 1
    # 经验阈值：训练集 D² 的 P95（= 目标 5% 假阳率）；同时保留参数化阈值 chi2_isf(0.05,k)
    # 阶段 5 实测发现参数化阈值（卡方假设）严重高估异常：真实指标是重尾/混合分布。
    # 因此同时算 P95/P96/P97 三档，给出「假阳率—敏感度」权衡表（发布时可取更保守的档）。
    CAL_Q = (0.95, 0.96, 0.97)
    thr = AE.percentile(train_d2, 0.95)
    role_thr = {k: AE.percentile(v, 0.95) for k, v in train_role_d2.items() if len(v) >= 20}
    role_thr_multi = {k: {q: AE.percentile(v, q) for q in CAL_Q}
                      for k, v in train_role_d2.items() if len(v) >= 20}
    per_role, tot, fp = {}, 0, 0
    per_role_param, tot_param, fp_param = {}, 0, 0
    per_role_cal, tot_cal, fp_cal = {}, 0, 0
    dim_n, dim_fp_param, dim_fp_cal = {}, {}, {}
    cal_stat = {q: {"n": 0, "fp": 0, "by_role": {}, "by_dim": {}} for q in CAL_Q}
    for _pid, venue, layout, doc in test_docs:
        rep = AE.evaluate_doc(doc, prof, venue=venue)
        for s in rep["per_page"]:
            if s.get("status") != "ok" or s.get("d2") is None:
                continue
            role = s["role"]
            for d in (s.get("losses") or {}):
                dim_n[d] = dim_n.get(d, 0) + 1
            worst = s.get("worst_dim")
            tot += 1
            is_fp = s.get("p_value") is not None and s["p_value"] < AE.ANOM_P
            per_role.setdefault(role, {"n": 0, "fp": 0})
            per_role[role]["n"] += 1
            per_role[role]["fp"] += int(is_fp)
            fp += int(is_fp)
            tot_param += 1
            fp_param += int(is_fp)
            per_role_param.setdefault(role, {"n": 0, "fp": 0})
            per_role_param[role]["n"] += 1
            per_role_param[role]["fp"] += int(is_fp)
            if is_fp and worst:
                dim_fp_param[worst] = dim_fp_param.get(worst, 0) + 1
            if role in role_thr:
                tot_cal += 1
                hit = s["d2"] > role_thr[role]
                fp_cal += int(hit)
                per_role_cal.setdefault(role, {"n": 0, "fp": 0})
                per_role_cal[role]["n"] += 1
                per_role_cal[role]["fp"] += int(hit)
                if hit and worst:
                    dim_fp_cal[worst] = dim_fp_cal.get(worst, 0) + 1
            for q in CAL_Q:
                if role not in role_thr_multi:
                    continue
                qthr = role_thr_multi[role].get(q)
                if qthr is None:
                    continue
                st = cal_stat[q]
                hit_q = s["d2"] > qthr
                st["n"] += 1
                st["fp"] += int(hit_q)
                r = st["by_role"].setdefault(role, {"n": 0, "fp": 0})
                r["n"] += 1
                r["fp"] += int(hit_q)
                if hit_q and worst:
                    st["by_dim"][worst] = st["by_dim"].get(worst, 0) + 1
    def _fin(d):
        return {k: {"n": v["n"], "fp": v["fp"],
                    "rate": round(v["fp"] / v["n"], 4) if v["n"] else None}
                for k, v in sorted(d.items())}

    def _by_dim(dim_fp):
        return {d: {"n": dim_n[d], "fp": dim_fp.get(d, 0),
                    "rate": round(dim_fp.get(d, 0) / dim_n[d], 4) if dim_n.get(d) else None}
                for d in sorted(dim_n)}

    return {"profile": prof, "n_train_pages": train_n,
            "train_p95_d2": thr, "role_thresholds": role_thr,
            "test": {"n_pages": tot, "fp": fp,
                     "rate": round(fp / tot, 4) if tot else None,
                     "by_role": _fin(per_role), "by_dim": _by_dim(dim_fp_param)},
            "test_param": {"n_pages": tot_param, "fp": fp_param,
                           "rate": round(fp_param / tot_param, 4) if tot_param else None,
                           "by_role": _fin(per_role_param), "by_dim": _by_dim(dim_fp_param)},
            "test_calibrated": {"n_pages": tot_cal, "fp": fp_cal,
                                "rate": round(fp_cal / tot_cal, 4) if tot_cal else None,
                                "by_role": _fin(per_role_cal), "by_dim": _by_dim(dim_fp_cal)},
            "calibration": {str(q): {"quantile": q, "n_pages": st["n"], "fp": st["fp"],
                                    "rate": round(st["fp"] / st["n"], 4) if st["n"] else None,
                                    "by_role": _fin(st["by_role"]),
                                    "by_dim": _by_dim(st["by_dim"])}
                            for q, st in cal_stat.items()}}


def run_fp_protocol(rows: list[dict], *, k: int = 5, seed: int = 13,
                    min_pages: int = 30, progress=None) -> dict:
    """12.2：k 折交叉，报告「参数化阈值 / 经验校准阈值（P95/P96/P97）」多口径假阳率。"""
    folds = fold_split(rows, k=k, seed=seed)
    res = []
    for i, f in enumerate(folds, 1):
        r = evaluate_fold(rows, f, min_pages=min_pages)
        r.pop("profile", None)               # 档案太大，不进报告
        r["fold"] = i
        r["n_train_papers"] = len(f["train"])
        r["n_test_papers"] = len(f["test"])
        res.append(r)
        if progress:
            progress(i, r)
    agg = {"param": _agg_fp(res, "test_param"),
           "calibrated": _agg_fp(res, "test_calibrated")}
    cal: dict = {}
    for q in ("0.95", "0.96", "0.97"):
        tot = sum((f.get("calibration") or {}).get(q, {}).get("n_pages", 0) for f in res)
        fp = sum((f.get("calibration") or {}).get(q, {}).get("fp", 0) for f in res)
        by_role, by_dim = {}, {}
        for f in res:
            c = (f.get("calibration") or {}).get(q) or {}
            for role, v in (c.get("by_role") or {}).items():
                by_role.setdefault(role, {"n": 0, "fp": 0})
                by_role[role]["n"] += v["n"]
                by_role[role]["fp"] += v["fp"]
            for d, v in (c.get("by_dim") or {}).items():
                by_dim.setdefault(d, {"n": 0, "fp": 0})
                by_dim[d]["n"] += v["n"]
                by_dim[d]["fp"] += v["fp"]
        cal[q] = {"quantile": float(q), "n_pages": tot, "fp": fp,
                  "rate": round(fp / tot, 4) if tot else None,
                  "by_role": {r: {"n": v["n"], "fp": v["fp"],
                                  "rate": round(v["fp"] / v["n"], 4) if v["n"] else None}
                              for r, v in sorted(by_role.items())},
                  "by_dim": {d: {"n": v["n"], "fp": v["fp"],
                                 "rate": round(v["fp"] / v["n"], 4) if v["n"] else None}
                             for d, v in sorted(by_dim.items())}}
    return {"schema": "eval_fp.v1", "folds": res, "aggregate": agg,
            "calibration_table": cal, "target": 0.05,
            "ok": {kk: (vv["rate"] is not None and vv["rate"] <= 0.05)
                   for kk, vv in agg.items()},
            "ok_calibrated_quantiles": {q: (v["rate"] is not None and v["rate"] <= 0.05)
                                        for q, v in cal.items()}}


def _agg_fp(folds: list[dict], key: str) -> dict:
    tot = sum(f[key]["n_pages"] for f in folds)
    fp = sum(f[key]["fp"] for f in folds)
    by_role: dict = {}
    by_dim: dict = {}
    for f in folds:
        for role, v in f[key]["by_role"].items():
            by_role.setdefault(role, {"n": 0, "fp": 0})
            by_role[role]["n"] += v["n"]
            by_role[role]["fp"] += v["fp"]
        for d, v in (f[key].get("by_dim") or {}).items():
            by_dim.setdefault(d, {"n": 0, "fp": 0})
            by_dim[d]["n"] += v["n"] or 0
            by_dim[d]["fp"] += v["fp"] or 0
    return {"n_pages": tot, "fp": fp,
            "rate": round(fp / tot, 4) if tot else None,
            "by_role": {r: {"n": v["n"], "fp": v["fp"],
                            "rate": round(v["fp"] / v["n"], 4) if v["n"] else None}
                        for r, v in sorted(by_role.items())},
            "by_dim": {d: {"n": v["n"], "fp": v["fp"],
                           "rate": round(v["fp"] / v["n"], 4) if v["n"] else None}
                       for d, v in sorted(by_dim.items())}}


# ---------------------------------------------------------------- 12.3 会议可分性

def paper_features(rows: list[dict], dims: list[str]) -> dict:
    """论文级特征 = 该篇各维（页级）中位数；少于 3 页的论文不参与。"""
    by_paper: dict = {}
    for r in rows:
        by_paper.setdefault(r["paper"], []).append(r)
    out = {}
    for pid, rs in by_paper.items():
        if len(rs) < 3:
            continue
        feat, venue = {}, rs[0]["venue"]
        for d in dims:
            vals = sorted(v for v in (r["metrics"].get(d) for r in rs) if v is not None)
            if len(vals) >= 2:
                feat[d] = AE.percentile(vals, 0.5)
        if len(feat) >= max(2, len(dims) // 2):
            out[pid] = {"venue": venue, "feat": feat}
    return out


def _zscore_fit(papers: dict, dims: list[str]):
    med, iqr = {}, {}
    for d in dims:
        vals = sorted(p["feat"][d] for p in papers.values() if d in p["feat"])
        if not vals:
            continue
        med[d] = AE.percentile(vals, 0.5)
        s = AE.percentile(vals, 0.75) - AE.percentile(vals, 0.25)
        iqr[d] = s if s > 1e-9 else 1.0
    return med, iqr


def _zvec(p, dims, med, iqr):
    return [((p["feat"][d] - med[d]) / iqr[d]) if d in p["feat"] and d in med else None
            for d in dims]


def _dist(a, b):
    tot, n = 0.0, 0
    for x, y in zip(a, b):
        if x is None or y is None:
            continue
        tot += (x - y) ** 2
        n += 1
    return (tot / n) ** 0.5 if n else None


def knn_accuracy(items: list[tuple], dims: list[str], *, k: int = 1) -> float | None:
    """留一交叉验证的 k-NN 准确率（items: [(label, feature_vec)]，已 z 标准化）。"""
    if len(items) < 4:
        return None
    hit = 0
    for i, (lab, vec) in enumerate(items):
        ds = []
        for j, (lab2, vec2) in enumerate(items):
            if i == j:
                continue
            d = _dist(vec, vec2)
            if d is not None:
                ds.append((d, lab2))
        if not ds:
            continue
        ds.sort(key=lambda t: t[0])
        top = [l for _, l in ds[:k]]
        best = max(set(top), key=top.count)
        hit += int(best == lab)
    return round(hit / len(items), 4)


def permutation_pvalue(observed: float, null: list[float]) -> float | None:
    """置换检验（单侧）：(1 + #{null >= obs}) / (1 + N)。"""
    if observed is None or not null:
        return None
    ge = sum(1 for v in null if v is not None and v >= observed)
    return round((1 + ge) / (1 + len(null)), 4)


def run_separability(rows: list[dict], dims: list[str], *, min_papers: int = 20,
                     perms: int = 50, seed: int = 7) -> dict:
    """12.3：用论文级画像特征做会议分类（留一 1-NN），置换检验 vs 随机。"""
    papers = paper_features(rows, dims)
    cnt: dict = {}
    for p in papers.values():
        cnt[p["venue"]] = cnt.get(p["venue"], 0) + 1
    venues = sorted(v for v, c in cnt.items() if v and c >= min_papers)
    sel = {pid: p for pid, p in papers.items() if p["venue"] in venues}
    if len(venues) < 2 or len(sel) < 2 * min_papers:
        return {"status": "skipped", "why": "会议数或论文数不足",
                "n_papers": len(sel), "venues": venues}
    med, iqr = _zscore_fit(sel, dims)
    items = [(p["venue"], _zvec(p, dims, med, iqr)) for p in sel.values()]
    obs = knn_accuracy(items, dims, k=1)
    labels = [lab for lab, _ in items]
    null = []
    rnd = random.Random(seed)
    for _ in range(perms):
        shuf = labels[:]
        rnd.shuffle(shuf)
        null.append(knn_accuracy([(shuf[i], items[i][1]) for i in range(len(items))],
                                 dims, k=1))
    maj = max(cnt[v] for v in venues) / sum(cnt[v] for v in venues)
    return {"status": "ok", "n_papers": len(items), "n_venues": len(venues),
            "venues": venues, "accuracy_loo_1nn": obs,
            "majority_baseline": round(maj, 4),
            "chance_uniform": round(1.0 / len(venues), 4),
            "null_mean": (round(sum(v for v in null if v is not None)
                                / max(1, len([v for v in null if v is not None])), 4)
                          if any(v is not None for v in null) else None),
            "p_value": permutation_pvalue(obs, null), "n_permutations": perms,
            "significantly_above_chance": (permutation_pvalue(obs, null) or 1.0) <= 0.05}


# ---------------------------------------------------------------- 12.4 稳定性

def stability_determinism(rows: list[dict], profile: dict, *, n_docs: int = 5) -> dict:
    """同文档重复测量（test–retest）：两次评估必须逐字节一致。"""
    docs = docs_from_rows(rows)[:n_docs]
    same, checked = True, 0
    for _pid, venue, layout, doc in docs:
        a = AE.evaluate_doc(doc, profile, venue=venue)
        b = AE.evaluate_doc(doc, profile, venue=venue)
        checked += 1
        if json.dumps(a, sort_keys=True) != json.dumps(b, sort_keys=True):
            same = False
    return {"ok": same, "n_docs": checked, "identical": same}


def stability_metrics_spread(base_items: list[dict], other_items: list[dict],
                             dims: list[str]) -> dict:
    """两次测量（不同渲染器/DPI）的指标相对漂移：max |Δ| / |base|（逐维）。"""
    out, worst = {}, 0.0
    for d in dims:
        b = [float(i[d]) for i in base_items if i.get(d) is not None]
        o = [float(i[d]) for i in other_items if i.get(d) is not None]
        if len(b) < 3 or len(b) != len(o):
            out[d] = None
            continue
        mb = sum(b) / len(b)
        mo = sum(o) / len(o)
        rel = abs(mo - mb) / abs(mb) if abs(mb) > 1e-9 else (0.0 if abs(mo) < 1e-9 else None)
        out[d] = None if rel is None else round(rel, 6)
        if rel is not None:
            worst = max(worst, rel)
    return {"max_rel_drift": round(worst, 6), "by_dim": out,
            "ok": worst < 0.05, "target": 0.05}


def stability_dpi(pdf_path: str, dims: list[str], *, dpi_a: int = 50,
                  dpi_b: int = 200, venue=None) -> dict:
    """12.4：渲染 DPI 变更下的指标漂移（本模型 8 维取自矢量/文本层，应恒为 0）。"""
    from . import extract as EX
    da = EX.extract_pdf(pdf_path, venue=venue, pixels=True, dpi=dpi_a)
    db = EX.extract_pdf(pdf_path, venue=venue, pixels=True, dpi=dpi_b)
    ia = [dict(PROF.page_metric_items(p)) for p in da["pages"]]
    ib = [dict(PROF.page_metric_items(p)) for p in db["pages"]]
    res = stability_metrics_spread(ia, ib, dims)
    res["dpi_a"], res["dpi_b"] = dpi_a, dpi_b
    res["note"] = ("像素代理量（ink_ratio / max_gap）会随 DPI 变；判定用的 8 维"
                   "来自矢量/文本层，理论上与 DPI 无关 —— 本检验即验证这一点")
    return res


def stability_recompile(tex_path: str, dims: list[str], outdir: str, *,
                        runs: int = 2, **kw) -> dict:
    """12.4：同一 .tex 重复编译两次，比较页级指标漂移（需要 LaTeX 工具链）。"""
    from . import engine, extract as EX
    sigs = []
    for i in range(runs):
        wd = os.path.join(outdir, f"recomp{i}")
        os.makedirs(wd, exist_ok=True)
        eng = engine.Engine(tex_path, workdir=wd, **kw)
        ok = eng.compile()
        if not ok or not eng.pdf_path:
            return {"status": "error", "why": f"第 {i + 1} 次编译失败"}
        doc = EX.extract_pdf(eng.pdf_path)
        sigs.append([dict(PROF.page_metric_items(p)) for p in doc["pages"]])
    if len(sigs) < 2:
        return {"status": "error", "why": "编译次数不足"}
    res = stability_metrics_spread(sigs[0], sigs[1], dims)
    res["status"] = "ok"
    res["runs"] = runs
    return res


# ---------------------------------------------------------------- 12.5 人类相关性

def spearman_rank(model: list[float], human: list[float]) -> float | None:
    """12.5（探索性）：模型排序与人类排序的 Spearman 相关。数据未采集时返回 None。

    与 `profile.spearman` 同口径：样本 < 8 对时不给结论（防止小样本上的假相关）。
    """
    if not model or not human or len(model) != len(human) or len(model) < 8:
        return None
    return PROF.spearman([float(x) for x in model], [float(x) for x in human])


# ---------------------------------------------------------------- 12.6 验收门槛

def gate_dim(dim: str, *, monotone: dict | None, fp: dict | None,
             stable: dict | None) -> dict:
    """单指标门槛：三项都过才可纳入 A（方案 12.6）。未过者只能作报告项。"""
    reasons = []
    if monotone is None:
        reasons.append("12.1 单调性：未测")
    elif not monotone.get("ok"):
        reasons.append(f"12.1 单调性不过（违反 {monotone.get('violations')} 次）")
    if fp is None:
        reasons.append("12.2 假阳率：未测")
    elif fp.get("rate") is None:
        reasons.append("12.2 假阳率：样本不足")
    elif fp["rate"] > 0.05:
        reasons.append(f"12.2 假阳率 {fp['rate']:.4f} > 0.05")
    if stable is None:
        reasons.append("12.4 稳定性：未测")
    elif not stable.get("ok", False):
        reasons.append(f"12.4 稳定性不过（漂移 {stable.get('max_rel_drift')}）")
    return {"dim": dim, "verdict": "pass" if not reasons else "report-only",
            "reasons": reasons}


def stability_by_dim(stability: dict | None) -> tuple[dict, bool | None]:
    """从 12.4 结果里取出「逐维漂移 + 总体是否通过」。

    兼容两种形状：
      · 扁平：{"by_dim": {dim: drift}, "ok": bool}（调用方直接喂 12.4 的 dpi 结果）
      · 报告：{"determinism": …, "dpi": {"by_dim": …}, "render": …}（`do_stability` 原样返回）
    第二种曾导致门槛永远读到「12.4 稳定性：未测」——踩过。
    """
    if not stability:
        return {}, None
    if "by_dim" in stability:
        return stability.get("by_dim") or {}, stability.get("ok")
    dpi = stability.get("dpi") or {}
    if isinstance(dpi, dict) and dpi.get("status") not in ("error", "skipped"):
        return dpi.get("by_dim") or {}, dpi.get("ok")
    return {}, None


def gate_verdicts(dims: list[str], injection: dict | None, fp: dict | None,
                  stability: dict | None) -> dict:
    """把 12.1 / 12.2 / 12.4 的结果汇成逐维门槛结论。"""
    by_dim_mono = (injection or {}).get("by_dim") or {}
    fp_by_dim = (fp or {}).get("by_dim") or {}
    st, stable_ok = stability_by_dim(stability)
    out, dropped = {}, []
    for d in dims:
        m = by_dim_mono.get(d)
        mono = {"ok": bool(m)} if m is not None else None
        f = fp_by_dim.get(d)
        fpr = {"rate": f} if isinstance(f, (int, float)) else None
        s = None
        if stable_ok is not None and d in st:
            s = {"ok": bool(stable_ok) if st[d] is None else st[d] < 0.05,
                 "max_rel_drift": st[d]}
        v = gate_dim(d, monotone=mono, fp=fpr, stable=s)
        out[d] = v
        if v["verdict"] != "pass":
            dropped.append(d)
    return {"schema": "eval_gate.v1", "dims": dims, "verdicts": out,
            "dropped": dropped, "n_pass": len(dims) - len(dropped),
            "note": "verdict != pass 的指标按方案 12.6 只能作报告项，不得参与 A"}


def load_gate(path: str) -> dict | None:
    if not path or not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            g = json.load(f)
    except Exception:
        return None
    return g if g.get("schema") == "eval_gate.v1" else None
