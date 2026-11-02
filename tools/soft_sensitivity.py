#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A_soft 指标**敏感性体检**（阶段 16，2026-11-02）。

可辨识性体检（`soft_identifiability.py`）回答的是「这个指标在真实语料上动不动」；
这里补另一半：**「版面坏掉的时候它动不动」**——一个指标在语料上几乎不变，
可能只是因为它只在异常页上才动（这正是它的职责）。

做法：造一批评测用 PDF，每个只改一处版面，量 8 个像素指标的变化：

    baseline      干净正文页（对照组）
    big-gap       页中塞一大块空洞            → 应触发 max_gap
    sparse        内容很少（半页不到）        → 应触发 ink_ratio 下侧 / bottom_blank
    bottom-flush  内容一直排到版心底          → bottom_blank 应变小
    imbalanced    内容全挤在上半页            → top_bottom_ratio 应异常
    full-figure   整页一张大图                → 角色应为 sparse/figure
    wide-table    超宽表格                    → 横向密度变化
    dense-text    塞满的双栏文字              → ink_ratio 上侧

输出：每个变体 × 每个指标的原始值与**损失贡献**（soft_metric_loss），
从而看出「哪些指标真的对坏版面有反应」。

用法：
    python3 tools/soft_sensitivity.py
    python3 tools/soft_sensitivity.py --dpi 50 --out metrics/soft_sensitivity_<date>.json
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from texopt import engine, score as S, visual  # noqa: E402

LOREM = ("Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do "
         "eiusmod tempor incididunt ut labore et dolore magna aliqua. ")
PARA = " ".join([LOREM] * 5)

PREAMBLE = r"""\documentclass[10pt,a4paper]{article}
\usepackage[margin=25mm]{geometry}
\usepackage{graphicx,float}
\begin{document}
"""


def _paras(n: int) -> str:
    return "\n\n".join(PARA for _ in range(n))


VARIANTS = {
    # 干净正文页：两页文字，第二页中等密度
    "baseline": PREAMBLE + "\\section{Baseline}\n" + _paras(7) + "\n\\end{document}\n",
    # 页中一大块空洞（浮动体被挤走 / 手动 \vfill）
    "big-gap": PREAMBLE + "\\section{Big Gap}\n" + _paras(3)
               + "\n\\vspace{95mm}\n" + _paras(3) + "\n\\end{document}\n",
    # 内容很少
    "sparse": PREAMBLE + "\\section{Sparse}\n" + _paras(1) + "\n\\end{document}\n",
    # 页面底部压满（去掉 \raggedbottom，加 \enlargethispage）
    "bottom-flush": PREAMBLE + "\\raggedbottom\n\\enlargethispage{20mm}\n"
                    "\\section{Bottom Flush}\n" + _paras(9) + "\n\\end{document}\n",
    # 内容全挤在上半页（下半页大留白）
    "imbalanced": PREAMBLE + "\\section{Imbalanced}\n" + _paras(2)
                  + "\n\\newpage\n\\vspace*{-40mm}\n\\enlargethispage{-90mm}\n"
                  + _paras(2) + "\n\\end{document}\n",
    # 整页一张大图
    "full-figure": None,     # 需生成图片，见 build()
    # 超宽表格
    "wide-table": PREAMBLE + "\\section{Wide Table}\n" + _paras(2)
                  + "\n\\begin{table}[H]\\centering\n"
                  + "\\begin{tabular}{p{60mm}p{60mm}p{60mm}}\n"
                  + "A & B & C \\\\\n" * 12
                  + "\\end{tabular}\\caption{wide}\\end{table}\n"
                  + _paras(2) + "\n\\end{document}\n",
    # 塞满的双栏文字（高密度）
    "dense-text": PREAMBLE.replace("\\begin{document}",
                                   "\\begin{document}\\twocolumn")
                  + "\\section{Dense}\n" + _paras(10) + "\n\\end{document}\n",
}


def _figure_pdf(outdir: str) -> str:
    """整页大图：先用 TikZ 画一个占满版心的灰色块。"""
    return (PREAMBLE
            + "\\section{Full Figure}\n"
            + "\\begin{figure}[H]\\centering\n"
            + "\\rule{150mm}{230mm}\n"
            + "\\caption{full page block}\\end{figure}\n"
            + "\\end{document}\n")


def build(variant: str) -> str:
    return VARIANTS.get(variant) or _figure_pdf("")


def render_metrics(tex_src: str, workdir: str, dpi: int) -> dict:
    os.makedirs(workdir, exist_ok=True)
    tex = os.path.join(workdir, "t.tex")
    with open(tex, "w", encoding="utf-8") as f:
        f.write(tex_src)
    res = engine.compile_tex(tex)
    if not res.ok or not res.pdf_path:
        return {"error": res.first_error or "编译失败"}
    out = visual.analyze_pdf(res.pdf_path, os.path.join(workdir, "vis"), dpi=dpi)
    pages = [p for p in (out.get("pages") or []) if "error" not in p]
    if not pages:
        return {"error": out.get("error") or "无页面指标"}
    # 取最后一页（正文最满的一页）作为代表；sparse 只有一页
    return {"page": pages[-1], "n_pages": len(pages)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dpi", type=int, default=50)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    base = os.environ.get("TEXOPT_SENS_DIR") or os.path.join(
        "/mnt/d/桌面/texopt", "_soft_sensitivity")
    shutil.rmtree(base, ignore_errors=True)
    os.makedirs(base, exist_ok=True)

    metrics = [m for m, sp in S.SOFT_SPEC.items() if sp.get("w")]
    table = {}
    try:
        for name in VARIANTS:
            workdir = os.path.join(base, name)
            res = render_metrics(build(name), workdir, args.dpi)
            if "error" in res:
                table[name] = {"error": res["error"]}
                print(f"  [跳过] {name}: {res['error']}")
                continue
            pg = res["page"]
            row = {}
            for m in metrics:
                x = pg.get(m)
                row[m] = {"x": x, "loss": (S.soft_metric_loss(m, x)
                                           if x is not None else None)}
            table[name] = {"n_pages": res["n_pages"], **row}
            print(f"  [{name}] " + "  ".join(
                f"{m}={row[m]['loss']}" for m in metrics if row[m]["loss"] is not None))
    finally:
        shutil.rmtree(base, ignore_errors=True)

    # 汇总：每个指标「变体间损失极差」——有反应才有资格进 A_soft
    summary = {}
    for m in metrics:
        vals = [v[m]["loss"] for v in table.values()
                if isinstance(v, dict) and isinstance(v.get(m), dict)
                and v[m]["loss"] is not None]
        summary[m] = {
            "n_variants": len(vals),
            "min": round(min(vals), 4) if vals else None,
            "max": round(max(vals), 4) if vals else None,
            "range": round(max(vals) - min(vals), 4) if vals else None,
            "distinct": len({round(v, 3) for v in vals}),
        }
    stamp = date.today().strftime("%Y%m%d")
    out = args.out or os.path.join(ROOT, "metrics", f"soft_sensitivity_{stamp}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"dpi": args.dpi, "variants": table, "summary": summary},
                  f, ensure_ascii=False, indent=2)

    print("\n== 指标对坏版面的反应（变体间损失极差）==")
    for m, v in sorted(summary.items(), key=lambda kv: -(kv[1]["range"] or 0)):
        flag = "有反应" if (v["range"] or 0) >= 0.10 else "几乎无反应"
        print(f"  {m:>17}  range={v['range']}  ({v['distinct']} 个不同取值)  -> {flag}")
    print(f"\n产物：{out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
