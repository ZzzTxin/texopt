# 人类成对比较数据（阶段 7 步骤三）

方案 10.3 步骤三：小规模人类成对比较 → Bradley–Terry / 偏好学习 → **带置信区间的权重**。
本目录用于放这批数据；**当前为空**（未采集），因此 `aesthetic_weights.json` 里
`human_calibration = null`，权重只来自步骤二消融。

## 文件

* `pairs.json` —— 采集到的成对比较（数组）。缺文件时工具如实记 null，不伪造数据。
* `pairs.example.json` —— 格式示例（两对，仅供参照，**不是**真实标注）。

## 格式

```json
[
  {"a": {"balance.d_mid": 0.31, "density.coverage_text": 1.12},
   "b": {"balance.d_mid": 1.86, "density.coverage_text": 0.24},
   "winner": "b",
   "note": "可选：人判断的理由"}
]
```

* `a` / `b`：两侧的**逐维归一化带外损失**（越大越差）。取值来源：
  - 单页：`aesthetic_shadow.json` → `per_page[].losses`，再按该页所属档用
    `Detector.norm_loss()` 归一；或
  - 整篇：`paper.dim_norm_top`（论文级池化值）。
* `winner`：`"a"` 或 `"b"`（人选的更顺眼的一侧）。
* 未给出的维度按 0 处理；**同一批数据必须用同一套维度**。

## 采集工具（阶段 8 新增，2026-10-01）

人工填指标既慢又易错，所以有了 `tools/make_pairs.py`：它从缓存页指标里挑页、算好
逐维归一化损失、配对（同一篇论文内的两页，保证“主导维明显、其余维接近”）、
把两页渲染成 PNG，生成一个**离线打分表**。人只需要选“左边/右边更顺眼”。

```bash
cd datasets/conf-specs
python3 tools/make_pairs.py --sheet --pairs 30          # 生成打分表（约 1 分钟）
# 浏览器打开 workbench-eval/pairs_sheet/sheet.html，逐对选择，
# 把页面底部文本框里的 JSON 复制存成 answers.json
python3 tools/make_pairs.py --import answers.json        # -> human/pairs.json
python3 tools/make_pairs.py --stats                      # 看覆盖度（对数/论文数）
python3 tools/calibrate_weights.py --pairs human/pairs.json --apply
```

细节：左右**随机**摆放（`display` 记在 `sheet.json` 里，导入时再映射回 a/b），避免位置偏差；
打分表**不显示指标值**（防止人向指标看齐）；三类对（都不错 / 都差 / 混合）各占 1/3，
主导维分散在 5 个维上。图与打分表放在 `workbench-eval/pairs_sheet/`（运行产物，不入库）。

## 采集建议（避免权重只学到极端对比）

* ≥ 30 对，覆盖 ≥ 6 篇论文；同一篇论文最多 6 对（防止单篇主导）。
* 混入两类：①**两者都不错**（差异细微）②**两者都差**；只有「好 vs 烂」会让权重退化成
  「谁最烂」的检测器。
* 每对尽量只让**一个维度**有明显差异，其余接近 —— 否则权重不可辨识。

## 用法

```bash
cd datasets/conf-specs
python3 tools/calibrate_weights.py --pairs ../human/pairs.json --apply
```

跑完 `aesthetic_weights.json` 的 `method` 变为 `ablation+human`，每维保留
`w`（消融）与 `w_human`（人类标定）；12.5 的 Spearman 相关性也会在这一步才可报告
（样本 < 8 对不给结论）。

> 注意：即便有了人类标定，**λ 仍是 0**。把 λ 接进验收口径属于改变优化目标，
> 需要用户明确审批（见 `docs/stage7_weight_calibration.md` §6）。
