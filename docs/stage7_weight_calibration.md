# 阶段 7 交付：审美权重校准（方案 10.3 步骤二/三）

> 对应设计方案第十章 10.2/10.3（合成与权重确定路径）与十五章「阶段 7：权重校准（消融 +
> 人类成对比较）→ 启用 λ>0」。
> 代码：`texopt/weights.py`（校准/标定/验收）、`texopt/aesthetic.py`（加权合成与接入）
> 工具：`datasets/conf-specs/tools/calibrate_weights.py`
> 产出：`metrics/profiles/aesthetic_weights.json`、`aesthetic_weights_report.md`，并把权重块挂回
> `aesthetic_profile.json` 的 `weights` 键
> 测试：`tests/run_tests.py::stage7_tests()`（11 项，纯逻辑 + 真实缓存指标）

## 1. 一句话

方案 10.3 的三步**已走到第三步**：**等权（阶段一）→ 消融校准（步骤二）→ 人类成对比较
（步骤三，2026-10-01 采集 8 对并在本人参与下完成标定）**。校准后的相对权重只改
`A_profile` 的**合成口径**（`Σ w·v / Σ w`），并且只有通过「不劣化 + 判别间隔严格改善」
验收才被启用（`applied=true`）；λ 仍为 **0**，不参与优化验收
（而且阶段 8 的 E4 现在会**代码强制**拦下 λ>0，见 `docs/stage8_eval_external.md` §5.2）。

## 2. 步骤二：消融校准怎么算的

每次试验 = 真实论文的一页 × 一个维度 × 按「推离本档常态」方向退化一档（复用阶段 5 的
`pick_degradation` / `inject_doc`，阶梯取中段，避免饱和）。对每个维度同时量：

| 量 | 定义 | 直觉 |
|---|---|---|
| **信号** `signal_d` | 该维被退化时，它的归一化带外损失增量（中位数） | 该动的时候动不动 |
| **噪声** `noise_d` | 对照试验里，该维在**未退化的原页**上的自发损失（P90） | 不该报的时候乱不乱报 |
| 信噪比 | `SN_d = signal_d / (noise_d + 0.05)` | 判别力 |

`w_d = SN_d` 先归一到均值 1，再裁剪到 `[0.25, 4.0]`；置信区间用**按论文聚类的 bootstrap**
（重采样论文而不是页 —— 同篇论文的页高度相关，按页重采样会把 CI 假性收窄，与阶段 2 同口径）。

## 3. 结果（80 组试验，bootstrap 200 次）

| 维度 | w | CI (5%, 95%) | 信号 | 噪声 | SN | 信号/对照 样本数 |
|---|---|---|---|---|---|---|
| balance.d_mid | **2.6521** | [0.844, 3.1559] | 3.439965 | 2.311743 | 1.4565 | 16/64 |
| balance.visual_centroid_y | 1.1560 | [0.5701, 2.3542] | 1.0578995 | 1.616357 | 0.6349 | 20/60 |
| whitespace.total_ratio | 0.6749 | [0.3627, 1.6627] | 0.606795 | 1.587052 | 0.3707 | 15/65 |
| density.coverage_text | 0.6066 | [0.3795, 1.6021] | 0.494618 | 1.434728 | 0.3331 | 13/67 |
| ratio.fig_text | 0.4552 | [0.3043, 0.7215] | 0.062433 | 1.654912 | 0.0366 | 4/76 |
| alignment.center_var | 0.4552 | [0.2769, 0.6726] | 0.023878 | 1.632969 | 0.0142 | 12/68 |

* 权重均值 = 1.0（相对权重）；`readability.leading_ratio`、`density.coverage_table` 因阶段 5
  门槛未过（12.1 未覆盖）**不参与校准**，保持只报告。
* 读法：`balance.d_mid`（版面上下均衡）在单页退化下最敏感；`ratio.fig_text` /
  `alignment.center_var` 的信号很弱（缩小一张图对全篇图文比的**池化**值影响有限）。

## 4. 验收（不劣化才启用）

| 判据 | 等权 | 校准后 | 结论 |
|---|---|---|---|
| 退化后 A 上升的正向率（12.1 必要条件） | 0.9875 | 0.9875 | 不劣化 ✓ |
| 中位判别间隔（退化后 A − 基线） | 0.115695 | **0.150557** | 严格改善 ✓ |
| 权重是否在 `[0.25, 4]` 内且有限 | — | 是 | ✓ |

→ `applied = true`。**重要**：两边都用同一个合成式（`Σw·v/Σw` + D² 项）重算，
不是「等权用记录值、加权用新值」—— 否则 D² 项与池化口径的差异会被算进「权重的贡献」，
结论不可信（实测踩到，见 §7 F2）。

## 5. 步骤三：人类成对比较（Bradley–Terry）

代码就位（`weights.fit_bradley_terry`）：`P(a≻b) = σ(w·(x_a − x_b))`，`x = −loss`，
纯 Python 梯度上升 + 朝等权收缩的 L2（小样本不跑飞）；CI 与 12.5 的 Spearman 接口复用
阶段 5 的实现（样本 < 8 对不给结论）。

**数据已采集（2026-10-01）：8 对 / 8 篇论文，成对准确率 0.875**，权重因此由
`ablation` 改为 `ablation+human`（每维保留 `w`（=人类值）与原始消融统计）。

诚实边界：8 对是**口径下限**（< 8 不给结论），加上 L2 朝等权收缩，这批数据主要效果是
**把消融得到的强权重拉回接近 1**（例：`balance.d_mid` 2.65 → 0.70），而不是给出高置信度的
人类偏好；要稳定主张“与人类偏好一致”，建议再攒到 ≥30 对（工具：
`tools/make_pairs.py --sheet` 生成打分表、`--import` 回写）。

采集方式（自动算指标，人只判“左右哪页更顺眼”）：

```bash
cd datasets/conf-specs
python3 tools/make_pairs.py --sheet --pairs 30          # 生成离线打分表（左右随机、不显示指标）
# 人填完后：把答案 JSON 导入 -> human/pairs.json
python3 tools/make_pairs.py --import <answers.json>
python3 tools/make_pairs.py --stats                     # 看对数/论文数/逐维差值
# 最后一步才会把 aesthetic_weights.json 变成 ablation+human
python3 tools/calibrate_weights.py --pairs human/pairs.json --apply
```

数据格式（`human/pairs.json`，由 `--import` 自动生成；也可手写）：

```json
[
  {"a": {"balance.d_mid": 0.3, "density.coverage_text": 1.1, ...},
   "b": {"balance.d_mid": 1.9, "density.coverage_text": 0.2, ...},
   "winner": "b", "note": "可选：人看的理由"}
]
```

`a`/`b` 是两页（或两稿）的**逐维归一化带外损失**（`aesthetic_shadow.json` 的
`per_page[].losses` 经 `norm_loss` 换算，或 `paper.dim_norm_top` 的页级版本），
`winner` 是人选的更顺眼的一侧。建议 ≥ 30 对、覆盖 ≥ 6 篇论文、含「两者都不错」与
「两者都差」两类（否则权重只学到极端对比）。把文件放到
`datasets/conf-specs/human/pairs.json` 后：

```bash
python3 tools/calibrate_weights.py --pairs ../human/pairs.json --apply
```

此时 `method` 变为 `ablation+human`，每维同时保留 `w`（消融）与 `w_human`（人类标定）。

## 6. λ 的状态（重要，别误读）

* `A = A_defect + λ·A_profile`，**λ 默认 0**，且当前代码里 λ>0 **只影响影子报告的
  `a_effective`**，不进入 `score.py` / `core.py` 的接受/回滚判定；
* CLI 已留口 `--aesthetic-lambda <float>`（会打印一行提醒），`Requirement.aesthetic_lambda`
  默认 0.0；
* 把 λ 接进验收口径属于「改变优化目标」的动作，按工作约定需要**用户在场审批** +
  步骤三人类标定数据，本阶段**未做**。

## 7. 本阶段修掉的真问题（都是实测暴露）

| # | 现象 | 根因 | 修法 |
|---|---|---|---|
| **F1** | 权重算出 0.12（越界） | 先裁剪 `[0.25,4]` 再归一到均值 1，归一化会把值推回区间外 | 改为**先归一后裁剪**，并再验一次界内 |
| **F2** | 「校准后判别间隔没改善」 | 等权用记录的 `a1−a0`，校准用另一套（只算逐维项、不含 D² 项）反推 —— 两边不同式，比的是口径差异不是权重差异 | 引入 `a_profile_from_parts()`：**两边同式**重算；并加 `recompute_mismatch` 自检（用试验时的权重复现记录值） |
| **F3** | 同一维在一份报告里拿到两个权重 | 合成时取「第一个出现的档」的 dims 子集，缺维回退 1.0 → 同维在不同角色下权重不同 | 合成改用**全局权重表**（`profile.weights.by_dim`），报告里写出 `weights_used` |
| **F4** | `eval_protocol.py` 跑 12.2 直接 `KeyError: 'default'` | 阶段 5 精简聚合键（去掉与 `param` 重复的 `default`）时漏改打印行；`evaluate_fold` 的 `test` 与 `test_param` 同源 | 打印改为「参数化 ← `param`、经验校准 ← `calibrated`」；在 `evaluate_fold` 注明 `test` 是兼容别名 |

## 8. 测试（11 项）

`tests/run_tests.py::stage7_tests()`：裁剪+归一的顺序回归（不越界）、分量重算与
`evaluate_doc` **同式**、Bradley–Terry 在合成数据上**恢复已知权重顺序**、缺数据/样本不足
返回 `None`、人类结果并入（`source=ablation+human`）、验收规则四种情形（正向率劣化 /
间隔未改善 / 权重越界 / 通过）、真实缓存指标上的消融可复现（`recompute_mismatch=0`）、
消融让中位间隔变大、权重接入 `evaluate_doc`（未启用≡等权、全 1 权重≡旧口径逐位相同）、
落盘与挂载不改输入。

## 9. 复现命令

```bash
cd datasets/conf-specs
python3 tools/calibrate_weights.py --trials 80 --bootstrap 200          # 干跑
python3 tools/calibrate_weights.py --trials 80 --bootstrap 200 --apply  # 挂回档案
cd ../.. && python3 tests/run_tests.py                                  # 含 11 项阶段 7 回归
```

## 10. 已知局限（不包装）

| # | 局限 | 影响 | 计划 |
|---|---|---|---|
| L1 | 消融校准 = **敏感性**校准（谁对可控退化更敏感谁权重大），**不等于人类偏好** | 权重可能把「机器容易造出的差异」放大 | 步骤三人类成对比较（需数据） |
| L2 | CI 较宽（如 `balance.d_mid` [0.84, 3.16] 跨过 1.0） | 权重的绝对大小不稳健，只能当**相对排序**用 | 增大试验数/多 seed 复核；人类标定收窄 |
| L3 | 只覆盖 6 个判定维（门槛剔除 2 维、D² 项仍固定权重 1.0） | 局部最优风险 | 阶段 8 外部验证时复核 |
| L4 | 判别间隔用「单页单维中段退化」测量，长文会被池化稀释 | 间隔数值偏小（0.12→0.15） | 与阶段 8 的整篇退化对照 |
| L5 | 步骤三数据仅 8 对（口径下限） | 不能主张「与人类偏好一致」；权重主要被拉回接近等权 | 继续攒到 ≥30 对（`tools/make_pairs.py --sheet`），重新 `--apply` |
