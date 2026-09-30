#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""shadow_report.py —— 阶段 4：全库影子评估（离线，用已提取的 page_metrics）。

为什么离线：页级指标阶段 1-3 已缓存（每篇一次，方案 13.5），影子评估只需
读 JSON 做判定，无需重新渲染 PDF。

产出：
    metrics/profiles/shadow_report.json   逐篇 A_profile / 异常页 / 归因
    metrics/profiles/shadow_summary.md    人读摘要

**口径诚实标注**：语料页本身就是档案的构建数据，属 in-sample 评估 ——
D^2 会偏小、异常率会偏低。本报告只用于①验证管线可跑②找明显的归因错误，
**不能**当作假阳率结论（那是方案 12.2 的正式协议，阶段 5 做）。

用法：
    python3 tools/shadow_report.py [--pages DIR] [--limit N]
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", default=PAGES)
    ap.add_argument("--profile", default=PROF)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    from texopt import aesthetic as AE, shadow as SH

    prof = SH.load_profile(args.profile)
    if not prof:
        print("档案缺 mahalanobis 块，先跑 tools/build_profile.py", file=sys.stderr)
        return 2

    t0 = time.time()
    files = sorted(f for f in os.listdir(args.pages) if f.endswith(".json"))
    if args.limit:
        files = files[:args.limit]
    per_paper, agg = [], {}
    for i, fn in enumerate(files, 1):
        try:
            with open(os.path.join(args.pages, fn), encoding="utf-8") as f:
                doc = json.load(f)
        except Exception:
            continue
        rep = AE.evaluate_doc(doc, prof)
        paper = rep["paper"]
        sid = fn[:-5]
        venue = (doc.get("doc") or {}).get("venue")
        # 数据质量标记：references 占绝对多数且篇幅长 -> 疑似 proceedings 合订本
        # （实测 s-acl-2025-012：46 页里 38 页 references，A_profile 12.3 属数据问题）
        pages_ = doc.get("pages") or []
        nref = sum(1 for x in pages_ if x.get("role") == "references")
        suspect = bool(pages_) and len(pages_) >= 25 and nref / len(pages_) > 0.6
        per_paper.append({"paper": sid, "venue": venue,
                          "suspect_compilation": suspect,
                          "a_profile": paper["a_profile"],
                          "d2_p90": paper["d2_p90"], "d2_max": paper["d2_max"],
                          "n_anomalous_pages": paper["n_anomalous_pages"],
                          "pages": rep["n_pages"],
                          "status": paper["status"],
                          "top_dim": (min(paper["top_anomalous"], key=lambda d: d["page"])
                                      if paper["top_anomalous"] else None)})
        key = venue or "?"
        a = agg.setdefault(key, {"n": 0, "a": [], "anom_pages": 0, "pages": 0,
                                 "n_suspect": 0})
        a["n"] += 1
        a["n_suspect"] += int(suspect)
        if suspect:                       # 合订本不计入分布统计（口径会脏）
            continue
        if paper["a_profile"] is not None:
            a["a"].append(paper["a_profile"])
        a["anom_pages"] += paper["n_anomalous_pages"] or 0
        a["pages"] += rep["n_pages_scored"] or 0
        if i % 100 == 0:
            print(f"  …{i}/{len(files)}")

    ok = [p for p in per_paper if p["a_profile"] is not None and not p["suspect_compilation"]]
    # 档内相对化：A_profile 只保证同档排序（方案 10.3 步骤一），跨档绝对值不可比
    by_venue = {}
    for p in ok:
        by_venue.setdefault(p["venue"] or "?", []).append(p["a_profile"])
    med = {k: AE.percentile(v, 0.50) for k, v in by_venue.items()}
    for p in per_paper:
        m = med.get(p["venue"] or "?")
        p["a_profile_rel"] = (round(p["a_profile"] / m, 4)
                             if p["a_profile"] is not None and m else None)
    ranked = sorted(ok, key=lambda p: -p["a_profile"])
    report = {
        "schema": "shadow_report.v1",
        "profile_version": prof.get("profile_version"),
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "in_sample": True,
        "note": "语料页即档案构建数据（in-sample）：D^2 偏小、异常率偏低；"
                "假阳率协议见方案 12.2（阶段 5）",
        "n_papers": len(per_paper), "n_scored": len(ok),
        "n_suspect_compilation": sum(1 for p in per_paper if p["suspect_compilation"]),
        "a_profile_by_venue_median": med,
        "venue": {k: {"n_papers": v["n"], "n_pages": v["pages"],
                      "a_profile_median": AE.percentile(v["a"], 0.50),
                      "a_profile_p90": AE.percentile(v["a"], 0.90),
                      "n_suspect": v["n_suspect"],
                      "anomalous_page_ratio": (round(v["anom_pages"] / v["pages"], 5)
                                               if v["pages"] else None)}
                  for k, v in sorted(agg.items())},
        "top_a_profile": ranked[:15],
        "papers": per_paper,
    }
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "shadow_report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)

    L = ["# 阶段 4 影子评估摘要（全库，in-sample）", "",
         f"- 论文：{report['n_scored']}/{report['n_papers']} 篇可判定；档案 "
         f"{report['profile_version']}；用时 {time.time() - t0:.0f}s",
         f"- ⚠ in-sample：语料页即档案构建数据，D² 偏小、异常率偏低，"
         "**不能**当假阳率结论（阶段 5 做正式协议）", "",
         "| 会议 | 篇 | 页 | A_profile 中位 | A_profile P90 | 异常页率 | 疑似合订本 |",
         "|---|---|---|---|---|---|---|"]
    for k, v in report["venue"].items():
        L.append(f"| {k} | {v['n_papers']} | {v['n_pages']} | {v['a_profile_median']} | "
                 f"{v['a_profile_p90']} | {v['anomalous_page_ratio']} | "
                 f"{v['n_suspect']} |")
    L += ["", "## A_profile 最高的 15 篇（归因自查：应为真的版面异常篇）", "",
          "| 论文 | 会议 | 页 | A_profile | 档内相对 | D² P90 | 异常页 |",
          "|---|---|---|---|---|---|---|"]
    for p in ranked[:15]:
        L.append(f"| {p['paper']} | {p['venue']} | {p['pages']} | {p['a_profile']} | "
                 f"{p.get('a_profile_rel')} | {p['d2_p90']} | {p['n_anomalous_pages']} |")
    sus = [p for p in per_paper if p["suspect_compilation"]]
    if sus:
        L += ["", f"## 疑似合订本/结构异常篇（{len(sus)} 篇，已排除出统计）", "",
              "| 论文 | 会议 | 页 | A_profile |", "|---|---|---|---|"]
        for p in sorted(sus, key=lambda x: -(x["a_profile"] or 0))[:10]:
            L.append(f"| {p['paper']} | {p['venue']} | {p['pages']} | {p['a_profile']} |")
    with open(os.path.join(OUT, "shadow_summary.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    print(f"输出：{OUT}/shadow_report.json, shadow_summary.md；用时 {time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
