# 阶段 5 评测与验收协议报告（方案 12.1-12.6）

- 生成：2026-09-30T18:57:57；语料：608 篇 / 10538 页（缓存指标，离线可复跑）
- 档案：v2；判定维度 8 个：density.coverage_text、whitespace.total_ratio、balance.visual_centroid_y、ratio.fig_text、readability.leading_ratio、alignment.center_var、balance.d_mid、density.coverage_table
- 诚实边界：本协议检验**实现与口径的自洽性**，不等于「与人类审美一致」；12.5 需人类成对比较数据，本阶段未采集（如实记 None，阶段 7 做）。

## 12.1 负样本注入（构造性验证）

- 指标层：81 组「真实页 + 阶梯退化」试验；A_profile 单调上升 **1.0**（容忍 0.1% 回落）/ 严格零回落 0.963；退化页定位命中 **0.963**（全页 D² top-3）、top-1 命中 0.6296、中位名次 1；逐维损失单调 1.0；因无外推空间/无损失可增跳过 0 例

退化方向不是写死的，而是按「推离本档常态区间」逐页选取（非单调带外损失是双向的，写死方向会把正确行为判成失败）。定位命中按角色拆分——`appendix`/`references`/`figure-page` 这类页本身 D² 就高，注入后未必上升到第一，属预期而非缺陷：

| 角色 | 定位命中率（top-3） |
|---|---|
| appendix | 0.7143 |
| body | 1.0 |
| figure-page | 0.8571 |
| references | 1.0 |
| section-head | 1.0 |
| title | 1.0 |

| 退化类型 | A 单调率 |
|---|---|
| break_alignment | 1.0 |
| change_density | 1.0 |
| inject_hole | 1.0 |
| move_float | 1.0 |
| shrink_figure | 1.0 |
| split_paragraph | 1.0 |

| 被注入维度 | 逐维损失单调率 |
|---|---|
| alignment.center_var | 1.0 |
| balance.d_mid | 1.0 |
| balance.visual_centroid_y | 1.0 |
| density.coverage_text | 1.0 |
| ratio.fig_text | 1.0 |
| whitespace.total_ratio | 1.0 |

## 12.2 假阳率（特异性，目标 ≤ 0.05）

- 5 折交叉（**按论文**留出：训练集重建档案 + 定阈值，留出页测误报）

| 口径 | 页数 | 误报 | 假阳率 | 结论 |
|---|---|---|---|---|
| 参数化阈值（χ², p<0.05） | 10536 | 1677 | 0.1592 | 不通过 |
| 经验校准（训练集 D² P95） | 10536 | 602 | 0.0571 | 不通过 |
| 经验校准（训练集 D² P96） | 10536 | 478 | 0.0454 | 通过 |
| 经验校准（训练集 D² P97） | 10536 | 361 | 0.0343 | 通过 |

**卡方假设不成立**：真实页级 D² 比 χ² 重尾（指标重尾/混合 + 每页可用维数不同），参数化阈值把假阳率抬到目标的 3 倍多；发布口径必须用**经验校准阈值**。

按 role（经验校准 P95 口径）：

| role | 页 | 误报 | 假阳率 |
|---|---|---|---|
| appendix | 2530 | 145 | 0.0573 |
| body | 3342 | 179 | 0.0536 |
| figure-page | 484 | 33 | 0.0682 |
| references | 2494 | 141 | 0.0565 |
| section-head | 969 | 60 | 0.0619 |
| table-page | 109 | 11 | 0.1009 |
| title | 608 | 33 | 0.0543 |

误报页按**最偏离维度**归因（逐维假阳率，供 12.6 门槛用）：

| 维度 | 页 | 误报 | 假阳率 |
|---|---|---|---|
| alignment.center_var | 9952 | 37 | 0.0037 |
| balance.d_mid | 10536 | 142 | 0.0135 |
| balance.visual_centroid_y | 10536 | 256 | 0.0243 |
| density.coverage_table | 109 | 0 | 0.0 |
| density.coverage_text | 10536 | 36 | 0.0034 |
| ratio.fig_text | 3412 | 29 | 0.0085 |
| readability.leading_ratio | 3273 | 66 | 0.0202 |
| whitespace.total_ratio | 10536 | 36 | 0.0034 |

## 12.3 会议可分性（有效性 sanity check）

- 参与：573 篇 / 11 个会议（每会 ≥20 篇）
- 论文级画像特征 1-NN 留一准确率 **0.5288**（均匀随机 0.0909，多数类 0.1187，置换检验 p = 0.0099，100 次置换）
- 结论：显著高于随机 → 指标确实抓到了会议风格差异

## 12.4 稳定性与可复现性

- 同文档重复测量：完全一致（5 篇，逐字段 diff）
- DPI 变更：未测 

## 12.5 与人类判断的相关性（探索性）

- **未做**：需要小规模人类成对比较数据，本阶段未采集；按方案要求如实记为 `null`，不得包装成「与人类审美一致」。留待阶段 7（Bradley-Terry 标定）一并做。

## 12.6 验收门槛（逐指标）

- 通过 **6/8** 维；未通过者按方案只能作报告项，不得参与 A（已写入 `eval_gate.json`，在线影子评估会自动剔除）。

| 维度 | 结论 | 未通过原因 |
|---|---|---|
| density.coverage_text | pass | — |
| whitespace.total_ratio | pass | — |
| balance.visual_centroid_y | pass | — |
| ratio.fig_text | pass | — |
| readability.leading_ratio | report-only | 12.1 单调性：未测 |
| alignment.center_var | pass | — |
| balance.d_mid | pass | — |
| density.coverage_table | report-only | 12.1 单调性：未测 |

> 剔除维度：readability.leading_ratio、density.coverage_table

