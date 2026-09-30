# -*- coding: utf-8 -*-
"""生成 examples/ 里的靶稿（demo / issues / chaos / nightmare / aidtest /
fig_violation / propose_target）。

背景：这批靶稿曾在工作区丢失（见 docs/stage0_visual_inventory.md 第 8 节），
套件里对应的集成检查只能长期 SKIP。这里用**可复现脚本**重建，并把生成结果
与脚本一起纳入 git —— 以后靶稿再丢，`python3 examples/gen_fixtures.py` 即可重建。

约定：
  * 纯 ASCII 正文，避免 CJK 字体依赖（xelatex + Latin Modern 即可编译）；
  * 图形一律用 mwe 包的 example-image（TeX Live 自带，不需要外部图片）；
  * 只生成「作者会写的稿子」，不预置 texopt 自己的注入块。

用法：python3 examples/gen_fixtures.py
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------- 段落池
PARAS = [
    "Layout optimization for academic manuscripts is a constrained problem: the "
    "visual result of a document is a global property of the whole file, while "
    "most editing actions are local. A change that removes one bad line can push "
    "a float to the next page and create a much larger gap, so an optimizer must "
    "always recompile and re-evaluate the entire document before accepting an edit.",

    "The scoring model used here separates logic from aesthetics. Logic asks "
    "whether the file compiles, whether the rendered PDF keeps the body text "
    "byte-identical, and whether the requested hard constraints such as font size, "
    "margins and page limits are satisfied. Aesthetics collects measurable layout "
    "defects such as overfull lines, underfull lines, badly placed floats and "
    "inconsistent vertical spacing.",

    "Intervention cost makes the optimizer conservative. Every edit that is "
    "applied to the source increases the intervention score, so a repair is only "
    "kept when the total objective improves after a full recompilation. This is "
    "what prevents the system from grooming its own score with edits that no human "
    "would ever make.",

    "Page limits deserve special care. Compressing a document by shrinking its "
    "margins changes the relationship between floats and the text that refers to "
    "them, and the resulting layout often looks wrong even though every number in "
    "the report is legal. For that reason the default policy refuses to touch the "
    "global text block and reports an honest failure instead.",

    "The pipeline is deterministic. Given the same source file, the same "
    "requirement specification and the same toolchain, it produces the same trace "
    "of candidate actions, the same accept and rollback decisions, and the same "
    "final document. Determinism matters for reproducibility, for regression "
    "testing and for the audit trail that is written next to every run.",

    "Perception is layered. The source layer parses the LaTeX file and looks for "
    "patterns that are known to be unstable, such as manual page breaks, manual "
    "vertical spacing, bare dollar math and float specifications that pin a float "
    "to its declaration point. The log layer reads the compiler log and counts "
    "overfull boxes, underfull boxes and badness warnings.",

    "The rendered layer measures the PDF itself. Page images give coverage "
    "statistics, the vertical position of ink, and the size of the largest empty "
    "band on each page. Those numbers are coarse on purpose: they are used as "
    "evidence that something looks wrong, not as a model of human taste.",

    "Float placement is the hardest part of the problem. A figure that is "
    "referenced in one paragraph may be typeset several pages later, and the "
    "quality of the page depends on whether the top, bottom and text fraction "
    "constraints of the float mechanism are balanced. Sanitising the float "
    "specification to the top, bottom and page forms is a cheap first step.",

    "Quality macros are injected before any structural edit. Penalties for "
    "widows and orphans, limits on consecutive hyphenated lines and a small "
    "emergency stretch are enough to remove a large fraction of the visual "
    "defects that a raw manuscript shows, and they do not change a single "
    "character of the body text.",

    "Reporting matters as much as repair. Every run writes a machine readable "
    "trace and a human readable report. The report lists the residual problems "
    "that the system deliberately left alone, together with the reason, so that "
    "a human author can decide whether to rewrite a sentence, move a figure or "
    "accept the page as it is.",
]

TABLE = r"""
\begin{table}[tbp]\centering
\caption{Reported layout observations per requirement class.}
\begin{tabular}{lll}\toprule
Class & Signal & Typical action \\\midrule
Hard spec & font size, margin & align to requirement \\
Compile & missing file & report and stop \\
Page limit & page count & pure-layout reduction \\
Quality & overfull, underfull & reflow or renormalize \\\bottomrule
\end{tabular}
\end{table}
"""

FIGURE = r"""
\begin{figure}[tbp]\centering
\includegraphics[width=0.78\linewidth]{example-image}
\caption{A schematic of the perceive--score--act loop. The optimizer never edits
the source without recompiling the whole document afterwards.}
\end{figure}
"""

BIB = r"""
\begin{thebibliography}{9}
\bibitem{knuth} D.~E. Knuth and M.~F. Plass, \emph{Breaking Paragraphs into
Lines}, Software: Practice and Experience, 1981.
\bibitem{luo} Y.~Luo, \emph{Global versus local optimisation in document
layout}, Journal of Typesetting Systems, 2024.
\bibitem{openclaw} The OpenClaw Project, \emph{Agent architecture notes}, 2026.
\end{thebibliography}
"""

# demo 的段落数：调过（见 _probe 调参）——自然 6 页 @10pt/a4/25.4mm，
# 末页填充率 ~5.7%（避免“末页几乎空白”被判 high 缺陷）。
DEMO_COUNTS = dict(intro=14, related=14, method=9, exp=15, disc=13)


def _sec(title, n, off=0, pool=None):
    pool = pool or PARAS
    out = ["\n\\section{%s}\n" % title]
    for i in range(n):
        out.append(pool[(i + off) % len(pool)] + "\n\n")
    return "".join(out)


def build_demo(counts=None, extra=0):
    """demo.tex：干净的目标稿（自然 6 页 @10pt/a4/25.4mm）。

    README 页数限制演示（--target 5）与闭环集成靶稿。默认要求下
    L=0、无 high 视觉缺陷；闭环只可能注入质量宏（DONE / CONVERGED）。

    extra：额外段落数（调页数/末页填充率用，见 tests 里的 6 页要求）。
    """
    c = dict(DEMO_COUNTS)
    if counts:
        c.update(counts)
    parts = [r"""\documentclass[10pt,a4paper]{article}
\usepackage[margin=25.4mm]{geometry}
\usepackage{graphicx,booktabs,amsmath,amssymb}
\usepackage[hidelinks]{hyperref}
\title{A Demonstrator Paper for Whole-Document Layout Optimization}
\author{Sh Lab \\ Zhejiang University}
\date{}
\begin{document}
\maketitle
\begin{abstract}
This document is a demonstrator. It is deliberately clean: no manual spacing,
no manual page breaks and no unstable float specifications. It exists so that
the deterministic closed loop can be run end to end on a realistic multi-page
article, and so that page-limit requests can be exercised without touching the
content.
\end{abstract}
"""]
    parts.append(_sec("Introduction", c["intro"], 0))
    parts.append(_sec("Related Work", c["related"], 3))
    parts.append(_sec("Method", c["method"], 3))
    parts.append(TABLE)
    parts.append(_sec("Experiments", c["exp"], 2))
    parts.append(FIGURE)
    parts.append(_sec("Discussion", c["disc"], 1))
    if c.get("ext"):
        parts.append(_sec("Extended Discussion", c["ext"], 4))
    parts.append(r"""
\section{Conclusion}
The demonstrator restates the design rule of the system: measure the whole
document, act locally, recompile, and keep an edit only when the global
objective improves.
""" + BIB + "\\end{document}\n")
    return "".join(parts)


# ---------------------------------------------------------------- issues
def build_issues():
    """issues.tex：只埋 4 类**规则可修**的问题（README 快速开始 0）。

    1) 手动垂直间距 \\vspace{2cm}       -> remove_excessive_vspace
    2) 正文手动分页 \\newpage            -> remove_manual_pagebreak
    3) 裸 $$..$$ 数学                    -> normalize_dollar_math
    4) [H] 强排浮动体                    -> sanitize_float_specs
    另加一处下划线（期刊禁用，仅报告，不自动改）。
    """
    parts = [r"""\documentclass[10pt,a4paper]{article}
\usepackage[margin=25.4mm]{geometry}
\usepackage{graphicx,float,amsmath}
\title{Four Common Layout Issues}
\author{Sh Lab}
\date{}
\begin{document}
\maketitle
\section{Introduction}
"""]
    parts.append(PARAS[0] + "\n\n" + PARAS[1] + "\n\n")
    parts.append(r"""\vspace{2cm}
""")
    parts.append(PARAS[2] + "\n\n")
    parts.append(r"""Here the author underlined an \underline{emphasised phrase} by hand,
which most venues do not allow in the final version.
""" + "\n")
    parts.append("\\newpage\n")
    parts.append(_sec("Method", 4, 3))
    parts.append(r"""The following display is written with bare dollar signs:
$$E = mc^2$$
which makes the surrounding vertical space inconsistent with the rest of the
document.
""" + "\n")
    parts.append(r"""\begin{figure}[H]\centering
\includegraphics[width=0.62\linewidth]{example-image}
\caption{A figure that is pinned to the exact position where it is declared.}
\end{figure}
""" + "\n")
    parts.append(_sec("Results", 5, 2))
    parts.append(r"""
\section{Conclusion}
Four problems, four deterministic repairs, no change to the body text.
""" + "\\end{document}\n")
    return "".join(parts)


# ---------------------------------------------------------------- chaos
def build_chaos():
    """chaos.tex：12 类常见混乱（比 nightmare 轻，用于 --full 回归）。"""
    parts = [r"""\documentclass[10pt,a4paper]{article}
\usepackage[margin=25.4mm]{geometry}
\usepackage{graphicx,float,amsmath,amssymb,booktabs,enumitem}
\setlength{\parskip}{14pt}
\title{Twelve Classes of Layout Chaos}
\author{Sh Lab}
\date{}
\begin{document}
\maketitle
\section{Introduction}
"""]
    parts.append(PARAS[0] + "\n\n" + PARAS[1] + "\n\n")
    parts.append(r"""A sentence ends with a hard line break here.\\
And the next line continues the same paragraph after a manual break.\\
The author kept doing this instead of letting TeX break the paragraph.\\
""" + "\n")
    parts.append(r"""\noindent This paragraph was manually de-indented.
""" + "\n")
    parts.append(r"""\vspace{4cm}
""" + "\n")
    parts.append(r"""Some emphasised words live in an \underline{underline} and another
\underline{underlined phrase}, which is not the house style.
""" + "\n")
    parts.append(r"""The display below uses bare dollar math:
$$f(x) = \sum_{i=1}^{n} a_i x_i$$
and a second one follows immediately:
$$g(x) = \int_0^T e^{-t^2}\,dt$$
""" + "\n")
    parts.append(r"""\newpage
""")
    parts.append(_sec("Method", 3, 3))
    parts.append(r"""An oversized media object is placed here:
\begin{figure}[H]\centering
\includegraphics[width=1.20\linewidth]{example-image}
\caption{A figure that is wider than the text block.}
\end{figure}
""" + "\n")
    parts.append(PARAS[4] + "\n\n")
    parts.append(r"""{\Large This sentence switches to a much larger font size inside a
paragraph, which breaks the rhythm of the page.} And then {\small it drops to a
smaller size again}, so the reader sees three sizes in one paragraph.
""" + "\n")
    parts.append(r"""\begin{table}[h!]\centering
\caption{A table mixing rule styles.}
\begin{tabular}{ll}\hline
Key & Value \\\hline
alpha & 1 \\\toprule
beta & 2 \\\bottomrule
\end{tabular}
\end{table}
""" + "\n")
    parts.append(r"""\begin{itemize}[itemsep=16pt,topsep=14pt]
\item A list with deliberately excessive vertical spacing.
\item Another item that makes the following page look loose.
\end{itemize}
""" + "\n")
    parts.append(r"""A pathological token appears here: pseudopseudohypoparathyroidismcounterrevolutionarieselectroencephalographically.
""" + "\n")
    parts.append(r"""\begin{center}
This entire paragraph of body text was wrapped in a center environment, which
makes the lines look ragged in a way that no journal accepts.
\end{center}
""" + "\n")
    parts.append(r"""\clearpage
""" + "\n")
    parts.append(_sec("Results", 6, 1))
    parts.append(r"""
\section{Conclusion}
Twelve classes of damage, all detectable from source, log and page image.
""" + "\\end{document}\n")
    return "".join(parts)


# ---------------------------------------------------------------- nightmare
def build_nightmare():
    """nightmare.tex：27 类排版灾难（--full 回归的重靶子）。"""
    parts = [r"""\documentclass[10pt,a4paper,fleqn]{article}
\usepackage[margin=0.55in]{geometry}
\usepackage{graphicx,float,amsmath,amssymb,booktabs,enumitem,multicol,titlesec,fancyhdr,tikz}
\setlength{\parskip}{16pt}
\setlength{\parindent}{0pt}
\linespread{1.7}
\titleformat{\section}{\Huge\bfseries}{\thesection}{0.2em}{}
\titleformat{\subsection}{\Large\bfseries}{\thesubsection}{0.1em}{}
\pagestyle{fancy}\fancyhf{}
\lhead{\tiny A Very Long Running Header That Carries No Information Whatsoever And Collides With The Rule}
\rhead{\tiny \today}
\title{\Huge A Title So Large That It Eats The Entire First Page Of The Manuscript}
\author{A. Student \and B. Student \and C. Student \and D. Student}
\date{}
\begin{document}
\maketitle
This opening paragraph is long enough to create an awkward block right under the
title. It repeats itself, spaces badly and mixes several poor decisions. The
point is not to communicate a result but to stress every mechanism at once:
headings, equations, figures, tables, lists, margins and page breaks.
\section{Introduction}
"""]
    parts.append(PARAS[0] + "\n\n" + PARAS[1] + "\n\n")
    parts.append(r"""A long unbreakable token follows: supercalifragilisticexpialidociousmicroscopicsilicovolcanoconiosispneumonoultramicroscopicsilicovolcanoconiosis.
""" + "\n")
    parts.append(r"""\noindent Manually de-indented paragraph one.
\noindent Manually de-indented paragraph two.
\noindent Manually de-indented paragraph three.
""" + "\n")
    parts.append(r"""\vspace{3cm}
""")
    parts.append(r"""\vspace{-1.5cm}
""" + "\n")
    parts.append(r"""Emphasis is all over the place: \underline{one}, \underline{two},
\underline{three}, \underline{four} and {\Large a size switch} inside the
running text, plus {\tiny a tiny fragment}.
""" + "\n")
    parts.append(r"""Bare dollar math appears four times:
$$a^2 + b^2 = c^2$$
$$e^{i\pi} + 1 = 0$$
$$\frac{\partial u}{\partial t} = \alpha \nabla^2 u$$
$$\int_0^1 x^2\,dx = \frac{1}{3}$$
""" + "\n")
    parts.append(r"""\newpage
""" + "\n")
    parts.append(_sec("Mathematical Model", 4, 4))
    parts.append(r"""\begin{center}
This whole paragraph of running text is centred, which destroys the left edge
that the reader uses to navigate the page.
\end{center}
\begin{flushright}
And this one is flushed right for no reason at all.
\end{flushright}
""" + "\n")
    parts.append(r"""\begin{align}
y &= a_0 + a_1 x + a_2 x^2 + a_3 x^3 + a_4 x^4 + a_5 x^5 + a_6 x^6 + a_7 x^7 \\
z &= \frac{\alpha + \beta + \gamma + \delta + \epsilon}{1 + \alpha^2 + \beta^2 + \gamma^2}
\end{align}
""" + "\n")
    parts.append(r"""\begin{figure}[H]\centering
\includegraphics[width=1.25\linewidth]{example-image}
\caption{A figure that is much wider than the text block.}
\end{figure}
\begin{figure}[h]\centering
\includegraphics[width=0.9\linewidth,height=0.55\textheight,keepaspectratio]{example-image}
\caption{A figure that eats more than half of the page height.}
\end{figure}
""" + "\n")
    parts.append(r"""\begin{table}[!ht]\centering
\caption{A dense table with mixed rules.}
\begin{tabular}{lrrrrrrrr}\hline
Method & Accuracy & Precision & Recall & F1 & Time & Memory & Score & Rank\\\hline
Method A & 0.912345 & 0.934567 & 0.901234 & 0.917321 & 123.45 & 1024 & 98.123 & 1 \\\toprule
Method B & 0.901234 & 0.923456 & 0.889012 & 0.905432 & 234.56 & 2048 & 91.456 & 2 \\\bottomrule
\end{tabular}
\end{table}
\begin{table}[!ht]\centering
\caption{Another table with narrow fixed columns.}
\begin{tabular}{p{2.0cm}p{2.0cm}p{2.0cm}}
\hline Very long heading that wraps & Another long heading & Third heading \\\hline
A large amount of text in a cell & More verbose text & Additional information \\\hline
\end{tabular}
\end{table}
""" + "\n")
    parts.append(r"""\begin{itemize}[leftmargin=1pt,itemsep=18pt,topsep=16pt]
\item A list with far too much vertical spacing between the items.
\item A second item, followed by a nested list:
\begin{enumerate}[itemsep=12pt]\item nested one\item nested two\end{enumerate}
\end{itemize}
""" + "\n")
    parts.append(r"""\begin{multicols}{2}
This mid-document two-column region has no reason to exist. The columns are
narrow, hyphenation explodes and the page rhythm is broken.
\subsection{A Small Subsection} Short text.
\end{multicols}
""" + "\n")
    parts.append(r"""An extreme closing remark: \hfill \vfill
""" + "\n")
    parts.append(r"""A footnote is abused here\footnote{This footnote is just as long as the
paragraph it annotates, which is not how footnotes work.}\footnote{A second
footnote on the very same line.} and the sentence keeps going for a while so
that the page has to stretch.
""" + "\n")
    parts.append(r"""A rotate box is used for no reason: \rotatebox{90}{rotated text}.
""" + "\n")
    parts.append(r"""\clearpage
""" + "\n")
    parts.append(_sec("Experiments", 5, 2))
    parts.append(r"""A duplicate label lives here \label{sec:dup} and the same label was
already used earlier in the document.
""" + "\n")
    parts.append(r"""\pagebreak
""" + "\n")
    parts.append(_sec("Conclusion", 2, 6))
    parts.append(r"""
\section*{Appendix}
Text in the appendix.
\end{document}
""")
    return "".join(parts)


# ---------------------------------------------------------------- aidtest
AID_TEXT = r"""\documentclass[10pt,a4paper]{article}
\usepackage[margin=25.4mm]{geometry}
\usepackage{graphicx,float,booktabs}
\title{Structure and Meta-Information Cleanup}
\author{Sh Lab}
\date{}
\begin{document}
\maketitle

START READING HERE

\section{Introduction}
The manuscript that follows was assembled by an editor who left several pieces
of scaffolding in the file. The reader of the final paper should never see them.

WARNING: the numbers in Table 1 were regenerated after the deadline and have not
been re-checked by the second author.

\begin{table}[tbp]\centering
\caption{A placeholder table kept for review.}
\begin{tabular}{ll}\toprule Key & Value \\\midrule alpha & 1 \\ beta & 2 \\\bottomrule
\end{tabular}
\end{table}

CAUTION: this figure must be replaced before submission, the current version is
only a draft rendering.

\begin{figure}[tbp]\centering
\includegraphics[width=160mm]{example-image}
\caption{A draft figure that is wider than the text block.}
\end{figure}
"""


def build_aidtest():
    """aidtest.tex：阅读辅助 + 2 处告示块 + 超宽图（v2 元信息/结构能力靶子）。"""
    parts = [AID_TEXT]
    parts.append(PARAS[0] + "\n\n" + PARAS[1] + "\n\n" + PARAS[2] + "\n\n")
    parts.append("\\newpage\n")
    parts.append(_sec("Method", 5, 3))
    parts.append(PARAS[5] + "\n\n" + PARAS[6] + "\n\n")
    parts.append(_sec("Results", 5, 2))
    parts.append(r"""
\section{Conclusion}
Once the scaffolding is gone and the figure is renormalised, the document is a
plain article again.
""" + "\\end{document}\n")
    return "".join(parts)


def build_fig_violation():
    """fig_violation.tex：图形保真反例 —— 与 aidtest.tex 相比，
    把那张图**重绘**成 TikZ（内容被改动，必须被 L 判违规）。
    """
    src = build_aidtest()
    tikz = r"""\begin{tikzpicture}
\draw[fill=gray!20] (0,0) rectangle (12,4);
\draw[thick] (0.5,0.5) -- (11.5,3.5);
\node at (6,2) {redrawn draft figure};
\end{tikzpicture}"""
    old = ("\\begin{figure}[tbp]\\centering\n"
           "\\includegraphics[width=160mm]{example-image}\n"
           "\\caption{A draft figure that is wider than the text block.}\n"
           "\\end{figure}")
    assert old in src, "aidtest 图形块与预期不一致"
    new = ("\\begin{figure}[tbp]\\centering\n" + tikz +
           "\n\\caption{A draft figure that is wider than the text block.}\n"
           "\\end{figure}")
    src = src.replace(old, new)
    # tikz 需要宏包
    src = src.replace("\\usepackage{graphicx,float,booktabs}",
                      "\\usepackage{graphicx,float,booktabs}\n\\usepackage{tikz}")
    return src


def build_propose_target():
    """propose_target.tex：模型在环靶稿。

    40mm 边距 -> 版心 130mm；图宽 140mm 超过版心但**低于** 150mm 超宽阈值，
    所以规则闭环不动它（只报 overfull），是给模型在环留的活口。
    """
    parts = [r"""\documentclass[10pt,a4paper]{article}
\usepackage[margin=40mm]{geometry}
\usepackage{graphicx,float,amsmath}
\title{A Target for Model-in-the-Loop Proposals}
\author{Sh Lab}
\date{}
\begin{document}
\maketitle
\section{Introduction}
"""]
    parts.append(PARAS[0] + "\n\n" + PARAS[1] + "\n\n" + PARAS[2] + "\n\n")
    parts.append(r"""\begin{figure}[tbp]\centering
\includegraphics[width=140mm]{example-image}
\caption{A figure that is slightly wider than the 130mm text block.}
\end{figure}
""" + "\n")
    parts.append(_sec("Method", 5, 3))
    parts.append(r"""
\section{Conclusion}
The closed loop reports the overfull figure and leaves the decision to the model
in the loop, which may resize it by a bounded amount.
""" + "\\end{document}\n")
    return "".join(parts)


FIXTURES = {
    "demo.tex": build_demo,
    "issues.tex": build_issues,
    "chaos.tex": build_chaos,
    "nightmare.tex": build_nightmare,
    "aidtest.tex": build_aidtest,
    "fig_violation.tex": build_fig_violation,
    "propose_target.tex": build_propose_target,
}


def main():
    for name, fn in FIXTURES.items():
        path = os.path.join(HERE, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(fn())
        print("wrote", path)


if __name__ == "__main__":
    main()
