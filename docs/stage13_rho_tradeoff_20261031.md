# 阶段 13：ρ 的无差异点重标定（0.341 → 15，2026-10-31）

> 结论先行：`score.W_PAGE_DEFECT`（即 ρ，model1 里 P 与 I 的汇率）从**闭环平均代价**口径的
> 0.341 改为**人工无差异点**口径的 **15**（区间约 [5, 32]，单人评分）。
> artifact：`metrics/rho_tradeoff_20261031.json`；旧值留档于 `metrics/rho_exchange_rate.json`。
> 回归：`python3 tests/run_tests.py` → **307 通过 / 0 失败 / 0 跳过**。

---

## 1　为什么旧口径不行

旧 ρ 由闭环实测得出：ρ = ΔI / (−ΔP)，4 篇文档 / 43 次动作，其中只有 6 次动作 `ΔI > 0`
（浮动体 `[H]→[tbp]`、超宽图归一）。中位 0.341。

问题在**选择效应**：那些动作是优化器「愿意试且被接受」的，天然落在「修得值」的一侧。
它回答的是「过去我们按什么汇率修过」，而不是「人认为修 1 个缺陷值多少代价」。
换掉被选中的样本，汇率就漂。另一个副作用是稀疏：43 次里 37 次 `cost = 0`，
ρ 的置信区间完全靠 6 个点撑着。

## 2　新方法：无差异点（等边际收益）

对每类缺陷，生成一对页面：

- **A**：保留缺陷；
- **B**：缺陷修好，但付出**已知代价** c（I 单位）。

人工三选一（A / B / 差不多），逐档加价，取偏好的**转折点** c\*，于是
`ρ_缺陷 = c* / w_缺陷`（w 为该项 P 权重）。这就是「修 1 单位缺陷 ≈ 抵消多少单位干预代价」。

| 轮次 | 设计 | 题数 | ρ 中位 |
|---|---|---|---|
| 第一轮 `make_tradeoff_sheet.py` | 5 缺陷 × 3 档，货币 = 边距 +12/+20/+30mm（I = 6/10/15） | 15 | **16.67** |
| 第二轮 `make_tradeoff_v2.py` | 边界加密（c\*±2）+ 字号货币（+1/+2 档，I = 3/6）+ 4 题一致性自检 | 18（含自检） | **13.33** |
| 复核 `make_tradeoff_check.py` | 3 空题（左右同页）+ 3 明显差异（2×c\*） | 6 | 6/6 正确 |
| **取值** | 两轮中位的中位 | — | **15** |

逐缺陷 c\*（I 单位）：widefig 13–15、overfull 10.5–12.5、vspace 8–10、
narrowtable 8–10、widetable 6–8。overfull 的 ρ（31–38）明显偏高、
widetable 偏低（5–7）——即 P 权重里这两项的个体偏差没校准，见 §5。

字号货币的交叉验证：4 类缺陷 × 2 档字号全部选「修好版」，说明 2 档字号（I = 6）
仍低于边距转折点（8–13）；反推 1 档字号 ≈ 4–6 I ≈ 8–12mm 边距，
与代码里的 3.0/档（≈6mm）同量级 —— `I` 内部「字号 : 边距」比例首次有了证据。

## 3　口径含义

ρ = 15 意味着：**人愿意用 30mm 级别的边距改动去换 1 个加权缺陷的修复**。
比 0.341 高约 44 倍，和「过去实现过度死守原版心、宁可留缺陷也不动版心」的观察一致。
副作用要盯：ρ 变高会让「有代价的动作」更容易被接受，需重新检查是否变成乱动版心
（见 §4 待办第 1 条）。

## 4　待办（下一步）

1. **ρ=15 的端到端影响未复测**：需在 `examples/{demo,issues,aidtest,nightmare,chaos}` 上
   对比 ρ=0.341 / 15 的 `accepted` 动作数、页数、L、M1，确认没有被校准带偏。
2. P 权重个体偏差（overfull 偏低约 2×、tab_overwide 偏高约 2.5×）需第二评分人复核。
3. I 的三个系数（字号 3.0/档、边距 0.5/mm、浮动体 0.4/处、图宽 0.4/处）里，
   「字号–边距」已验证同量级，「浮动体/图宽 vs 边距」仍无证据。
4. 单人评分（n_raters = 1）：区间 [5,32] 主要反映同一人的前后差异，不是人群方差。

## 5　复现

```bash
cd /mnt/d/桌面/texopt
python3 tools/make_tradeoff_sheet.py --build    # 第一轮 15 题 → workbench-tradeoff/sheet
python3 tools/make_tradeoff_sheet.py --import answers.json
python3 tools/make_tradeoff_v2.py --build       # 第二轮 → workbench-tradeoff2/
python3 tools/make_tradeoff_v2.py --import answers.json
python3 tools/make_tradeoff_check.py --build    # 一致性复核 → workbench-tradeoff-check/
python3 tools/make_tradeoff_check.py --import answers.json
```

产物：`workbench-tradeoff*/{,sheet,build}`（页面图 + key.json + 作答结果）；
落在代码里的只有一个数：`texopt/score.py::W_PAGE_DEFECT`。
