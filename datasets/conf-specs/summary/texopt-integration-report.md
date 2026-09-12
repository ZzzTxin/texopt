# 会议模板 → texopt 接入现状（自动生成，勿手改）

- 模板目录：`/mnt/d/桌面/texopt/datasets/conf-specs/templates-v2`（共 16 个会议）
- 接入方式：`python3 optimize.py paper.tex --conference <id>`
- 原则：**官方硬约束 → 违规判定（L）；真实论文统计 → 合理性参考（不入 L、不影响评分）；接不上的字段逐条记录**。
- 生成：`python3 tools/check_conference_integration.py`

## 1. 已接入的字段（会议 json → texopt Requirement）

| 会议 | 页数上限 | 页数口径 | 字号 | 边距下限 | 浮动体 | 超宽图阈值 | 公式居中 | 质量宏 |
|---|---|---|---|---|---|---|---|---|
| aaai | 7 | content | 10 | 19.05 | tbp | 177.8 | False | True |
| acl | 8 | content | 11 | 25.0 | tbp | 160.0 | False | True |
| cvpr | 8 | content | 10 | 20.6 | tbp | 174.6 | False | True |
| eccv | 14 | content | 10 | 12 | tbp | 122 | False | True |
| emnlp | 8 | content | 11 | 25.0 | tbp | 160.0 | False | True |
| iccv | 8 | content | 10 | 20.6 | tbp | 174.6 | False | True |
| iclr | 10 | content | 10 | 25.4 | tbp | 139.7 | False | True |
| icml | 8 | content | 10 | 22.225 | tbp | 171.45 | False | True |
| ijcai | 7 | content | 10 | 19.05 | tbp | 177.8 | False | True |
| kdd | 8 | content | 9 | 19.05 | tbp | 177.8 | False | True |
| neurips | 9 | content | 10 | 25.4 | tbp | 139.7 | False | True |
| nsdi | 12 | content | 10 | 19.05 | tbp | 177.8 | False | True |
| osdi | 12 | content | 10 | 19.05 | tbp | 177.8 | False | True |
| siggraph | 7 | content | 9 | 18.34 | tbp | 179.2 | False | True |
| sosp | 12 | content | 10 | —（未接入） | tbp | 178 | False | True |
| www | 8 | content | 9 | 19.05 | tbp | 177.8 | False | True |

### 字段来源与依据（每会议）

| 会议 | 字段 | 模板路径 | basis |
|---|---|---|---|
| aaai | `page_limit` | `hard_constraints.page_limit_content` | official |
| aaai | `font_pt` | `typography.body_font_pt` | official |
| aaai | `margin_mm` | `geometry.margin_floor_mm` | official |
| aaai | `float_spec` | `float_policy.float_spec` | derived |
| aaai | `overwide_fig_threshold_mm` | `float_policy.figure_width.overwide_threshold_mm` | derived |
| aaai | `eq_fleqn_allowed` | `texopt_flat.eq_fleqn_allowed` | derived |
| aaai | `enable_quality_macros` | `texopt_flat.enable_quality_macros` | derived |
| acl | `page_limit` | `hard_constraints.page_limit_content` | official |
| acl | `font_pt` | `typography.body_font_pt` | official |
| acl | `margin_mm` | `geometry.margin_floor_mm` | official |
| acl | `float_spec` | `float_policy.float_spec` | derived |
| acl | `overwide_fig_threshold_mm` | `float_policy.figure_width.overwide_threshold_mm` | derived |
| acl | `eq_fleqn_allowed` | `texopt_flat.eq_fleqn_allowed` | derived |
| acl | `enable_quality_macros` | `texopt_flat.enable_quality_macros` | derived |
| cvpr | `page_limit` | `hard_constraints.page_limit_content` | official |
| cvpr | `font_pt` | `typography.body_font_pt` | official |
| cvpr | `margin_mm` | `geometry.margin_floor_mm` | official |
| cvpr | `float_spec` | `float_policy.float_spec` | derived |
| cvpr | `overwide_fig_threshold_mm` | `float_policy.figure_width.overwide_threshold_mm` | derived |
| cvpr | `eq_fleqn_allowed` | `texopt_flat.eq_fleqn_allowed` | derived |
| cvpr | `enable_quality_macros` | `texopt_flat.enable_quality_macros` | derived |
| eccv | `page_limit` | `hard_constraints.page_limit_content` | official |
| eccv | `font_pt` | `typography.body_font_pt` | template-implied |
| eccv | `margin_mm` | `geometry.margin_floor_mm` | official |
| eccv | `float_spec` | `float_policy.float_spec` | derived |
| eccv | `overwide_fig_threshold_mm` | `float_policy.figure_width.overwide_threshold_mm` | derived |
| eccv | `eq_fleqn_allowed` | `texopt_flat.eq_fleqn_allowed` | derived |
| eccv | `enable_quality_macros` | `texopt_flat.enable_quality_macros` | derived |
| emnlp | `page_limit` | `hard_constraints.page_limit_content` | official |
| emnlp | `font_pt` | `typography.body_font_pt` | official |
| emnlp | `margin_mm` | `geometry.margin_floor_mm` | official |
| emnlp | `float_spec` | `float_policy.float_spec` | derived |
| emnlp | `overwide_fig_threshold_mm` | `float_policy.figure_width.overwide_threshold_mm` | derived |
| emnlp | `eq_fleqn_allowed` | `texopt_flat.eq_fleqn_allowed` | derived |
| emnlp | `enable_quality_macros` | `texopt_flat.enable_quality_macros` | derived |
| iccv | `page_limit` | `hard_constraints.page_limit_content` | official |
| iccv | `font_pt` | `typography.body_font_pt` | official |
| iccv | `margin_mm` | `geometry.margin_floor_mm` | official |
| iccv | `float_spec` | `float_policy.float_spec` | derived |
| iccv | `overwide_fig_threshold_mm` | `float_policy.figure_width.overwide_threshold_mm` | derived |
| iccv | `eq_fleqn_allowed` | `texopt_flat.eq_fleqn_allowed` | derived |
| iccv | `enable_quality_macros` | `texopt_flat.enable_quality_macros` | derived |
| iclr | `page_limit` | `hard_constraints.page_limit_content` | official |
| iclr | `font_pt` | `typography.body_font_pt` | template-implied |
| iclr | `margin_mm` | `geometry.margin_floor_mm` | official |
| iclr | `float_spec` | `float_policy.float_spec` | derived |
| iclr | `overwide_fig_threshold_mm` | `float_policy.figure_width.overwide_threshold_mm` | derived |
| iclr | `eq_fleqn_allowed` | `texopt_flat.eq_fleqn_allowed` | derived |
| iclr | `enable_quality_macros` | `texopt_flat.enable_quality_macros` | derived |
| icml | `page_limit` | `hard_constraints.page_limit_content` | official |
| icml | `font_pt` | `typography.body_font_pt` | template-implied |
| icml | `margin_mm` | `geometry.margin_floor_mm` | official |
| icml | `float_spec` | `float_policy.float_spec` | derived |
| icml | `overwide_fig_threshold_mm` | `float_policy.figure_width.overwide_threshold_mm` | derived |
| icml | `eq_fleqn_allowed` | `texopt_flat.eq_fleqn_allowed` | derived |
| icml | `enable_quality_macros` | `texopt_flat.enable_quality_macros` | derived |
| ijcai | `page_limit` | `hard_constraints.page_limit_content` | official |
| ijcai | `font_pt` | `typography.body_font_pt` | official |
| ijcai | `margin_mm` | `geometry.margin_floor_mm` | official |
| ijcai | `float_spec` | `float_policy.float_spec` | derived |
| ijcai | `overwide_fig_threshold_mm` | `float_policy.figure_width.overwide_threshold_mm` | derived |
| ijcai | `eq_fleqn_allowed` | `texopt_flat.eq_fleqn_allowed` | derived |
| ijcai | `enable_quality_macros` | `texopt_flat.enable_quality_macros` | derived |
| kdd | `page_limit` | `hard_constraints.page_limit_content` | official |
| kdd | `font_pt` | `typography.body_font_pt` | template-implied |
| kdd | `margin_mm` | `geometry.margin_floor_mm` | official |
| kdd | `float_spec` | `float_policy.float_spec` | derived |
| kdd | `overwide_fig_threshold_mm` | `float_policy.figure_width.overwide_threshold_mm` | derived |
| kdd | `eq_fleqn_allowed` | `texopt_flat.eq_fleqn_allowed` | derived |
| kdd | `enable_quality_macros` | `texopt_flat.enable_quality_macros` | derived |
| neurips | `page_limit` | `hard_constraints.page_limit_content` | official |
| neurips | `font_pt` | `typography.body_font_pt` | template-implied |
| neurips | `margin_mm` | `geometry.margin_floor_mm` | official |
| neurips | `float_spec` | `float_policy.float_spec` | derived |
| neurips | `overwide_fig_threshold_mm` | `float_policy.figure_width.overwide_threshold_mm` | derived |
| neurips | `eq_fleqn_allowed` | `texopt_flat.eq_fleqn_allowed` | derived |
| neurips | `enable_quality_macros` | `texopt_flat.enable_quality_macros` | derived |
| nsdi | `page_limit` | `hard_constraints.page_limit_content` | official |
| nsdi | `font_pt` | `typography.body_font_pt` | official |
| nsdi | `margin_mm` | `geometry.margin_floor_mm` | official |
| nsdi | `float_spec` | `float_policy.float_spec` | derived |
| nsdi | `overwide_fig_threshold_mm` | `float_policy.figure_width.overwide_threshold_mm` | derived |
| nsdi | `eq_fleqn_allowed` | `texopt_flat.eq_fleqn_allowed` | derived |
| nsdi | `enable_quality_macros` | `texopt_flat.enable_quality_macros` | derived |
| osdi | `page_limit` | `hard_constraints.page_limit_content` | official |
| osdi | `font_pt` | `typography.body_font_pt` | official |
| osdi | `margin_mm` | `geometry.margin_floor_mm` | official |
| osdi | `float_spec` | `float_policy.float_spec` | derived |
| osdi | `overwide_fig_threshold_mm` | `float_policy.figure_width.overwide_threshold_mm` | derived |
| osdi | `eq_fleqn_allowed` | `texopt_flat.eq_fleqn_allowed` | derived |
| osdi | `enable_quality_macros` | `texopt_flat.enable_quality_macros` | derived |
| siggraph | `page_limit` | `hard_constraints.page_limit_content` | official |
| siggraph | `font_pt` | `typography.body_font_pt` | template-implied |
| siggraph | `margin_mm` | `geometry.margin_floor_mm` | official |
| siggraph | `float_spec` | `float_policy.float_spec` | derived |
| siggraph | `overwide_fig_threshold_mm` | `float_policy.figure_width.overwide_threshold_mm` | derived |
| siggraph | `eq_fleqn_allowed` | `texopt_flat.eq_fleqn_allowed` | derived |
| siggraph | `enable_quality_macros` | `texopt_flat.enable_quality_macros` | derived |
| sosp | `page_limit` | `hard_constraints.page_limit_content` | official |
| sosp | `font_pt` | `typography.body_font_pt` | official |
| sosp | `float_spec` | `float_policy.float_spec` | derived |
| sosp | `overwide_fig_threshold_mm` | `float_policy.figure_width.overwide_threshold_mm` | derived |
| sosp | `eq_fleqn_allowed` | `texopt_flat.eq_fleqn_allowed` | derived |
| sosp | `enable_quality_macros` | `texopt_flat.enable_quality_macros` | derived |
| www | `page_limit` | `hard_constraints.page_limit_content` | official |
| www | `font_pt` | `typography.body_font_pt` | template-implied |
| www | `margin_mm` | `geometry.margin_floor_mm` | official |
| www | `float_spec` | `float_policy.float_spec` | derived |
| www | `overwide_fig_threshold_mm` | `float_policy.figure_width.overwide_threshold_mm` | derived |
| www | `eq_fleqn_allowed` | `texopt_flat.eq_fleqn_allowed` | derived |
| www | `enable_quality_macros` | `texopt_flat.enable_quality_macros` | derived |


## 3. 模板是怎么进入优化过程的（代码路径）

```
python3 optimize.py paper.tex --conference aaai
  │
  ├─ texopt.conference.load('aaai')        # 读 templates-v2/aaai.json
  │    PROJECTIONS 表：json 路径 → Requirement 字段（带 basis 门控）
  │      L 字段只接受 basis ∈ {official, template-implied, inferred}
  │      其余（density_targets/*_observed/position_prior）→ soft，仅参考
  ├─ Requirement.load(base=<投影字段>)     # 会议优先级最低
  ├─ conference.apply_to(req, profile)     # 写字段 + 页数口径 + 附 soft/deferred
  ├─ core.Optimizer.run()                  # 与不指定会议同一条代码路径
  │    score.l_violations()：官方硬约束 → 违规（L）
  │    score.page_status()：页数按正文页/总页口径（pdftotext 定位参考文献首页）
  └─ finalize()：报告 + state.json 附 conference 块（合理性核对、未接入项）
```

语义约定：

| 模板内容 | 用途 | 说明 |
|---|---|---|
| hard_constraints（official/template-implied/inferred） | **违规判定（L）** | 不满足即不计入验收达标 |
| 页数上限 | L | 默认按「正文页」口径：pdftotext 找参考文献首页 k，下界 k−1 超限才判违规（避免把恰好写到参考文献首页的合法论文误判） |
| 官方最小边距 margin_floor_mm | L（下限语义） | 低于才判违规；高于不干预，**不得把合法的宽/不对称边距改小** |
| typography.caption_* / density_targets / observed / position_prior | **合理性参考** | 只写进报告（reasonableness），不进 L、不参与 A 打分 |
| 无对应字段/动作的项 | **明确记录** | 见下方第 2 节，不强行接入 |

优先级（从低到高）：会议模板 < --require 文件 < --settings < CLI 参数。不指定 --conference 时 `base=None`，代码路径与行为与以前完全一致。

## 4. 暂时没有用上的内容汇总

共 33 类原因（合计 376 条记录）：

- 匿名要求：texopt 没有匿名检查/清理动作（不在白名单）（16 条）
- 已用于 typography.body_font_pt 投影（不重复接入）（16 条）
- 栏数：需改 documentclass（texopt 明确不改文档类）（16 条）
- 题注字号/位置等细节：本版无对应动作（不改 caption 样式），仅作参考（16 条）
- 几何观测值与版心尺寸：仅作参考（texopt 只消费 margin_floor_mm）（16 条）
- 浮动体统计与位置先验：仅作参考（texopt 只消费 float_spec 与超宽阈值）（16 条）
- 样本统计量：只用于『排版是否合理』的参考核对，不作硬约束（16 条）
- 设计期优化建议（priority/actions/avoid/unsupported）：供人工与后续自动化消费（16 条）
- 可信度元信息（样本量/可靠字段/冲突）：供报告展示（16 条）
- 来源清单：溯源信息（16 条）
- 字段级 basis 登记：溯源信息（16 条）
- 统计口径：溯源信息（16 条）
- 生成器信息：溯源信息（16 条）
- 题注字号与位置：本版无对应动作（只比对，不改）（16 条）
- 四边边距明细：已折算为 margin_floor_mm（不对称边距需后续字段支持）（15 条）
- 纸张尺寸：需改文档类/geometry 选项（后续阶段）（15 条）
- 版心宽：仅作参考（set_margin 只改边距，不改版心）（15 条）
- 附录政策：texopt 不改内容，仅记录（13 条）
- 栏间距：需改文档类/宏包（后续阶段）（13 条）
- 参考文献风格：需换 .bst/宏包，属跨文档类迁移（后续阶段）（11 条）
- 页码策略：需改模板页脚/样式（后续阶段）（11 条）
- 录用后加页规则：本次按投稿版口径，不加页（11 条）
- 附录计页：仅用于口径说明（9 条）
- 标题格式：需改文档类/模板（后续阶段）（8 条）
- 字体族：需换文档类/宏包（跨类迁移，后续阶段）（8 条）
- 版心高：仅作参考（6 条）
- checklist：texopt 不生成也不检查（内容层，不在白名单）（5 条）
- 行距：当前无对应白名单动作（属版心参数）（5 条）
- 浮动体规则描述：已部分体现为 float_spec，其余为文字说明（2 条）
- 摘要字数限制：属内容层，texopt 不改内容（2 条）
- 图题位置：无对应动作（不改 caption 样式）（1 条）
- 表题位置：无对应动作（1 条）
- 四边最小边距：texopt 压页下限，不得低于此值：basis=sample-stat 不是官方来源（仅 ('official', 'template-implied', 'inferred')），按任务要求不作硬约束（1 条）

## 2. 暂未接入的内容（明确记录，不强行加入）

共 376 条记录，按原因分组：

### 匿名要求：texopt 没有匿名检查/清理动作（不在白名单）（16）

- 涉及字段：`hard_constraints.anonymity`
- 涉及会议：16 个（aaai, acl, cvpr, eccv, emnlp, iccv, iclr, icml, ijcai, kdd, neurips, nsdi, osdi, siggraph, sosp, www）

### 已用于 typography.body_font_pt 投影（不重复接入）（16）

- 涉及字段：`hard_constraints.body_font_size_pt`
- 涉及会议：16 个（aaai, acl, cvpr, eccv, emnlp, iccv, iclr, icml, ijcai, kdd, neurips, nsdi, osdi, siggraph, sosp, www）

### 栏数：需改 documentclass（texopt 明确不改文档类）（16）

- 涉及字段：`hard_constraints.columns`
- 涉及会议：16 个（aaai, acl, cvpr, eccv, emnlp, iccv, iclr, icml, ijcai, kdd, neurips, nsdi, osdi, siggraph, sosp, www）

### 题注字号/位置等细节：本版无对应动作（不改 caption 样式），仅作参考（16）

- 涉及字段：`typography`
- 涉及会议：16 个（aaai, acl, cvpr, eccv, emnlp, iccv, iclr, icml, ijcai, kdd, neurips, nsdi, osdi, siggraph, sosp, www）

### 几何观测值与版心尺寸：仅作参考（texopt 只消费 margin_floor_mm）（16）

- 涉及字段：`geometry`
- 涉及会议：16 个（aaai, acl, cvpr, eccv, emnlp, iccv, iclr, icml, ijcai, kdd, neurips, nsdi, osdi, siggraph, sosp, www）

### 浮动体统计与位置先验：仅作参考（texopt 只消费 float_spec 与超宽阈值）（16）

- 涉及字段：`float_policy`
- 涉及会议：16 个（aaai, acl, cvpr, eccv, emnlp, iccv, iclr, icml, ijcai, kdd, neurips, nsdi, osdi, siggraph, sosp, www）

### 样本统计量：只用于『排版是否合理』的参考核对，不作硬约束（16）

- 涉及字段：`density_targets`
- 涉及会议：16 个（aaai, acl, cvpr, eccv, emnlp, iccv, iclr, icml, ijcai, kdd, neurips, nsdi, osdi, siggraph, sosp, www）

### 设计期优化建议（priority/actions/avoid/unsupported）：供人工与后续自动化消费（16）

- 涉及字段：`optimization_policy`
- 涉及会议：16 个（aaai, acl, cvpr, eccv, emnlp, iccv, iclr, icml, ijcai, kdd, neurips, nsdi, osdi, siggraph, sosp, www）

### 可信度元信息（样本量/可靠字段/冲突）：供报告展示（16）

- 涉及字段：`confidence`
- 涉及会议：16 个（aaai, acl, cvpr, eccv, emnlp, iccv, iclr, icml, ijcai, kdd, neurips, nsdi, osdi, siggraph, sosp, www）

### 来源清单：溯源信息（16）

- 涉及字段：`sources`
- 涉及会议：16 个（aaai, acl, cvpr, eccv, emnlp, iccv, iclr, icml, ijcai, kdd, neurips, nsdi, osdi, siggraph, sosp, www）

### 字段级 basis 登记：溯源信息（16）

- 涉及字段：`traceability`
- 涉及会议：16 个（aaai, acl, cvpr, eccv, emnlp, iccv, iclr, icml, ijcai, kdd, neurips, nsdi, osdi, siggraph, sosp, www）

### 统计口径：溯源信息（16）

- 涉及字段：`data_basis`
- 涉及会议：16 个（aaai, acl, cvpr, eccv, emnlp, iccv, iclr, icml, ijcai, kdd, neurips, nsdi, osdi, siggraph, sosp, www）

### 生成器信息：溯源信息（16）

- 涉及字段：`generated_by`
- 涉及会议：16 个（aaai, acl, cvpr, eccv, emnlp, iccv, iclr, icml, ijcai, kdd, neurips, nsdi, osdi, siggraph, sosp, www）

### 题注字号与位置：本版无对应动作（只比对，不改）（16）

- 涉及字段：`typography.caption_font_pt / caption_position`
- 涉及会议：16 个（aaai, acl, cvpr, eccv, emnlp, iccv, iclr, icml, ijcai, kdd, neurips, nsdi, osdi, siggraph, sosp, www）

### 四边边距明细：已折算为 margin_floor_mm（不对称边距需后续字段支持）（15）

- 涉及字段：`hard_constraints.margins_mm`
- 涉及会议：15 个（aaai, acl, cvpr, eccv, emnlp, iccv, iclr, icml, ijcai, kdd, neurips, nsdi, osdi, siggraph, www）

### 纸张尺寸：需改文档类/geometry 选项（后续阶段）（15）

- 涉及字段：`hard_constraints.paper_size`
- 涉及会议：15 个（aaai, acl, cvpr, emnlp, iccv, iclr, icml, ijcai, kdd, neurips, nsdi, osdi, siggraph, sosp, www）

### 版心宽：仅作参考（set_margin 只改边距，不改版心）（15）

- 涉及字段：`hard_constraints.text_width_mm`
- 涉及会议：15 个（aaai, acl, cvpr, eccv, iccv, iclr, icml, ijcai, kdd, neurips, nsdi, osdi, siggraph, sosp, www）

### 附录政策：texopt 不改内容，仅记录（13）

- 涉及字段：`hard_constraints.appendix_allowed`
- 涉及会议：13 个（aaai, acl, cvpr, eccv, emnlp, iccv, iclr, icml, kdd, neurips, nsdi, siggraph, www）

### 栏间距：需改文档类/宏包（后续阶段）（13）

- 涉及字段：`hard_constraints.column_gap_mm`
- 涉及会议：13 个（aaai, acl, cvpr, emnlp, iccv, icml, ijcai, kdd, nsdi, osdi, siggraph, sosp, www）

### 参考文献风格：需换 .bst/宏包，属跨文档类迁移（后续阶段）（11）

- 涉及字段：`hard_constraints.bib_style`
- 涉及会议：11 个（aaai, acl, eccv, emnlp, iclr, icml, ijcai, kdd, neurips, siggraph, www）

### 页码策略：需改模板页脚/样式（后续阶段）（11）

- 涉及字段：`hard_constraints.page_numbering`
- 涉及会议：11 个（aaai, acl, cvpr, emnlp, iccv, iclr, ijcai, nsdi, osdi, siggraph, sosp）

### 录用后加页规则：本次按投稿版口径，不加页（11）

- 涉及字段：`hard_constraints.camera_ready_extra_pages`
- 涉及会议：11 个（acl, eccv, emnlp, iclr, icml, ijcai, kdd, neurips, nsdi, osdi, siggraph）

### 附录计页：仅用于口径说明（9）

- 涉及字段：`hard_constraints.appendix_counted`
- 涉及会议：9 个（acl, emnlp, iclr, icml, kdd, neurips, nsdi, siggraph, www）

### 标题格式：需改文档类/模板（后续阶段）（8）

- 涉及字段：`hard_constraints.title_format`
- 涉及会议：8 个（aaai, acl, cvpr, eccv, iccv, icml, ijcai, osdi）

### 字体族：需换文档类/宏包（跨类迁移，后续阶段）（8）

- 涉及字段：`hard_constraints.body_font_family`
- 涉及会议：8 个（acl, cvpr, eccv, emnlp, iccv, ijcai, osdi, sosp）

### 版心高：仅作参考（6）

- 涉及字段：`hard_constraints.text_height_mm`
- 涉及会议：6 个（cvpr, eccv, iccv, nsdi, osdi, sosp）

### checklist：texopt 不生成也不检查（内容层，不在白名单）（5）

- 涉及字段：`hard_constraints.checklist_required`
- 涉及会议：5 个（aaai, acl, emnlp, ijcai, neurips）

### 行距：当前无对应白名单动作（属版心参数）（5）

- 涉及字段：`hard_constraints.line_spacing`
- 涉及会议：5 个（cvpr, iccv, nsdi, osdi, sosp）

### 浮动体规则描述：已部分体现为 float_spec，其余为文字说明（2）

- 涉及字段：`hard_constraints.float_placement_rules`
- 涉及会议：2 个（aaai, neurips）

### 摘要字数限制：属内容层，texopt 不改内容（2）

- 涉及字段：`hard_constraints.abstract_max_words`
- 涉及会议：2 个（acl, emnlp）

### 图题位置：无对应动作（不改 caption 样式）（1）

- 涉及字段：`hard_constraints.figure_caption_position`
- 涉及会议：1 个（aaai）

### 表题位置：无对应动作（1）

- 涉及字段：`hard_constraints.table_caption_position`
- 涉及会议：1 个（aaai）

### 四边最小边距：texopt 压页下限，不得低于此值：basis=sample-stat 不是官方来源（仅 ('official', 'template-implied', 'inferred')），按任务要求不作硬约束（1）

- 涉及字段：`geometry.margin_floor_mm`
- 涉及会议：1 个（sosp）

