#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""eval_external.py —— 阶段 8：外部验证（方案 13）。

三段，可分段跑（结果合并到同一个 json）：

    E1 端到端退化    真实 .tex 文档 + 真实优化器（真编译）：
                     干净稿 / 逐档退化 / 退化稿再优化，检验 A 对退化档数单调、
                     影子 A_profile 同向、以及「优化器把 A 拉回干净稿水平」。
    E2 第二套工具链  真实论文 PDF，矢量/文本层（pdfminer）与像素层（pdftoppm）
                     两条测量路径逐量比较（排序一致性 + 绝对偏差 + 分歧页）。
    E3 论文级报告    缓存页指标 -> 按**论文**聚合档案判定，并与页级池化口径对照
                     （回应阶段 7 的局限 L4：长文被池化稀释）。
    E4 缺陷敏感性    源码级退化注入 + 真编译，逐维检查 A_profile 动不动 →
                     **λ 前置门**（测不出来的维不允许拿去当奖励）；
                     写出 metrics/profiles/profile_sensitivity.json。

产出：
    metrics/profiles/eval_external.json   完整结果
    metrics/profiles/eval_external.md     人读报告
    metrics/profiles/profile_sensitivity.json   λ 前置门（仅 E4）

用法：
    python3 tools/eval_external.py                      # 全跑（E1 默认 2 篇、E2 12 篇、E3 60 篇）
    python3 tools/eval_external.py --only e2,e3         # 只跑测量层（跳过真编译，快）
    python3 tools/eval_external.py --only e4            # E4：A_profile 缺陷敏感性（λ 前置门）
    python3 tools/eval_external.py --only e3 --e3-papers 200
    python3 tools/eval_external.py --e2-papers 24 --e2-max-pages 8 --e2-dpi 60
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
OUTDIR = os.path.join(DS, "metrics", "profiles")
PDFS = os.path.join(DS, "sources", "raw", "pdfs")
WORK = os.path.join(DS, "workbench-eval")           # 必须在 /mnt/c|d 下（Windows 引擎写不了）

#: E1 候选文档（相对 texopt 仓库根）：真实论文工程 + 靶稿
DOC_CANDIDATES = [
    {"name": "neurips-real", "tex": os.path.join(ROOT, "examples", "NeurlPS examples", "main.tex")},
    {"name": "paper-real", "tex": os.path.join(ROOT, "examples", "test0913", "main.tex")},
    {"name": "demo-fixture", "tex": os.path.join(ROOT, "examples", "demo.tex")},
    {"name": "issues-fixture", "tex": os.path.join(ROOT, "examples", "issues.tex")},
]


def _p(msg):
    print(msg, flush=True)


def _stamp():
    return time.strftime("%Y-%m-%dT%H:%M:%S")


# ---------------------------------------------------------------- E1

def do_e1(names, levels_n, outdir):
    from texopt import evalexternal as EE
    from texopt.requirements import Requirement

    docs = [d for d in DOC_CANDIDATES if not names or d["name"] in names]
    missing = [d["name"] for d in docs if not os.path.isfile(d["tex"])]
    docs = [d for d in docs if os.path.isfile(d["tex"])]
    ladder = EE.LADDER[:levels_n] if levels_n else EE.LADDER
    req = Requirement(verbose=False)
    t0 = time.time()
    res = []
    for d in docs:
        _p(f"  E1 {d['name']}：干净 + {len(ladder)} 档退化（每档一次完整闭环）…")
        r = EE.end_to_end_doc(d, req=req, outdir=os.path.join(outdir, d["name"]),
                              levels=ladder)
        c = r["checks"]
        ser = r["series"]
        _p(f"    clean A={r['clean'].get('a')} | 退化态 A(修复前)="
           + " → ".join(str(v) for v in ser["a_before"])
           + " | 修复后 A=" + " → ".join(str(v) for v in ser["a"]))
        _p(f"    单调 {c['degradation_monotone']} 可见 {c['degradation_visible']} "
           f"影子同向 {c['shadow_monotone_before']} "
           f"回到干净 {c['repaired_back_to_clean']} 低于修复前 {c['repaired_below_before']}")
        res.append(r)
    def _cnt(k):
        return sum(1 for r in res if r["checks"].get(k) is True)
    summary = {
        "n_docs": len(res),
        "degradation_monotone": _cnt("degradation_monotone"),
        "degradation_visible": _cnt("degradation_visible"),
        "shadow_monotone_before": _cnt("shadow_monotone_before"),
        "repaired_back_to_clean": _cnt("repaired_back_to_clean"),
        "repaired_below_before": _cnt("repaired_below_before"),
        "missing_docs": missing,
    }
    _p(f"  E1 汇总（{len(res)} 篇）：退化态 A 单调 {summary['degradation_monotone']}、"
       f"退化可见 {summary['degradation_visible']}、"
       f"影子退化态同向 {summary['shadow_monotone_before']}、"
       f"修复回干净水平 {summary['repaired_back_to_clean']}、"
       f"修复后低于退化态 {summary['repaired_below_before']}"
       + (f"（缺文档 {missing}）" if missing else ""))
    return {"docs": res, "summary": summary, "levels": ladder,
            "seconds": round(time.time() - t0, 1)}


# ---------------------------------------------------------------- E2

def do_e2(pdfs_dir, n_papers, dpi, max_pages):
    from texopt import evalexternal as EE
    if not os.path.isdir(pdfs_dir):
        return {"error": f"找不到论文 PDF 目录 {pdfs_dir}"}
    names = sorted(fn for fn in os.listdir(pdfs_dir) if fn.lower().endswith(".pdf"))
    items = [{"paper": fn, "pdf": os.path.join(pdfs_dir, fn)} for fn in names[:n_papers]]
    t0 = time.time()
    _p(f"  E2 {len(items)} 篇真实论文（每篇最多 {max_pages or '全部'} 页，dpi {dpi}）…")
    res = EE.compare_toolchains(items, dpi=dpi,
                                tmpdir=os.path.join(WORK, "e2_gray"),
                                max_pages=max_pages)
    for s in res["summary"]:
        _p(f"    {s['vector_key']} vs {s['pixel_key']}：中位 ρ={s['spearman_median']} "
           f"(最低 {s['spearman_min']})，中位 |Δ|={s['median_abs_delta_overall']}"
           + ("（同量纲）" if s["same_unit"] else "（量纲不同，只比排序）"))
    res["seconds"] = round(time.time() - t0, 1)
    return res


# ---------------------------------------------------------------- E3

def do_e3(pages_dir, profile_path, n_papers, venue):
    from texopt import evalexternal as EE
    from texopt import shadow as SH
    prof = SH.load_profile(profile_path)
    if not prof:
        return {"error": "档案缺失（先跑 build_profile.py）"}
    t0 = time.time()
    _p(f"  E3 论文级聚合：{n_papers} 篇（venue={venue or '按各篇自身'}）…")
    res = EE.paper_level_report(pages_dir, prof, limit=n_papers, venue=venue,
                                drop_dims=SH.gate_drop_dims())
    _p(f"    论文级 A_profile 中位 {res['paper_a_profile_median']}"
       f"（P90 {res['paper_a_profile_p90']}，{res['n_papers']} 篇）")
    res["seconds"] = round(time.time() - t0, 1)
    return res


# ---------------------------------------------------------------- E4

def do_e4(names, levels_n, outdir):
    """E4：源码级退化注入 → A_profile 逐维敏感性 + λ 前置门。"""
    from texopt import evalexternal as EE

    docs = [d for d in DOC_CANDIDATES if not names or d["name"] in names]
    missing = [d["name"] for d in docs if not os.path.isfile(d["tex"])]
    docs = [d for d in docs if os.path.isfile(d["tex"])]
    ladder = EE.LADDER[:levels_n] if levels_n else EE.LADDER
    t0 = time.time()
    _p(f"  E4 缺陷敏感性：{len(docs)} 篇 × （干净 + {len(ladder)} 档），每档只编译一次…")
    res = EE.sensitivity_sweep(docs, outdir=outdir, levels=ladder)
    for d, v in sorted((res.get("dims") or {}).items()):
        _p(f"    {d:32s} 响应 {v['respond_docs']}/{v['n_docs']} 篇 "
           f"单调 {v['monotone_docs']} 中位Δ {v['median_delta']} → {v['verdict']}")
    _p(f"  E4 结论：λ 可用 = {res['lambda_eligible']}（{res['reason']}）"
       + (f"；缺文档 {missing}" if missing else ""))
    res["seconds"] = round(time.time() - t0, 1)
    # 前置门文件：给 shadow.lambda_eligible() 读
    gate = {k: v for k, v in res.items() if k != "docs"}
    gp = os.path.join(OUTDIR, "profile_sensitivity.json")
    with open(gp, "w", encoding="utf-8") as f:
        json.dump(gate, f, ensure_ascii=False, indent=1)
    _p(f"    写出前置门：{gp}")
    return res


# ---------------------------------------------------------------- 报告

def write_report(path, res):
    L = ["# 阶段 8：外部验证（方案 13）", "",
         f"生成时间：{res.get('stamp')} ｜ 用时 {res.get('seconds')}s", "",
         "> 诚实边界：E1 走真编译，检验的是「实现-口径自洽 + 修复能力」；",
         "> E2 的两条路径读同一批 PDF（渲染/解析路径不同），不是两套完全独立的链路；",
         "> E3 复用真实论文缓存指标，λ 恒为 0，只改报告口径、不改验收。", ""]
    e1 = res.get("e1_end_to_end")
    if e1:
        s = e1["summary"]
        L += ["## E1 端到端退化（真实文档 + 真实优化器，真编译）", "",
              f"- 文档 {s['n_docs']} 篇；退化档 `{e1['levels']}`（逐档累加）",
              f"- **退化态 A（修复前）对退化档单调不降：{s.get('degradation_monotone')}/{s['n_docs']}**"
              f"（最重档 ≥ 最轻档：{s.get('degradation_visible')}/{s['n_docs']}）",
              f"- **退化态影子 A_profile 同向：{s.get('shadow_monotone_before')}/{s['n_docs']}**",
              f"- 闭环修复后 A 回到 ≤ 干净稿：**{s.get('repaired_back_to_clean')}/{s['n_docs']}**"
              f"（且 ≤ 自身退化态：{s.get('repaired_below_before')}/{s['n_docs']}）", "",
              "每组：干净稿 A ｜ 逐档退化态 A（修复前）｜ 逐档闭环修复后 A。", ""]
        for d in e1["docs"]:
            ser = d.get("series") or {}
            ch = d["checks"]
            L += [f"### {d['name']}", "",
                  f"- 干净稿 A={d['clean'].get('a')}"
                  f"（{d['clean'].get('pages')} 页，状态 {d['clean'].get('status')}）",
                  "- 退化态 A（修复前）："
                  + " → ".join(str(v) for v in (ser.get("a_before") or [])),
                  "- 闭环修复后 A："
                  + " → ".join(str(v) for v in (ser.get("a") or [])),
                  "- 退化态影子 A_profile："
                  + " → ".join(str(v) for v in (ser.get("a_profile_before") or [])),
                  f"- 判定：单调 `{ch.get('degradation_monotone')}`、"
                  f"可见 `{ch.get('degradation_visible')}`、"
                  f"影子同向 `{ch.get('shadow_monotone_before')}`、"
                  f"回到干净 `{ch.get('repaired_back_to_clean')}`、"
                  f"低于修复前 `{ch.get('repaired_below_before')}`", ""]
    e2 = res.get("e2_toolchains")
    if e2 and not e2.get("error"):
        L += ["## E2 第二套工具链复测（矢量/文本层 vs 像素层）", "",
              f"- 论文 {len(e2['papers'])} 篇，dpi {e2['dpi']}，"
              f"每篇最多 {e2['max_pages'] or '全部'} 页", "",
              "| 矢量层 | 像素层 | 同量纲 | 中位 ρ | 最低 ρ | 中位 \\|Δ\\| | 退化篇数 |",
              "|---|---|---|---|---|---|---|"]
        for s in e2["summary"]:
            L.append(f"| `{s['vector_key']}` | `{s['pixel_key']}` | "
                     f"{'是' if s['same_unit'] else '否'} | {s['spearman_median']} | "
                     f"{s['spearman_min']} | {s['median_abs_delta_overall']} | "
                     f"{s.get('n_degenerate', 0)}/{s['n_papers']} |")
        L.append("")
        lp = e2.get("last_page_trailing") or {}
        if lp.get("n_papers"):
            L += [f"末页对照（`whitespace.trailing_ratio` vs `bottom_blank`，每篇取"
                  f"**抽样范围内最后一页**，n={lp['n_papers']}，其中矢量侧非零 "
                  f"{lp.get('n_nonzero_vector')} 篇）：Spearman ρ={lp.get('spearman')}、"
                  f"中位 \\|Δ\\|={lp.get('median_abs_delta')}。",
                  "（抽样窗口内矢量侧 trailing_ratio 恒为 0 —— 该量在排满的正文页上无取值，"
                  "所以这一对的页级秩相关在 8 页窗口里无可辨识性；该量在语料上的覆盖率见 E3。）", ""]
    e3 = res.get("e3_paper_level")
    if e3 and not e3.get("error"):
        L += ["## E3 论文级报告", "",
              f"- 论文 {e3['n_papers']} 篇；论文级 A_profile 中位 "
              f"**{e3['paper_a_profile_median']}**（P90 {e3['paper_a_profile_p90']}）", "",
              "| 维度 | 页数（页级值个数） | 页级池化中位 |",
              "|---|---|---|"]
        for row in e3["page_pooled_by_dim"]:
            L.append(f"| `{row['dim']}` | {row['n_page_values']} | {row['page_pooled_median']} |")
        L.append("")
        mc = e3.get("metric_coverage") or {}
        if mc:
            L += ["原始量在语料上的可辨识性（非空且非零的页占比）：", "",
                  "| 原始量 | 有效页数 | 非零页数 | 非零占比 |", "|---|---|---|---|"]
            for d, r in sorted(mc.items()):
                L.append(f"| `{d}` | {r['n']} | {r['n_nonzero']} | {r['share_nonzero']} |")
            L.append("")
    e4 = res.get("e4_sensitivity")
    if e4:
        L += ["## E4 缺陷敏感性（A_profile 的 λ 前置门）", "",
              f"- 文档 {e4['n_docs']} 篇；退化档 `{e4['levels']}`（源码级注入 + 真编译，每档只编一次）",
              f"- **λ 可用 = {e4['lambda_eligible']}**（{e4['reason']}）", "",
              "| 维 | 响应篇数 | 单调篇数 | 中位 Δ | 判定 |", "|---|---|---|---|---|"]
        for d, v in sorted((e4.get("dims") or {}).items()):
            L.append(f"| `{d}` | {v['respond_docs']}/{v['n_docs']} | "
                     f"{v['monotone_docs']} | {v['median_delta']} | {v['verdict']} |")
        L += ["", "（λ>0 会被代码拦下：`shadow.assert_lambda_allowed()` 读 "
              "`metrics/profiles/profile_sensitivity.json`；λ=0 不受影响。）", ""]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", default=PAGES)
    ap.add_argument("--profile", default=PROF)
    ap.add_argument("--pdfs", default=PDFS)
    ap.add_argument("--out", default=OUTDIR)
    ap.add_argument("--work", default=WORK)
    ap.add_argument("--only", default="e1,e2,e3")
    ap.add_argument("--e1-docs", default="", help="逗号分隔的文档 name（默认全部可用的）")
    ap.add_argument("--e1-levels", type=int, default=4, help="E1 退化档数（1-4）")
    ap.add_argument("--e2-papers", type=int, default=12)
    ap.add_argument("--e2-dpi", type=int, default=50)
    ap.add_argument("--e2-max-pages", type=int, default=6)
    ap.add_argument("--e3-papers", type=int, default=60)
    ap.add_argument("--e3-venue", default=None)
    ap.add_argument("--list-docs", action="store_true")
    args = ap.parse_args()

    if args.list_docs:
        for d in DOC_CANDIDATES:
            print(f"{d['name']:14s} {d['tex']} "
                  + ("[存在]" if os.path.isfile(d["tex"]) else "[缺失]"))
        return 0

    want = {s.strip() for s in args.only.split(",") if s.strip()}
    t0 = time.time()
    _p(f"阶段 8 外部验证开始：{sorted(want)}")
    res = {"schema": "stage8.external.v1", "stamp": _stamp(),
           "repo_root": ROOT, "profile_file": args.profile}
    os.makedirs(args.work, exist_ok=True)
    os.makedirs(args.out, exist_ok=True)

    if "e1" in want:
        names = [s.strip() for s in args.e1_docs.split(",") if s.strip()]
        res["e1_end_to_end"] = do_e1(names, args.e1_levels,
                                      os.path.join(args.work, "e1"))
    if "e2" in want:
        res["e2_toolchains"] = do_e2(args.pdfs, args.e2_papers, args.e2_dpi,
                                     args.e2_max_pages)
    if "e3" in want:
        res["e3_paper_level"] = do_e3(args.pages, args.profile, args.e3_papers,
                                      args.e3_venue)
    if "e4" in want:
        e4names = [s.strip() for s in args.e1_docs.split(",") if s.strip()]
        res["e4_sensitivity"] = do_e4(e4names, args.e1_levels,
                                      os.path.join(args.work, "e4"))

    res["seconds"] = round(time.time() - t0, 1)
    pj = os.path.join(args.out, "eval_external.json")
    if os.path.isfile(pj) and want != {"e1", "e2", "e3"}:
        try:                                   # 分段跑：与已有结果合并
            with open(pj, encoding="utf-8") as f:
                old = json.load(f)
            secs = res["seconds"]
            old.update({k: v for k, v in res.items() if k != "seconds"})
            res = old
            res["seconds"] = secs            # 分段跑只记本次用时，不把旧值当本次
            _p("  （分段运行：已与既有 eval_external.json 合并）")
        except Exception as e:
            _p(f"  （合并旧结果失败，按本次结果写：{type(e).__name__}）")
    with open(pj, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    md = os.path.join(args.out, "eval_external.md")
    write_report(md, res)
    _p(f"输出：{pj} / {md}（总用时 {res['seconds']}s）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
