#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""构建《texopt 评分模型 v2 讲解版》HTML 文档。

流程：
  1) 每个公式用 LaTeX(standalone) 单独编译成紧裁剪 PDF；
  2) 用 mutool 把 PDF 转成 SVG（矢量，浏览器直接可看，无需联网）；
  3) 读回 SVG 的固有宽高，按统一缩放写进 HTML 模板的占位符。

用法：
    python3 docs/make_formula_doc.py            # 生成 HTML + assets

依赖（本机已具备）：pdflatex、mutool（mupdf-tools）。
占位符：模板里写 {{EQ:名字}}，会被替换成该公式的 <img> 标签。
"""
from __future__ import annotations

import glob
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "formula_doc_assets")
# 多文档：同一套公式图，不同模板
# 注（2026-10-31）：v2（L+A+I 单一总分）已被 v3 取代，讲解版文档整套删除；
# 公式图资产 formula_doc_assets/ 仍由 v3 文档引用，保留。
DOCS = [
    {
        "template": os.path.join(HERE, "scoring_report_20261102.template.html"),
        "output": os.path.join(HERE, "scoring_report_20261102.html"),
        "single": os.path.join(HERE, "scoring_report_20261102_single.html"),
        "note": "阶段汇报：打分评价体系现状（2026-11-02）",
    },
    {
        "template": os.path.join(HERE, "model_v3_design_20261014.template.html"),
        "output": os.path.join(HERE, "model_v3_design_20261014.html"),
        "single": os.path.join(HERE, "model_v3_design_20261014_single.html"),
        "note": "v3 结构设计说明（gate / model1 / model2）",
    },
]

# 公式表：名字 -> LaTeX（英语标签，避免中文字体依赖）
EQS = {
    "eq_L": r"L(x')=\sum_{i\in\mathcal{H}} w_i\,\ell_i(x')"
            r"=w_c\ell_{\text{compile}}+w_p\ell_{\text{page}}"
            r"+w_s\ell_{\text{spec}}+w_f\ell_{\text{fig}}",
    "eq_lcompile": r"\ell_{\text{compile}}(x')=1-\mathbf{1}"
                   r"\big[\,\text{compiles}\ \wedge\ \text{produces a PDF}\,\big]",
    "eq_lpage": r"\ell_{\text{page}}(x')="
                r"\begin{cases}\mathbf{1}\big[N_{\text{pages}}(x')>b\,\big],"
                r"& b\neq\varnothing\\[2pt]"
                r"\text{this term does not exist},& b=\varnothing\end{cases}",
    "eq_lspec": r"\ell_{\text{spec}}(x')=\frac{1}{K}\sum_{j=1}^{K}"
                r"\mathbf{1}\big[\,p_j(x')\neq p_j^{\text{req}}\,\big]",
    "eq_lfig": r"\ell_{\text{fig}}(x')=\mathbf{1}"
               r"\big[\,\text{fingerprints}(x')\neq\text{fingerprints}(x_0)\,\big]",
    "eq_keep": r"\mathrm{Keep}(x')=\frac{\sum_{c}\min\big(n_c(x'),\,n_c(x_0)\big)}"
               r"{\sum_{c}\max\big(n_c(x'),\,n_c(x_0)\big)}",
    "eq_dcontent": r"D_{\text{content}}(x')=1-\mathrm{Keep}(x')",
    "eq_Istruct": r"I_{\text{struct}}(x')=0.5\,|\Delta m|+3.0\,|\Delta f|"
                   r"+0.4\,N_{\text{float}}+0.4\,N_{\text{width}}",
    "eq_I": r"I(x')=I_{\text{struct}}(x')+\beta\,D_{\text{content}}(x')"
            r",\qquad \beta=50",
    "eq_J1": r"x'\ \text{is feasible}\iff L(x')=0,\qquad J_1(x')="
             r"\begin{cases}+\infty,& L(x')>0\\ I(x'),& L(x')=0\end{cases}",
    "eq_total_now": r"\text{total}=10^{6}\cdot|L|+A+I(x')",
    "eq_A": r"A(x')=A_{\text{defect}}(x')+\lambda\,A_{\text{profile}}(x'),"
            r"\qquad \lambda=0\ \text{(shadow mode)}",
    "eq_Adefect": r"\begin{aligned}"
                  r"A_{\text{defect}}={}&1.0\,N_{\text{overfull}}+0.6\,N_{\text{underfull}}"
                  r"+1.0\,N_{\text{vboxOver}}+1.4\,N_{\text{vboxUnder}}\\"
                  r"&+1.6\,N_{\text{floatwarn}}+1.2\,N_{\text{tabOverwide}}"
                  r"+0.3\,N_{\text{warn}}+1.0\,N_{\text{figOverwide}}\\"
                  r"&+2.0\,\mathbf{1}[\text{quality macros missing}]\\"
                  r"&+\sum_{fe}\big(0.8\,\mathbf{1}[\text{spec unstable}]"
                  r"+0.5\,\mathbf{1}[\text{spec}=H]\big)+\sum_{h}w_{\text{hyg}}(h)"
                  r"+D_{\text{vis}}\\"
                  r"&+2.5\,\mathbf{1}[\text{TOC missing}]+2.5\,\mathbf{1}"
                  r"[\text{header missing}]+1.5\,\mathbf{1}[\text{headings uncolored}]"
                  r"\end{aligned}",
    "eq_vis": r"D_{\text{vis}}=\sum_{d}\mathrm{weight}(d)\cdot\mathrm{severity}(d)",
    "eq_s1": r"\tilde x_i=\log(1+x_i)",
    "eq_s2": r"z_i=\mathrm{clip}\!\left(\frac{\tilde x_i-m_i}{s_i},\,-4,\,+4\right)",
    "eq_s3": r"\mathrm{loss}_i=W_{\text{low}}\frac{\max(0,\mathrm{lo}_i-\tilde x_i)}{s_i}"
             r"+W_{\text{high}}\frac{\max(0,\tilde x_i-\mathrm{hi}_i)}{s_i},"
             r"\quad W_{\text{low}}=1.2>W_{\text{high}}=1.0",
    "eq_s4": r"\widehat{\mathrm{loss}}_i=\min\!\left("
             r"\frac{\mathrm{loss}_i}{\mathrm{ref}_i},\,20\right)",
    "eq_s5": r"D^2=z^{\top}\Sigma^{-1}z,\qquad \Sigma=(1-\delta)R+\delta I,"
             r"\qquad \widehat{D^2}=D^2/d2_{\text{ref}}",
    "eq_s6": r"\mathrm{pool}(u)=0.5\cdot\mathrm{topk}(u)+0.5\cdot\mathrm{mean}(u),"
             r"\qquad k=\max\!\big(1,\mathrm{round}(0.05\,N_{\text{pages}})\big)",
    "eq_s7": r"A_{\text{profile}}="
             r"\frac{\sum_i w_i\,\mathrm{pool}\big(\widehat{\mathrm{loss}}_i\big)"
             r"+w_M\,\mathrm{pool}\big(\widehat{D^2}\big)}{\sum_i w_i+w_M}",
    # ---- v3 结构（2026-10-14）：底层逻辑门 + model1 + model2 ----
    "eq_gate": r"\text{Gate}(x')=\Bigl\{\ \text{compile},\ \text{PDF},\ "
               r"N_{\text{pages}}\le b,\ \text{fig fidelity},\ \text{font},\ "
               r"\text{margin},\ \text{fleqn / TOC / header}\ \Bigr\}",
    "eq_M1": r"M_1(x')=\rho\,P(x')+I(x'),\qquad \rho=2.0",
    "eq_M2": r"M_2(x')=A_{\text{soft}}(x')+\lambda\,A_{\text{profile}}(x'),"
             r"\qquad \lambda=0",
    "eq_P": r"P(x')=\sum_{k} w_k\,N_k\;+\;\sum_{fe}\Bigl(0.8\,\mathbf{1}"
            r"[\text{spec unstable}]+0.5\,\mathbf{1}[\text{spec}=H]\Bigr)"
            r"\;+\;\sum_h w_{\text{hyg}}(h)"
            r"\;+\;\sum_{d\in D_1} w_d\,s(d)",
    "eq_softloss": r"\mathrm{loss}_i(p)=W_{\text{low}}\frac{\max\big(0,\ \mathrm{lo}_i-x_i(p)\big)}{N_i}"
                   r"+W_{\text{high}}\frac{\max\big(0,\ x_i(p)-\mathrm{hi}_i\big)}{N_i},"
                   r"\quad N_i=\mathrm{hi}_i-\mathrm{lo}_i",
    "eq_softpool": r"A_{\text{soft}}(x')=\sum_i w_i\Bigl[\,0.5\,\mathrm{topk}_k\big(\mathrm{loss}_i\big)"
                   r"+0.5\,\mathrm{mean}\big(\mathrm{loss}_i\big)\Bigr],"
                   r"\quad k=\max\!\big(1,\mathrm{round}(0.05\,N_{\text{pages}})\big)",
    # ---- 阶段汇报（2026-11-02）：现行口径 ----
    "eq_rep_m1": r"M_1(x')=\rho\,P(x')+I(x'),\qquad \rho=15"
                 r"\ \ \text{(indifference-point calibrated)}",
    "eq_rep_w": r"w_k=\frac{c_k^{*}}{\rho},\qquad c_k^{*}:\ \text{human indifference}"
                r"\ \text{cost (in }I\text{ units) at which}"
                r"\ \text{``keep the defect''}\equiv\text{``fix it''}",
    "eq_rep_scale": r"s=\frac{\sum_{k\in\mathcal{C}} w_k^{\mathrm{before}}}"
                    r"{\sum_{k\in\mathcal{C}} w_k^{\mathrm{raw}}},\qquad "
                    r"w_k^{\mathrm{final}}=s\,w_k^{\mathrm{raw}}",
    "eq_rep_loss": r"\ell_i(p)=w_i\Bigl(1-e^{-d_i(p)^2/2}\Bigr),\qquad "
                   r"d_i(p)=\frac{\bigl|\,x_i(p)-t_i\,\bigr|}{s_i^{\pm}},\qquad "
                   r"t_i=\text{corpus median},\ \ s_i^{\pm}=\text{dist. to }p_{5}/p_{95}",
    "eq_rep_pool": r"A_{\mathrm{soft}}(x')=\sum_{i}w_i\Bigl[\,0.5\,\mathrm{topk}_k\big(\ell_i\big)"
                   r"+0.5\,\mathrm{mean}\big(\ell_i\big)\Bigr],\qquad "
                   r"k=\max\bigl(1,\mathrm{round}(0.05\,N_{\mathrm{pages}})\bigr)",
    "eq_rep_order": r"\mathrm{rank}(x'):\;\Bigl(\;|\mathrm{Gate}(x')|,\;\;M_1(x'),\;\;M_2(x')\;\Bigr)"
                    r"\quad\text{lexicographic (no summation)}",
    "eq_rep_accept": r"\text{accept}\iff \Delta|\mathrm{Gate}|<0\ \ \vee\ \ "
                     r"\bigl(\Delta|\mathrm{Gate}|=0\ \wedge\ \Delta M_1<0\bigr)\ \ \vee\ \ "
                     r"\bigl(\Delta M_1=0\ \wedge\ \Delta M_2<0\bigr)",
    "eq_rep_page": r"p_p=\sum_{d:\,\mathrm{page}(d)=p} w_d\,s(d),\qquad "
                   r"\bar p=\frac{1}{N}\sum_{p}p_p,\qquad "
                   r"\mathrm{topk}_k(p),\qquad \max_p p_p",
    "eq_order": r"\text{rank}\;:\;\big(\;|\mathrm{Gate}(x')|,\;\;M_1(x'),\;\;M_2(x')\;\big)"
                r"\ \ \text{lexicographic},\qquad "
                r"T(x')=\rho P+I+A_{\text{soft}}\ (\text{implementation})",
}

PREAMBLE = (r"\documentclass[border=2pt]{standalone}" "\n"
            r"\usepackage{amsmath,amssymb}" "\n"
            r"\begin{document}" "\n"
            "$\\displaystyle %s$" "\n"
            r"\end{document}" "\n")

SCALE = 1.30          # SVG(px) -> HTML(px) 的放大倍数
SIZE_RE = re.compile(r'<svg[^>]*\bwidth="([0-9.]+)"[^>]*\bheight="([0-9.]+)"')


def build_svg(name: str, tex: str, outdir: str) -> tuple[float, float]:
    """编译单个公式并转成 SVG，返回 (宽, 高)。"""
    tmp = tempfile.mkdtemp(prefix="eqbuild_")
    try:
        src = os.path.join(tmp, name + ".tex")
        with open(src, "w", encoding="utf-8") as fh:
            fh.write(PREAMBLE % tex)
        rc = subprocess.run(["pdflatex", "-interaction=nonstopmode",
                             "-halt-on-error", name + ".tex"],
                            cwd=tmp, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, timeout=180)
        pdf = os.path.join(tmp, name + ".pdf")
        if rc.returncode != 0 or not os.path.isfile(pdf):
            raise RuntimeError(f"pdflatex 失败：{name}\n"
                               + rc.stdout.decode("utf-8", "replace")[-1500:])
        rc = subprocess.run(["mutool", "draw", "-F", "svg",
                             "-o", name + ".svg", pdf],
                            cwd=tmp, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, timeout=120)
        svgs = sorted(glob.glob(os.path.join(tmp, name + "*.svg")))
        if rc.returncode != 0 or not svgs:
            raise RuntimeError(f"mutool 失败：{name}\n"
                               + rc.stdout.decode("utf-8", "replace")[-800:])
        raw = open(svgs[0], encoding="utf-8").read()
        m = SIZE_RE.search(raw)
        if not m:
            raise RuntimeError(f"SVG 尺寸解析失败：{name}")
        w, h = float(m.group(1)), float(m.group(2))
        dst = os.path.join(outdir, name + ".svg")
        with open(dst, "w", encoding="utf-8") as fh:
            fh.write(raw)
        return w, h
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> int:
    os.makedirs(ASSETS, exist_ok=True)
    sizes = {}
    for name in EQS:
        sys.stdout.write(f"  [公式] {name} ... ")
        sys.stdout.flush()
        sizes[name] = build_svg(name, EQS[name], ASSETS)
        print(f"{sizes[name][0]:.0f}x{sizes[name][1]:.0f}px")

    import base64

    def make_img(name, inline: bool) -> str:
        w, h = sizes[name]
        if inline:
            raw = open(os.path.join(ASSETS, name + ".svg"), "rb").read()
            b64 = base64.b64encode(raw).decode("ascii")
            src = f"data:image/svg+xml;base64,{b64}"
        else:
            src = f"formula_doc_assets/{name}.svg"
        return (f'<img class="eq" alt="{name}" src="{src}" '
                f'style="width:{w * SCALE:.1f}px;max-width:100%;height:auto">')

    for doc in DOCS:
        tpl = open(doc["template"], encoding="utf-8").read()

        def repl(m, _inline=False):
            name = m.group(1)
            if name not in sizes:
                raise KeyError(f"模板引用了未定义的公式：{name}")
            return make_img(name, _inline)

        html = re.sub(r"\{\{EQ:([A-Za-z0-9_]+)\}\}", repl, tpl)
        with open(doc["output"], "w", encoding="utf-8") as fh:
            fh.write(html)
        single = re.sub(r"\{\{EQ:([A-Za-z0-9_]+)\}\}",
                        lambda m: repl(m, True), tpl)
        with open(doc["single"], "w", encoding="utf-8") as fh:
            fh.write(single)
        print(f"  写出 {os.path.basename(doc['output'])}（{len(html) / 1024:.0f} KB，"
              f"{doc['note']}） + 单文件版（{len(single) / 1024:.0f} KB）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
