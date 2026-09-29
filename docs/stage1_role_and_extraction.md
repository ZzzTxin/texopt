# 阶段 1 交付：页面角色标注 + 页面级指标提取

> 对应《学术论文排版审美量化模型设计方案（修订版 v2）》第十五章「阶段 1」与
> `docs/stage0_visual_inventory.md` 第 6 节的阶段 1 清单。
> 代码：`texopt/roles.py`、`texopt/extract.py`、`datasets/conf-specs/tools/extract_metrics.py`
> 测试：`tests/run_tests.py::stage1_tests()`（18 项）

## 1. 交付物

| 文件 | 作用 |
|---|---|
| `texopt/roles.py` | 页面角色标注器（规则 + 置信度 + 可解释理由 + 正交 flags） |
| `texopt/extract.py` | PDF → `page_metrics.v1` 的页面级提取器（矢量/文本层为主，像素层可选） |
| `datasets/conf-specs/tools/extract_metrics.py` | 全库批量提取 + 缓存 + 索引（可续跑、单篇隔离） |
| `datasets/conf-specs/metrics/pages/*.json` | 每篇论文的 `page_metrics.v1` |
| `datasets/conf-specs/metrics/index.json` | 逐篇状态/页数/角色分布/耗时索引 |

## 2. 关键口径（精确定义，方案第六章的落地）

**`A_usable`（版心）**：由**正文页的正文尺寸行**测出 —— 左右取行首/行尾众数；
上下取正文尺寸行的中位位置（排除页眉/页码/脚注这类小字号行）。
双栏时 `A_usable = 左栏面积 + 右栏面积`（**栏间距不计入**）。
所有覆盖率/留白率的分母一律用它；面积用 **4pt 网格掩码**累计（同一格不重复计入，
且掩码本身就把栏间距挖掉），因此**覆盖率天然 ≤ 100%**。

**页内正文尺寸**：按页算（字符数加权众数），不用文档级字号。原因：参考文献/附录页
常用更小字号，若用文档级字号过滤，这些页只剩标题行 → `chars_per_line=10`、
行距/对齐全成假值（阶段 1 实测踩到）。

**浮动区**：用**题注锚定**（`Figure N:` / `Table N:`）—— 从题注出发只在**图形元素**
上做连续链扩张（正文行不参与，否则会吃穿整页），再限制在题注所在栏内。
不解析表格结构，只量"这块区域多大"。

**面积份额类指标**（`balance.d_top/mid/bot`、`left_right`、`visual_centroid_y`）：
按**内容面积份额**归一，和恒为 1，与 `A_usable` 的绝对值无关。

## 3. 角色标注规则（方案第五章 5.1）

优先级（先命中者胜）：

```
title > references > appendix > figure-page > table-page > math-heavy
      > section-head > last-page > body > unknown
```

| 角色 | 判据 | 置信度 |
|---|---|---|
| `title` | 第 1 页 | 0.95 |
| `references` | 出现 References/Bibliography 标题，**其后各页延续**（跨页状态机） | 0.85 |
| `appendix` | 出现 Appendix/Supplementary 标题（要求后面是大写/数字/冒号，避免误吃正文句），其后延续 | 0.85 |
| `figure-page` | 浮动覆盖 ≥ 50% 版心 **且** 正文覆盖 < 25% | 0.75 |
| `table-page` | 表格覆盖 ≥ 40% 版心 | 0.70 |
| `math-heavy` | 数学字形（CMMI/CMSY/CMEX/…）占比 ≥ 35% | 0.60 |
| `section-head` | 章节标题位于版心**顶部 30%** 内（标题判据：短、无句末标点、字号≥正文+0.4 或加粗、且形如 `1.2 xxx` / `Introduction` 等） | 0.60 |
| `last-page` | 文档最后一页且无更强结构信号 | 0.50 |
| `body` | 默认 | 0.50 |
| `unknown` | 无可抽取文本（扫描页/整页图/空白页） | 0.90 |

正交信息放在 `role_flags`（`last-page` / `section-start` / `float-dominated`），
不把互相独立的属性压成一个枚举。

每页都带 `role_reason`（人可读）与 `role_confidence`，便于**人工抽检**与误差上报。

## 4. 提取覆盖矩阵（阶段 1 后）

| 指标组 | 阶段 0 | 阶段 1 | 说明 |
|---|---|---|---|
| `units` | placeholder | **extracted** | 版心几何（mm 计）+ 栏数 |
| `density.coverage_text/figure/table` | placeholder | **extracted** | 网格掩码，分母 `A_usable` |
| `density.ink_ratio_text` | placeholder | placeholder | 需像素遮罩（阶段 2） |
| `ratio.fig_text / figtab_text` | placeholder | **extracted** | — |
| `balance`（三段密度/左右/重心/分栏） | placeholder | **extracted** | 双栏按栏独立算 |
| `whitespace.total_ratio` | placeholder | **extracted** | 1 − 覆盖率 |
| `whitespace`（五类分类 + regions） | placeholder | placeholder | 阶段 3 |
| `alignment`（左右/中心方差） | placeholder | **extracted** | **按栏**计算后取中位 |
| `consistency.figure_width_cv` | partial | **extracted** | 页级 + 文档级 |
| `readability`（行长/行距比/字号/段行数） | partial | **extracted** | 行距 = 同行边相邻差 / 字号 |
| `microtype`（overfull 等） | partial | **unavailable**（语料） | 语料 PDF 无编译日志，不假装有 |
| `figure_quality`（有效 dpi/拉伸） | placeholder | **extracted** | 由 `LTImage.srcsize` ÷ 显示尺寸 |
| `role` | placeholder | **extracted** | 本阶段核心 |
| 浮动体→首次引用距离 | placeholder | placeholder | 需源码 `\ref`，阶段 3 |

## 5. 实测

### 5.1 两个典型靶子（抽查）

| 论文 | 页/栏 | 角色分布 | 关键量 |
|---|---|---|---|
| CVPR 2025（双栏） | 11p / 2col | title 1 / body 7 / references 3 | body=10pt，`cpl`≈39–46，行距比 1.196，参考页 9pt（行距比 1.096）|
| ACL 2025（双栏，**整页 Form 包装**） | 22p / 2col | title 1 / body 8 / references 6 / appendix 7 | body=11pt，`cpl`≈40，行距比 1.232，覆盖率 ≤ 0.97 |

### 5.2 全库（608 篇 / 10538 页）

```
完成：ok=608  failed=0  missing=0  共 608 篇，用时 2661s（44.3 分钟）
单篇耗时：中位 2.7s
总页数 10538｜平均 17.3 页/篇｜中位 16｜范围 1–77
布局：双栏 525 篇 / 单栏 83 篇
```

| 会议 | 篇 | 总页 | 平均页 | | 会议 | 篇 | 总页 | 平均页 |
|---|---|---|---|---|---|---|---|---|
| aaai | 36 | 321 | 8.9 | | ijcai | 66 | 577 | 8.7 |
| acl | 67 | 1351 | 20.2 | | kdd | 6 | 80 | 13.3 |
| cvpr | 68 | 727 | 10.7 | | neurips | 37 | 1340 | 36.2 |
| eccv | 36 | 635 | 17.6 | | nsdi | 45 | 895 | 19.9 |
| emnlp | 66 | 1334 | 20.2 | | osdi | 24 | 470 | 19.6 |
| iccv | 68 | 747 | 11.0 | | siggraph | 7 | 81 | 11.6 |
| iclr | 6 | 151 | 25.2 | | sosp | 7 | 165 | 23.6 |
| icml | 62 | 1559 | 25.1 | | www | 7 | 105 | 15.0 |

**角色分布（10538 页）**：`body` 3423（32.5%）· `appendix` 2875（27.3%）·
`references` 2639（25.0%）· `section-head` 976（9.3%）· `title` 604（5.7%）·
`table-page` 16 · `figure-page` 3 · `last-page` 2。

> 附录/参考文献合计占一半以上，是 arXiv 预印本常态（正文 8–10 页 + 巨大附录）。
> 这正是必须**分层统计**的理由：拿附录页去和正文页比密度毫无意义。

**关键指标分位（阶段 2 校准的原始依据）**：

| 指标 | P10 | P25 | P50 | P75 | P90 | P99 | max |
|---|---|---|---|---|---|---|---|
| `coverage_text` | 0.289 | 0.515 | 0.715 | 0.831 | 0.893 | 0.964 | 1.000 |
| `coverage_figure` | 0.000 | 0.000 | 0.000 | 0.113 | 0.250 | 0.544 | 1.000 |
| `coverage_table` | 0.000 | 0.000 | 0.000 | 0.000 | 0.012 | 0.164 | 1.000 |
| `whitespace.total_ratio` | 0.055 | 0.118 | 0.206 | 0.391 | 0.616 | 0.980 | 1.000 |
| `chars_per_line_mean` | 20.9 | 36.4 | 41.5 | 48.4 | 61.4 | 83.0 | 129.8 |
| `leading_ratio` | 0.996 | 1.096 | 1.196 | 1.196 | 1.232 | 1.801 | 2.680 |
| `alignment.left_var` | 0.91 | 3.93 | 14.77 | 34.47 | 59.84 | 115.2 | 158.0 |
| `min_effective_dpi` | 175 | 283 | 439 | 728 | 1183 | 4162 | 21091 |

从上面已经能读出三条校准结论（阶段 2 据此改阈值）：

- **`figure-page` 阈值 0.50 定得过高** —— 浮动覆盖的 P99 才 0.544，所以全库只判出 **3 页**。
  建议改到 P95 附近（约 0.32~0.35），或改用「浮动覆盖 / 正文覆盖」的比值判据。
- **`table-page` 阈值 0.40 也过高** —— 表格覆盖 P99 只有 0.164，全库只判出 **16 页**。同理下调。
- **`alignment.left_var` 中位 14.8pt 偏大** —— 因为参考文献的悬挂缩进、题注居中、公式行
  都被算进了行首方差。阶段 2 要按行类型细分（只统计「两端对齐的满行」）。
- `leading_ratio` 中位 1.196（≈单倍行距），符合预期 —— 说明口径修正后行距量是可信的。
- `chars_per_line` 中位 41.5 字符/行，与双栏版面一致（单栏约 60–90）。

> 数据修正说明：全量跑完后复核发现 5 个覆盖率值 >1.0（最大 1.0116，占 31614 个值的
> 0.016%），成因是网格**末格越界量化**；提取器已修正（格心越界不计），那 5 个值已
> 截到 1.0 并存进各文件的 `meta.notes`，无需重跑全库。

## 6. 阶段 1 修掉的 5 个真 bug（都是实测暴露的）

1. **整页 Form 包装导致正文全丢**（最严重）：ACL Anthology 这类 PDF 把整页内容包进一个
   Form XObject，pdfminer 给出"面积=100% 页面"的 `LTFigure`。早期实现把它当插图 →
   页内正文行全被标成 `fig=True` 而丢弃，**只抽得到页眉页码**（抽不到 References，
   角色全错）。修法：`≥75% 页面面积` 的 Figure 视为**版面容器**，其内文本按正文处理；
   并加 **Form 内字符重建行**回退（`group_chars()`，与 `tools/measure_pdf.py` 同法）。
2. **整页 Form 参与浮动链式扩张** → 浮动区吃满整页，覆盖率出现 **104%**。
   修法：`_graphic_ok()` 过滤"面积 ≥ 75% 页面"的图形元素 + 过滤细线条（章节分隔线/
   表格横线，h≈0.5pt）。
3. **覆盖率分母与掩码口径不一致**（2 栏时掩码含栏间距、分母不含）→ 覆盖率可 >100%。
   修法：掩码挖掉栏间距（`GridMask(exclude_x=...)`），与 `A_usable` 同口径。
4. **行距比算错**：用"上一行下边 − 下一行上边"得到的是**行间空隙**而非基线间距，
   10pt 正文算出 0.199。修法：改用**同行边的相邻差**。
5. **对齐方差跨栏混算**：左栏 x≈58pt、右栏 x≈317pt，混算 std ≈ 130pt（无意义）。
   修法：按栏计算（相对各栏左/右沿）后取中位。另：**页级字号过滤**导致参考文献页
   `cpl=10`、行距 None 等假值，改为页内自适应字号。

## 7. 已知局限与阶段 2 校准清单

| # | 现象 | 处理 |
|---|---|---|
| L1 | `figure-page`/`table-page` 阈值（0.5/0.4）实测几乎不触发（全库仅 3 / 16 页） | **已有证据**（见 5.2 分位表）：浮动覆盖 P99=0.544、表格覆盖 P99=0.164；阶段 2 改到 P95 附近 |
| L2 | 题目/附录判定依赖文本标题；少数论文（无 Appendix 字样）会把附录并入 `references`（全库 appendix 27%+references 25% 偏高，含此成分） | 阶段 2 抽检 20 篇，必要时补"参考文献行占比"作为第二判据 |
| L3 | 表格覆盖是"题注锚定区域面积"，不等于表格结构 | 在报告里标注为近似；阶段 3 再接表格结构识别 |
| L4 | 纯图像/整页 Form PDF：**已解决** —— 原先失败的 siggraph 样本现在也能正常抽取（13 页） | 已由 Form 包装 + 字符重建行修复 |
| L6 | `alignment.left_var` 把悬挂缩进/题注/公式行混在一起算 | 阶段 2 按行类型细分 |
| L5 | 页眉/页脚行未单独识别（只按字号排除） | 阶段 3 与留白分类一起做 |

## 8. 复现命令

```bash
cd datasets/conf-specs
python3 tools/extract_metrics.py                 # 全库（可续跑，已存在则跳过）
python3 tools/extract_metrics.py --limit 20       # 前 20 篇
python3 tools/extract_metrics.py --venues cvpr,acl
python3 tools/extract_metrics.py --force --limit 5
cd ../.. && python3 tests/run_tests.py            # 含 18 项阶段 1 回归
```
