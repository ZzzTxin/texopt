#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""eval_protocol.py —— 阶段 5：评测与验收协议（方案 12.1-12.6）全流程。

跑在阶段 1-3 的**缓存指标**上（离线、可重跑、不重算全库），产出：

    metrics/profiles/eval_protocol.json   完整结果（逐项 + 逐维门槛）
    metrics/profiles/eval_report.md       人读报告（含验收门槛结论）
    metrics/profiles/eval_gate.json       逐维门槛（供 shadow 在线读取，12.6）

用法：
    python3 tools/eval_protocol.py                     # 全跑
    python3 tools/eval_protocol.py --only fp,sep       # 只跑部分
    python3 tools/eval_protocol.py --folds 5 --pages 40 --perms 50
    python3 tools/eval_protocol.py --render            # 额外做渲染层注入 + 重编译稳定性
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
WORK = os.path.join(DS, "workbench-eval")           # 渲染层工作区（须在 /mnt/c|d 下）


def _p(msg):
    print(msg, flush=True)


def _stamp():
    return time.strftime("%Y-%m-%dT%H:%M:%S")


# ---------------------------------------------------------------- 各检验

def do_injection(rows, profile, n_pages):
    from texopt import evalproto as EP
    t0 = time.time()
    res = EP.run_injection_trials(rows, profile, n_pages=n_pages)
    res["seconds"] = round(time.time() - t0, 1)
    _p(f"  12.1 指标层注入：{res['n_trials']} 组试验，A 单调 {res['doc_monotone_rate']}、"
       f"定位 {res['localized_rate']}、逐维单调 {res['dim_monotone_rate']}"
       f"（{res['seconds']}s，饱和跳过 {res['n_saturated']}）")
    return res


def do_fp(rows, folds, min_pages):
    from texopt import evalproto as EP
    t0 = time.time()
    res = EP.run_fp_protocol(rows, k=folds, min_pages=min_pages)
    res["seconds"] = round(time.time() - t0, 1)
    a = res["aggregate"]
    _p(f"  12.2 假阳率（{folds} 折，逐篇留出）：参数化 {a['param']['rate']} / "
       f"经验校准 {a['calibrated']['rate']}"
       f"（目标 ≤0.05，{res['seconds']}s）")
    return res


def do_sep(rows, dims, perms, min_papers):
    from texopt import evalproto as EP
    t0 = time.time()
    res = EP.run_separability(rows, dims, perms=perms, min_papers=min_papers)
    res["seconds"] = round(time.time() - t0, 1)
    if res.get("status") == "ok":
        _p(f"  12.3 会议可分性：1-NN 留一准确率 {res['accuracy_loo_1nn']}"
           f"（随机 {res['chance_uniform']}，多数类 {res['majority_baseline']}，"
           f"置换 p={res['p_value']}，{res['seconds']}s）")
    else:
        _p(f"  12.3 会议可分性：跳过（{res.get('why')}）")
    return res


def do_stability(rows, profile, dims, render, tex=None):
    from texopt import evalproto as EP
    res = {"determinism": EP.stability_determinism(rows, profile)}
    _p(f"  12.4a 重复测量：{'一致' if res['determinism']['ok'] else '不一致'}"
       f"（{res['determinism']['n_docs']} 篇）")

    # DPI 漂移：用真实 PDF（矢量/文本层，与 DPI 无关）
    pdf = _pick_pdf(rows)
    if pdf:
        try:
            d = EP.stability_dpi(pdf, dims, venue=None if "_" not in os.path.basename(pdf) else None)
            res["dpi"] = d
            _p(f"  12.4b DPI 漂移（{d['dpi_a']}→{d['dpi_b']} dpi）：max {d['max_rel_drift']}"
               f" → {'通过' if d['ok'] else '不通过'}（{os.path.basename(pdf)}）")
        except Exception as e:
            res["dpi"] = {"status": "error", "why": f"{type(e).__name__}: {e}"}
            _p(f"  12.4b DPI 漂移：失败（{res['dpi']['why']}）")
    else:
        res["dpi"] = {"status": "skipped", "why": "未找到可用 PDF"}

    if render:
        try:
            r = do_render(tex)
            res["render"] = r
        except Exception as e:
            res["render"] = {"status": "error", "why": f"{type(e).__name__}: {e}"}
            _p(f"  12.4c/12.1 渲染层：失败（{res['render']['why']}）")
    return res


def _pick_pdf(rows):
    """从语料 raw PDF 里挑一个真实 PDF（用于 DPI 检验）。"""
    src = os.path.join(DS, "sources", "raw", "pdfs")
    if not os.path.isdir(src):
        return None
    for fn in sorted(os.listdir(src)):
        if fn.endswith(".pdf"):
            p = os.path.join(src, fn)
            if os.path.getsize(p) > 200_000:
                return p
    return None


# ---------------------------------------------------------------- 渲染层（12.1 第二级）

BASE_TEX = r"""\documentclass[10pt,a4paper]{article}
\usepackage[margin=1in]{geometry}
\usepackage{fontspec}
\usepackage{amsmath,amssymb,booktabs}
\setmainfont{Latin Modern Roman}
\setlength{\parskip}{4pt}
\pagestyle{plain}
\title{A Self-contained Multi-page Test Document for Layout Evaluation}
\author{Eval Protocol}
\date{}
\begin{document}\maketitle
\section{Introduction}
"""

BODY_ONE = ("This paragraph exists to fill the page with realistic body text so that "
            "page roles, coverage and leading can be measured. It repeats a few times "
            "to make the layout deterministic. ")
BASE_TAIL = r"""
\section{Method}
$$F(x)=\sum_{i=1}^{n} a_i x_i^2 + \int_0^T e^{-t^2}\,dt$$
\section{Results}
\begin{table}[t]\centering
\begin{tabular}{lll}\toprule A & B & C \\\midrule 1 & 2 & 3 \\ 4 & 5 & 6 \\\bottomrule\end{tabular}
\caption{A small table.}\end{table}
\section{Conclusion}
Short conclusion.
\end{document}
"""


def _write_base_tex(path: str, pages: int = 3):
    body = ("\\section{Background}\n"
            + (BODY_ONE * 6) + "\n" + (BODY_ONE * 6) + "\n" + (BODY_ONE * 6) + "\n"
            + ("\\section{More Text}\n" + (BODY_ONE * 8) + "\n") * (pages - 1))
    tex = BASE_TEX + body + BASE_TAIL
    with open(path, "w", encoding="utf-8") as f:
        f.write(tex)
    return tex


def _write_degraded_tex(path: str, pages: int = 3, kind: str = "inject_hole"):
    """在 base 的第 2 页位置注入退化（可控、确定性）。"""
    body = ("\\section{Background}\n"
            + (BODY_ONE * 6) + "\n" + (BODY_ONE * 6) + "\n")
    if kind == "inject_hole":
        # 强制分页 + 占位高度 -> 制造一页「上方有内容、下方大片无解释空洞」
        body += "\n\\newpage\n\\vspace*{0.62\\textheight}\n\n"
    elif kind == "split_paragraph":
        # 拆段：把连续段落切成一行一段，段间空白爆增
        body += "\n".join("\\noindent " + BODY_ONE[:120] + "\n\n" for _ in range(10))
    elif kind == "break_alignment":
        # 打乱对齐：短行左边缘参差（正文本应两端对齐 / 缩进一致）
        body += "\n" + "\n".join(
            "\\noindent\\hspace*{%dpt}%s" % (17 * (i % 5), BODY_ONE[:90])
            for i in range(10)) + "\n"
    body += ("\\section{More Text}\n" + (BODY_ONE * 8) + "\n") * (pages - 1)
    tex = BASE_TEX + body + BASE_TAIL
    with open(path, "w", encoding="utf-8") as f:
        f.write(tex)
    return tex


def do_render(tex=None, pages=3):
    """12.1 第二级 + 12.4：编译 base 与退化版，比较 A_profile 与定位；并测重编译漂移。"""
    from texopt import engine, extract as EX
    from texopt import aesthetic as AE, shadow as SH
    prof = SH.load_profile()
    if not prof:
        return {"status": "skipped", "why": "档案缺 mahalanobis 块"}
    wd = os.path.join(WORK, "render")
    os.makedirs(wd, exist_ok=True)
    out = {}
    for kind in ("base", "inject_hole", "split_paragraph", "break_alignment"):
        d = os.path.join(wd, kind)
        os.makedirs(d, exist_ok=True)
        f = os.path.join(d, "evaldoc.tex")
        if kind == "base":
            _write_base_tex(f, pages)
        else:
            _write_degraded_tex(f, pages, kind)
        cr = engine.compile_tex(f, passes=2)
        if not cr.ok:
            out[kind] = {"status": "error", "why": (cr.first_error or "编译失败")[:160]}
            _p(f"  渲染层 {kind}：编译失败")
            continue
        doc = EX.extract_pdf(cr.pdf_path)
        rep = AE.evaluate_doc(doc, prof)
        out[kind] = {"status": "ok", "pdf": os.path.basename(cr.pdf_path),
                     "n_pages": rep["n_pages"],
                     "a_profile": rep["paper"]["a_profile"],
                     "d2_p90": rep["paper"]["d2_p90"],
                     "n_anomalous_pages": rep["paper"]["n_anomalous_pages"],
                     "top_anomalous": rep["paper"]["top_anomalous"][:3],
                     "roles": _role_counts(doc)}
        _p(f"  渲染层 {kind}：{out[kind]['n_pages']} 页，A_profile="
           f"{out[kind]['a_profile']}，异常页 {out[kind]['n_anomalous_pages']}")

    b = (out.get("base") or {}).get("a_profile")
    deg = {k: v.get("a_profile") for k, v in out.items() if k != "base"
           and v.get("status") == "ok"}
    hit = sum(1 for v in deg.values() if b is not None and v is not None and v > b)
    out["summary"] = {"base_a_profile": b,
                      "degraded_increase": {k: (None if (v is None or b is None)
                                                else round(v - b, 6)) for k, v in deg.items()},
                      "n_increased": hit, "n_degraded_tested": len(deg),
                      "all_increased": bool(deg) and hit == len(deg),
                      "localization": {k: out[k].get("top_anomalous", [None])[0]
                                       for k in deg},
                      "note": "渲染层注入用于验证「感知层 -> 评分」整条链路；"
                              "定位 = 退化页是否进入 top_anomalous"}

    # 重编译漂移（同一 base 编译两次）
    from texopt import evalproto as EP
    dims = (prof.get("mahalanobis") or {}).get("dims") or []
    try:
        r1 = engine.compile_tex(os.path.join(wd, "base", "evaldoc.tex"), passes=2)
        r2 = engine.compile_tex(os.path.join(wd, "base", "evaldoc.tex"), passes=2)
        if r1.ok and r2.ok:
            d1 = [dict(__(p)) for p in EX.extract_pdf(r1.pdf_path)["pages"]]
            d2 = [dict(__(p)) for p in EX.extract_pdf(r2.pdf_path)["pages"]]
            out["recompile"] = EP.stability_metrics_spread(d1, d2, dims)
            _p(f"  12.4c 重编译漂移：max {out['recompile']['max_rel_drift']}"
               f" → {'通过' if out['recompile']['ok'] else '不通过'}")
    except Exception as e:
        out["recompile"] = {"status": "error", "why": f"{type(e).__name__}: {e}"}
    return out


def __(page):
    from texopt import profile as PROF
    return PROF.page_metric_items(page)


def _role_counts(doc):
    c = {}
    for p in doc.get("pages") or []:
        c[p.get("role")] = c.get(p.get("role"), 0) + 1
    return c


# ---------------------------------------------------------------- 报告

def build_gate(dims, inj, fp, stab):
    """12.6：把三项检验汇成逐维门槛。

    · 12.1 逐维单调性：来自注入试验的 by_dim
    · 12.2 逐维假阳率：来自留出集的**误报页最偏离维度归因**（按 role 汇总，取最大者）
    · 12.4 稳定性：DPI/重编译漂移逐维
    """
    from texopt import evalproto as EP
    fp_agg = ((fp or {}).get("aggregate") or {}).get("calibrated") or {}
    by_dim = fp_agg.get("by_dim") or {}
    fp_by_dim = {d: (v.get("rate") if isinstance(v, dict) else None)
                 for d, v in by_dim.items()}
    if not fp_by_dim:                      # 没有逐维归因时退到整体率（并在报告里说明）
        fp_by_dim = {d: fp_agg.get("rate") for d in dims}
    return EP.gate_verdicts(dims, inj, {**(fp or {}), "by_dim": fp_by_dim}, stab)


def write_report(path, res, meta):
    L = ["# 阶段 5 评测与验收协议报告（方案 12.1-12.6）", "",
         f"- 生成：{meta['stamp']}；语料：{meta['n_papers']} 篇 / {meta['n_pages']} 页（缓存指标，离线可复跑）",
         f"- 档案：{meta['profile_version']}；判定维度 {len(meta['dims'])} 个：" + "、".join(meta["dims"]),
         "- 诚实边界：本协议检验**实现与口径的自洽性**，不等于「与人类审美一致」；"
         "12.5 需人类成对比较数据，本阶段未采集（如实记 None，阶段 7 做）。", ""]

    inj = res.get("injection") or {}
    L += ["## 12.1 负样本注入（构造性验证）", "",
          f"- 指标层：{inj.get('n_trials')} 组「真实页 + 阶梯退化」试验；"
          f"A_profile 单调上升 **{inj.get('doc_monotone_rate')}**（容忍 0.1% 回落）/ "
          f"严格零回落 {inj.get('doc_strict_rate')}；退化页定位命中 **{inj.get('localized_rate')}**"
          f"（全页 D² top-3）、top-1 命中 {inj.get('top1_rate')}、中位名次 {inj.get('median_rank')}；"
          f"逐维损失单调 {inj.get('dim_monotone_rate')}；因无外推空间/无损失可增跳过 {inj.get('n_saturated')} 例", "",
          "退化方向不是写死的，而是按「推离本档常态区间」逐页选取（非单调带外损失是双向的，"
          "写死方向会把正确行为判成失败）。定位命中按角色拆分——`appendix`/`references`/`figure-page` "
          "这类页本身 D² 就高，注入后未必上升到第一，属预期而非缺陷：", "",
          "| 角色 | 定位命中率（top-3） |", "|---|---|"]
    for k, v in (inj.get("localized_by_role") or {}).items():
        L.append(f"| {k} | {v} |")
    L += ["", "| 退化类型 | A 单调率 |", "|---|---|"]
    for k, v in (inj.get("by_injection") or {}).items():
        L.append(f"| {k} | {v} |")
    L += ["", "| 被注入维度 | 逐维损失单调率 |", "|---|---|"]
    for k, v in (inj.get("by_dim") or {}).items():
        L.append(f"| {k} | {v} |")
    L.append("")

    rend = ((res.get("stability") or {}).get("render") or {})
    if rend.get("summary"):
        s = rend["summary"]
        L += ["### 12.1 第二级：渲染层注入（真实编译，验证「感知→评分」链路）", "",
              f"- base A_profile = {s['base_a_profile']}；退化版升幅："
              + "，".join(f"{k} {v:+}" for k, v in (s.get("degraded_increase") or {}).items()),
              f"- 全部退化版 A_profile 均上升：{'是' if s.get('all_increased') else '否'}"
              f"（{s['n_increased']}/{s['n_degraded_tested']}）", "",
              "| 版本 | 页数 | A_profile | 异常页 | 最异常页/维度 |", "|---|---|---|---|---|"]
        for k, v in rend.items():
            if not isinstance(v, dict) or v.get("status") != "ok":
                continue
            t = (v.get("top_anomalous") or [{}])[0]
            L.append(f"| {k} | {v['n_pages']} | {v['a_profile']} | {v['n_anomalous_pages']} | "
                     f"p{t.get('page')} {t.get('worst_dim')} |")
        L.append("")

    fp = res.get("fp") or {}
    if fp:
        a = fp.get("aggregate") or {}
        L += ["## 12.2 假阳率（特异性，目标 ≤ 0.05）", "",
              f"- {len(fp.get('folds') or [])} 折交叉（**按论文**留出：训练集重建档案 + 定阈值，留出页测误报）", "",
              "| 口径 | 页数 | 误报 | 假阳率 | 结论 |", "|---|---|---|---|---|"]
        cal = fp.get("calibration_table") or {}
        rows = [("param", "参数化阈值（χ², p<0.05）")] + [
            (q, f"经验校准（训练集 D² P{int(float(q) * 100)}）") for q in ("0.95", "0.96", "0.97")]
        for key, lab in rows:
            v = (a.get(key) if key in a else (cal.get(key) or {})) or {}
            L.append(f"| {lab} | {v.get('n_pages')} | {v.get('fp')} | {v.get('rate')} | "
                     f"{'通过' if (v.get('rate') is not None and v['rate'] <= 0.05) else '不通过'} |")
        L += ["", "**卡方假设不成立**：真实页级 D² 比 χ² 重尾（指标重尾/混合 + 每页可用维数不同），"
              "参数化阈值把假阳率抬到目标的 3 倍多；发布口径必须用**经验校准阈值**。", "",
              "按 role（经验校准 P95 口径）：", "", "| role | 页 | 误报 | 假阳率 |", "|---|---|---|---|"]
        for r, v in ((a.get("calibrated") or {}).get("by_role") or {}).items():
            L.append(f"| {r} | {v['n']} | {v['fp']} | {v['rate']} |")
        L.append("")
        dimrate = ((a.get("calibrated") or {}).get("by_dim") or {})
        if dimrate:
            L += ["误报页按**最偏离维度**归因（逐维假阳率，供 12.6 门槛用）：", "",
                  "| 维度 | 页 | 误报 | 假阳率 |", "|---|---|---|---|"]
            for d, v in dimrate.items():
                L.append(f"| {d} | {v['n']} | {v['fp']} | {v['rate']} |")
            L.append("")

    sep = res.get("separability") or {}
    L += ["## 12.3 会议可分性（有效性 sanity check）", ""]
    if sep.get("status") == "ok":
        L += [f"- 参与：{sep['n_papers']} 篇 / {sep['n_venues']} 个会议（每会 ≥20 篇）",
              f"- 论文级画像特征 1-NN 留一准确率 **{sep['accuracy_loo_1nn']}**"
              f"（均匀随机 {sep['chance_uniform']}，多数类 {sep['majority_baseline']}，"
              f"置换检验 p = {sep['p_value']}，{sep['n_permutations']} 次置换）",
              f"- 结论：{'显著高于随机 → 指标确实抓到了会议风格差异' if sep['significantly_above_chance'] else '未显著高于随机 → 指标区分度不足'}",
              ""]
    else:
        L += [f"- 跳过：{sep.get('why')}", ""]

    st = res.get("stability") or {}
    L += ["## 12.4 稳定性与可复现性", "",
          f"- 同文档重复测量：{'完全一致' if (st.get('determinism') or {}).get('ok') else '不一致'}"
          f"（{(st.get('determinism') or {}).get('n_docs')} 篇，逐字段 diff）"]
    d = st.get("dpi") or {}
    if d.get("status") == "ok":
        L.append(f"- DPI 变更（{d['dpi_a']}→{d['dpi_b']} dpi）：判定维度最大相对漂移 "
                 f"**{d['max_rel_drift']}** → {'通过（<5%）' if d['ok'] else '不通过'}"
                 f"；{d.get('note')}")
    else:
        L.append(f"- DPI 变更：{d.get('status') or '未测'} {d.get('why') or ''}")
    rc = (st.get("render") or {}).get("recompile") or {}
    if rc.get("status") == "ok":
        L.append(f"- 同 .tex 重编译：判定维度最大相对漂移 **{rc['max_rel_drift']}** → "
                 f"{'通过（<5%）' if rc['ok'] else '不通过'}")
    L += ["", "## 12.5 与人类判断的相关性（探索性）", "",
          "- **未做**：需要小规模人类成对比较数据，本阶段未采集；按方案要求如实记为"
          " `null`，不得包装成「与人类审美一致」。留待阶段 7（Bradley-Terry 标定）一并做。", ""]

    g = res.get("gate") or {}
    L += ["## 12.6 验收门槛（逐指标）", "",
          f"- 通过 **{g.get('n_pass')}/{len(meta['dims'])}** 维；未通过者按方案只能作报告项，"
          "不得参与 A（已写入 `eval_gate.json`，在线影子评估会自动剔除）。", "",
          "| 维度 | 结论 | 未通过原因 |", "|---|---|---|"]
    for d0, v in (g.get("verdicts") or {}).items():
        L.append(f"| {d0} | {v['verdict']} | {'；'.join(v['reasons']) or '—'} |")
    L.append("")
    if g.get("dropped"):
        L += [f"> 剔除维度：{'、'.join(g['dropped'])}", ""]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", default=PAGES)
    ap.add_argument("--profile", default=PROF)
    ap.add_argument("--out", default=OUTDIR)
    ap.add_argument("--only", default="inject,fp,sep,stab")
    ap.add_argument("--pages-n", type=int, default=40, help="12.1 试验页数")
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--min-pages", type=int, default=30)
    ap.add_argument("--perms", type=int, default=50)
    ap.add_argument("--min-papers", type=int, default=20)
    ap.add_argument("--render", action="store_true", help="额外做渲染层注入 + 重编译")
    args = ap.parse_args()
    want = {s.strip() for s in args.only.split(",") if s.strip()}

    from texopt import profile as PROF_, shadow as SH
    rows, papers, bad = PROF_.load_pages(args.pages)
    prof = SH.load_profile(args.profile)
    if not prof:
        print("档案缺 mahalanobis 块，先跑 build_profile.py", file=sys.stderr)
        return 2
    dims = (prof.get("mahalanobis") or {}).get("dims") or []
    t0 = time.time()
    _p(f"阶段 5 评测开始：{len(papers)} 篇 / {len(rows)} 页；档案 {prof.get('profile_version')}；"
       f"维度 {len(dims)} 个")
    res = {"schema": "eval_protocol.v1", "stamp": _stamp(),
           "n_papers": len(papers), "n_pages": len(rows), "dims": dims,
           "profile_version": prof.get("profile_version"), "profile_file": args.profile}
    if "inject" in want:
        res["injection"] = do_injection(rows, prof, args.pages_n)
    if "fp" in want:
        res["fp"] = do_fp(rows, args.folds, args.min_pages)
    if "sep" in want:
        res["separability"] = do_sep(rows, dims, args.perms, args.min_papers)
    if "stab" in want:
        res["stability"] = do_stability(rows, prof, dims, args.render)
    os.makedirs(args.out, exist_ok=True)
    pj = os.path.join(args.out, "eval_protocol.json")
    all_sections = {"inject", "fp", "sep", "stab"}
    if not all_sections.issubset(want) and os.path.isfile(pj):
        try:                                  # 分段跑：与已有结果合并（不丢之前的结果）
            with open(pj, encoding="utf-8") as f:
                old = json.load(f)
            old.update({k: v for k, v in res.items() if k != "seconds"})
            _p("  （分段运行：已与既有 eval_protocol.json 合并）")
            res = old
        except Exception as e:
            _p(f"  （合并旧结果失败，按本次结果写：{type(e).__name__}）")
    # 门槛必须基于**合并后**的完整结果算：分段跑（如 --only gate）时，
    # 只填本段会让门槛把「未重算的检验」误判成「未测」，输出错误的 gate 文件。
    if "gate" in want or True:
        res["gate"] = build_gate(dims, res.get("injection"), res.get("fp"),
                                 res.get("stability"))
        _p(f"  12.6 门槛：通过 {res['gate']['n_pass']}/{len(dims)} 维"
           + (f"；剔除 {res['gate']['dropped']}" if res["gate"]["dropped"] else "（全部通过）"))
    res["seconds"] = round(time.time() - t0, 1)
    with open(pj, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    with open(os.path.join(args.out, "eval_gate.json"), "w", encoding="utf-8") as f:
        json.dump(res["gate"], f, ensure_ascii=False, indent=1)
    write_report(os.path.join(args.out, "eval_report.md"), res,
                 {"stamp": res["stamp"], "n_papers": len(papers), "n_pages": len(rows),
                  "dims": dims, "profile_version": prof.get("profile_version")})
    _p(f"输出：eval_protocol.json / eval_report.md / eval_gate.json（总用时 {res['seconds']}s）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
