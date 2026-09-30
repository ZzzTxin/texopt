# texopt —— 论文整体排版优化 Agent

基于 **L + A 双数学量化**的 LaTeX 论文排版优化 Agent（SRTP 项目主线版）。

> 主线定位（2026-09-09）：对论文做**整体排版优化**——满足目标期刊/会议的
> 排版要求 + 排版质量全局最优。**Page Limit 只是要求规格里的一个可选字段**，
> 不是系统主体；纯排版手段穷尽后才允许语义抛光（LLM 保意精简，后续阶段）。
>
> 术语诚实性（重要）：`A` 是**排版质量/审美代理**，非人类审美评分；内容校验是
> **严格的归一化文本内容保持检查**，不声称“证明语义等价”；系统**不声称全局最优**，
> 只保证“全局评分单调不劣化 + 有界收敛”。

输入一篇 `.tex` 与一份「要求规格」（期刊模板 / 自定义 / 页数限制等），Agent
在「感知 → 决策 → 执行 → 验证」闭环里自动排版，正文内容一字不改，输出
优化稿 + 可审计报告（每步全局评分轨迹）。

## 设计原则：规则 / 算法 / 模型 / 编译器，职责分离

> **“规则负责底线，算法负责搜索，模型负责复杂判断，编译器负责现实验证。”**

系统按三个层次处理排版问题，**不是把所有问题都交给 LLM**：

| 层次 | 问题类型 | 决策者 | 例子 |
|---|---|---|---|
| **Level 1** | 硬性约束 / 明确规则 | 确定性程序（规则） | 字号、页边距、页数、fleqn、能否编译、图表结构完整、正文是否被改 |
| **Level 2** | 可检测+可量化的质量 | 程序感知 + 评分 + 候选搜索 | overfull/underfull、vbox（孤行寡行代理）、浮动体警告、超宽图/表、不稳定 float spec、总分变化 |
| **Level 3** | 复杂整体布局 / 审美判断 | LLM（模型在环） | 留白是否过大、视觉重心、图该浮到哪/多大、图文关系、整体节奏 |

- **Level 1**：程序直接解决（如“发现 12pt、要求 10pt → 直接改 → 重编译 → 复查”），**不调用 LLM**。
- **Level 2**：沿用本项目的 `Perceive → Score → Candidate Actions → Compile → Verify → Accept/Reject/Rollback` 机制。
- **Level 3**：LLM 提出**结构化候选修改（白名单动作）**，程序执行-编译-重评，变好保留、变差回滚，再把新状态交回 LLM —— 这才是 Model-in-the-loop。

### Model-in-the-loop 的正确含义

> 不是“让 LLM 一次性改论文”，而是让 LLM **真正进入优化循环**：

```
论文状态 → 程序感知 → LLM 判断 → LLM 提出候选修改（白名单动作）
   → 程序执行 → XeLaTeX 编译 → 重新感知 PDF/log/source → 计算全局分
   → 变好保留 / 变差回滚 → 新状态再交给 LLM → 下一轮
```

LLM **只提出方案，不直接改文件、不跑 shell**：提案必须命中白名单动作，
否则 BLOCKED；执行结果一律过编译验证。详见下文「模型在环（Model-in-the-loop）」。

## 快速开始

```bash
# 0) 纯质量模式：不改内容地消掉常见排版问题（演示稿埋了 4 类问题）
python3 optimize.py examples/issues.tex

# 0b) 混乱论文试验（chaos.tex 埋了 12 类问题：裸 $$/手动分页/硬换行/下划线…）
python3 optimize.py examples/chaos.tex

# 1) 页数限制（Page Limit 只是要求之一；demo 自然 6 页，目标 5）
#    默认版心保护：不靠调边距/字号硬压，超页会诚实 EXHAUSTED 并给建议；
#    确需授权全局版心调整时加 --tune-geometry
python3 optimize.py examples/demo.tex --target 5 --tune-geometry
python3 optimize.py examples/demo.tex --target 5   # 对比：不授权版心 -> EXHAUSTED

# 2) 期刊模板：字号等硬性要求自动对齐
python3 optimize.py examples/demo.tex --template ieee

# 3) 自定义详细要求文件（可叠加模板）
python3 optimize.py my_paper.tex --template acm --require my-reqs.json

# 4) 你的论文（原文件只读，结果输出到 <论文目录>/workbench/）
python3 optimize.py D:/path/to/paper.tex --template springer-llncs

# 5) 全部配置走 settings.json
python3 optimize.py paper.tex --settings settings.json

# 6) 结构/版面规范（v2 新增）：目录页 + 页眉 + 彩色标题
python3 optimize.py paper.tex --toc --header --heading-color 0,62,120
python3 optimize.py paper.tex --template report        # 目录+页眉+彩色标题一键

# 7) 元信息清理（默认为开）：阅读辅助内容 / WARNING 告示块
python3 optimize.py paper.tex --no-strip-aids          # 保留阅读辅助内容
python3 optimize.py paper.tex --no-warning-boxes       # 保留 WARNING 告示

# 8) 图形保真：从原 PDF 裁切原图原样嵌入（不重绘、不改坐标轴）
python3 optimize.py --extract-fig orig.pdf --page 3 \
    --box 308,112,432,258 --out figs/fig1.png --dpi 400

# 查看可用模板
python3 optimize.py --list-templates
```

运行结束查看：
- `workbench/paper.tex` —— 优化后的论文（连同 `paper.pdf`）
- `workbench/report.md` —— 人读报告：L 状态 / A·I 评分轨迹 / 残余问题清单
- `workbench/state.json` —— 机读状态：供上层 Agent / 后续流程消费

## 核心：两个数学量化（整篇文档级别，全局重编译后计算）

```
total = L_fail × 1e6 + A + I        （lexicographic：先保底，后求美）
```

| 分量 | 含义 | 内容 |
|---|---|---|
| **L** 基础逻辑量化 | 硬约束，不满足 = 不可接受 | 能否编译 / 能否渲染 PDF / 内容完整保留（机器 diff 校验）/ 页数限制 / 硬性规范（要求指定的字号、页边距、公式居中） |

> 内容完整保留的口径（2026-09-11 明确）：正文区域**归一化后**逐字符比较，
> 正文文字/词序/标点/公式/引用/图表内容一律严格；属「排版面」的 token
> （手动分页、过大 `\vspace`、行内字号、断词点 `\-`、列表间距选项、表格
> 环境名/列格式、浮动体位置参数、插图宽度）可被确定性动作删/改，不判违规。
| **A** 排版质量/审美代理 | 越低越好 | ① LaTeX 层：overfull/underfull、vbox（孤行寡行代理）、浮动体警告、超宽图/表、其余编译 Warning；② 源码卫生/版面层（手动分页 1.0、标题字号 0.8、过大 vspace/列表间距/长词/图片过大 0.6、行内字号 0.5、页眉/段距/中途双栏…）；③ **页面视觉层（量自实际 PDF）**：巨大内容块、底部大面积空白、页面中部空洞、孤立内容、几乎空白页、页间密度失衡。**注意：A 是可复现的版面缺陷量，不是人类审美评分** |
| **I** 干预代价 | 越低越好（最小干预） | 页边距偏离原稿 mm、字号降档、被改的浮动体参数/图片宽度处数 |

**全局性（局部最优 ≠ 全局最优）**：每个候选修复都要先**整篇重编译、全局
重评分**，验收判据是全局目标改善——修了第 3 页孤行却弄坏第 7 页浮动体的
改动会被判负回滚；达标后评分会自动把参数拉回「最宽松且最优」的临界点。

## 要求对接接口（期刊/会议/自定义）

要求来源按优先级合并：**模板预设 < `--require` 要求文件 < settings.json < CLI 参数**。

- 内置模板：`ieee` / `acm` / `springer-llncs` / `custom`（`templates/` 可扩展外置）
- 每个模板 = 一组结构化 Requirement 字段（见 `templates/README.md`）：
  字号档、页数上限、页边距、浮动体参数规范、超宽图阈值、质量开关等
- 自定义要求文件给出任意详细规则，Agent 按要求执行

字段全部可选，缺省 = 不约束/不干预（尊重原稿）。

## 会议模板（`--conference`，2026-09-12 新增）

```bash
python3 optimize.py paper.tex --conference aaai   # 按 AAAI 排版要求优化
python3 optimize.py paper.tex --conference icml   # 按 ICML 排版要求优化
python3 optimize.py --list-conferences            # 列出 16 个会议模板
```

模板来自 `datasets/conf-specs/templates-v2/<id>.json`（16 个会议：NeurIPS/ICML/ICLR/ACL/
EMNLP/CVPR/ICCV/ECCV/AAAI/IJCAI/SIGGRAPH/KDD/WWW/OSDI/SOSP/NSDI），由「官方规范 +
真实论文实测」数据集生成。加载与投影在 `texopt/conference.py`，**不为任何会议写单独代码**。

| 模板内容 | 进入优化过程的方式 |
|---|---|
| `hard_constraints`（official / template-implied / inferred） | 转为 **L 硬约束**：页数上限、字号、边距下限、公式居中 → 用于判「是否违规」 |
| 页数上限 | 默认按**正文页口径**：`texopt/engine.py` 用 pdftotext 定位参考文献首页 k，只有下界 k−1 超限才判违规（避免把恰好写到参考文献首页的合法论文误判） |
| `geometry.margin_floor_mm` | 作**下限**使用：低于才判违规，高于不干预（不会把合法的宽/不对称边距改小） |
| `float_policy.float_spec` / `overwide_fig_threshold_mm` | 浮动体参数目标档（`tbp`）与超宽图归一阈值 |
| `density_targets` / `*_observed` / `position_prior`（sample-stat） | **只做「排版是否合理」的参考核对**（`conference.reasonableness`，写进报告与 state.json），不进 L、不参与 A 打分 |
| 无对应字段/动作的项（栏数、纸张、字体族、匿名、checklist…） | **逐条记录**，不强行接入：见 `datasets/conf-specs/summary/texopt-integration-report.md` |

优先级：**会议模板 < `--require` < settings.json < CLI 参数**（CLI 如 `--target` 可覆盖模板页数）。
不指定 `--conference` 时 `base=None`，代码路径与行为与以前完全一致。

## 已覆盖的 Basic 排版模块

| 模块 | 处理方式 |
|---|---|
| 1. 页数限制 | **默认不动全局版心**（边距/字号调整会改变版面分布、导致图表与正文错位）——先做版面内质量修复（浮动体/图宽/断行）；仍超页则诚实 EXHAUSTED 并给建议（作者精简/合并图表/语义抛光）。仅当 `--tune-geometry` 显式授权才启用边距/字号压缩（带下限与松弛回拉） |
| 2. 孤行寡行 | 注入 club/widow/displaywidow penalty 等断行质量宏（缓解）；像素级检测属图像视觉层（advanced） |
| 3. 浮动体位置 | 不稳定参数 `[h]`/`[h!]` 规范为要求档 `[tbp]`；浮动体警告计入 A 并列出 |
| 4. 公式居中 / 表格超宽 | fleqn 选项自动移除（公式居中）；超宽表格按源行号定位后改用 tabularx（见模块 9） |
| 5. 字体字号/间距等基础规范 | 字号档对齐要求（documentclass）、页边距对齐要求（geometry） |
| 6. 多期刊/会议要求 | 模板库 + 自定义要求接口，见上 |
| 7. 排版卫生（确定性修复 + 源码层检测） | 有对应动作的自动修：手动分页（删）→手动垂直间距（删过大）→行内字号乱标（删）→标题字号超限（压回上限）→列表间距过大（收紧）→超长不可断词（插 \\- 断词点）；其余（下划线/\\noindent/硬换行/center 包正文/缺题注）仍计入 A 并逐条入报告，需作者意图，不自动改 |
| 8. 结构/版面规范（v2） | 目录页、页眉、标题着色、阅读辅助清理、WARNING 告示清理、图形保真 —— 见下节 |
| 9. 超宽表格 | 检测（overfull 落在 tabular 区间）→ 改用 tabularx（\\linewidth 自适应列宽）；不用 \\resizebox 压缩，不改数据/顺序 |
| 10. 页面平衡 | 删除手动分页/过大 vspace 后交给 LaTeX 全局断页；必要时注入 \\raggedbottom 抑制“为凑满页而拉伸” |

## 页面级视觉量化与版面级修复（Phase 2，2026-09-11）

### 为什么需要

Phase 1 之后，A 仍然主要衡量「LaTeX warning + 源码违规」：`chaotic_layout_test.tex`
能被压到 6 页并报 DONE，但生成的 PDF 里**仍有明显的大面积空白、巨大图片、窄表格、
中途双栏、巨大标题、异常页眉** —— 也就是说**评分没有真正衡量视觉版面质量**，
DONE 也结束得太早。Phase 2 的目标：让优化器**根据实际编译出的 PDF 的版面质量**优化。

### 视觉量化（`texopt/visual.py`，全部量自编译后的 PDF）

每页渲染低分辨率灰度图（默认 50dpi，`visual_dpi` 可调），逐页量取：

| 指标 | 含义 |
|---|---|
| `ink_ratio` | 墨迹占比（页密度） |
| `content_height` / `top_blank` / `bottom_blank` | 内容包围盒高度、顶部/底部空白比例 |
| `max_gap` / `max_gap_at` | 最大连续空白带大小与位置（页中空洞） |
| `band` / `band_at` | 最大「实在内容带」（行墨迹≥50%行宽）——巨大图/表的判据 |
| `left_blank` / `right_blank` | 左右空白（内容宽度） |
| `top_bottom_ratio` | 上/下半页墨迹比（视觉重心偏置） |

由这些量判定**视觉缺陷**（`find_defects`，带 severity，阈值取「明显差」的粗档）：

| 缺陷 | 判据 | 权重（high/moderate） |
|---|---|---|
| `giant_content` | 单一块内容 ≥ 40% 页高（巨大图/表） | 1.5 |
| `stranded_block` | 几乎只有一块内容 + 底部大半空白 | 1.2 |
| `bottom_blank` | 页底空白 ≥ 35%（high）/ ≥ 25%（moderate） | 1.0 / 0.6 |
| `mid_gap` | 页面中部 ≥ 28% 页高连续空洞 | 0.8 |
| `near_empty` | 墨迹 ≤ 2%（几乎空白页） | 0.6 |
| `density_imbalance` | 页间密度相差 ≥ 10 倍或 ≥ 30 个百分点 | 1.0 |

这些缺陷**已并入 A**（`aesthetic_score` = LaTeX 层 + 源码层 + 视觉层），
并写入 `report.md` 的「视觉版面质量」表与 `state.json.visual`。
`workbench/visual.md` 仍输出页面图给视觉模型（Level-3 补充判断）。

### 新增版面级动作（同样走「应用→重编译→重评→接受/回滚」）

| 动作 | 触发 | 做什么 |
|---|---|---|
| `normalize_title` | `title_size` | `\title{\Huge ...}` 压回上限（默认 ≤ `\LARGE`） |
| `normalize_parskip` | `parskip` | 过大的 `\parskip` 收敛（默认 ≤ 8pt；整篇段距） |
| `normalize_header` | `header_abnormal` | 清空过长/无意义页眉内容（保留 fancyhdr） |
| `remove_mid_multicols` | `multicols_mid` | 移除正文中途的局部双栏（内容原样保留） |
| `reduce_oversized_figures` | `fig_oversized` / `subfig_overfull` | 图高超限压到上限；并排子图宽度之和超版心时等比缩小 |
| `fix_table_width`（扩展） | `table_narrow` / `tables_overwide` | `p{2cm}` 这类**明显窄于版心**的表格改 tabularx 自适应列宽 |
| `balance_pages`（扩展） | 视觉缺陷 / vbox | `\raggedbottom` + 浮动体比例调优（`\floatpagefraction` 等），不给“半空浮动页”留机会 |

诚实边界：这些都是**版面层**修改（不改正文/公式/引用/图表内容/图文件），
每条都必须通过整篇重编译后的全局评分（含视觉分）才被接受，变差即回滚。
若某项修正让视觉变差（例如缩图后仍是大块内容却新增底部空白），会被判负并回滚，
如实留在报告中。

### 出口状态（Phase 2 重新定义）

| 状态 | 条件 |
|---|---|
| `DONE` | L 达标 + **无 high 级视觉缺陷** + 应用了 ≥1 个被接受的动作 |
| `CONVERGED` | L 达标 + 无 high 级视觉缺陷 + **没有任何可动候选** |
| `NEEDS_REVIEW` | L 达标但**仍有 high 级视觉缺陷**（或配置了 `done_max_a` 且 A 超限）—— 明确不判 DONE |
| `NO_IMPROVEMENT` | L 达标 + 有候选但全部没改善（已回滚） |
| `EXHAUSTED` / `FAILED` | 仍缺 L（通常超页）/ 基线编译不了 |

另外：连续 `min_stall_rounds`（默认 2）轮无改善才停止，避免“一轮没吃到就收敛”。

## 确定性排版修复动作（2026-09-11 新增：检测必须进入 Act）

修复的问题：感知层早就能报出这批卫生问题，但**过去没有任何动作能修它们**，
于是闭环第一轮就无事可做、直接 CONVERGED，A 分永远停在原地，"优化版"与
原版几乎一样。现在每个可安全自动修复的问题都有对应动作，仍然全部走
「应用 → 整篇重编译 → 全局重评分 → 接受/回滚」：

| 动作 | 触发（感知层） | 做什么 |
|---|---|---|
| `remove_manual_pagebreak` | `manual_pagebreak` | 删正文 `\newpage`/`\clearpage`/`\pagebreak`，交回 LaTeX 全局断页 |
| `remove_excessive_vspace` | `manual_vspace` | 删正文里 ≥ 阈值的 `\vspace{...}`（默认 10mm；小值不动） |
| `normalize_local_font_size` | `size_switch` | 删正文孤立的行内字号切换（`{\Large ...}`）；数学/表格/verbatim 内不动 |
| `normalize_heading_size` | `heading_size` | `\titleformat`/`\xxxfont` 里超限标题字号压回上限（section ≤ `\Large`，subsection ≤ `\large`，subsubsection ≤ `\normalsize`） |
| `reduce_list_spacing` | `list_spacing` | 收紧列表环境里过大的 `itemsep/topsep/parsep/partopsep` |
| `add_hyphenation_points` | `unbreakable` | 给超长不可断词（默认 ≥ 80 字符）插入 `\-` 断词点（TeX 合法机制，不改语义） |
| `break_long_urls` | `long_url` | 给 `\url{}`/`\href{}`/`\path{}` 形式的长 URL 注入 `\usepackage{xurl}`（允许任意位置断行，不改 URL 文字） |
| `fix_table_width` | `tables_overwide` | 列格式简单的超宽表改 tabularx（自适应列宽），不用 resizebox |
| `balance_pages` | `vbox` 问题 | 注入 `\raggedbottom`，抑制“凑满页”式垂直拉伸 |

要点：

- 全部幂等、可回滚；**没有任何一条能绕过全局评分**（变差即回滚）。
- `sanitize_float_specs` 新增 `include_H`：`[H]`（float 宏包强排）会把图
  钉死在本行，是页面失衡/大块留白的常见来源，闭环会尝试解绑为 `[tbp]`，
  由全局分仲裁（默认仍尊重作者的 `[H]`，LLM 请求时需显式传 `include_H`）。
- `normalize_fig_width` 现在同时认**相对超宽**：`width=1.18\linewidth` /
  `1.2\textwidth`（系数 > 1）→ `\linewidth`；`0.92\textwidth` 这类合理尺寸不动。
- 为支持这些动作，内容校验的「排版命令可动面」相应扩展（见下文），正文
  文字/公式/引用/图表内容仍是逐字符严格比较。
- 开关：`tidy_manual_pagebreaks` / `tidy_manual_vspace` / `vspace_min_mm` /
  `normalize_heading_size` / `normalize_local_font_size` / `reduce_list_spacing` /
  `list_spacing_max_pt` / `break_long_words` / `break_long_urls` /
  `fix_overwide_tables` / `balance_pages` / `free_floating_H`；Phase 2：
  `visual_metrics` / `visual_dpi` / `normalize_title` / `title_size_cap` /
  `normalize_parskip` / `parskip_max_pt` / `normalize_header` / `header_max_chars` /
  `remove_mid_multicols` / `reduce_oversized_figures` / `max_fig_height_frac` /
  `subfig_max_sum` / `narrow_table_min_frac` / `tune_float_placement` /
  `done_max_a` / `min_stall_rounds`（均为 Requirement 字段，可写在
  `--require` / `settings.json` 里单独关闭）。

## 结构 / 版面规范（2026-09-10 新增）

面向「投稿规范 / 报告规范」的一组结构能力，全部为可配置字段：

| 能力 | 要求字段（默认） | 动作 | 归属 |
|---|---|---|---|
| 目录页 | `toc`（False）/`toc_min_sections`（3） | `insert_toc` | L（要求指定时）/ A |
| 页眉 | `running_header`（False）/`header_left`/`header_right` | `add_header` | L（要求指定时）/ A |
| 标题着色 | `heading_color`（None，如 `0,62,120`） | `color_headings` | A（审美突出） |
| 阅读辅助清理 | `strip_reading_aids`（**True**） | `strip_reading_aids` | 元信息清理 |
| 告示块清理 | `remove_warning_boxes`（**True**） | `remove_warning_boxes` | 元信息清理 |
| 图形保真 | `preserve_figures`（**True**） | 图形指纹 L 校验 + `--extract-fig` | L |

要点：

- **目录页/页眉**属“前置结构”，要求开启时作为 **L 硬约束**（缺失即违规，
  闭环必自动修复）；`insert_toc` 幂等，插在正文首节前并单独成页。
- **标题着色**用 `sectsty` 给 section/（子）小节着色（`heading_color` 支持
  `R,G,B` / `RGB:...` / `HTML:...` / 颜色名或表达式），已有 `titlesec` 时
  不擅动（避免与 `\titleformat` 冲突）。
- **阅读辅助 / 告示清理**只删已知模式（`START READING HERE`、
  `document order was not finalized`、行首 `WARNING:/CAUTION:/ATTENTION:`），
  绝不匹配正文句子；属“元信息定点删除”，由内容校验器的元信息归一器豁免，
  不破坏“正文零改动”铁律。关闭：`--no-strip-aids` / `--no-warning-boxes`。
- **图形保真**：图的唯一合法来源是原稿——禁止用 TikZ 重画、禁止换算坐标轴。
  感知层为每个 figure/table 环境计算**内容指纹**（宽度/位置参数归一），
  与 `--original` 对照，不一致即 L 违规“图形/表格内容被改动”，并给
  `figure_unpreserved` 建议。重建/嵌图用 `--extract-fig` 从原 PDF 裁切
  （400dpi，按原始 bp 尺寸嵌入）。

## 架构：感知-决策-执行-验证闭环

```
                    ┌──────────────────────────────────────┐
                    │   主循环：候选动作池，全局评分验收       │
                    │   （每步：备份→应用→整篇重编译→全局重评） │
                    └──────────────────────────────────────┘
  感知 (perceive.py)        决策 (core.py + score.py)        执行 (actions.py)
  L1 源码：类/字号/geometry/    L 硬门槛优先（编译/内容/页数/   白名单动作（只动排版面）：
     浮动体 spec/图宽/tabular   规范）→ 质量/松弛候选按序推进；   set_margin / set_fontsize
  L2 日志：页数/overfull/      每轮取首个全局正收益动作；       sanitize_float_specs /
     underfull/vbox/浮动警告    失败动作记 blocked 防重复；      normalize_fig_width /
  L3 PDF：pdfinfo 真实页数      验收失败一律回滚（正文零改动    drop_fleqn /
     （与日志交叉验证）         由 body 归一化 diff 机器校验）    inject_quality_macros
                              终止：DONE / CONVERGED / NO_IMPROVEMENT /
                                    EXHAUSTED / FAILED
                              每步写 state.json（评分轨迹）

  （v2 新增模式：结构层——目录/页眉/标题着色/阅读辅助/WARNING/图形指纹；
    对应动作 insert_toc / add_header / color_headings /
    strip_reading_aids / remove_warning_boxes，以及 engine.extract_pdf_region）
```

### 闭环四条保证（继承自 MVP 并推广）
1. **全局单调性**：只接受整篇重编译后全局目标不劣化的动作（压页阶段放宽为
   「页数不增」以保留组合收益，达标后自动回到严格模式）；
2. **全局最优趋近**：L 达标后，松弛动作（回放页边距/字号）因降低 I 被自动
   接受，直到临界点 —— 最小干预与压缩质量由同一评分函数仲裁；
3. **有界性**：候选动作有限 + `max_iterations` 兜底 + 编译超时强杀重试；
4. **可审计**：原文件只读；每步动作、L/A/I、总分、回滚原因全量记录。

## 模型在环（Model-in-the-loop）：LLM 真正进入优化循环

两步往返（可重复多轮）：

```bash
# ① 跑确定性闭环，并输出「请求包」给 LLM（状态+残余问题+可用动作+页面图）
python3 optimize.py paper.tex --template acme --emit-request
#    -> workbench/{paper.tex, report.md, state.json, advisory.json,
#                 llm_request.json, pages/page-*.png, visual.md}

# ② LLM 读 llm_request.json，产出 proposals.json（结构化提案）
# ③ 程序逐条执行：白名单校验 → 应用 → 编译 → 全局验收 → 变差回滚，再出下一轮
python3 optimize.py paper.tex --proposals proposals.json --emit-request
#    -> 更新 paper.tex/report/state + 下一轮 llm_request.json（round+1）

python3 optimize.py --list-actions        # 查看可用白名单动作
```

**提案格式**（宽松，兼容嵌套/扁平两种写法）：

```json
{
  "schema": "texopt.proposals/v1", "round": 1,
  "assessment": "整体布局判断……",
  "proposals": [
    {"id": "p1", "issue": "page_balance", "location": "page 5",
     "severity": "moderate", "reason": "页面下半部分空白过大",
     "proposal": {"action": "set_float_spec", "target": "figure#2",
                  "params": {"spec": "tbp"},
                  "suggestion": "允许该图浮到页顶/页底以填补空白"}}
  ]
}
```

**安全闸门（LLM 不能随意改论文）**：

1. 提案里的 `action` 必须在**白名单**（`texopt/whitelist.py`）里，否则 **BLOCKED**；
2. 每个参数做类型/取值/正则校验（禁花括号与控制序列注入）；
3. 所有动作都只落在**排版面**（页边距/字号/浮动体位置参数/图片宽度/结构）；
4. 执行后一律**整篇重编译 + 全局重评分**，`L` 变差或总分不改善 → **回滚**；
5. 未知动作、非法参数、已失败过的提案 → 跨轮阻止（audit 可查）。

白名单动作（`--list-actions`）：`set_margin`、`set_fontsize`、`drop_fleqn`、
`inject_quality_macros`、`insert_toc`、`add_header`、`color_headings`、
`strip_reading_aids`、`remove_warning_boxes`、`sanitize_float_specs`、
`normalize_fig_width`，确定性排版修复：`remove_manual_pagebreak`、
`remove_excessive_vspace`、`normalize_local_font_size`、`normalize_heading_size`、
`reduce_list_spacing`、`add_hyphenation_points`、`break_long_urls`、`fix_table_width`、
`balance_pages`，
以及两个 **Level-3 定点动作**：

| 动作 | 作用 |
|---|---|
| `set_float_spec` | 定点让某张图/表浮到页顶(t)/页底(b)/单独页(p)：`target="figure#2"` |
| `set_fig_width` | 定点设置某张插图宽度：`width="0.9\\linewidth", target="fig#1"` |

`workbench/state.json` 的 `steps` 每步带 `source`（`rule`/`llm`）与 `detail`，
完整保留「为什么改 / 改了什么 / 编译结果 / 指标变化 / 为什么接受或回滚」。

## 视觉感知（Phase 4：给 LLM 一双眼睛）

`--emit-request` 会把每页 PDF 渲染成 PNG（`workbench/pages/page-*.png`），
附在 `llm_request.json` 的 `page_images` 里，交给**具备视觉能力的模型**判断
留白/视觉重心/图文关系等 Level-3 问题。

同时给出**实验性像素代理**（写进 `workbench/visual.md`）：墨迹占比、上/下半
页墨迹比、最大空白带及其位置——它们是**粗略实验量，不是人类审美评分，
默认不并入 A 分**（不改变 `score.py` 语义），仅供参考与后续研究。

> 边界：本版**只做了“把页面变成图像交给模型”**，**尚未做视觉审美量化**，
> 不声称“视觉审美优化”。真正的视觉量化（whitespace/content density/
> visual balance…）属 Phase 5 研究项。

## 输出四态（2026-09-11 细分：不再“L=0 就 CONVERGED”）

| 状态 | 含义 | 处理 |
|---|---|---|
| DONE | L 全达标，且本轮**应用了 ≥1 个被接受的动作**（A/页数真的变了） | 报告给出 `Applied N accepted actions. A: old -> new. Pages: old -> new` |
| CONVERGED | L 全达标，且**根本没有可动的候选动作**（文档本身没问题） | 报告列出残余 cosmetic 问题（如有） |
| NO_IMPROVEMENT | L 全达标，有可动候选，但**没有任何一个能改善全局评分**（已全部回滚） | 如实说“未修改任何内容”，不伪造“优化成功” |
| EXHAUSTED | 排版手段用尽仍缺 L（通常超页） | 报告给出差距与语义抛光建议，等用户决策 |
| FAILED | 基线无法编译 / 环境缺失 | 报告给出首个编译错误 |

判定规则：`L 违规 > 0 → EXHAUSTED`；否则按「是否有候选 → 是否有接受」区分
`DONE / NO_IMPROVEMENT / CONVERGED`。**L 与 A 分开看**：L=0 不再等于“已优化”。

## 环境要求与已知约束

- TeX：自动探测 Windows TeX Live（`/mnt/c/texlive/*/bin/windows/`）或 PATH 中的
  XeLaTeX；文档必须位于 `/mnt/c`、`/mnt/d` 等 Windows 真实盘符路径下
  （Windows 引擎无法写 WSL 原生文件系统）。`--outdir` 也会被校验，不在
  Windows 盘符下会提前报错（避免“编译成功不了”的坑）。
- 修改面白名单：文档字号档（仅 tune-geometry 压页时）、页边距（仅 tune-geometry，有下限）、
  断行质量宏、浮动体位置参数、超宽/定点图片宽度、documentclass 的 fleqn 选项、
  前置结构（目录/页眉/标题着色）、**正文排版卫生命令**（手动分页/过大垂直间距/行内字号乱标/
  标题字号/列表间距/断词点/表格列格式）；**不做**：正文
  文字/公式/引用/标签/图表内容改动、注释改动、文档类更换、语义改写。
- 本版暂不实现（后续阶段）：页面图像的**视觉量化**（留白/孤行像素级），
  跨文档类模板迁移，LLM 语义保意缩行，历史版本存档。

## 开发阶段与现状（已实现 / 接口预留 / 未来）

诚实标注每个阶段的状态（对应「不要为了满足目标而虚构不存在的功能」）：

| 阶段 | 内容 | 状态 |
|---|---|---|
| **Phase 1** 确定性优化 | Perceive→Score→Action→Compile→Verify→Rollback 闭环 | ✅ 已实现（`optimize.py` / `texopt/core.py`） |
| **Phase 2** LLM advisory | 残余问题→结构化建议（severity/line/suggestion/suggested_actions） | ✅ 已实现（`texopt/advise.py`） |
| **Phase 3** LLM 提案入环 | 白名单提案→程序执行→编译→验收→保留/回滚→下一轮 | ✅ 已实现（`texopt/whitelist.py` + `texopt/proposal.py` + `Optimizer.apply_proposals` + CLI `--proposals`） |
| **Phase 4** 页面图像 | PDF→逐页 PNG + 页面级像素量化，交给视觉模型 | ✅ 已实现（`texopt/visual.py`：render + `page_metrics`） |
| **Phase 5** 视觉审美量化 | whitespace/content density/visual balance 等并入 A | ✅ 已实现（2026-09-11 起 `page_metrics`/`find_defects` 并入 A；阈值化、可审计，仍非人类审美评分） |
| **Phase 6** 高级语义优化 | 物理排版↔语义压缩/重构 + 更强语义保持验证 | ⬜ 尚未实现（需用户在场审批） |

**审美量化流水线（2026-09-28 起，独立于上面的 Phase 1-6）**：

| 阶段 | 内容 | 状态 |
|---|---|---|
| 阶段 0 | 指标盘点 + `page_metrics.v1` schema + 修 4 个真 bug | ✅ |
| 阶段 1 | 页面角色标注 + 页级提取 + 全库 608 篇 / 10538 页 | ✅ |
| 阶段 2 | 审美档案（venue×role 正常范围 + CI + 可信度）+ 去冗余 | ✅ |
| 阶段 3 | **留白结构化识别（五类 + region 列表）+ 页眉页脚识别 + 未锚图形计入** | ✅（`texopt/whitespace.py`） |
| 阶段 4 | 马氏距离异常检测 + 带外损失 `A_profile`（λ=0 影子模式） | ✅（`texopt/aesthetic.py` + `texopt/shadow.py`；提交 `ae741fc`） |
| 阶段 5 | **评测与验收协议 12.1-12.6**（负样本注入 / 假阳率 / 会议可分性 / 稳定性 / 人类相关性接口 / 逐维门槛） | ✅（`texopt/evalproto.py`；门槛 6/8 维通过，`eval_gate.json` 由影子评估自动加载） |
| 阶段 6 | 影子接入 texopt（λ=0 真正进 `score`/`core`，只报告不改判定） | ✅（`texopt/shadow.py` + `core.py` 观测钩子 + `aesthetic_shadow.md/json`；CLI `--shadow-only` / `--no-aesthetic-shadow`） |
| 阶段 7 | **权重校准**（消融拟合 + bootstrap CI + Bradley-Terry 接口） | ✅ 步骤二已完成并启用（`texopt/weights.py`，`aesthetic_weights.json`）；步骤三（人类成对比较）**数据未采集 → null** |
| 阶段 8 | 外部验证（真实论文端到端退化 / 第二套工具链复测 / 论文级报告） | ⬜ |

阶段 5 结果要点（诚实边界：检验的是实现与口径的**自洽性**，不等于「与人类审美一致」；12.5 数据未采集，如实记 null）：

- 12.1 负样本注入：A 单调上升 100%（严格零回落 96.3%）、退化页定位 96.3%
- 12.2 假阳率：卡方阈值 **15.9%**（假设不成立，重尾）→ 发布口径改用**经验校准**，仍为 **5.71%**（略高于 5% 目标，报告给了 P95/96/97 权衡表）
- 12.3 会议可分性：1-NN 留一 0.529（随机 0.091），置换 p=0.0099
- 12.4 稳定性：重复测量完全一致、DPI 50→200 漂移 0
- 12.6 门槛：6/8 维通过；未过者 `readability.leading_ratio`、`density.coverage_table`（12.1 未覆盖 → 只能作报告项）

阶段 7 结果要点（方案 10.3）：信号 = 该维被退化时的损失增量，噪声 = 对照试验里它在未退化页上的自发损失（P90）；
`w = SN` 归一到均值 1、裁剪 [0.25, 4]（先归一再裁剪），CI 用按论文聚类的 bootstrap。
80 组试验下：`balance.d_mid` **2.65**、`balance.visual_centroid_y` 1.16、`whitespace.total_ratio` 0.67、
`density.coverage_text` 0.61、`ratio.fig_text` 0.46、`alignment.center_var` 0.46；
验收：退化后 A 上升正向率 0.9875 不变、中位判别间隔 0.1157 → **0.1506**（严格改善）→ `applied=true`。
**λ 仍为 0**：权重只改 `A_profile` 合成口径（`Σw·v/Σw`），不参与验收；λ>0 需人类标定 + 用户审批。

文档：`docs/stage0_visual_inventory.md`、`stage1_role_and_extraction.md`、`stage2_profile.md`、`stage3_whitespace.md`、`stage4_aesthetic_profile.md`、`stage5_eval_protocol.md`、`stage6_shadow_integration.md`、`stage7_weight_calibration.md`。

阶段 6 接入要点（详见 `docs/stage6_shadow_integration.md`）：影子只在「判定完成之后」被调用（基线 / 接受分支 / 终态），λ 恒为 0；每次运行产
`workbench/<run>/aesthetic_shadow.md`（人读，含逐轮 trace 与人工核对清单）与
`aesthetic_shadow.json`（机器），并在 `state.json` 写**版本化快照**（13.4）。
端到端证据：同文档开/关影子，`status`/`accepted`/`total`/`a`/`L`/页数逐项相同。

**接口/placeholder（已预留但未落地）**：`Requirement.microtype`（None=不干预）；
视觉代理指标 (`texopt/visual.py`) 已计算但默认不影响评分；
历史版本存档（advanced，代码侧未接）。

## 目录结构

```text
texopt/
├── optimize.py            # CLI 入口（--template/--require/--target/--settings/
│                           #   --emit-request/--proposals/--list-actions/--visual）
├── settings.json          # 默认要求/运行参数（Agent 对接接口）
├── templates/             # 期刊/会议要求预设库（.json，可扩展）
├── texopt/
│   ├── engine.py          # 编译引擎（超时强杀重试）+ PDF 图形裁切 + 输出目录校验
│   ├── perceive.py        # 感知层 L1/L2/L3（源码+日志+PDF）+ 结构/图形指纹
│   ├── actions.py         # 执行层白名单动作（含定点 float/图宽）
│   ├── whitelist.py       # 动作白名单注册表（模型在环唯一可请求面 + 参数校验）
│   ├── proposal.py        # 模型在环提案：解析/校验/请求包构造（llm_request.json）
│   ├── visual.py          # 视觉感知层：PDF→页面图 + 实验性像素代理（未并入 A）
│   ├── score.py           # L + A + I 全局量化（含结构规范与图形保真）
│   ├── requirements.py    # 要求规格模型（模板/自定义合并）
│   ├── advise.py          # 残余问题→结构化建议（模型在环消费）
│   ├── page_metrics.py    # page_metrics.v1 结构/校验/聚合/旧输出适配（纯 stdlib）
│   ├── roles.py           # 页面角色规则器（title/body/references/appendix/figure-page…）
│   ├── extract.py         # 阶段 1：PDF→page_metrics.v1（矢量/文本层为主）
│   ├── whitespace.py      # 阶段 3：留白结构化（五类 + region 列表）
│   ├── profile.py         # 阶段 2：审美档案（分位/聚类 bootstrap/Spearman/PCA，纯 Python）
│   ├── aesthetic.py       # 阶段 4：马氏距离 D² + 非单调带外损失 A_profile
│   ├── shadow.py          # 阶段 4/5：影子评估（λ=0）+ 加载 eval_gate.json 剔除未过门槛的维
│   ├── evalproto.py       # 阶段 5：评测与验收协议 12.1-12.6
│   ├── weights.py         # 阶段 7：权重校准（消融 + Bradley-Terry + 验收）
│   └── core.py            # 决策主循环 + 模型在环提案执行 + 请求包发射
├── tests/run_tests.py     # 回归测试：单元 + 端到端闭环 + 模型在环往返
├── examples/              # 靶子稿（重建脚本 + 结果一起进 git，见 examples/README.md）
│   ├── gen_fixtures.py       # 一键重建全部靶稿（demo/issues/chaos/nightmare/aidtest/…）
│   ├── demo.tex              # 干净稿（自然 6 页，页数限制演示用）
│   ├── issues.tex            # 4 类可修问题（README 快速开始 0）
│   ├── aidtest.tex           # 阅读辅助 + 告示块 + 超宽图
│   ├── fig_violation.tex     # 图形保真反例（重绘的图 → L 违规）
│   └── propose_target.tex    # Level-3 模型在环靶子
├── skills/latex-opt/      # OpenClaw 技能说明（模型在环用法）
├── AGENTS.md / SOUL.md    # Agent 身份与工作流（OpenClaw 集成）
└── workbench/             # 运行产物（工作副本/PDF/报告/状态/请求包/页面图）
```

## 测试

```bash
python3 tests/run_tests.py          # 单元 + 常用靶子闭环 + 模型在环往返
python3 tests/run_tests.py --full   # 含 chaos/nightmare 大靶子
```

阶段 5 评测协议（离线跑缓存指标，约 2-3 分钟；加 `--render` 额外做渲染层注入 + 重编译稳定性）：

```bash
cd datasets/conf-specs
python3 tools/eval_protocol.py --pages-n 80 --perms 100     # 12.1/12.2/12.3/12.4 → eval_gate.json
python3 tools/eval_protocol.py --only gate                 # 只重算门槛（基于既有结果，秒级）
```

阶段 6 影子评估（λ=0，仅报告；不改文档）：

```bash
python3 optimize.py paper.tex --shadow-only        # 只出 aesthetic_shadow.md/.json
python3 tests/run_tests.py                         # 含 s6/no-decision-change（开关影子判定一致）
```

阶段 7 权重校准（离线跑缓存指标，秒级；`--apply` 才挂回档案）：

```bash
cd datasets/conf-specs
python3 tools/calibrate_weights.py --trials 80 --bootstrap 200 --apply
python3 tools/calibrate_weights.py --pairs ../human/pairs.json --apply   # 步骤三（需人类数据）
```

测试只写 `_regress/`（Windows 盘符下），跑完自动清理；examples/ 里的靶子只读。
