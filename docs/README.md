# docs 索引

> 2026-10-31 整理：本目录区分「**现行规范**」与「**阶段记录（历史证据）**」。
> 读文档时先看前者；后者只在追溯"这个数怎么来的"时才需要。

## 现行规范（看这三份就够）

| 文档 | 内容 |
|---|---|
| [`../README.md`](../README.md) | 项目总览：定位、闭环、动作面、模板、环境要求、目录结构、测试 |
| [`scoring/README.md`](scoring/README.md) | **打分模型**：gate / model1（ρ·P+I）/ model2 / 验收规则 / 权重来源 / 字段 / 局限 |
| [`aesthetic/README.md`](aesthetic/README.md) | **审美量化**：`page_metrics.v1`、`A_soft` 参数、视觉缺陷、`A_profile`、标定与验证 |

数据与结构规范：

| 文档 | 内容 |
|---|---|
| [`page_metrics_v1.md`](page_metrics_v1.md) | 页面级指标 schema（字段、status、provenance） |
| [`corpus_inventory_20261026.md`](corpus_inventory_20261026.md) | 语料层采集清单（采集了什么、分析了什么、哪些留白） |
| [`corpus_fields_plain_20261026.md`](corpus_fields_plain_20261026.md) | 上述每一项字段的白话解释 |

## 阶段记录（历史证据，不是现行口径）

按时间顺序，每份都带「当时的问题 / 改了什么 / 复测数字 / 局限」。
**若与上面三份现行规范冲突，以现行规范 + 代码为准。**

| 文档 | 阶段 |
|---|---|
| [`stage0_visual_inventory.md`](stage0_visual_inventory.md) | 0：指标盘点 + schema 定型 |
| [`stage1_role_and_extraction.md`](stage1_role_and_extraction.md) | 1：页面角色 + 全库提取 |
| [`stage2_profile.md`](stage2_profile.md) | 2：审美档案（分位/CI/去冗余） |
| [`stage3_whitespace.md`](stage3_whitespace.md) | 3：留白结构化（五类） |
| [`stage4_aesthetic_profile.md`](stage4_aesthetic_profile.md) | 4：马氏距离 + 带外损失 |
| [`stage5_eval_protocol.md`](stage5_eval_protocol.md) | 5：评测协议 12.1–12.6 |
| [`stage6_shadow_integration.md`](stage6_shadow_integration.md) | 6：影子接入（λ=0） |
| [`stage7_weight_calibration.md`](stage7_weight_calibration.md) | 7：权重校准（消融 + BT） |
| [`stage8_eval_external.md`](stage8_eval_external.md) | 8：外部验证（E1/E2/E3 + 两条负面结果） |
| [`stage9_detector_check_20261027.md`](stage9_detector_check_20261027.md) | 9：检测器体检（精度/漏检/band 口径） |
| [`stage10_a_soft_smooth_form_20261028.md`](stage10_a_soft_smooth_form_20261028.md) | 10：A_soft 改平滑目标形式 |
| [`stage10b_pair_sheet_20261028.md`](stage10b_pair_sheet_20261028.md) | 10b：成对比较验收表（12 对） |
| [`stage11_severity_sheet_20261028.md`](stage11_severity_sheet_20261028.md) | 11：缺陷严重度标定（BT + 频率） |
| [`stage12_gate_exit_two_lines_20261030.md`](stage12_gate_exit_two_lines_20261030.md) | 12：gate 退出 + 两线分离 + P 权重回填 + ρ |
| [`stage13_rho_tradeoff_20261031.md`](stage13_rho_tradeoff_20261031.md) | 13：ρ 无差异点重标定（0.341 → 15） |
| [`stage14_pweight_unified_20261102.md`](stage14_pweight_unified_20261102.md) | 14：P 权重统一到无差异点口径（口径 A） |
| [`stage15_local_global_20261102.md`](stage15_local_global_20261102.md) | 15：连档压页修复 + 单页打分/整篇打分的分层诊断 |

## 其他

| 路径 | 说明 |
|---|---|
| `model_v3_design_20261014.html` / `_single.html` | v3 结构设计说明（带公式图，可离线打开） |
| `model_v3_design_20261014.template.html` | 上者的模板 |
| `make_formula_doc.py` | 由公式表生成上面两个 HTML（需 TeX 渲染公式） |
| `formula_doc_assets/*.svg` | 公式图资产（上面两个 HTML 引用） |
| `notes/frequency_weighting_idea_20261016.md` | 早期想法记录：按"频率 × 严重度"定权重（已落地为阶段 11） |

## 已删除（2026-10-31 清理，可从 git 历史取回）

| 删除对象 | 原因 |
|---|---|
| `model_v2_formulas_*`（md/tex/pdf）、`model_v2_explained_*`（html/template/single） | v2 的 `total = L+A+I` 单一总分已被 v3 取代，公式与解释已在 `scoring/` 与 `aesthetic/` 重写 |
| `weight_calibration_plan_20261016.md` | 计划已全部执行完，结果与口径分别落在阶段 7/11 与 `scoring/README.md` |
| `corpus_report_20261026.md` | 由 `tools/corpus_analyze.py` 生成的报告，可随时重建 |
