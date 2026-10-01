#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""calibrate_weights.py —— 阶段 7：审美权重校准（方案 10.3 步骤二/三）。

在**缓存的页级指标**上跑可控退化消融（不重新渲染 PDF）：

    每个维度 → 信号（该维被退化时自己的损失增量）
             噪声（别的维被退化时它乱动的幅度）
        w_d ∝ 信噪比 → 裁剪 [0.25, 4] → 归一到均值 1（相对权重）
        bootstrap（**按论文聚类**重采样）→ 5%/95% 区间

验收：只有「退化后 A 上升的正向率不下降」+「中位判别间隔严格变大」+「权重不越界」
才写 `applied=true`；否则保留等权并如实记 `applied=false` + 原因。

产出：
    metrics/profiles/aesthetic_weights.json          权重块（含 CI / 信号 / 噪声）
    metrics/profiles/aesthetic_weights_report.md     人读报告
    （--apply）把权重块挂回 aesthetic_profile.json 的 "weights" 键

用法：
    python3 tools/calibrate_weights.py                    # 干跑（不落盘档案）
    python3 tools/calibrate_weights.py --trials 120 --apply
    python3 tools/calibrate_weights.py --pairs human/pairs.json   # 步骤三（人类数据）
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
DS = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(DS))
sys.path.insert(0, ROOT)

PAGES = os.path.join(DS, "metrics", "pages")
PROF = os.path.join(DS, "metrics", "profiles", "aesthetic_profile.json")
OUT = os.path.join(DS, "metrics", "profiles")


def _p(msg):
    print(msg, flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", default=PAGES)
    ap.add_argument("--profile", default=PROF)
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--trials", type=int, default=80, help="消融试验数（每试验一次页级退化）")
    ap.add_argument("--bootstrap", type=int, default=200)
    ap.add_argument("--pairs", default=None, help="人类成对比较数据（步骤三；默认无）")
    ap.add_argument("--apply", action="store_true", help="把权重块挂回档案文件")
    args = ap.parse_args()

    from texopt import profile as PROF_, shadow as SH, weights as WT

    rows, papers, bad = PROF_.load_pages(args.pages)
    prof = SH.load_profile(args.profile)
    if not prof:
        print("档案缺 mahalanobis 块，先跑 build_profile.py", file=sys.stderr)
        return 2
    drop = SH.gate_drop_dims()
    t0 = time.time()
    _p(f"阶段 7 权重校准：{len(papers)} 篇 / {len(rows)} 页；档案 "
       f"{prof.get('profile_version')}；门槛剔除 {drop or '无'}")

    dims = [d for d in WT._default_dims(prof) if d not in drop]
    trials = WT.ablation_trials(rows, prof, dims=dims, n_pages=args.trials,
                                gate_drop=drop)
    block = WT.weights_from_trials(trials, dims, n_boot=args.bootstrap,
                                   gate_drop=drop)
    _p(f"  步骤二（消融）：{block['n_trials']} 组试验，"
       f"{len(block['by_dim'])} 维权重 + bootstrap {block['n_boot']} 次")
    w = {d: v["w"] for d, v in block["by_dim"].items()}
    eq = WT.margin_stats(trials)
    cal = WT.margin_stats(trials, w)
    verdict = WT.accept_verdict(eq, cal, weights=w)
    block["applied"] = bool(verdict["applied"])
    block["verdict"] = verdict
    _p(f"  判别间隔（退化后 A − 基线）：等权中位 {eq['median']} → 校准后 {cal['median']}"
       f"（正向率 {eq['positive_rate']} → {cal['positive_rate']}）")
    _p(f"  验收：{'接受（applied=true）' if block['applied'] else '不接受（保留等权）'}"
       + ("" if block["applied"] else f" — {'；'.join(verdict['reasons'])}"))

    pairs = WT.load_pairs(args.pairs) if args.pairs else []
    bt = WT.fit_bradley_terry(pairs, list(block["by_dim"])) if pairs else None
    if bt:
        _p(f"  步骤三（人类成对比较）：{bt['n_pairs']} 对，成对准确率 "
           f"{bt['pair_accuracy']} → 权重改由人类标定结果覆盖")
    else:
        _p("  步骤三（人类成对比较）：未采集数据（如实记 null；不包装成已标定）")
    block = WT.merge_human(block, bt)
    block["built_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    block["profile_version"] = prof.get("profile_version")

    os.makedirs(args.out, exist_ok=True)
    wp = os.path.join(args.out, "aesthetic_weights.json")
    WT.save(block, wp)
    if args.apply:
        prof2 = WT.apply_to_profile(prof, block)
        with open(args.profile, "w", encoding="utf-8") as f:
            json.dump(prof2, f, ensure_ascii=False, indent=1)
        _p(f"  已挂回档案：{args.profile} → weights.applied={block['applied']}")
    _write_report(os.path.join(args.out, "aesthetic_weights_report.md"),
                  block, prof, eq, cal, trials)
    _p(f"输出：{wp} / aesthetic_weights_report.md（用时 {time.time() - t0:.1f}s）")
    return 0


def _write_report(path, block, prof, eq, cal, trials):
    L = ["# 阶段 7 权重校准报告（方案 10.3 步骤二/三）", "",
         f"- 生成：{block.get('built_at')}；档案 {block.get('profile_version')}；"
         f"方法：{block.get('method')}；试验 {block.get('n_trials')} 组；"
         f"bootstrap {block.get('n_boot')} 次（按论文聚类）",
         f"- 结论：**applied = {block.get('applied')}**"
         + ("" if block.get("applied") else
            "（验收未过 → 保留等权；原因见下）"),
         "- 诚实边界：权重是**相对权重**（均值 1），只影响 A_profile 的排序口径；"
         "λ 仍为 0，不参与优化验收。人类成对比较（步骤三）数据未采集时如实记 null。", ""]
    v = block.get("verdict") or {}
    L += ["## 验收（不劣化才启用）", "",
          f"- 退化后 A 上升的正向率：等权 {eq.get('positive_rate')} → "
          f"校准后 {cal.get('positive_rate')}（不得下降）",
          f"- 中位判别间隔：等权 {eq.get('median')} → 校准后 {cal.get('median')}"
          f"（须严格变大）",
          f"- 结论：{'接受' if block.get('applied') else '不接受'}"
          + (f"；原因：{'；'.join(v.get('reasons') or [])}" if v.get("reasons") else ""), ""]
    L += ["## 逐维权重（信号 / 噪声 / 信噪比 / 95% CI）", "",
          "| 维度 | w | CI(5%,95%) | 信号 | 噪声 | SN | n(信号/对照) | 来源 |",
          "|---|---|---|---|---|---|---|---|"]
    for d, x in block.get("by_dim", {}).items():
        L.append(f"| {d} | {x.get('w')} | {x.get('ci')} | {x.get('signal')} | "
                 f"{x.get('noise')} | {x.get('sn')} | {x.get('n_signal')}/"
                 f"{x.get('n_noise')} | {x.get('source')} |")
    L.append("")
    if any((x.get("w_human") is not None) for x in (block.get("by_dim") or {}).values()):
        L += ["> 注：`w` 在启用人类标定（步骤三）后是**人类权重**（w_human，已归一到均值 1），"
              "而 `CI / 信号 / 噪声 / SN` 来自**步骤二消融**——两者口径不同，"
              "`w` 不必落在该 CI 区间内。", ""]
    if block.get("excluded_dims"):
        L += [f"> 未参与校准（阶段 5 门槛剔除，只报告不参与判定）："
              f"{'、'.join(block['excluded_dims'])}", ""]
    hc = block.get("human_calibration")
    L += ["## 步骤三：人类成对比较（Bradley–Terry）", "",
          (f"- 已标定：{hc.get('n_pairs')} 对，成对准确率 {hc.get('pair_accuracy')}"
           if hc else "- **未采集数据**（如实记 null）：权重仅来自步骤二消融；"
           "启用 λ>0 前需补小规模成对比较"), ""]
    med = sorted((x.get("signal") or 0, d) for d, x in block.get("by_dim", {}).items())
    if med:
        L += [f"- 信号最弱：{med[0][1]}（{med[0][0]}）；最强：{med[-1][1]}"
              f"（{med[-1][0]}）", ""]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")


if __name__ == "__main__":
    sys.exit(main())
