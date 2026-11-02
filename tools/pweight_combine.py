#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P 权重：把多轮标定表的作答合并成一条曲线，估每类缺陷的无差异点 c*。

背景（2026-11-02）：
    单轮阶梯只能给出「落在这两档之间」的信息，第一轮阶梯（I=8/15）偏高、第二轮
    （I=2/4/6）偏低，各自求 c* 都会贴到边界（8 或 2），权重退化成常数。
    本工具把两轮的点并到一条 b(c) 曲线上，用**翻转区间**估 c*：

        b(c) = 1  → 选「修好版」（值得修）
        b(c) = .5 → 选「差不多」（无差异）
        b(c) = 0  → 选「缺陷版」（不划算，宁可留缺陷）

        c_lo = 满足 b >= 0.5 的最大代价（还愿意修的上界）
        c_hi = 满足 b == 0 的最小代价（开始宁留缺陷的下界）
        c*   = (c_lo + c_hi) / 2     两点都有时
             = c_hi                 只有 b == 0（c* 是上界）
             = c_lo                 只有 b >= 0.5（c* 是下界）

    若阶段 13 的旧标定给过同名缺陷的区间（overfull / widetable），用作先验区间
    与本次结果求交（2 人时复核用得上；单人时只是收窄）。

输出：metrics/p_weight_tradeoff_<date>.json，并在终端打印三种归一化口径。

用法：
    python3 tools/pweight_combine.py \
        --rounds workbench-pweight,workbench-pweight2 \
        --out metrics/p_weight_tradeoff_20261102.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# 标定表里的 defect id → score.PAGE_DEFECT_WEIGHT 的键
KEY_MAP = {"widetable": "tab_overwide"}
REPORT_DEFAULT = os.path.join("metrics", "p_weight_tradeoff_20261102.json")
# 阶段 13 的旧标定（metrics/rho_tradeoff_20261031.json）里能一一对上的缺陷
PRIOR_FROM_STAGE13 = {"overfull": (10.5, 12.5), "widetable": (6.0, 8.0)}


def load_round(work: str, answers_name: str = "answers.json") -> dict:
    base = os.path.join(ROOT, work)
    key = json.load(open(os.path.join(base, "key.json"), encoding="utf-8"))
    ans = json.load(open(os.path.join(base, answers_name), encoding="utf-8"))
    got = {int(a["q"]): a["choice"] for a in ans.get("answers", [])}
    pts, nulls = {}, {"n": 0, "correct": 0}
    for q in key["questions"]:
        ch = got.get(q["q"])
        if ch is None:
            continue
        if q["defect"] == "null":
            nulls["n"] += 1
            nulls["correct"] += (ch == "same")
            continue
        b = 0.5 if ch == "same" else (
            1.0 if ((ch == "left") == (q["left_is"] == "B")) else 0.0)
        pts.setdefault(q["defect"], []).append([q["cost"], b])
    return {"work": work, "ts": ans.get("ts"), "points": pts, "nulls": nulls,
            "costs": sorted({c for v in pts.values() for c, _ in v})}


def estimate(points: list, prior: tuple | None = None) -> dict:
    pts = sorted({(float(c), float(b)) for c, b in points})
    b_ge = [c for c, b in pts if b >= 0.5]
    b_0 = [c for c, b in pts if b == 0.0]
    c_lo = max(b_ge) if b_ge else None
    c_hi = min(b_0) if b_0 else None
    prior_applied = False
    if prior:
        p_lo, p_hi = prior
        new_lo = p_lo if c_lo is None else max(c_lo, p_lo)
        new_hi = p_hi if c_hi is None else min(c_hi, p_hi)
        if new_lo <= new_hi:
            c_lo, c_hi, prior_applied = new_lo, new_hi, True
    if c_lo is not None and c_hi is not None:
        cstar, kind = (c_lo + c_hi) / 2, "区间中点"
    elif c_hi is not None:
        cstar, kind = c_hi, "上界（从未见过 b>=0.5）"
    else:
        cstar, kind = c_lo, "下界（从未见过 b==0）"
    return {"points": [[c, b] for c, b in pts], "c_lo": c_lo, "c_hi": c_hi,
            "cstar": None if cstar is None else round(cstar, 3),
            "kind": kind, "prior_from_stage13": prior if prior_applied else None}


def load_applied(path: str) -> dict | None:
    p = os.path.join(ROOT, path) if not os.path.isabs(path) else path
    if not os.path.isfile(p):
        return None
    return json.load(open(p, encoding="utf-8"))


def write_applied(report: dict, date: str = "20261102") -> str:
    from texopt import score as S

    kept = report["proposed_weights_kept_sum"]
    cur = dict(S.PAGE_DEFECT_WEIGHT)
    applied = {
        "schema": "texopt.p_weight_applied.v1",
        "source": os.path.relpath(REPORT_DEFAULT, ROOT).replace(os.sep, "/"),
        "method": "w = c*/ρ（两轮无差异点合并），口径 A：整体缩放使 7 项权重和与旧值相等，ρ=15 不动",
        "rho": report["rho_used"],
        "scale_factor": report["rescale_to_keep_sum"],
        "sum_before": report["sum_old_measured"],
        "sum_after": round(sum(kept.values()), 3),
        "page_defect_weight": {k: kept[k] for k in sorted(kept)},
        "untouched_priors": report["untouched_priors"],
        "row_ids": [r["work"] for r in report["rounds"]],
    }
    p = os.path.join(ROOT, "metrics", f"pweight_applied_{date}.json")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    json.dump(applied, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    diffs = {k: (cur.get(k), kept[k]) for k in kept}
    return p + "\n" + "\n".join(
        f"  {k:<14} {str(o):>8} -> {n:>8}" for k, (o, n) in diffs.items())


def check_applied(path: str = "metrics/pweight_applied_20261102.json",
                  tol: float = 1e-6) -> list[str]:
    from texopt import score as S

    d = load_applied(path)
    if not d:
        return [f"缺少 artifact：{path}"]
    bad = []
    for k, v in d["page_defect_weight"].items():
        cur = S.PAGE_DEFECT_WEIGHT.get(k)
        if cur is None or abs(cur - v) > tol:
            bad.append(f"PAGE_DEFECT_WEIGHT[{k}] 代码={cur} artifact={v}")
    return bad


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", default="workbench-pweight,workbench-pweight2")
    ap.add_argument("--out", default="metrics/p_weight_tradeoff_20261102.json")
    ap.add_argument("--rho", type=float, default=15.0)
    ap.add_argument("--apply", action="store_true", help="写 applied artifact")
    ap.add_argument("--check", action="store_true", help="校验 score.py 与 artifact 一致")
    a = ap.parse_args()

    if a.check:
        bad = check_applied()
        print("[check] " + ("OK" if not bad else "漂移:\n  " + "\n  ".join(bad)))
        return 0 if not bad else 1

    from texopt import score as S

    rounds = [load_round(w.strip()) for w in a.rounds.split(",") if w.strip()]
    pooled: dict[str, list] = {}
    for r in rounds:
        for d, pts in r["points"].items():
            pooled.setdefault(d, []).extend(pts)

    per, proposed = {}, {}
    for d in sorted(pooled):
        est = estimate(pooled[d], PRIOR_FROM_STAGE13.get(d))
        est["key"] = KEY_MAP.get(d, d)
        est["rho"] = a.rho
        est["w"] = None if est["cstar"] is None else round(est["cstar"] / a.rho, 3)
        per[d] = est
        if est["w"] is not None:
            proposed[est["key"]] = est["w"]

    # 旧权重基线：优先取第一次 import 时记下的 old（避免二次运行把新值当旧值，形成自我迭代）
    current = dict(S.PAGE_DEFECT_WEIGHT)
    base_f = os.path.join(ROOT, "metrics", "p_weight_tradeoff_round1_20261102.json")
    if os.path.isfile(base_f):
        try:
            r1 = json.load(open(base_f, encoding="utf-8"))
            for d in r1.get("diffs", []):
                if d.get("old") is not None:
                    current[d["key"]] = d["old"]
        except Exception:
            pass
    measured = set(proposed)
    sum_old = round(sum(current[k] for k in measured if k in current), 3)
    sum_new = round(sum(proposed.values()), 3)
    k = round(sum_old / sum_new, 4) if sum_new else None

    diffs = [{"key": kk, "old": current.get(kk), "new": proposed[kk],
              "ratio": None if not current.get(kk) else round(proposed[kk] / current[kk], 3)}
             for kk in sorted(proposed)]

    report = {
        "schema": "texopt.p_weight_tradeoff.v2",
        "method": ("两轮作答合并成一条 b(c) 曲线；c* = 翻转区间中点（见 tools/pweight_combine.py）；"
                   "w = c* / ρ"),
        "rho_used": a.rho,
        "rounds": [{"work": r["work"], "ts": r["ts"], "costs": r["costs"],
                    "nulls": r["nulls"]} for r in rounds],
        "null_total": {"n": sum(r["nulls"]["n"] for r in rounds),
                       "correct": sum(r["nulls"]["correct"] for r in rounds)},
        "per_defect": per,
        "proposed_weights_raw": proposed,
        "untouched_priors": {kk: v for kk, v in current.items() if kk not in measured},
        "sum_old_measured": sum_old,
        "sum_new_raw": sum_new,
        "rescale_to_keep_sum": k,
        "proposed_weights_kept_sum": {kk: round(v * k, 3) for kk, v in proposed.items()} if k else None,
        "rho_if_unscaled": round(a.rho * k, 3) if k else None,
        "diffs": diffs,
        "warnings": [
            "六类缺陷在 4–12mm 代价带内全部判「差不多」，16mm 起翻成「缺陷更好」："
            "只隔一档，彼此的差别低于本次阶梯的分辨率，权重只能给到同一层级。",
        ],
    }
    for d, e in per.items():
        if e["kind"].startswith("上界"):
            report["warnings"].append(f"{d}：只见过 b==0，c* 是其上界 {e['c_hi']}（阶段13 先验帮助收窄）")

    out = os.path.join(ROOT, a.out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump(report, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    if a.apply:
        print("[apply] " + write_applied(report))

    print(f"作答轮次：{', '.join(r['work'] for r in rounds)}"
          f" | 空题 {report['null_total']['correct']}/{report['null_total']['n']}")
    for d, e in per.items():
        print(f"  {d:12s} c*={e['cstar']:>6} (lo={e['c_lo']}, hi={e['c_hi']}, {e['kind']})"
              f"  w={e['w']}")
    print(f"\n旧和={sum_old} 新和={sum_new} 缩放系数 k={k}")
    print(f"  口径A 保持总权重和： {report['proposed_weights_kept_sum']}")
    print(f"  口径B 不缩放、ρ 等比下调： ρ={report['rho_if_unscaled']}")
    print(f"  口径C 不缩放、ρ 不动： {proposed}")
    print(f"\n-> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
