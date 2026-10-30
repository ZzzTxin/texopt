# 阶段 12：gate 一票否决 + 两线分离 + P 权重回填 + ρ 等边际收益（2026-10-30）

> 用户指令（2026-10-30）：ρ 的「平衡」选 **等边际收益**；然后按顺序完成三件事：
> ① gate 退出（一票否决 → 直接退出 + 修改建议）② 两线分离（model1 / model2 并行、
> 不相加）③ P 权重回填（把 2026-10-28 标定出的 11 项比重落到代码）。
> 另外把 ρ 从手拍的 2.0 换成**用闭环实测数据**定的值。

---

## 1　任务1：gate 一票否决（入口门，不是分数项）

**改之前**：gate 违规 = `+1e6` 罚分，但仍算 P/I/A，仍会用确定性动作去修（改边距、去 fleqn）。

**改之后**（`score.gate_issues()` + `core.Optimizer._gate_repair()`）：

| 情形 | 行为 |
|---|---|
| gate 有违规 | 立即 `scored=False`：**不进入 model1/model2 打分** |
| 含**不可修复**项（编译失败/无 PDF/正文硬改动/图表指纹变化） | 直接退出 `BLOCKED_GATE` + 逐项修改建议 |
| 全部**可修复**（页数/字号/边距/fleqn/目录/页眉） | 先跑 **gate 定向修复**（只允许 `GATE_REPAIR_KEYS`：改 gate 项 + 纯空间类压页动作），判据只看 gate 违规数 / 页数，**不看审美** |
| 修复后仍不通过 | 退出 `BLOCKED_GATE` + 建议（不再进入打分，也不再试审美动作） |
| 修复后通过 | 才进入正常闭环（此时才开始算 M1 / M2） |

结构化字段：`{code, text, repairable, suggestion}`；`GATE_REPAIRABLE` / `GATE_SUGGEST`
逐项列出「哪类违规、能不能靠排版动作修、人工该怎么改」。
`report.md` 在 `BLOCKED_GATE` 时单列「修改建议」小节，标注 `可排版修复 / 需人工源码修改`。

> 为什么区分可修复/不可修复：页数超限正是本工具的核心场景，若一票否决后立刻退出，
> 「压页」就永远做不了。所以可修复项先给一次纯排版的修复机会，失败才退出。

---

## 2　任务2：两线分离（model1 / model2 并行，不相加）

**改之前**：`total = 1e6·|gate| + M1 + M2`；验收第 3 条允许「M1 变差但 M1+M2 改善」。

**改之后**：

- `total_score()` **不再返回 `total`**（返回 `m1` / `m2` / `scored` / `gate`）；
- 验收严格字典序 **(gate, M1, M2)**：
  1. gate 违规数少者胜（未过 → 直接拒绝，不进打分）；
  2. 双方都在压页时：页数不增即保留（保组合收益）；
  3. M1 严格改善 → 接受；M1 变差 → **拒绝（M2 再大也不补偿）**；
  4. M1 完全持平 → M2 严格改善才接受（**仅 tie-break**）；
- 报告里两条线并列成两行（`model1: M1 = ρ·P + I`、`model2: M2 = A_soft`），
  迭代轨迹表由「总分」列改为 `gate | P | I | M1 | M2`；
- `state.json` / `verify` / `proposal` / `evalexternal` 的字段同步改为 `m1`/`m2`。

---

## 3　任务3：P 权重回填（数据来源）

`PAGE_DEFECT_WEIGHT` 由手拍 11 项 → 5 项换成 `human×corpus` 标定值：

| 项 | 旧 | 新 | 来源 |
|---|---|---|---|
| overfull | 1.0 | **0.33** | human×corpus |
| underfull | 0.6 | **0.273** | human×corpus |
| vbox_over | 1.0 | **2.344** | human×corpus |
| floatwarn | 1.6 | **1.254** | human×corpus |
| vbox_under / tab_overwide / fig_overwide / spec_H | 先验 | 先验 | 语料计数 0 或无字段 → 不作分母 |
| warn / macros_missing / unstable_spec | 先验 | 先验 | 人眼不可判的技术项 |

- 公式：`w = severity(BT, 15 题人判) / freq(200 篇 3898 页 per_page)`，sqrt 阻尼，
  再缩放到现行权重同量纲（详见 `stage11_severity_sheet_20261028.md`）。
- 落库方式：`metrics/severity_weights_applied.json`（含 provenance 与每项 basis），
  `tools/apply_severity_weights.py --check` 做代码↔artifact 漂移校验（`s12` 测试里也跑）。
- **ρ 是总尺度锚点**：这次只改 P 的内部相对结构，不改 model1 与 model2 的总体权衡。

---

## 4　ρ：等边际收益（用闭环实测数据定）

定义（用户拍定）：**修 1 单位缺陷 与 付出 1 单位干预代价，边际价值相等**
⇒ `ρ = ΔI / (−ΔP)`，即在闭环里**实际付出**的干预代价 ÷ 实际修掉的缺陷数。

`tools/calibrate_rho.py`：

- 采集：`--run <tex...>` 真跑闭环（内存里取 `baseline` + 每条 `records`）；
  `--state <state.json...>` 读历史运行；
- **只统计每次「尝试」动作的 (ΔP, ΔI)**，不只看被接受的动作 —— 接受与否本身依赖 ρ，
  只统计被接受的动作等于用 ρ 论证 ρ；
- 输出：每篇的 ρ 明细 + 全库中位数 / P25 / P75，裁剪到 `[0.2, 10]` 后写
  `metrics/rho_exchange_rate.json`；
- 结果见下节（跑完填充）。

---

## 5　实测

### 5.1 ρ 实测（2026-10-30，4 篇真编译闭环）

| 文档 | 出口状态 | 动作数 | 修缺陷动作 | 付费修复 | ρ 中位 |
|---|---|---|---|---|---|
| issues.tex | DONE | 6 | 6 | 1 | 0.800 |
| aidtest.tex | DONE | 6 | 5 | 1 | 0.301 |
| nightmare.tex | NEEDS_REVIEW | 19 | 16 | 2 | 0.307 |
| chaotic_layout_test.tex | NEEDS_REVIEW | 18 | 16 | 2 | 0.378 |

- 合计 43 次修复动作，其中 **37 次 ΔI = 0（零代价修掉）**、6 次付费；
- ρ（付费口径）中位 **0.341**，p25 0.304，p75 0.383 → 回填 `W_PAGE_DEFECT = 0.341`；
- 若把免费修复也算进去，ρ 中位是 **0.0** —— 这也是为什么标定必须排除它们：
  免费修复在任何 ρ > 0 下都会被接受，不携带汇率信息。
- 口径局限：付费样本只有 6 个，且都落在「0.4 一次浮动体参数改动」附近；
  后续采到更多闭环数据（尤其边距/字号这类大代价动作）应重跑 `tools/calibrate_rho.py`。

### 5.2 gate 退出实测（`python3 optimize.py … --target N`）

| 场景 | 结果 |
|---|---|
| demo.tex，`--target 1`（不可达，且未授权版心调整） | `BLOCKED_GATE`，0 个动作可试，报告写「没有任何可用的纯排版修复动作」+ 建议 |
| demo.tex，`--target 3 --tune-geometry` | 先跑 gate 定向修复：页边距 25.4→23.4mm 未减页 → 回滚 → `BLOCKED_GATE`（未进入打分，报告无 M1/M2 数字） |

### 5.3 全量回归（2026-10-30 19:05）

**308 通过 / 0 失败 / 0 跳过**（新增 `s12` 13 项：gate 结构化完整性、gate 修复动作面、
无 total 字段、验收无补偿、权重 artifact 对齐、ρ 中位数/裁剪/artifact 对齐）。

closure 期望状态全部维持：demo / issues / aidtest / propose_target = DONE，
chaotic_layout = NEEDS_REVIEW（仍留 1 项 high 巨型内容块）。

参考终态（新权重 + 新 ρ）：

| 文档 | 状态 | 页数 | P | I | M1 | M2 |
|---|---|---|---|---|---|---|
| demo | DONE | 6 | 0.0 | 0.0 | 0.0 | 1.197 |
| issues | DONE | 2 | 0.8 | 0.0 | 0.273 | 1.120 |
| aidtest | DONE | 2 | 0.0 | 0.4 | 0.400 | 0.894 |
| propose_target | DONE | 2 | 0.33 | 0.0 | 0.113 | 1.453 |
| chaotic_layout | NEEDS_REVIEW | 5 | 3.603 | 0.0 | 1.229 | 3.007 |

### 5.4 已知边界

1. ρ 的付费样本 n=6，只够定量级，不够定小数点后一位；
2. `GATE_REPAIR_KEYS` 里的空间类动作目前只在「单步就能减页」时生效，
   连续两档才减页的情形仍会被单步回滚挡住（与改动前行为一致，未在本次范围内改）；
3. λ 仍为 0，model2 的 A_profile 不参与验收（`shadow.assert_lambda_allowed` 代码级拦截）。
