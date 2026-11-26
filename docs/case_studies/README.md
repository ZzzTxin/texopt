# 真实稿件排版案例：论文附录材料

本目录包含四个真实作者稿件的案例、实际 PDF 页面比较图，以及可审计的运行证据。补充 PiFold 全文复核后的中文附录已编译为 **6 页**，正文解释、章节标题、图注、表头和比较图标签均为中文。主稿文件路径尚未提供，因此先以独立、可 `\input` 的形式交付。

- [最新中文附录预览（6 页）](preview_full_review.pdf)
- [中文 LaTeX 正文](appendix_case_studies.tex)
- [中文案例说明](案例说明.md)
- [机器可读结果](case_summary.json)
- [自动生成的结果表](case_metrics_table.tex)

## 两次排版生成的完整 PDF

PiFold 的两次实际输出已分别导出，可打开两个窗口逐页对照：

- [第一次排版完整稿：规则闭环后（14 页）](comparisons/pifold_round1_full.pdf)
- [第二次排版完整稿：视觉提案后（14 页）](comparisons/pifold_round2_full.pdf)
- **[继续全文复核后的完整稿（14 页，仍需复核）](comparisons/pifold_full_review.pdf)**

前两份作为历史输出保留，不覆盖。逐页核对已确认：旧第二次输出只改变了首页，第 2—14 页文字与位置完全相同。2026-11-25 继续审阅全文并执行三轮提案后，新增接受 4 项调整，M2 从 1.574 降为 1.308；第 7—9 页直接重排，第 10—13 页受到正文流动影响。但第 9 页标题重叠和第 14 页附录表格顺序仍未修复，案例按 `NEEDS_REVIEW` 报告，程序自身的 `DONE` 状态另存证据。

三份均为实际编译生成的完整论文 PDF，已核对页数与哈希。完整结论见 [PiFold 全文复核记录](PiFold全文复核.md)，版本核对信息见 [完整 PDF 版本记录](comparisons/full_pdf_versions.json)。

## 案例与实测结果

| 真实稿件 | 主要展示内容 | 页数 | 日志变化 | 实际结论 |
|---|---|---|---|---|
| OpenSTL，arXiv:2306.11249v2 | 误删必要结构留白与分页的失败案例 | 37 → 36（失败尝试） | vbox 2 → 0，float warning 3 → 1 | 虽评分下降，但附录分隔和图文邻接退化；不采用，保留原稿 |
| SimVP，arXiv:2206.05099v1 | 图表浮动参数规范化与重排 | 12 → 12 | float warning 8 → 1 | M1 下降；一处 overfull 未解决，M2 略升 |
| PiFold，arXiv:2209.12643v4 | 首页修正之后继续全文复核，记录动作与评分缺口 | 14 → 14 | float warning 1 → 0 | 初次只改首页；后续新增 4 项调整，M2 由旧第二版 1.574 降为 1.308。仍有标题重叠等问题，案例结论为需复核 |
| Omniview-Tuning，arXiv:2404.12139v1 | 回滚、部分改善和残余问题报告 | 24 → 24 | vbox 3 → 0 | 第 15 页 60.5% 的空白仍在，终态 `NEEDS_REVIEW` |

原稿均来自未注入排版缺陷的作者工程。另筛选了一份本地激光论文稿，因缺少原始 `introduction_figure.pdf`、基线无法编译而排除。四个案例是定性展示，不作为整体测试集成功率或平均收益的证据。

**OpenSTL 复核更正：此前把“空白变少、页数下降”称为成功不成立。** 原稿参考文献与附录另起页的留白、图表冲刷边界应保留。处理后Moving MNIST说明与图5由同在17页变为16页与21页，阅读关系变差。现撤回成功结论，不采用该处理稿；详见[结构留白核验](../../真实稿件排版案例集/01_OpenSTL/运行证据/结构留白复核_不采用.json)。

## 放进文章

把本目录复制到文章工程根目录并命名为 `case_studies/`。使用 XeLaTeX 编译，主稿需具备中文排版支持（例如使用 `ctexart` 文档类，或加载 `ctex` 宏包），并加载 `graphicx`、`booktabs`、`hyperref`。正文结尾使用：

```tex
\appendix
\input{case_studies/appendix_case_studies.tex}
```

若主稿已经有 `\appendix`，只加入 `\input` 即可。附录源文件本身不再次发出 `\appendix`，也不重设文档类、版心和字号。

如果直接从当前仓库根目录引用，使用：

```tex
\appendix
\newcommand{\texoptCaseAssetPath}{docs/case_studies/figures/}
\input{docs/case_studies/appendix_case_studies.tex}
```

比较图提供矢量 PDF，`PNG` 为浏览副本。图中原稿内容来自真实编译 PDF 的页面导入；新增内容仅为中文页外面板标签，没有重绘论文图表。原始论文页面中的英文保留原样。附录使用 `figure*` 和 `table*`，可用于双栏文章的通栏展示。`preview_full_review.tex` 的分页控制仅服务于独立预览，使用 `ctexart` 提供中文排版支持。旧的 `preview.pdf` 保留为先前五页版本；当前正文和结果表以最新六页预览为准。

## 实验口径

- 使用 TeX Live 2024。每个案例的前后版本使用同一个编译器：OpenSTL 为 XeLaTeX，其余三个为 pdfLaTeX。后者的作者源码或宏包依赖 pdfTeX primitive；选择编译器由案例脚本适配，生产优化器模块没有改动。
- 使用 `Optimizer.run()` 执行实际确定性闭环。没有页数目标，没有授权压缩全局字号/页边距；关闭元信息删除与影子评分，开启 `content_hard`、图表指纹校验和页面视觉量化。
- PiFold 另外执行一轮实际模型在环：生成请求包、提出 `set_float_spec(target=1, spec=!b)`，通过白名单校验、整篇编译和相同验收函数决定接受。
- 2026-11-25 PiFold 继续完整审阅 14 页，执行三轮全文提案：4 项接受、4 项回滚、1 项因动作无效果跳过。第 9 页标题重叠未被当前评分检测，案例结论采用模型视觉复核的 `NEEDS_REVIEW`，不以程序的 `DONE` 替代。
- 独立核对归一化正文、显示公式内容、其他源码与图文件的字节哈希，以及原始工程哈希。`.synctex`、`.brf` 等再生成的编译文件不算源码变化；排除名单写在各案例证据里。
- 最终重编译检查连续两次测量一致，再同步最终评分、状态和报告。`M1=15P+I` 为主判据，`M2=A_soft` 仅在 M1 持平时打破平局；不能把 `DONE` 解读为所有视觉指标都改善。

## 证据与复现

`evidence/<case>.json` 含输入来源与版本、配置、前后日志计数、页面测量、接受/回滚轨迹、完整性检查与稳定性检查；`evidence/<case>.patch` 是最终源码差异。PiFold 证据还包含模型提案及其实际验收结果。`figures/manifest.json` 登记比较图哈希。

完整工作副本、PDF、编译日志、原始请求包及中间状态保存在本地 `workbench/case_studies/runs/<case>/`。这些大文件不包含在本目录中。

已有本地原始语料与 Windows TeX Live 的 WSL 环境，可从仓库根目录复现：

```bash
python3 -B docs/case_studies/run_cases.py experiment pifold simvp omniview laser openstl
python3 -B docs/case_studies/refine_pifold.py
python3 -B docs/case_studies/stabilize_cases.py openstl pifold simvp omniview
python3 -B docs/case_studies/render_cases.py pair openstl 14 14 docs/case_studies/figures/openstl_page14.png
python3 -B docs/case_studies/render_cases.py pair simvp 7 7 docs/case_studies/figures/simvp_page7.png
python3 -B docs/case_studies/render_cases.py triple pifold 1 docs/case_studies/figures/pifold_visual_loop.png
python3 -B docs/case_studies/render_cases.py pair omniview 15 15 docs/case_studies/figures/omniview_page15.png
python3 -B docs/case_studies/build_evidence.py
```

PiFold 后续全文复核的入口为 `review_pifold.py`（prepare / round / finalize），三轮结构化提案已保存在 `evidence/pifold_full_review.json` 中；`publish_pifold_review.py` 导出新完整稿和逐页对照记录。原始两次输出保持不变，新增候选及请求包保存在 `workbench/case_studies/pifold_full_review/`。

脚本对已存在的优化目录会跳过，PiFold 提案脚本也拒绝覆盖已有的提案实验。重新开展一整轮实验应使用新的工作区副本，保留已交付的证据。渲染脚本需要 PyMuPDF 和 Pillow；优化核心的本轮运行未启用 pdfminer 影子评估。

独立预览在本目录运行 XeLaTeX 两遍：

```bash
xelatex -interaction=nonstopmode -halt-on-error preview_full_review.tex
xelatex -interaction=nonstopmode -halt-on-error preview_full_review.tex
```

