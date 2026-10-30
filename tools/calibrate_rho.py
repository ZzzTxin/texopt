# -*- coding: utf-8 -*-
"""ρ 标定（等边际收益口径）：用闭环实际数据定 W_PAGE_DEFECT。

模型1：M1 = ρ·P + I
  P = 页面缺陷（加权条数）    I = 干预代价（边距/字号/浮动体/图宽改动量）

「等边际收益」的定义（2026-10-30 用户拍定）：
  修掉 1 单位缺陷，与付出 1 单位干预代价，**边际价值相等**。
  ⇒ ρ 就是闭环里**实际付出**的干预代价 / 修掉的缺陷：
        ρ = ΔI / (−ΔP)     （对每个尝试动作分别测量，ΔP<0 的那些）

为什么用「每个尝试动作」而不是「被接受的动作」：
  接受与否本身依赖 ρ（M1 里就带着 ρ），只统计被接受的动作会把数据变成
  自己论证自己。每次动作的 (ΔP, ΔI) 是在编译后直接量出来的，与 ρ 无关。

输入（两种来源可混用）：
  1. `--run <tex>`：真跑一遍确定性闭环，用运行内存里的 baseline + records；
  2. `--state <state.json>`：读历史运行的 steps（首次动作的 delta 无法还原 → 跳过）。

输出：metrics/rho_exchange_rate.json + 终端报告；`--apply` 才回写 score.py 的 ρ。
"""
from __future__ import annotations

import argparse
import json
import os
import statistics as st
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
ARTIFACT = os.path.join(ROOT, "metrics", "rho_exchange_rate.json")
SCORE = os.path.join(ROOT, "texopt", "score.py")

# ρ 的可用区间：低于 0.2 等于「缺陷几乎不要紧」，高于 10 等于「改一点都不划算」
RHO_MIN, RHO_MAX = 0.2, 10.0


def _deltas_from_steps(steps: list[dict]) -> list[dict]:
    """由 steps 还原每次动作的 (ΔP, ΔI)；首条无法还原 → 跳过。"""
    out = []
    prev = None
    for s in steps:
        p, i = s.get("p"), s.get("i")
        if p is None or i is None:
            continue
        if prev is not None:
            dp, di = p - prev[0], i - prev[1]
            out.append({"action": s.get("action"), "accepted": s.get("accepted"),
                        "dP": round(dp, 4), "dI": round(di, 4),
                        "pages": s.get("pages"),
                        "source": s.get("source", "rule")})
        if s.get("accepted"):
            prev = (p, i)
        elif prev is None:
            prev = (p, i)           # 首次动作被回滚 → 该状态就是基线
    return out


def harvest_state(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        state = json.load(f)
    steps = state.get("steps") or []
    return {"doc": path, "status": state.get("status"),
            "steps": len(steps), "deltas": _deltas_from_steps(steps)}


def harvest_run(tex: str, outdir: str, req_kwargs: dict | None = None) -> dict:
    """真跑一遍确定性闭环，取 baseline + records。"""
    from texopt.core import Optimizer
    from texopt.requirements import Requirement
    req = Requirement(**{k: v for k, v in (req_kwargs or {}).items()
                         if hasattr(Requirement, k)})
    opt = Optimizer(tex, req, outdir)
    res = opt.run()
    base = opt.baseline or {}
    deltas = []
    prev = (base.get("p"), base.get("i"))
    if prev[0] is not None:
        for rec in opt.records:
            p, i = rec.get("p"), rec.get("i")
            if p is None or i is None:
                continue
            deltas.append({"action": rec.get("action"),
                           "accepted": rec.get("accepted"),
                           "dP": round(p - prev[0], 4),
                           "dI": round(i - prev[1], 4),
                           "pages": rec.get("pages"),
                           "source": rec.get("source", "rule")})
            if rec.get("accepted"):
                prev = (p, i)
    return {"doc": tex, "status": res.get("status"), "steps": len(opt.records),
            "deltas": deltas}


def rho_stats(deltas: list[dict]) -> dict:
    """等边际收益：ρ = ΔI / (−ΔP)，只取真正修掉缺陷的动作（ΔP < 0）。

    两个口径都要看：
      rho_paid  —— 只在**真的付了代价**（ΔI > 0）的动作上算。
                   「交出 I 换掉 P」这件事只在这类动作里发生，才是汇率；
      rho_all   —— 含免费修复（ΔI = 0）。免费修复在任何 ρ > 0 下都会发生，
                   不携带汇率信息，只说明「有些缺陷根本不用付代价」。
    标定取 rho_paid（无付费样本时退回 rho_all）。
    """
    rows = []
    for d in deltas:
        if d["dP"] >= -1e-9:
            continue
        removal = -d["dP"]
        rows.append({"action": d["action"], "removal": removal,
                     "cost": d["dI"], "rho": d["dI"] / removal,
                     "accepted": d["accepted"], "pages": d.get("pages")})
    rhos = [r["rho"] for r in rows]
    paid = [r["rho"] for r in rows if r["cost"] > 1e-9]
    out = {"n_actions": len(deltas), "n_repairs": len(rows),
           "n_paid": len(paid),
           "n_free": len(rows) - len(paid),
           "rows": rows}
    if rhos:
        out.update({
            "rho_all_median": round(st.median(rhos), 4),
            "rho_median": round(st.median(paid), 4) if paid
            else round(st.median(rhos), 4),
            "rho_p25": round(_pct(paid or rhos, 25), 4),
            "rho_p75": round(_pct(paid or rhos, 75), 4),
            "basis": "paid" if paid else "all",
        })
    return out


def _pct(xs: list[float], q: float) -> float:
    xs = sorted(xs)
    if len(xs) == 1:
        return xs[0]
    k = (len(xs) - 1) * q / 100.0
    lo, hi = int(k), min(int(k) + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def decide(stats_rows: list[dict]) -> dict:
    """汇总多篇：优先用「付费」动作的 ρ 中位数，裁剪到 [RHO_MIN, RHO_MAX]。"""
    all_rows = [r for s in stats_rows for r in s["rows"]]
    paid = [r["rho"] for r in all_rows if r["cost"] > 1e-9]
    rhos = paid or [r["rho"] for r in all_rows]
    if not rhos:
        return {"ok": False, "reason": "没有可用的修复动作（ΔP<0 为 0 条）"}
    med = st.median(rhos)
    clipped = min(max(med, RHO_MIN), RHO_MAX)
    return {"ok": True, "rho_raw": round(med, 4),
            "rho_applied": round(clipped, 3),
            "clipped": abs(clipped - med) > 1e-9,
            "n": len(rhos),
            "n_free_excluded": len(all_rows) - len(paid),
            "p25": round(_pct(rhos, 25), 4),
            "p75": round(_pct(rhos, 75), 4),
            "basis": "paid" if paid else "all",
            "note": "ρ = 实际付出的干预代价 / 修掉的缺陷（等边际收益）；"
                    "只在 ΔI>0 的动作上取汇率（免费修复不携带汇率信息），"
                    "按每次**尝试**动作统计（不因 ρ 的选择效应而失真）"}


def write_artifact(rows: list[dict], decision: dict, path: str = ARTIFACT) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    payload = {"schema": "texopt.rho_exchange_rate.v1",
               "definition": "等边际收益：ρ = ΔI / (−ΔP)",
               "decision": decision,
               "per_doc": [{"doc": r["doc"], "status": r["status"],
                            "n_actions": r["n_actions"],
                            "n_repairs": r["n_repairs"],
                            "rho_median": r.get("rho_median"),
                            "rows": r["rows"]} for r in rows]}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", nargs="*", default=[], help="要真跑的 .tex")
    ap.add_argument("--state", nargs="*", default=[], help="已有 state.json")
    ap.add_argument("--recompute", default=None,
                    help="只从已有 artifact 的 rows 重算 ρ（不重新编译）")
    ap.add_argument("--outdir", default=os.path.join(ROOT, "workbench-rho"))
    ap.add_argument("--apply", action="store_true", help="把 ρ 写回 score.py")
    ap.add_argument("--write", action="store_true", help="写 artifact")
    args = ap.parse_args()
    if args.recompute:
        with open(args.recompute, encoding="utf-8") as f:
            old = json.load(f)
        stats = []
        for doc in old.get("per_doc") or []:
            rows_ = doc.get("rows") or []
            paid = [r["rho"] for r in rows_ if r["cost"] > 1e-9]
            stats.append({"doc": doc["doc"], "status": doc.get("status"),
                          "n_actions": doc.get("n_actions"),
                          "n_repairs": len(rows_), "n_paid": len(paid),
                          "n_free": len(rows_) - len(paid),
                          "rows": rows_,
                          "basis": "paid" if paid else "all",
                          "rho_median": round(st.median(paid), 4) if paid
                          else (round(st.median([r["rho"] for r in rows_]), 4)
                                if rows_ else None)})
        decision = decide(stats)
        print("\n== ρ（等边际收益，重算）==")
        for k, v in decision.items():
            print(f"  {k}: {v}")
        if decision.get("ok") and args.write:
            print("[写]", write_artifact(stats, decision))
        return 0 if decision.get("ok") else 1
    if not args.run and not args.state:
        ap.error("至少给 --run 或 --state")
    rows = []
    for tex in args.run:
        od = os.path.join(args.outdir, os.path.splitext(os.path.basename(tex))[0])
        print(f"[跑] {tex} → {od}")
        h = harvest_run(tex, od)
        s = rho_stats(h["deltas"])
        s.update({"doc": h["doc"], "status": h["status"]})
        rows.append(s)
        print(f"     状态={h['status']}  动作={s['n_actions']}  "
              f"修缺陷={s['n_repairs']}  ρ中位={s.get('rho_median')}")
    for pth in args.state:
        h = harvest_state(pth)
        s = rho_stats(h["deltas"])
        s.update({"doc": h["doc"], "status": h["status"]})
        rows.append(s)
        print(f"[读] {pth}  动作={s['n_actions']}  修缺陷={s['n_repairs']}  "
              f"ρ中位={s.get('rho_median')}")
    decision = decide(rows)
    print("\n== ρ（等边际收益）==")
    for k, v in decision.items():
        print(f"  {k}: {v}")
    if decision.get("ok") and args.write:
        print("[写]", write_artifact(rows, decision))
    if decision.get("ok") and args.apply:
        print("[提示] 回写请手工改 score.py 的 W_PAGE_DEFECT =",
              decision["rho_applied"], "（并同步注释里的含义）")
    return 0 if decision.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
