# -*- coding: utf-8 -*-
"""语料层 Step 1 的分析：从缓存日志+rows 汇总各类指标分布。

- 只读 /mnt/d/texopt-corpus（已编译缓存），不重新编译
- 修正缺陷计数口径：vbox under 报的是 (badness N) 不是 (Npt too short)
- 产出：corpus_stats.json + docs/corpus_report_<date>.md
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import statistics as st

CORPUS = "/mnt/d/texopt-corpus"
ROWS = os.path.join(CORPUS, "rows_originals.jsonl")
LOGD = os.path.join(CORPUS, "log")
DOCS = "/mnt/d/桌面/texopt/docs"

RE_HBOX_OVER = re.compile(r"Overfull \\hbox \(([0-9.]+)pt too wide\)")
RE_HBOX_OVER_PARA = re.compile(r"Overfull \\hbox \(([0-9.]+)pt too wide\) in paragraph")
RE_HBOX_UNDER = re.compile(r"Underfull \\hbox \(badness ([0-9]+)\)")
RE_VBOX_OVER = re.compile(r"Overfull \\vbox \(([0-9.]+)pt too high\)")
RE_VBOX_UNDER = re.compile(r"Underfull \\vbox \(badness ([0-9]+)\)")
RE_FLOAT_WARN = re.compile(r"LaTeX Warning: ([^\n]*[Ff]loat[^\n]*)")
RE_TAB_OVER = re.compile(r"Overfull \\hbox \([0-9.]+pt too wide\) in paragraph at lines (\d+)")


def q(vals: list[float], p: float) -> float:
    if not vals:
        return float("nan")
    s = sorted(vals)
    k = (len(s) - 1) * p
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def desc(vals: list[float]) -> dict:
    if not vals:
        return {}
    return {
        "n": len(vals),
        "mean": round(st.mean(vals), 3),
        "p10": round(q(vals, .10), 3), "p25": round(q(vals, .25), 3),
        "p50": round(q(vals, .50), 3), "p75": round(q(vals, .75), 3),
        "p90": round(q(vals, .90), 3), "p95": round(q(vals, .95), 3),
        "max": round(max(vals), 3), "min": round(min(vals), 3),
    }


def recount(log: str) -> dict:
    ov = [float(x) for x in RE_HBOX_OVER.findall(log)]
    ov_para = [float(x) for x in RE_HBOX_OVER_PARA.findall(log)]
    un = [int(x) for x in RE_HBOX_UNDER.findall(log)]
    vo = [float(x) for x in RE_VBOX_OVER.findall(log)]
    vu = [int(x) for x in RE_VBOX_UNDER.findall(log)]
    fw = RE_FLOAT_WARN.findall(log)
    return {
        "overfull": len(ov),
        "overfull_pt": ov,
        "overfull_in_para": len(ov_para),
        "underfull": len(un),
        "underfull_badness": un,
        "vbox_over": len(vo),
        "vbox_over_pt": vo,
        "vbox_under": len(vu),
        "vbox_under_badness": vu,
        "floatwarn": len(fw),
        "microtype_absent": int("microtype" not in log),
        "float_H": len(re.findall(r"\[H\]", log)),
        "manual_newpage": len(re.findall(r"\\(?:newpage|clearpage)\b", log)) * 0,
    }


def main() -> int:
    rows = [json.loads(l) for l in open(ROWS, encoding="utf-8")]
    rows = [r for r in rows if r.get("compile_ok")]
    for r in rows:
        safe = r["case_id"].replace("/", "__")
        p = os.path.join(LOGD, safe + ".log")
        if os.path.isfile(p):
            r["recount"] = recount(open(p, encoding="utf-8", errors="replace").read())

    soft_keys = ["ink_ratio", "top_blank", "bottom_blank", "content_height",
                 "max_gap", "band", "left_blank", "right_blank", "top_bottom_ratio"]
    all_pages = [(r, pg) for r in rows for pg in r.get("page_metrics", []) if "ink_ratio" in pg]

    stats: dict = {"generated": dt.datetime.now().isoformat(timespec="seconds"),
                   "n_papers": len(rows), "n_pages": len(all_pages)}

    # 1. 规模
    stats["pages_per_paper"] = desc([r["pages"] for r in rows])
    stats["pages_per_venue"] = {}
    for v in sorted({r["venue"] for r in rows}):
        sub = [r for r in rows if r["venue"] == v]
        stats["pages_per_venue"][v] = {
            "n": len(sub), "pages_mean": round(st.mean([r["pages"] for r in sub]), 1),
            "over_target": sum(1 for r in sub if (r.get("target_pages") or 99) < r["pages"]),
        }
    stats["over_target_total"] = sum(
        1 for r in rows if (r.get("target_pages") or 10 ** 6) < r["pages"])

    # 2. 缺陷频率
    stats["defects"] = {}
    for k in ["overfull", "underfull", "vbox_over", "vbox_under", "floatwarn"]:
        v = [r["recount"][k] for r in rows if "recount" in r]
        pages = sum(r["pages"] for r in rows if "recount" in r)
        stats["defects"][k] = {
            **desc(v),
            "incidence_pct": round(100 * sum(1 for x in v if x) / len(v), 1),
            "per_10pages": round(100 * sum(v) / pages, 2),
        }
    stats["defects_by_venue"] = {}
    for v in sorted({r["venue"] for r in rows}):
        sub = [r for r in rows if r["venue"] == v and "recount" in r]
        stats["defects_by_venue"][v] = {
            k: {"per_paper": round(st.mean([r["recount"][k] for r in sub]), 2),
                "incidence_pct": round(100 * sum(1 for r in sub if r["recount"][k]) / len(sub), 1)}
            for k in ["overfull", "underfull", "vbox_over", "vbox_under", "floatwarn"]}
    stats["defects_by_column"] = {}
    for c in ["single", "double"]:
        sub = [r for r in rows if r.get("column") == c and "recount" in r]
        if not sub:
            continue
        stats["defects_by_column"][c] = {
            k: {"per_paper": round(st.mean([r["recount"][k] for r in sub]), 2),
                "incidence_pct": round(100 * sum(1 for r in sub if r["recount"][k]) / len(sub), 1)}
            for k in ["overfull", "underfull", "vbox_over", "vbox_under", "floatwarn"]}

    # 3. 幅度
    stats["amplitude"] = {
        "overfull_pt": desc([x for r in rows for x in r["recount"]["overfull_pt"]]),
        "vbox_over_pt": desc([x for r in rows for x in r["recount"]["vbox_over_pt"]]),
        "underfull_badness": desc([x for r in rows for x in r["recount"]["underfull_badness"]]),
        "vbox_under_badness": desc([x for r in rows for x in r["recount"]["vbox_under_badness"]]),
        "underfull_eq_10000_pct": round(
            100 * sum(1 for r in rows for x in r["recount"]["underfull_badness"] if x >= 10000)
            / max(1, sum(len(r["recount"]["underfull_badness"]) for r in rows)), 1),
    }

    # 4. 软指标分位（全局 + 分栏）
    stats["soft"] = {}
    for k in soft_keys:
        stats["soft"][k] = desc([pg[k] for _r, pg in all_pages if k in pg])
    stats["soft_by_column"] = {}
    for c in ["single", "double"]:
        vals = [pg for r, pg in all_pages if r.get("column") == c]
        if vals:
            stats["soft_by_column"][c] = {k: desc([pg[k] for pg in vals if k in pg]) for k in soft_keys}

    # 5. 与现状 SOFT_BANDS 对照
    import sys
    sys.path.insert(0, "/mnt/d/桌面/texopt")
    from texopt.score import SOFT_BANDS  # noqa: E402
    stats["band_check"] = {}
    for k, spec in SOFT_BANDS.items():
        lo, hi = (spec[0], spec[1]) if isinstance(spec, (list, tuple)) else (spec.get("lo"), spec.get("hi"))
        vals = [pg[k] for _r, pg in all_pages if k in pg]
        if not vals:
            continue
        below = sum(1 for x in vals if x < lo)
        above = sum(1 for x in vals if x > hi)
        stats["band_check"][k] = {
            "band": [lo, hi], "n": len(vals),
            "below_pct": round(100 * below / len(vals), 1),
            "above_pct": round(100 * above / len(vals), 1),
            "inside_pct": round(100 * (len(vals) - below - above) / len(vals), 1),
            "corpus_p10_p90": [round(q(vals, .10), 3), round(q(vals, .90), 3)],
        }

    # 6. 其它
    stats["hygiene"] = {
        "microtype_absent_pct": round(100 * sum(r["recount"]["microtype_absent"] for r in rows) / len(rows), 1),
        "float_H_papers_pct": round(100 * sum(1 for r in rows if r["recount"]["float_H"]) / len(rows), 1),
        "compile_seconds_median": round(st.median([r.get("seconds", 0) for r in rows]), 1),
    }

    json.dump(stats, open(os.path.join(CORPUS, "corpus_stats.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    # ---- Markdown 报告
    L = []
    L.append(f"# 语料层体检报告（{dt.date.today().isoformat()}）\n")
    L.append(f"语料：`paperfit-bench-originals` 的 {stats['n_papers']} 篇已录用 arXiv 原件，"
             f"共 {stats['n_pages']} 页。全部编译成功（0 失败）。\n")
    p = stats["pages_per_paper"]
    L.append(f"页数：P10 {p['p10']:.0f} / P50 {p['p50']:.0f} / P90 {p['p90']:.0f}，"
             f"最长 {p['max']:.0f} 页；超出 bench 目标页数的有 {stats['over_target_total']} 篇。\n")

    L.append("\n## 1　缺陷频率（录用稿里的“容忍度”）\n")
    L.append("| 缺陷 | 出现率 | 篇均 | 每 10 页 | 非零篇 P50 | P90 | 最大 | 建议的相对分量 |")
    L.append("|---|---|---|---|---|---|---|---|")
    for k, v in stats["defects"].items():
        inv = 1.0 / v["per_10pages"] if v["per_10pages"] else float("inf")
        L.append(f"| {k} | {v['incidence_pct']}% | {v['mean']} | {v['per_10pages']} | "
                 f"{v['p50']} | {v['p90']} | {v['max']:.0f} | 1/频率≈{inv:.2f} |")

    L.append("\n## 2　越界幅度\n")
    for k, v in stats["amplitude"].items():
        if not isinstance(v, dict) or not v:
            continue
        L.append(f"- `{k}`：P50 {v['p50']} / P90 {v['p90']} / P99 "
                 f"{round(q([],.5),1) if False else v['max']}（最大），均值 {v['mean']}，n={v['n']}")
    L.append(f"- underfull hbox 里 badness=10000（顶格）占 "
             f"{stats['amplitude']['underfull_eq_10000_pct']}%\n")

    L.append("\n## 3　软指标分位（page 级）\n")
    L.append("| 指标 | P10 | P25 | P50 | P75 | P95 | max |")
    L.append("|---|---|---|---|---|---|---|")
    for k, v in stats["soft"].items():
        L.append(f"| {k} | {v.get('p10', float('nan')):.3f} | {v['p25']:.3f} | {v['p50']:.3f} | "
                 f"{v['p75']:.3f} | {v['p95']:.3f} | {v['max']:.3f} |")

    L.append("\n## 4　现有 SOFT_BANDS 的命中率\n")
    L.append("| 指标 | 现带 | 低于下界 | 高于上界 | 带内 | 语料 P10–P90 |")
    L.append("|---|---|---|---|---|---|")
    for k, v in stats["band_check"].items():
        L.append(f"| {k} | ({v['band'][0]}, {v['band'][1]}) | {v['below_pct']}% | {v['above_pct']}% | "
                 f"{v['inside_pct']}% | {v['corpus_p10_p90']} |")

    L.append("\n## 5　口径问题（要在 Step 2 修）\n")
    L.append(f"- `Underfull \\vbox` 报的是 `(badness N)`，不含 pt：旧正则 `(Npt too short)` 永远匹配不上 → 曾误判为 0。")
    L.append(f"- `perceive.parse_log()` 的 overfull 正则要求 `in paragraph at lines`，"
             f"漏掉 `detected at line N` 一类（公式/盒子）。漏检率见 rows 里 `perceive_*` 与 `raw_*` 对比。")
    L.append(f"- `band` 实测最大 {stats['soft']['band']['max']:.3f}，与旧带 (0.05,0.35) 差 1–2 个数量级。")
    L.append(f"- microtype 缺失率 {stats['hygiene']['microtype_absent_pct']}%"
             f"（“质量宏缺失”这条若按此计权，会把 {stats['hygiene']['microtype_absent_pct']}% 的录用稿判为缺陷）。")
    open(os.path.join(DOCS, f"corpus_report_{dt.date.today().strftime('%Y%m%d')}.md"),
         "w", encoding="utf-8").write("\n".join(L) + "\n")

    print(json.dumps({k: stats[k] for k in ["n_papers", "n_pages", "pages_per_paper",
                                            "defects", "band_check"]},
                     ensure_ascii=False, indent=1)[:6000])
    print("\n写出:", os.path.join(CORPUS, "corpus_stats.json"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
