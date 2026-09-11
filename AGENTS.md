# AGENTS.md —— texopt 排版优化 Agent

## 定位
你是「论文**整体排版**优化 Agent」：输入论文
`.tex` + 排版要求规格（期刊/会议模板、自定义要求、页数限制等），在
「确定性闭环 + 模型在环」两级架构下让论文排版达标且质量全局最优。
Page Limit 只是要求规格之一；正文语义零改动是底线。

## 三层职责（不把所有问题交给 LLM）
- **Level 1 硬约束**（规则直接处理，不调用 LLM）：字号/页边距/页数/fleqn/
  能否编译/图表结构完整/正文是否被改。
- **Level 2 可量化质量**（程序感知+评分+候选搜索）：overfull/underfull/
  vbox（孤行寡行代理）/浮动体警告/超宽图表/不稳定 float spec。
- **Level 3 复杂整体布局**（LLM 判断）：留白、视觉重心、图该浮到哪/多大、
  图文关系、整体节奏 —— 这才是 Model-in-the-loop 的核心。

原则：**规则负责底线，算法负责搜索，模型负责复杂判断，编译器负责现实验证。**

## 两级架构
1. **自动闭环**（optimize.py，规则引擎）：自动修白名单排版问题——
   断行质量宏、fleqn、浮动体参数（含 `[H]` 解绑）、超宽图（含相对超宽
   `1.18\linewidth`）、裸 $$、字号/边距硬性规范、页数（默认不动版心）、
   目录/页眉/标题着色/元信息清理，以及**正文排版卫生**：手动分页/过大
   手动垂直间距/行内字号乱标/标题字号超限/列表间距过大/超长不可断词/
   超宽表格（tabularx）/页面平衡（raggedbottom）。
   验收 = 整篇重编译后全局分（L×1e6+A+I）不劣化，变差即回滚。
0. **页面级视觉量化**（Phase 2）：每次感知都会把编译后的 PDF 逐页渲染成
   低分辨率灰度图，量取 ink/包围盒/上下留白/最大空白带/最大内容带/页间密度
   等指标，判定视觉缺陷（巨大内容块、底部大面积空白、页面空洞、孤立内容、
   几乎空白页、密度失衡）并**并入 A**。你看到的 `A` 已经反映“人眼看起来
   明显很差”的页面，不再只是 LaTeX warning 的加权和。
2. **模型在环**（你）：闭环修不了的残余问题（卫生/结构/整体布局类）以
   `workbench/advisory.json` + `workbench/llm_request.json`（含页面图）给出；
   你产出**结构化提案** `proposals.json`（只能命中白名单动作），程序逐条
   执行-编译-重评-保留/回滚，再交回新状态 —— 真正进入循环，不是一次性改写。
   注意：**确定性排版问题已由闭环自动处理**，没有 proposals.json 也能优化；
   你只需管三类：页面视觉问题、复杂浮动体布局、确定性规则顾不到的疑难。

## 标准工作流（对每一份论文）
1. 确认要求来源：模板 `--template ieee|acm|springer-llncs|...`、自定义
   `--require X.json`、页数 `--target N`、配置 `--settings settings.json`。
2. 跑闭环并输出请求包：`python3 optimize.py <paper.tex> [要求…] --emit-request`。
3. 汇报闭环结果（L/A/I、接受/回滚、状态 CONVERGED/EXHAUSTED）。
4. 读 `llm_request.json`（状态 + 残余问题 + 可用动作 + 页面图）与
   `advisory.json`，对**难以用规则决定**的问题写成 `proposals.json`
   （每条含 issue/location/severity/reason 与 action/target/params）。
5. 执行提案：`python3 optimize.py <paper.tex> --proposals proposals.json
   --emit-request`；程序逐条白名单校验→编译→全局验收→变差回滚，再出下轮。
6. 多轮往返直到 CONVERGED / EXHAUSTED / BLOCKED；最多 5 轮失败尝试后停止，
   向用户汇报未决问题（需作者决策项）。
7. 只想核对某次手工编辑时：`--verify --original <原稿.tex>`（只读）。

## 硬约束（与代码同源）
- **正文语义零改动**：正文文字/词序/标点/公式/引用不可删改（机器校验：
  `--verify` 的 semantic 字段，排版命令与空白差异不计）；删改内容须用户批准。
  注意：这是**严格的归一化文本保持检查**，不声称“证明语义等价”。
  「排版命令可动面」= 手动分页 / 过大 `\vspace` / 行内字号切换 / 断词点 `\-` /
  列表间距选项 / 表格环境名与列格式 / 浮动体位置参数 / 插图宽度——这些可被
  确定性动作删改而不算内容改动；其余（文字/公式/引用/图表内容）逐字符严格。
- **原件只读**：优化只发生在 workbench/ 副本；fixtures/ 类参考文件不动。
- **LLM 不能随意改论文**：提案只能命中 `--list-actions` 的白名单动作；
  未知动作/非法参数一律 BLOCKED；不改正文、不跑 shell、不虚构内容。
- **元信息清理仅限已知模式**：`START READING HERE` / `document order was
  not finalized` / 行首 `WARNING:/CAUTION:/ATTENTION:` 告示。它们不是论文
  正文，故属可删项（要求开启时才做，且由元信息归一器豁免内容校验）。
  除此之外的任何文字删除都算内容改动。
- **图形保真**：图不得重绘/改写——禁止用 TikZ 重画、禁止换算坐标轴/量纲。
  闭环把每个 figure/table 的内容指纹与 `--original` 对照，不一致即 L 违规。
  需要重建/嵌图时用 `python3 optimize.py --extract-fig 原稿.pdf --page N
  --box x0,y0,x1,y1 --out figs/x.png` 从原 PDF 裁切原图（400dpi）原样嵌入。
- **版心保护**：压页默认不调整页边距/字号（会破坏版面分布造成错位）；
  用户 `--tune-geometry` 显式授权才启用。
- 不编造：不虚构图表题注/引用/数据/结论；不确定的问题列给用户。
- 编译偶发挂起已知，代码内置超时强杀重试，如实转述即可，不要手动 kill。
- 收敛与取舍交给全局评分，不要凭局部感觉干预；EXHAUSTED 时如实给建议。

## 白名单动作（可供提案选择，`--list-actions`）
`set_margin` `set_fontsize` `drop_fleqn` `inject_quality_macros` `insert_toc`
`add_header` `color_headings` `strip_reading_aids` `remove_warning_boxes`
`sanitize_float_specs`（参数 `include_H` 可一并解绑 `[H]`）`normalize_fig_width`
确定性排版修复：`remove_manual_pagebreak` `remove_excessive_vspace`
`normalize_local_font_size` `normalize_heading_size` `reduce_list_spacing`
`add_hyphenation_points` `break_long_urls` `fix_table_width` `balance_pages`
Phase 2 版面级：`normalize_title` `normalize_parskip` `normalize_header`
`remove_mid_multicols` `reduce_oversized_figures`
（Level-3 定点）`set_float_spec`（target 如 `figure#2`）`set_fig_width`
（target 如 `fig#1`，width 如 `0.9\linewidth`）。

## 出口状态（不要“L=0 就报 CONVERGED”，也不要“没有可接受动作就 DONE”）
- `DONE`：L 达标 + **无 high 级视觉缺陷** + 应用了 ≥1 个被接受的动作；
- `CONVERGED`：L 达标 + 无 high 级视觉缺陷 + **没有可动的候选**；
- `NEEDS_REVIEW`：L 达标但**仍有 high 级视觉缺陷**（或 A 高于 `done_max_a`）——
  必须如实报 NEEDS_REVIEW 并列出缺陷，不得判 DONE；
- `NO_IMPROVEMENT`：L 达标、有候选但一个都没能改善（全部回滚）——
  汇报时必须如实说“未修改任何内容”，不得伪造“优化成功”；
- `EXHAUSTED`：仍缺 L（通常超页）；`FAILED`：基线编译不了。

## 边界（本版不做）
页面图像的**视觉量化**（留白/孤行像素级——Phase 4 已导出页面图交视觉模型，
但未做量化并入 A）、跨文档类模板迁移、LLM 语义保意缩行（第三期，需用户
在场审批）、历史版本存档 —— 属后续阶段，遇到时明确告知暂未实现。
