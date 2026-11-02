# 打分模型（gate + model1 + model2）

> 这里只讲**怎么打分、怎么比较、为什么这么设计**。审美指标的细节见
> [`docs/aesthetic/README.md`](../aesthetic/README.md)；闭环动作与模板见仓库根 `README.md`。

## 1. 一句话

```
排序（严格字典序）：(|gate|, M1, M2)

gate  底层逻辑门：必须满足；不满足 = 不可行，**不进入打分**
M1 = ρ·P + I                model1（主）：页面缺陷 P 与干预代价 I
M2 = A_soft + λ·A_profile   model2（审美）：λ = 0，A_profile 只报告
```

三条硬规定：

1. **gate 不是分数项**。早期把它折算成 `1e6` 罚分，结果是"分数上看起来还能接受"，
   于是程序会拿审美动作去试一个根本不合规的稿子。现在 gate 有违规就 `scored=False`。
2. **两条线不相加**。相加允许"审美大幅变好"补偿"缺陷明显变多"，这不是我们要的。
3. **M2 只在 M1 完全持平时作 tie-break**，不参与主判定。

## 2. 为什么不是单一总分（三次修正的教训）

| 版本 | 口径 | 出的问题 |
|---|---|---|
| v1 | `total = A + I` | 把"降 A 但增 I"的真修复拒掉：阶段 8 E1 里 `[H]→[tbp]` 让 A 17.5→16.0，但 I 升到 2.8，`total` 18.8 > 17.5 → 回滚 |
| v2（阶段 8 修正 a） | `total = gate·1e6 + A + I`，A 优先、I 作 tie-break | 修好了上面的问题，但 gate 仍可被"罚分"绕过；且 A 与 I 仍混在一个数里 |
| v3（阶段 12） | `(|gate|, M1, M2)` 严格字典序，两线分离 | 现行口径 |

结论写进代码注释：**验收口径本身会改变优化器的行为**，所以口径必须可审计、有测试。

## 3. gate：底层逻辑门

实现在 `texopt/score.py: gate_issues()`，返回结构化清单：

```json
{"code": "pages", "text": "正文页数 7–8（参考文献之前）超出限制 6（PDF 共 9 页）",
 "repairable": true, "suggestion": "先用纯排版压（收边距/降字号/修浮动体/缩图宽）…"}
```

### 3.1 检查项

| code | 判据 | 可修 | 修复动作 |
|---|---|---|---|
| `compile` | 编译失败 / 无 `per.ok` | ✗ | —（不在排版动作面内） |
| `pdf` | 未产出 PDF | ✗ | — |
| `content` | 仅当 `content_hard=True` 时正文被改 | ✗ | — |
| `figures` | 图/表内容指纹与 `--original` 不一致（宽度/位置参数归一后比） | ✗ | —（保真底线） |
| `pages` | 超出 `page_limit`（口径见 3.2） | ✓ | `margin_cut` / `font_cut` / `fig_norm` / `fig_size` / `pagebreak_rm` / `vspace_rm` … |
| `font` | 正文字号 ≠ 要求档位 | ✓ | `font_spec` / `font_cut` / `font_back` |
| `margin` | 页边距不符（会议模板按**下限**判，低于才违规） | ✓ | `margin_spec` / `margin_cut` |
| `fleqn` | 要求公式居中但文档类带 `fleqn` | ✓ | `drop_fleqn` |
| `toc` | 要求目录（且节数 ≥ `toc_min_sections`）但缺失 | ✓ | `insert_toc` |
| `header` | 要求页眉但缺失/异常 | ✓ | 页眉动作 |

### 3.2 页数口径（避免误伤合法论文）

按**正文页**判：用 `pdftotext` 定位参考文献首页 `k`，只有 `k−1` 超过上限才算违规；
正则判不出来时退回"总页数"并显式标注。这样"恰好写到参考文献首页"的合法论文不会被判超页。

### 3.3 gate 定向修复（可修项的一次机会）

页数超限正是本工具的核心场景，一票否决立刻退出等于永远压不了页。所以：

```
gate 有违规
 ├─ 含不可修复项（compile/pdf/content/figures） → 直接 BLOCKED_GATE + 逐项建议
 └─ 全部可修复 → 只跑 GATE_REPAIR_KEYS 里的动作（改 gate 项 + 纯空间类压页）
       判据只看「gate 违规数 / 页数」，**不看审美**
       轮数上限 gate_repair_rounds（默认 12）
       通过 → 进入正常闭环（此时才开始算 M1/M2）
       失败 → BLOCKED_GATE + 建议（不再试审美动作）
```

`report.md` 在 `BLOCKED_GATE` 时单列「修改建议」小节，并标 `可排版修复` / `需人工源码修改`。

## 4. model1：`M1 = ρ·P + I`

### 4.1 P：页面缺陷（半硬性）

`texopt/score.py: PAGE_DEFECT_WEIGHT`。权重来源两类，**逐项标注**：

| 项 | 权重 | 来源 |
|---|---|---|
| `overfull` | 0.33 | human×corpus |
| `underfull` | 0.273 | human×corpus |
| `vbox_over` | 2.344 | human×corpus |
| `floatwarn` | 1.254 | human×corpus |
| `vbox_under` | 1.4 | 先验（语料计数 0） |
| `tab_overwide` | 1.2 | 先验（语料无字段） |
| `fig_overwide` | 1.0 | 先验（语料无字段） |
| `warn` | 0.3 | 先验（人不可判） |
| `macros_missing` | 2.0 | 先验（人不可判） |
| `unstable_spec` | 0.8 | 先验（人不可判） |
| `spec_H` | 0.5 | 先验（语料计数 0） |

标定公式：`w = 人判严重度(BT, 15 题) ÷ 语料频率(200 篇/3898 页 per_page)`，
sqrt 阻尼后缩放到现行量纲；artifact `metrics/severity_weights_applied.json`，
`tools/apply_severity_weights.py --check` 做代码↔artifact 漂移校验。

另加两块：

- **源码卫生** `HYGIENE_WEIGHT`（22 项，0.3–1.0）：手动分页 1.0、标题字号 0.8、
  过大 vspace/列表间距/断词 0.6、行内字号/缺题注 0.5、`$$`/下划线/硬换行 0.3…
- **页面视觉缺陷** `VISUAL_DEFECT_M1`：`stranded_block` 1.2、`near_empty` 0.6，
  再乘 severity 系数（high 1.0 / moderate 0.6）。其余视觉缺陷只做出口门控
  （`NEEDS_REVIEW`），不进 P —— 避免同一现象重复计分。

### 4.2 ρ：缺陷 ↔ 代价的汇率

```
M1 = ρ·P + I         ρ = 15（人判无差异点标定）
```

- **定义（用户 2026-10-30 拍定：等边际收益）**：修 1 单位缺陷的质量收益，恰好抵消
  1 单位干预代价的保真收益 → **ρ 是边际替代率**，在无差异点上有 `ρ·w = c*`。
- **测量方法（2026-10-31）**：生成「缺陷保留、版心不动」vs「缺陷修掉、付出代价」的版本对，
  人工三选一（左/右/无差异），取偏好转折点 `c*`；`ρ = c*/w`。
  两轮：第一轮 5 缺陷 × 3 档边距（+12/20/30mm）→ 中位 **16.7**；
  第二轮边界加密 + 字号货币 → 中位 **13.3**；随后 6 题一致性复核（3 空题 + 3 明显差异）**6/6 通过**。
- **取值**：`ρ = 15`，区间约 [5, 32]（单人评分、5 类缺陷）。
  artifact `metrics/rho_tradeoff_20261031.json`；
  工具 `tools/make_tradeoff_sheet.py` / `make_tradeoff_v2.py` / `make_tradeoff_check.py`。
- **含义**：修 1 个加权缺陷，在人眼里约值 15 个代价单位——即愿意用 30mm 级别的边距改动去换。
- **与旧值的关系**：早期 `ρ=0.341` 来自闭环里**已发生的付费修复**取中位数
  （`ΔI/(−ΔP)`，4 篇 / 43 次动作 / 6 次付费）。那是**平均代价**，不是无差异点：
  它只覆盖优化器愿意试的动作，天然偏向"修得值"的一侧。旧数据保留在
  `metrics/rho_exchange_rate.json`，不再作为当前取值。
- **局限**：单一评分人；每缺陷只有 2–3 个代价档；两轮间转折点整体差 2 个单位（4mm），
  说明中等代价档上判断有噪声；P 权重的个体偏差（见下）尚未复核。

### 4.3 I：干预代价

```
I = I_struct + β·D_content        β = 50（CONTENT_PENALTY）
```

`I_struct`（`intervention_cost()`，越接近原稿越小）：

| 改动 | 代价 |
|---|---|
| 页边距每偏离原稿 1mm | 0.5 |
| 字号每偏离 1 档 | 3.0 |
| 每处浮动体位置参数被规范化 | 0.4 |
| 每处图片宽度表达式被归一 | 0.4 |

`D_content`（`content_deviation()`）：正文归一化后字符多重集的
`D = 1 − Jaccard`（增删都计偏差）。**排版面 token 不计**（浮动体参数、图宽、
`\newpage`、`\noindent`、行内字号、断词点、列表间距选项…）。

> 内容保留默认已从 gate 降级为软项（`CONTENT_PENALTY·D_content`），因为后续语义抛光
> 阶段要合法改正文；要恢复"零改动"硬约束时把 `Requirement.content_hard = True`。
> `D_content` 是**改动幅度代理**，不是语义等价证明。

### 4.4 参考终态（阶段 12，真编译）

| 文档 | 状态 | 页数 | P | I | M1 | M2 |
|---|---|---|---|---|---|---|
| demo | DONE | 6 | 0.0 | 0.0 | 0.0 | 1.197 |
| issues | DONE | 2 | 0.8 | 0.0 | 0.273 | 1.120 |
| aidtest | DONE | 2 | 0.0 | 0.4 | 0.400 | 0.894 |
| propose_target | DONE | 2 | 0.33 | 0.0 | 0.113 | 1.453 |
| chaotic_layout | NEEDS_REVIEW | 5 | 3.603 | 0.0 | 1.229 | 3.007 |

## 5. model2：`M2 = A_soft + λ·A_profile`

- `A_soft`：像素层软指标的**平滑目标损失**，8 个指标（`band` 权重 0），
  参数、公式、为什么废掉"带内恒 0" → 见 [`docs/aesthetic/README.md`](../aesthetic/README.md)。
- `A_profile`：与同会议·同角色语料档案的马氏距离 + 非单调带外损失。
- **指标集待收紧（阶段 16）**：8 个指标里 3 个是准常数、1 个是阈值型，详见
  [`stage16_model2_metrics_20261102.md`](stage16_model2_metrics_20261102.md)；
  v2 草案（4 指标 + 位置条件 + 角色门控）尚未落地。
- **λ = 0**：`A_profile` 只进报告与 `state.json`，不参与判定；
  `shadow.assert_lambda_allowed` 代码级拦截 λ>0（需人类标定 + 审批）。

### 5.5　单页打分 / 整篇打分（阶段 15，2026-11-02）

定位：**只做归因与度量，不改判定**。M1/M2 公式、ρ=15、14 项 c\* 全部原样。

`texopt/page_score.py` 把两条线都拆成「能归到页」与「归不到页」：

| 缺陷 | 归因方式 |
|---|---|
| overfull / underfull / 表格超宽 | 源码行号 → SyncTeX → PDF 页号（编译带 `-synctex=1`） |
| 源码卫生项、浮动体 `[H]`/不稳定参数 | 同上（扫描自带行号） |
| 渲染层视觉缺陷（内容孤立、近空白页） | 本来就有页号 |
| vbox、浮动体警告、其余 Warning、质量宏缺失、超宽图表达式 | 归不到页，单列 `unattributed_p` |

三种读法同时给（不替人做选择）：

```
mean = 页均        topk = 最差 k 页均值（k = max(1, round(5%·页数)))      peak = 单页峰值
```

落地位置：`state.json.page_diagnostics` + `report.md`「逐页诊断」小节，
由 `finalize()` 算一次（诊断失败不影响主流程）。

实测（`examples/issues.tex` 原件，3 页）：

| 口径 | model1 · P | model2 · A_soft |
|---|---|---|
| 页均 | 1.311 | 1.769 |
| 最差 1 页 | 1.900 | 2.618 |
| 单页峰值 | 1.900 | 2.618 |
| 全篇 | 5.933（含 2.0 归不到页） | — |

第 3 页（`near_empty` + A_soft 2.618）是全篇最差页，但在全篇 P 里只占 10%——
这就是「整体分摊平局部病灶」的实例。是否要把局部项写进 M1（`ρ_peak·P_peak`）、
同类缺陷是否饱和、局部恶化是否可否决全局改善，见
[`stage15_local_global_20261102.md`](stage15_local_global_20261102.md) §3，**尚未拍定**。

## 6. 验收规则（`core.py: _accept`）

按顺序判，先命中先返回：

| # | 条件 | 结果 |
|---|---|---|
| 1 | gate 违规数减少 / 增加 | 接受 / 拒绝 |
| 2 | 双方都还有页数违规，且页数不增 | **接受**（压页可能需连续多档才兑现，保组合收益） |
| 3 | gate 未过（`scored=False`） | 拒绝（M1/M2 仅供诊断） |
| 4 | M1 严格改善 | 接受 |
| 5 | M1 变差 | **拒绝**（M2 再好也不补偿） |
| 6 | M1 完全持平，M2 严格改善 | 接受（仅 tie-break） |
| 7 | 其他 | 拒绝 |

配套机制：

- 每个候选都**整篇重编译 + 全局重评**（不接受局部估计），变差即回滚；
- 失败动作跨轮 `blocked`，避免重复尝试；
- 连续 `min_stall_rounds`（默认 2）轮无改善才停；
- `done_max_a` 可给 M2 设上限，超过则出口判 `NEEDS_REVIEW` 而不是 `DONE`。

## 7. 字段与产物

`total_score()` 返回：

| 字段 | 含义 |
|---|---|
| `l` / `gate` | gate 违规文本列表 / 结构化清单（`code/text/repairable/suggestion`） |
| `scored` | gate 是否通过（False = 不参与判定） |
| `p` | model1 · 页面缺陷分 |
| `i_struct` / `d_content` / `i` | model1 · 结构代价 / 正文偏差率 / 合成代价 |
| `m1` | `ρ·P + I` |
| `a` / `m2` | model2 · `A_soft` / `A_soft + λ·A_profile` |
| `content_preserved` | `D_content == 0` |

落盘：`workbench/state.json`（每步 `gate/P/I/M1/M2` + `source` + 理由）、
`workbench/report.md`（两行并列：`model1: M1 = ρ·P + I`、`model2: M2 = A_soft`，
迭代表列 `gate | P | I | M1 | M2`）。

> 注意：**没有 `total` 字段**（阶段 12 起删除）。E4/proposal/evalexternal 等
> 下游都已同步；若见到 `l_violations` / `L` 命名，那是兼容别名（指向 gate）。

## 8. 复现与自检

```bash
cd /mnt/d/桌面/texopt

# 回归（含 s12：gate 结构化完整性 / gate 修复动作面 / 无 total 字段 /
#            验收无补偿 / 权重 artifact 对齐 / ρ 中位与裁剪）
python3 tests/run_tests.py

# 权重 artifact 漂移检查
python3 tools/apply_severity_weights.py --check

# ρ 的人工无差异标定（生成 15 题 → 人填 → 解 ρ）
python3 tools/make_tradeoff_sheet.py --build
python3 tools/make_tradeoff_sheet.py --import answers.json

# ρ 的历史口径（闭环平均代价，仅作交叉参考）
python3 tools/calibrate_rho.py --run examples/demo.tex examples/issues.tex

# gate 行为验证：不可达页数 → BLOCKED_GATE（0 个动作可试 + 建议）
python3 optimize.py examples/demo.tex --target 1
python3 optimize.py examples/demo.tex --target 3 --tune-geometry   # 修复失败 → BLOCKED_GATE
```

## 9. 已知局限

1. **ρ 来自单个评分人、5 类缺陷**：两轮中位 16.7 / 13.3，取 15；区间 [5, 32]。
   两轮间同一对图片出现过方向翻转，说明中等代价档的差别人眼不敏感——小数点后的精度没有意义。
2. **P 里有 7 项仍是先验**（无频率分母或无对应字段），未标定就明确标着"先验"。
3. ~~`GATE_REPAIR_KEYS` 的空间类动作只在「单步就能减页」时生效~~
   **2026-11-02 已修**：改为「暂存链」——不增页不减页的单步可暂存，后续任一步兑现
   则整链提交；链长到 `gate_repair_plateau`（默认 3）仍未兑现则整链回滚。
   见 [`stage15_local_global_20261102.md`](stage15_local_global_20261102.md) §1。
4. **λ 恒为 0**：`A_profile` 不参与验收，`M2` 实际等于 `A_soft`。
5. **两线分离后没有总分**：想快速比较两个不同文档的整体好坏，请分别看 `M1` 与 `M2`，
   不要自行相加——相加正是这套设计刻意避免的事。
