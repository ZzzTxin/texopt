# 阶段 6 交付：影子模式接入 texopt（λ = 0，仅报告）

> 对应设计方案第十三章（与 texopt 的最终结合）与十五章「阶段 6」。
> 关键产出：**影子报告 + 人工核对**（方案原文：阶段 6 → 「影子报告，人工核对」）
> 代码：`texopt/shadow.py`（观测与报告）、`texopt/core.py`（接入点）、`optimize.py`（CLI）
> 测试：`tests/run_tests.py::stage6_tests()`（7 项，含端到端「开/关影子判定完全一致」）

## 1. 一句话

影子评估**只观测、不决策**：每次整篇重编译后读一次 PDF 的页级指标做档案判定，
把结果（A_profile / D² / 异常页 / 归因 / 逐轮 trace）写进工作区的报告，
但**不进入** `total`、不参与接受/回滚，λ 恒为 0 —— 这是方案 13.1/13.3 的落地。

## 2. 口径（13.1）

```
A = A_defect + λ · A_profile        λ = 0（默认，影子模式）
```

| 量 | 来源 | 是否参与验收 | 写在哪 |
|---|---|---|---|
| `A_defect` | `score.py::aesthetic_score`（确定性缺陷加权计数，口径未改） | ✅ 参与 | `state.json` → `scores.a` |
| `A_profile` | `aesthetic.py::evaluate_doc`（马氏 D² + 非单调带外损失） | ❌ 只报告 | `aesthetic_shadow.json` → `final.a_profile` |
| `a_effective` | `A_defect + λ·A_profile` | ❌（λ=0 时等于 `A_defect`） | 同上 |

两者**独立记录、独立报告、独立回归**：A_defect 的回归（既有 `stage*_tests`）完全不变。

## 3. 接入点（唯一的、顺序上安全的）

`core.py` 里影子只在三处被调用，**全部发生在判定之后**：

| 调用点 | 时机 | 用途 |
|---|---|---|
| `run()` 基线 | 基线编译 + 评分完成后 | trace 第一行 `baseline` |
| `_step()` 接受分支 | `_accept()` 已返回 True、`self._state` 已就绪之后 | trace 的逐轮观测 |
| `finalize()` | 终态评分完成后 | 终态报告 + 落盘 |

> 顺序保证：影子读取的是**已经决定完**的状态，且不写回 `cur`/`total` 之外的任何决策量
> （只往 `cur["a_profile_shadow"]` / `cur["aesthetic_shadow"]` 塞报告字段），
> 因此「影子改变判定」在结构上不可能发生 —— 这一点由端到端测试
> `s6/no-decision-change` 直接验证（同文档开/关影子，`status`、`accepted`、
> `total`、`a`、`L`、页数**逐项相同**）。

## 4. 产物

| 文件 | 内容 | 读者 |
|---|---|---|
| `workbench/<run>/aesthetic_shadow.md` | 人读影子报告：版本/档 → 分数 → 页级统计 → 最偏离维度 → 最异常页 → 门槛剔除 → **逐轮 trace 表** → 门控 → **人工核对清单** | 人工核对 |
| `workbench/<run>/aesthetic_shadow.json` | 机器可读：`baseline` / `final` / `trace` / `gate` + λ 与档案版本 | 上层 Agent / 后续阶段 |
| `workbench/<run>/state.json` → `aesthetic_shadow` | **版本化快照**（13.4）：`profile_version` / `venue` / `levels_used` / `n_pages_scored` / `n_anomalous_pages` / `dropped_dims` / `a_defect` / `a_profile` | 跨时间可比、可追溯 |
| `workbench/<run>/report.md` | 同名章节（与 `aesthetic_shadow.md` 同源渲染） | 报告消费者 |

`report.md`、`state.json` 与影子产物**彼此一致**：`a_defect` 与 `scores.a` 同源，
`trace` 的每一行都是「整篇重编译后的真实观测」，不是估算。

## 5. 开关与用法

优先级：CLI > settings.json/模板 > 默认（开）；环境变量可全局关闭。

```bash
# 只看影子报告，不优化（基线编译一次，四处不改文档）
python3 optimize.py paper.tex --shadow-only

# 正常优化（默认带影子观测）
python3 optimize.py paper.tex -T neurips25

# 关闭影子（离线/受限环境或纯确定性回归）
python3 optimize.py paper.tex --no-aesthetic-shadow
TEXOPT_NO_SHADOW=1 python3 tests/run_tests.py

# 用别的档案（例如消融实验的档案）
python3 optimize.py paper.tex --shadow-profile datasets/conf-specs/metrics/profiles/aesthetic_profile.json
```

`settings.json` 字段：`"aesthetic_shadow": true`、`"shadow_profile": null`。

## 6. 逐维门槛（阶段 5 的联动）

影子判定**自动**载入 `datasets/conf-specs/metrics/profiles/eval_gate.json`：

* 12.1 单调性 / 12.2 假阳率 / 12.4 稳定性三项未全过的维度 → **只报告、不参与判定**
  （当前剔除 2 维：`readability.leading_ratio`、`density.coverage_table`，原因均为 12.1 未覆盖）；
* 门槛文件缺失 → `dropped_dims=[]`（不剔除任何维，行为退化为「全维报告」）。

## 7. 人工核对清单（阶段 6 的正式产出动作）

`aesthetic_shadow.md` 末尾会把这 6 条打印出来；全库级别的核对用
`datasets/conf-specs/tools/shadow_report.py`（产出 `shadow_summary.md`，含逐会统计与
A_profile 最高的 15 篇归因自查表）：

1. λ 是否为 0、`A_defect` 是否与 `state.json.scores.a` 一致（现行口径未被动过）
2. 基线 → 终态 `A_profile` 走势；若终态变差而 `A_defect` 未变差 → 动作把版面推离会议常态，需人判断
3. 最偏离维度是否对应人眼可见问题（无可见问题 → 疑似误报，记入台账，阶段 7 复核假阳率）
4. 最异常页是否真是排版异常页（而非数据/合订本问题）
5. 门槛剔除维度是否合理
6. 档案版本与会议档是否与本次论文匹配

> 诚实边界：本阶段的「报告」是**实现与口径的自洽性观测**，不是「与人类审美一致」；
> 阶段 5 报告里 12.5（人类相关性）仍为 `null`，需阶段 7 的成对比较数据。

## 8. 实测片段（回归靶稿，`_regress/s6_run_on`）

| 轮次 | 事件 | A_defect | A_profile | D² P90 | 异常页 |
|---|---|---|---|---|---|
| 0 | baseline | 7.4 | 7.408519 | 104.84 | 2 |
| 1 | quality 宏 | 5.4 | 7.408519 | 104.84 | 2 |
| 2 | 删手工 `\newpage` | 2.68 | 4.992503 | 81.51 | 1 |
| 3 | 收敛 `\parskip` | 2.4 | 5.339465 | 87.73 | 1 |
| 4 | final | 2.4 | 5.339465 | 87.73 | 1 |

可读出的信息：整体 A_profile 改善（7.41 → 5.34），但第 3 轮 `\parskip` 收敛
**局部**抬高了 A_profile（4.99 → 5.34）—— 这正是「A_defect 与 A_profile 会给出
不同信号」的例子，也是阶段 7 权重校准要处理的输入。

## 9. 已知局限

| # | 局限 | 计划 |
|---|---|---|
| L1 | 影子只跑「待优化论文」，不做全库在线重算（方案 13.5 的成本约束） | 全库仍用缓存的离线报告（`shadow_report.py`） |
| L2 | `venue` 取会议模板 id；未指定模板时落 `role` / `role_layout` 档（如示例中 `（无）`） | 阶段 7 起可让 Agent 先判会议再优化 |
| L3 | trace 只记每次*接受*后的观测（回滚态不记，避免噪声） | 需要时加 `--shadow-trace-all`（未实现） |
| L4 | 影子失败（缺档案/提取异常）被隔离成报告项，`report.md` 只留一行说明 | 属预期：影子不得影响主流程 |
