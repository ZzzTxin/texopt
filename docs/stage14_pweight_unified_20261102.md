# 阶段 14：P 权重的「同一把尺子」标定（2026-11-02）

> 结论先行：`PAGE_DEFECT_WEIGHT` 里 7 项从两套不同口径（human×corpus / 先验拍值）统一到
> **人判无差异点 c\***，即 `w = c*/ρ`；再按**口径 A**（总权重和不变，ρ=15 继续锚定）
> 缩放进代码。overfull 0.33 → **1.696**，vbox_over 2.344 → **0.737**，
> tab_overwide 1.2 → **1.033**。作答 33 题（两轮阶梯 + 4 道空题全对）。
> artifact：`metrics/p_weight_tradeoff_20261102.json`（原始估计）、
> `metrics/pweight_applied_20261102.json`（落地值）。

---

## 1　问题：P 的内部结构是两张皮

阶段 11/12 之后，`PAGE_DEFECT_WEIGHT` 的 11 项里有 5 项是「人判严重度 ÷ 语料频率」，
其余是 9 月手拍的先验。两套口径不可比：

- human×corpus 是**每篇文档**的相对代价，先验是**每次出现**的严重度；
- 阶段 13 的 ρ 标定反推出的逐缺陷汇率（overfull ≈ 31–38、widetable ≈ 5–7，中位 15）
  说明这两套值确实偏了，且方向相反（overfull 偏低、tab_overwide 偏高）。

要修的是「同一把尺子」：所有缺陷都用同一个问题问——**保留这个缺陷** vs
**修掉它但页边距加宽 c mm**，取无差异点 c\*，则 `w = c*/ρ`。

## 2　方法：两轮阶梯 + 翻转区间

| 轮次 | 设计 | 题数 | 结果 |
|---|---|---|---|
| 第一轮 `workbench-pweight` | 7 缺陷 × 2 档，边距 +16/+30mm（I = 8/15）+ 2 空题 | 14 | **全部在最低档就判「缺陷更好」**，c\* 只到上界 8 |
| 第二轮 `workbench-pweight2` | 同 7 缺陷 × 3 档，+4/+8/+12mm（I = 2/4/6）+ 2 空题 | 19 | 六类在 4–12mm 全判「差不多」，16mm 起翻成「缺陷更好」 |

单轮都会贴边界（分别贴 8 和 2），所以把两轮的点并到同一条 `b(c)` 曲线上估：

```
b(c) = 1  选「修好版」     b(c) = 0.5  选「差不多」     b(c) = 0  选「缺陷版」
c_lo = b ≥ 0.5 的最大代价（还愿意修）      c_hi = b = 0 的最小代价（开始宁留缺陷）
c* = (c_lo + c_hi)/2；只有一侧时，取该侧作为上/下界
```

overfull 与 tab_overwide 两轮只各有一次「缺陷更好」，用阶段 13 的先验区间
（10.5–12.5 / 6–8）收窄，避免单点定值。

## 3　结果

| 缺陷 | 点（I, b） | c\* | 原始 w = c\*/15 | 旧值 | 口径 A 落地 |
|---|---|---|---|---|---|
| overfull | (12.5, 0) + 先验 | 11.5 | 0.767 | 0.33 | **1.696** |
| floatwarn | (2,.5)(4,.5)(6,.5)(8,0) | 7.0 | 0.467 | 1.254 | **1.033** |
| spec_H | 同上 | 7.0 | 0.467 | 0.5 | **1.033** |
| vbox_under | (2,.5)(4,.5)(6,.5)(8,0) | 7.0 | 0.467 | 1.4 | **1.033** |
| tab_overwide | (8, 0) + 先验 | 7.0 | 0.467 | 1.2 | **1.033** |
| underfull | (2,.5)(4,.5)(6,**0**)(8,0) | 5.0 | 0.333 | 0.273 | **0.737** |
| vbox_over | (2,.5)(4,.5)(6,**0**)(8,0) | 5.0 | 0.333 | 2.344 | **0.737** |

空题（左右同一页）4/4 全对；第 5、7 题等对照题没有位置偏差信号。

## 4　口径 A：为什么缩放

M1 = **ρ·P + I**，P 的量级变了就必须同步调 ρ，否则等于偷偷改了「最小干预」的强度：

| 口径 | 做法 | 后果 |
|---|---|---|
| **A（采）** | 7 项和从 7.301 → 3.301，整体 ×2.212 拉回 7.301 | ρ=15 继续锚定，只改 P 的内部结构 |
| B | 权重不缩放，ρ 15 → 33.2 | 等于重新锚定，阶段 13 的 A/B 结论不可直接比 |
| C | 都不动 | 缺陷相对代价便宜 2.2×，最小干预被悄悄放松 |

## 6　回填后的行为 A/B（2026-11-02，`tools/pweight_ab_compare.py`）

同一批靶稿分别在**旧权重**与**现行权重**下跑完整闭环（产物 `workbench-pweight-ab/`）：

| 文档 | accepted | 页数 | L | 残余 P | M1 | 状态 |
|---|---|---|---|---|---|---|
| demo | 1 / 1 | 6 / 6 | 0 / 0 | 0 → 0 | 0 → 0 | DONE / DONE |
| issues | 5 / 5 | 2 / 2 | 0 / 0 | 0.3 → 0.3 | 4.9 → 4.9 | DONE / DONE |
| aidtest | 6 / 6 | 2 / 2 | 0 / 0 | 0 → 0 | 0.4 → 0.4 | DONE / DONE |
| nightmare | 17 / 17 | 5 / 5 | 0 / 0 | 3.03 → **4.40** | 46.65 → 67.14 | NEEDS_REVIEW 同 |
| chaos | 16 / 16 | 5 / 5 | 0 / 0 | 0.273 → **0.737** | 6.095 → 13.055 | NEEDS_REVIEW 同 |

读法：

- **动作集合逐个文档完全相同**（accepted 数、页数、L 一致）：这次改的是 P 的内部结构，
  没有在 5 篇靶稿上掀起新的取舍，属于「口径更正」而非「行为改变」。
- **残余 P 上升的两篇都是 overfull 主导**：overfull 0.33 → 1.696（×5.1）后，
  nightmare / chaos 里残留的正是正文行溢出，说明「未覆盖缺陷」里最贵的仍然是这一项，
  后续动作优先级应排在溢出上，而不是继续调权重。
- M1 不可跨权重比较（尺度变了），只能比 accepted / 页数 / 残余缺陷归属。

## 7　局限（必须写进论文）

1. **六类缺陷落在同一无差异带**（4–12mm 都「差不多」，16mm 起「缺陷更好」）：
   本次阶梯只能分辨到「一类」层级，六类的互相差别低于分辨率，不能声称按序排出了强弱。
2. **单人评分**（n_raters = 1），且 c\* 是**中点估计**，区间宽度约 ±1 档（≈2mm）。
3. 代价货币只有边距一种；字号货币在阶段 13 验证过 1 档 ≈ 4–6 I，本轮未复用。
4. `fig_overwide` 未进表（构造未验证），`warn` / `macros_missing` / `unstable_spec` 人不可判，仍是先验。

## 8　复现

```bash
cd /mnt/d/桌面/texopt
python3 tools/make_pweight_sheet.py --build                                  # 第一轮 14 题
python3 tools/make_pweight_sheet.py --import workbench-pweight/answers.json  # 需人工作答
python3 tools/make_pweight_sheet.py --build --costs 2,4,6 --work workbench-pweight2
python3 tools/make_pweight_sheet.py --import workbench-pweight2/answers.json --work workbench-pweight2
python3 tools/pweight_combine.py              # 合并两轮 → metrics/p_weight_tradeoff_20261102.json
python3 tools/pweight_combine.py --apply      # 落地 artifact（口径 A）
python3 tools/pweight_combine.py --check      # 校验 score.py 与 artifact 一致
python3 tools/pweight_ab_compare.py           # 旧权重 vs 现行权重的闭环 A/B
```

辅助工具：`tools/_ink_profile.py`（墨迹行剖面，无视觉能力时验证「压进边距 / 留洞」）、
`tools/pweight_ab_run.py`（单篇 A/B 运行器）。
