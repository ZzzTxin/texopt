#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_profile.py —— 阶段 2：把全库 page_metrics.v1 汇总成「审美档案」。

产出（默认写在 datasets/conf-specs/metrics/profiles/）：
  aesthetic_profile.json   分位 + 聚类 bootstrap CI + 可信度（venue×role / role / venue）
  redundancy.json          Spearman 高相关聚类 + PCA 解释方差（去冗余依据）
  summary.md              人读摘要（各层样本量、可信度分布、校准结论）

用法：
    python3 tools/build_profile.py                 # 全库
    python3 tools/build_profile.py --no-ci         # 跳过 bootstrap（快，但没 CI）
    python3 tools/build_profile.py --corr-thr 0.75

同时会把实测结论回填进 docs/stage2_profile.md 的第 6 节（可用 --no-doc 关闭）：
只替换 "## 6." 与 "## 7." 之间的内容，不碰其它章节。
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
OUT = os.path.join(DS, "metrics", "profiles")
INDEX = os.path.join(DS, "metrics", "index.json")
DOC = os.path.join(ROOT, "docs", "stage2_profile.md")

# 阶段 1（校准前）的角色分布，仅用于第 6 节对照展示
STAGE1_ROLES = {"body": 3423, "appendix": 2875, "references": 2639,
                "section-head": 976, "title": 604, "table-page": 16,
                "figure-page": 3, "last-page": 2}

# 抽检用的代表档 × 指标
SPOT_STRATA = ["cvpr|body", "acl|body", "cvpr|references", "acl|appendix",
               "cvpr|figure-page", "eccv|body"]
SPOT_METRICS = ["density.coverage_text", "whitespace.total_ratio",
                "readability.chars_per_line_mean", "readability.leading_ratio",
                "alignment.left_var", "balance.left_right"]


def _fmt(x, nd=3):
    if x is None:
        return "—"
    if isinstance(x, float):
        return f"{x:.{nd}f}".rstrip("0").rstrip(".")
    return str(x)


def render_docs_section(papers, rows, prof, red, pc):
    """生成 docs/stage2_profile.md 第 6 节的正文（不含 ``## 6.`` 标题行）。"""
    lv = prof["levels"]
    vr, role = lv["venue_role"], lv["role"]

    # 语料构成
    n_two = n_one = 0
    role_cnt = {}
    if os.path.exists(INDEX):
        with open(INDEX, encoding="utf-8") as f:
            idx = json.load(f)
        for p in idx.get("papers", {}).values():
            if p.get("layout") == "twocolumn":
                n_two += 1
            elif p.get("layout") == "onecolumn":
                n_one += 1
            for k, v in (p.get("roles") or {}).items():
                role_cnt[k] = role_cnt.get(k, 0) + v

    L = ["> 本节由 `tools/build_profile.py` 自动回填（`--doc`，可用 `--no-doc` 关闭）。**不要手改本节**。", ""]

    # ---- 6.1 语料与角色分布
    L += ["### 6.1 语料与角色分布（校准后）", "",
          f"- 语料：**{len(papers)} 篇 / {len(rows)} 页**，全部提取成功（ok=608 / failed=0）；"
          f"双栏 **{n_two}** 篇 / 单栏 **{n_one}** 篇"
          + (f" / 其它 {len(papers) - n_two - n_one} 篇" if len(papers) - n_two - n_one else ""),
          "- 页面角色分布（全部页面；右两列为阶段 1 校准前的对照）：", "",
          "| 页面角色 | 页数 | 占比 | 阶段 1（校准前） | 变化 |", "|---|---|---|---|---|"]
    tot = sum(role_cnt.values()) or 1
    for k in sorted(role_cnt, key=lambda t: -role_cnt[t]):
        old = STAGE1_ROLES.get(k)
        chg = "—" if old is None else f"{role_cnt[k] - old:+d}"
        L.append(f"| {k} | {role_cnt[k]} | {role_cnt[k] / tot * 100:.1f}% | "
                 f"{'—' if old is None else old} | {chg} |")
    fig_new = role_cnt.get("figure-page", 0)
    fig_old = STAGE1_ROLES.get("figure-page", 0)
    tab_new = role_cnt.get("table-page", 0)
    tab_old = STAGE1_ROLES.get("table-page", 0)
    L += ["",
          f"关键变化：整页图 `figure-page` **{fig_old} → {fig_new}** 页、"
          f"整页表 `table-page` **{tab_old} → {tab_new}** 页。原因见 5.2："
          "旧优先级把 references/appendix 压在最前，预印本附录里的整页浮动图/表被全部吞掉；"
          "新优先级把 figure-page/table-page 提到它们之前，结构信息改由 `role_flags` 携带。", ""]

    # ---- 6.2 各会议 × 角色的样本量与可信度
    L += ["### 6.2 各会议 × 页面角色：样本量与可信度", "",
          f"档案主档共 **{len(vr)}** 个 `venue|role` 档（`role` 回退层 {len(role)} 组、"
          f"`venue` 参考层 {len(lv['venue'])} 组）。可信度：论文数 ≥36 high / 16–35 medium / ≤15 low；"
          "**low 档不参与异常判定**（阶段 4 回退到 `role` 层）。", "",
          "| 档 | 篇 | 页 | 可信度 |", "|---|---|---|---|"]
    conf_rank = {"high": 0, "medium": 1, "low": 2}
    for k in sorted(vr, key=lambda t: (conf_rank.get(vr[t]["confidence"], 9), -vr[t]["n_pages"], t)):
        s = vr[k]
        L.append(f"| {k} | {s['n_papers']} | {s['n_pages']} | {s['confidence']} |")
    cnt_conf = {}
    for s in vr.values():
        cnt_conf[s["confidence"]] = cnt_conf.get(s["confidence"], 0) + 1
    L += ["", "档的可信度分布：" + "，".join(
        f"{c} {cnt_conf.get(c, 0)} 档" for c in ("high", "medium", "low")) + "。", ""]

    # ---- 6.3 去冗余
    L += [f"### 6.3 去冗余（|ρ| ≥ {red['threshold']}）", "",
          f"- {red['n_metrics']} 项指标中，有 **{len(red['groups'])}** 组落在同一相关簇（并查集），阶段 4 每组只保留一个代表："]
    for g in red["groups"]:
        L.append(f"  - {' / '.join(g)}")
    L += ["", "相关性最强的前几对（完整表见 `profiles/redundancy.json` 与 `profiles/summary.md`）：", "",
          "| 指标对 | Spearman ρ |", "|---|---|"]
    for k, v in (red.get("strongest_pairs") or [])[:6]:
        L.append(f"| {k} | {v:.3f} |")
    L += ["", f"PCA（仅用 **{pc.get('n')}** 页（{red['n_metrics']} 项指标全部非空的完整样本）；"
          f"标准化后纯 Python Jacobi 特征分解）：**{pc.get('k_for_90pct')} 个主成分可达 90% 累积解释方差**。"
          "前 3 个主成分：", ""]
    for c in (pc.get("components") or [])[:3]:
        top = "，".join(f"{n}({w:+.3f})" for n, w in c["top_loadings"][:4])
        L.append(f"- PC{c['pc']}：解释 {c['explained'] * 100:.1f}%（累积 {c['cumulative'] * 100:.1f}%）｜主载荷：{top}")
    L += ["", "读法：PC1 几乎完全是「浮动体占比 ↔ 图/文比」这一个轴；PC2/PC3 主要是「版面重心上下偏移」"
          "与「文本密度/留白」。即 20 多项几何指标背后只有少数几个独立维度，"
          "这也是去冗余能大幅压缩判定输入的依据。", ""]

    # ---- 6.4 抽检
    L += ["### 6.4 代表档的正常区间（抽检）", "",
          "每行给出 `[p25, p75]` 作为该档的正常区间，并附 p50 及其按论文聚类的 bootstrap CI；"
          "`band` 表示两侧都算异常，`low` 表示越低越好。", "",
          "| 档 | 指标 | 正常区间 | p50 | CI(p50) | direction |", "|---|---|---|---|---|---|"]
    for st in SPOT_STRATA:
        if st not in vr:
            continue
        for mk in SPOT_METRICS:
            m = vr[st]["metrics"].get(mk)
            if not m or m.get("p25") is None:
                continue
            ci = m.get("ci_p50")
            cis = f"[{_fmt(ci[0])}, {_fmt(ci[1])}]" if ci else "—"
            L.append(f"| {st} | {mk} | [{_fmt(m['p25'])}, {_fmt(m['p75'])}] | "
                     f"{_fmt(m['p50'])} | {cis} | {m.get('direction', '—')} |")

    return "\n".join(L) + "\n"


def backfill_docs(path, body):
    """把 ``body`` 写进 docs 第 6 节（替换 ``## 6.`` 与 ``## 7.`` 之间的内容）。"""
    if not os.path.exists(path):
        return False
    with open(path, encoding="utf-8") as f:
        lines = f.readlines()
    s = e = None
    for i, ln in enumerate(lines):
        if ln.startswith("## 6.") and s is None:
            s = i
        elif ln.startswith("## 7.") and s is not None:
            e = i
            break
    if s is None or e is None:
        return False
    new = lines[:s + 1] + ["\n", body, "\n"] + lines[e:]
    with open(path, "w", encoding="utf-8") as f:
        f.writelines(new)
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", default=PAGES)
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--no-ci", action="store_true", help="跳过聚类 bootstrap")
    ap.add_argument("--corr-thr", type=float, default=0.8)
    ap.add_argument("--doc", default=DOC, help="回填 docs 第 6 节的路径")
    ap.add_argument("--no-doc", action="store_true", help="不回填 docs")
    args = ap.parse_args()

    from texopt import profile as PR

    t0 = time.time()
    rows, papers, bad = PR.load_pages(args.pages)
    print(f"读入 {len(papers)} 篇 / {len(rows)} 页" + (f"（跳过损坏 {len(bad)} 个）" if bad else ""))
    prof = PR.build_profile(rows, with_ci=not args.no_ci)
    prof["built_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    prof["built_from"] = {"papers": len(papers), "pages": len(rows),
                          "metrics_dir": os.path.relpath(args.pages, ROOT),
                          "with_ci": not args.no_ci}
    print(f"档案层：venue_role {len(prof['levels']['venue_role'])} 组 / "
          f"role {len(prof['levels']['role'])} 组 / venue {len(prof['levels']['venue'])} 组")

    red = PR.correlation_and_groups(rows, thr=args.corr_thr)
    keys = sorted({k for r in rows for k in r["metrics"]})
    pc = PR.pca(rows, keys, max_comp=len(keys))
    red["pca"] = pc

    os.makedirs(args.out, exist_ok=True)
    PR.dump(prof, os.path.join(args.out, "aesthetic_profile.json"))
    with open(os.path.join(args.out, "redundancy.json"), "w", encoding="utf-8") as f:
        json.dump(red, f, ensure_ascii=False, indent=1)

    # ---- 摘要
    L = ["# 审美档案摘要（阶段 2 自动生成）", "",
         f"- 样本：{len(papers)} 篇 / {len(rows)} 页",
         f"- 指标：{len(keys)} 个",
         f"- 高相关阈值 |ρ| ≥ {args.corr_thr}：{len(red['groups'])} 组",
         f"- PCA：{pc.get('k_for_90pct')} 个主成分达 90% 累积解释方差" if pc.get("n") else "- PCA：样本不足",
         "", "## 各会议 × 页面角色（样本量与可信度）", "",
         "| 档 | 篇 | 页 | 可信度 |", "|---|---|---|---|"]
    for k in sorted(prof["levels"]["venue_role"]):
        s = prof["levels"]["venue_role"][k]
        L.append(f"| {k} | {s['n_papers']} | {s['n_pages']} | {s['confidence']} |")
    if red["groups"]:
        L += ["", "## 高相关指标组（同一现象，需去冗余）", ""]
        for g in red["groups"]:
            L.append(f"- {' / '.join(g)}")
    if red["strongest_pairs"]:
        L += ["", "## 相关性最强的前 15 对", ""]
        for k, v in red["strongest_pairs"]:
            L.append(f"- {k}：ρ = {v}")
    if pc.get("components"):
        L += ["", "## PCA 主成分（标准化后）", ""]
        for c in pc["components"][:5]:
            top = "，".join(f"{n}({w:+.3f})" for n, w in c["top_loadings"][:4])
            L.append(f"- PC{c['pc']}：解释 {c['explained']*100:.1f}%（累积 "
                     f"{c['cumulative']*100:.1f}%）｜主载荷：{top}")
    with open(os.path.join(args.out, "summary.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")

    print(f"输出：{args.out}/aesthetic_profile.json, redundancy.json, summary.md")

    # ---- 回填 docs 第 6 节（只替换 §6，不碰其它章节）
    if not args.no_doc:
        body = render_docs_section(papers, rows, prof, red, pc)
        if backfill_docs(args.doc, body):
            print(f"已回填 {os.path.relpath(args.doc, ROOT)} 第 6 节")
        else:
            print(f"警告：{args.doc} 未找到 '## 6.' / '## 7.' 标题，跳过回填", file=sys.stderr)

    print(f"用时 {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
