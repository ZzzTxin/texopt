# 阶段 8：外部验证（方案 13）

生成时间：2026-10-01T11:34:20 ｜ 用时 2471.2s

> 诚实边界：E1 走真编译，检验的是「实现-口径自洽 + 修复能力」；
> E2 的两条路径读同一批 PDF（渲染/解析路径不同），不是两套完全独立的链路；
> E3 复用真实论文缓存指标，λ 恒为 0，只改报告口径、不改验收。

## E1 端到端退化（真实文档 + 真实优化器，真编译）

- 文档 4 篇；退化档 `[('vspace',), ('vspace', 'pagebreak'), ('vspace', 'pagebreak', 'float_H'), ('vspace', 'pagebreak', 'float_H', 'overwide')]`（逐档累加）
- **退化态 A（修复前）对退化档单调不降：3/4**（最重档 ≥ 最轻档：3/4）
- **退化态影子 A_profile 同向：0/4**
- 闭环修复后 A 回到 ≤ 干净稿：**3/4**（且 ≤ 自身退化态：4/4）

每组：干净稿 A ｜ 逐档退化态 A（修复前）｜ 逐档闭环修复后 A。

### neurips-real

- 干净稿 A=17.8（24 页，状态 DONE）
- 退化态 A（修复前）：58.74 → 59.74 → 61.24 → 65.24
- 闭环修复后 A：17.8 → 17.8 → 17.8 → 17.8
- 退化态影子 A_profile：1.119428 → 1.119428 → 1.044011 → 2.942058
- 判定：单调 `True`、可见 `True`、影子同向 `False`、回到干净 `True`、低于修复前 `True`

### paper-real

- 干净稿 A=3.1（11 页，状态 DONE）
- 退化态 A（修复前）：25.88 → 25.4 → 21.9 → 22.9
- 闭环修复后 A：3.7 → 6.5 → 6.5 → 7.5
- 退化态影子 A_profile：1.32879 → 1.307907 → 1.490456 → 1.490456
- 判定：单调 `False`、可见 `False`、影子同向 `False`、回到干净 `False`、低于修复前 `True`

### demo-fixture

- 干净稿 A=0.48（6 页，状态 DONE）
- 退化态 A（修复前）：2.9 → 5.5 → 6.18 → 9.8
- 闭环修复后 A：0.48 → 0.48 → 0.48 → 0.48
- 退化态影子 A_profile：0.574243 → 3.148669 → 3.171488 → 2.841139
- 判定：单调 `True`、可见 `True`、影子同向 `False`、回到干净 `True`、低于修复前 `True`

### issues-fixture

- 干净稿 A=0.78（2 页，状态 DONE）
- 退化态 A（修复前）：9.2 → 10.2 → 10.2 → 14.5
- 闭环修复后 A：0.78 → 0.78 → 0.78 → 0.3
- 退化态影子 A_profile：4.566816 → 4.566816 → 4.566816 → 4.344507
- 判定：单调 `True`、可见 `True`、影子同向 `False`、回到干净 `True`、低于修复前 `True`

## E2 第二套工具链复测（矢量/文本层 vs 像素层）

- 论文 12 篇，dpi 50，每篇最多 8 页

| 矢量层 | 像素层 | 同量纲 | 中位 ρ | 最低 ρ | 中位 \|Δ\| | 退化篇数 |
|---|---|---|---|---|---|---|
| `whitespace.total_ratio` | `non_ink_ratio` | 否 | 0.5833 | 0.2381 | 0.7379 | 0/12 |
| `whitespace.trailing_ratio` | `bottom_blank` | 是 | None | None | 0.045 | 12/12 |
| `balance.visual_centroid_y` | `centroid_y` | 是 | 0.1852 | -0.6667 | 0.0223 | 0/12 |

末页对照（`whitespace.trailing_ratio` vs `bottom_blank`，每篇取**抽样范围内最后一页**，n=12，其中矢量侧非零 0 篇）：Spearman ρ=None、中位 \|Δ\|=0.045。
（抽样窗口内矢量侧 trailing_ratio 恒为 0 —— 该量在排满的正文页上无取值，所以这一对的页级秩相关在 8 页窗口里无可辨识性；该量在语料上的覆盖率见 E3。）

## E3 论文级报告

- 论文 60 篇；论文级 A_profile 中位 **0.7664**（P90 1.3885）

| 维度 | 页数（页级值个数） | 页级池化中位 |
|---|---|---|
| `alignment.center_var` | 735 | 0.0 |
| `balance.d_mid` | 765 | 0.0 |
| `balance.visual_centroid_y` | 765 | 0.0 |
| `density.coverage_text` | 765 | 0.0 |
| `ratio.fig_text` | 238 | 0.0 |
| `whitespace.total_ratio` | 765 | 0.0 |

原始量在语料上的可辨识性（非空且非零的页占比）：

| 原始量 | 有效页数 | 非零页数 | 非零占比 |
|---|---|---|---|
| `balance.d_mid` | 765 | 757 | 0.9895 |
| `balance.visual_centroid_y` | 765 | 765 | 1.0 |
| `density.coverage_text` | 765 | 759 | 0.9922 |
| `ratio.fig_text` | 759 | 311 | 0.4097 |
| `whitespace.total_ratio` | 765 | 764 | 0.9987 |
| `whitespace.trailing_ratio` | 765 | 46 | 0.0601 |

## E4 缺陷敏感性（A_profile 的 λ 前置门）

- 文档 4 篇；退化档 `[['vspace'], ['vspace', 'pagebreak'], ['vspace', 'pagebreak', 'float_H'], ['vspace', 'pagebreak', 'float_H', 'overwide']]`（源码级注入 + 真编译，每档只编一次）
- **λ 可用 = False**（2 个维对源码级退化无响应（alignment.center_var, ratio.fig_text））

| 维 | 响应篇数 | 单调篇数 | 中位 Δ | 判定 |
|---|---|---|---|---|
| `alignment.center_var` | 1/4 | 2 | 0.0 | blind |
| `balance.d_mid` | 4/4 | 2 | 1.468609 | responds |
| `balance.visual_centroid_y` | 4/4 | 1 | 2.836499 | responds |
| `density.coverage_text` | 4/4 | 1 | 0.903651 | responds |
| `ratio.fig_text` | 0/2 | 1 | 0.0 | blind |
| `whitespace.total_ratio` | 4/4 | 1 | 1.712468 | responds |

（λ>0 会被代码拦下：`shadow.assert_lambda_allowed()` 读 `metrics/profiles/profile_sensitivity.json`；λ=0 不受影响。）

