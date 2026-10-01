# 阶段 8：外部验证（方案 13）

> 目标：把「审美量化 + 影子接入」从**自洽性检验**（阶段 5，全在缓存页指标上做）
> 推进到**外部验证**：真实文档、真编译、两条独立测量路径、按论文聚合的报告口径。
>
> 诚实边界（写在最前面）：本阶段**不引入任何新的分数定义、不调 λ（λ 恒为 0）**，
> 只做「已验证 / 未验证 / 测得多少」的如实记录。E1 检验的是「实现-口径自洽 + 修复能力」，
> 不等于「与人类审美一致」；E2 的两条路径读的是同一批 PDF（渲染/解析路径不同），
> 不是两套完全独立的工具链；E3 复用真实论文缓存指标。

状态（2026-10-01）：**E1 ✅ / E2 ✅ / E3 ✅**，产出见
`datasets/conf-specs/metrics/profiles/eval_external.json`（机器）与 `eval_external.md`（人读）。

---

## 1. E1 端到端退化（真实文档 + 真实优化器，真编译）

### 1.1 设计

- 取 4 篇**真实文档**：`neurips-real`（真实论文工程，含 .sty/图/bib）、
  `paper-real`（真实论文工程）、`demo-fixture`、`issues-fixture`（随仓库靶稿）。
- 源码级退化档逐档累加（`texopt/evalexternal.py::LADDER`）：
  `vspace`（过大手动间距）→ `pagebreak`（手动分页）→ `float_H`（强排浮动体）→
  `overwide`（超宽图 1.25\linewidth）。
- 每档跑**完整确定性闭环**（编译 → 感知 → 评分 → 动作 → 重编译 → 验收/回滚），
  与阶段 5 的 12.1（在**缓存页指标**上注入）不同：这里走**真编译**。

### 1.2 关键修正：必须记录「修复前」的一组量

初版实现只记录每档**闭环修复后**的 A。实测发现：源码级退化会被确定性动作
**完全修回去**（`\vspace{3cm}` 被移除、`\newpage` 被移除），于是各档修复后 A
完全相同，"退化让 A 上升"这一条**无法被检验**（是空转的 True）。

因此每档记录两组量：

| 记号 | 含义 |
|---|---|
| `a_before` / `a_profile_before` | 退化态（闭环**修复前**）的 A 与影子 A_profile |
| `a` / `a_profile` | 闭环**修复后**（终态）的量 |

单调性看前者（退化是否真的变差），修复能力看后者是否回到干净稿水平。
`a_before` 取自闭环的**基线评分**，`a_profile_before` 取自闭环**基线影子快照**
（阶段 6 的 `baseline` 观测，λ=0，只读）——为此在 `core.run()` 的返回里补了一个
只读字段 `aesthetic_shadow_baseline`（不改判定、不落盘状态改变）。

### 1.3 结果（2026-10-01，`--e1-levels 4`，整段 2206.5s）

| 文档 | 类型 | 干净稿 A | 退化态 A（修复前，4 档） | 闭环修复后 A | 单调 | 可见 | 影子同向 | 回干净 |
|---|---|---|---|---|---|---|---|---|
| `neurips-real` | 真实论文工程 | 17.8 | 58.74 → 59.74 → 61.24 → 65.24 | 17.8 → 17.8 → 17.8 → 17.8 | ✓ | ✓ | ✗ | ✓ |
| `paper-real` | 真实论文工程 | 3.1 | 25.88 → 25.4 → 21.9 → 22.9 | 3.7 → 6.5 → 11.3 → 12.3 | ✗ | ✗ | ✗ | ✗ |
| `demo-fixture` | 靶稿（干净） | 0.48 | 2.9 → 5.5 → 6.18 → 9.8 | 0.48 ×4 | ✓ | ✓ | ✗ | ✓ |
| `issues-fixture` | 靶稿（4 类可修问题） | 0.78 | 9.2 → 10.2 → 10.2 → 14.5 | 0.78 → 0.78 → 0.78 → **0.3** | ✓ | ✓ | ✓ | ✓ |

汇总（4 篇）：A_defect 单调 **3/4**、退化可见 3/4、闭环把 A 拉回 ≤ 干净稿 **3/4**、
修复后 ≤ 自身退化态 **4/4**；退化态影子 A_profile 同向 **1/4**。

页数侧旁证：`neurips-real` 退化态 27→27→27→28 页 vs 干净 24 页；`demo` 6→7→7→7 vs 6。
退化确实改变了版面（不只是评分器里的数字）。

### 1.4 三条结论（含两条负面结果）

**① 成功的部分（3/4 篇）**：源码级退化使 A_defect 单调上升，闭环把它拉回干净稿水平——
`neurips-real` 58.7-65.2 → **17.8**（= 干净稿）、`demo` 2.9-9.8 → **0.48**、
`issues` 9.2-14.5 → **0.78/0.3**（比干净稿还低：顺手把靶稿自带的 4 个问题也修了）。

**② 负面结果 A（`paper-real`）**：退化态 A 本身**不单调**（25.88 → 25.4 → 21.9 → 22.9），
闭环也只能部分修复（3.7 → 6.5 → 11.3 → 12.3，均 > 干净稿 3.1）。
该篇干净稿的**基线 A 本身就高**（`a_before`=25.6 → 闭环后 3.1），说明它自带大量可修问题，
与注入的退化纠缠在一起；页数 11 → 12 → 10 也说明 `[H]` + 超宽图的组合改变了分页。
→ 如实记录：**当前动作白名单在「真实文档 + 多类退化组合」上修复不完全**，
且 A 对退化档数不保证单调。这类「像真实论文那样又脏又长」的文档是后续重点。

**③ 负面结果 B（影子不敏感）**：退化态 A_profile 只有 1/4 篇同向。
例：`neurips-real` deg1 与 deg2 的 A_profile **完全相同**（1.524625），deg3 反而**更低**（1.295835）；
`demo` 0.677（vspace）→ 4.079（+pagebreak）→ 4.091（+float_H）→ 3.849（+overwide）。
即：**A_defect（现行评分）对这批退化敏感，A_profile（阶段 4-7 口径）不敏感且不单调**。
候选原因（本阶段未逐一归因，列为下一步）：

1. A_profile 测的是「离**会议常态**的距离」，**带内损失为 0**；双栏会议稿里
   `\vspace`/`[H]`/超宽图造成的版面常常仍落在常态带内——它测「异常」，不测「缺陷」；
2. 退化集中作用的维可能正是被阶段 5 门槛剔除的维（`readability.leading_ratio`、
   `density.coverage_table`）或覆盖率极低的维（`whitespace.trailing_ratio` 仅 6% 非零）；
3. 影子只走**矢量/文本层**（`shadow.evaluate_pdf` → `extract_pdf`，无像素层），
   而 `\vspace`/`[H]` 这类改动在文本层上容易被版面重整吸收掉。

→ 这组差异正是「影子只报告、不参与验收」（λ=0）最直接的证据：
**在 A_profile 的敏感性问题解决之前，λ>0 是不安全的**。

判定口径（全部三态：`True` / `False` / `None`=数据缺失，**None 不算通过**）：

- `degradation_monotone`：退化态 A 对档数单调不降；
- `degradation_visible`：最重档退化态 A ≥ 最轻档（退化真的可见）；
- `shadow_monotone_before`：退化态影子 A_profile 同向；
- `repaired_back_to_clean`：闭环修复后 A ≤ 干净稿 A；
- `repaired_below_before`：闭环修复后 A ≤ 自身退化态 A。

### 1.5 归因（2026-10-01 补做，两个负面结果都说清楚了）

#### A. 为什么 `paper-real` 不单调且修复不完全

证据：`workbench-eval/e1/paper-real/deg3/run/report.md` 的迭代轨迹：

- 步 2「7 处浮动体 `[H]` → `[tbp]`」：**A 17.5 → 16.0（A 确实改善了）**，但 I 0 → 2.8，
  总分 17.5 → 18.8 → 按 lexicographic 验收（L 同 → 总分必须严格改善）被**回滚**；
- 步 4「删正文行内 `\small`」：A 9.5 → 10.3 无改善 → 回滚；
- 被阻塞动作：`float_spec`、`local_font`、`pagebreak_rm`、`vspace_rm`。

→ 三条原因：①验收用 `total = L·1e6 + A + I`，**“降 A 但增干预”的修复会被拒**；
②动作白名单对该文档的 `\vspace`/行内字号切换打不通（一直 blocked）；
③退化与文档自带问题纠缠，闭环收敛到**不同的分页局部最优**（10 页 vs 干净稿 11 页），
A 差异里混着整篇版面差异。

#### B. 为什么 A_profile 对退化不敏感

方法：**只编译一次、不跑闭环**（新工具 `datasets/conf-specs/tools/profile_attr.py`），
用与影子**完全相同**的口径（`extract_pdf` + `evaluate_doc` + 门槛剔除 + 已启用权重）
把 A_profile 拆到每一维。

**`neurips-real`（决定性证据）**：clean / deg1 / deg2 的**渲染结果完全相同**——
页数 27/27/27，`whitespace.total_ratio` 中位三档都是 0.3304，六个维的归一化损失**逐位相同**，
A_profile 三档都是 1.245107。原因：注入的 `\vspace{3cm}`/`\newpage` 正好落在
`\section{Background}` 之前，**在分栏断页处被 TeX 丢弃**——A_profile 的唯一输入是渲染结果，
自然看不到它。而 A_defect 会动（58.14 → 58.74 → 59.74）：`score.py` 的 A 同时看**源码**
（`manual_vspace`、手动分页、质量宏缺失…都是 A 的项）。

**`demo`（非单调的机制）**：A_profile clean 0.688 → deg1 **0.677（不升反降）** → deg2 4.079
→ deg3 4.091 → deg4 3.849。逐维看：`\vspace` 把 `whitespace.total_ratio` 从 0.032 抬到 0.084，
却把 `balance.d_mid` 0.836→0.817、`visual_centroid_y` 0.790→0.658、`density.coverage_text`
0.917→0.892 三个维**压低了**；`+pagebreak` 让某页接近空白，CVaR 式 top-k 聚合立刻把所有维抬爆
（d_mid 4.41、centroid 5.60、whitespace 2.96）；`+overwide` 才让 `ratio.fig_text` 起振（0→0.854）。

**交叉校验**：同一探针在 `issues` 上得到 A_profile = 5.615216 / 5.615216 / 5.615216 / 5.737138，
与 E1 闭环里记录的退化态影子值**逐位一致**——说明 E1 的基线影子取值是可靠的（不是取错了 PDF）。

→ 结论：A_profile 是「**离会议常态的距离**」（带内损失 = 0，论文级用 CVaR top-k），
它测**异常**不测**缺陷**：①渲染上无效果的退化当然不动；②一段 3cm 空白在真实语料里本来就常见，
落在带内；③一页变空会非线性地把 A_profile 拉爆（不单调）。
→ 对 λ 的含义：**要让 A_profile 参与决策（λ>0），必须先把“缺陷敏感”与“常态偏离”拆开**
（例如把 12.1 式页级注入检验扩展成逐维门槛、或引入缺陷项子分数），否则闭环会被
「看起来正常但更糟」的版面骗过。这正是本阶段最重要的结论。

复现：

```bash
cd datasets/conf-specs
python3 tools/profile_attr.py demo neurips issues     # 每档只编译一次（不分档跑闭环）
# 产出 workbench-eval/profile_attr/attr_profile.json
```

### 1.6 诚实边界

- 退化是**源码级注入**（4 类），不是「任意排版灾难」；能覆盖的是规则可修的常见问题。
- `demo/issues` 是随仓库靶稿（非真实论文），单独列出；真实论文工程为 `neurips-real`
  / `paper-real`。
- 影子仍为影子（λ=0）：E1 只说明「A_defect 对退化敏感、A_profile 对这批退化不敏感」，
  **不**说明「λ>0 会让闭环决策更好」——而且 1.5-B 恰恰说明现在还不能开（见该节结论）。

---

## 2. E2 第二套工具链复测（矢量/文本层 vs 像素层）

### 2.1 口径

同一批真实论文 PDF，两条测量路径分别量取同一批页：

- ① **矢量/文本层**：`texopt/extract.py`（pdfminer）→ `page_metrics.v1`；
- ② **像素层**：`pdftoppm` 灰图 → `texopt/visual.py` + `page_metrics`。

三个同义量（`texopt/evalexternal.py::COMPARABLE`）：

| 矢量层 | 像素层 | 同量纲 | 口径差异 |
|---|---|---|---|
| `whitespace.total_ratio` | `non_ink_ratio` | 否 | 矢量=版心内留白结构量；像素=1-墨迹占比。只比排序 |
| `whitespace.trailing_ratio` | `bottom_blank` | 是 | 矢量=版心内页尾留白区域（**排满页恒 0**）；像素=最后一行墨迹以下的整页高度（**含页码带**） |
| `balance.visual_centroid_y` | `centroid_y` | 是 | 两边同约定（0=页底，1=页顶）。矢量只算版心内，像素含全页 |

### 2.2 结果（12 篇真实论文 × 每篇前 8 页，dpi 50）

| 矢量层 | 像素层 | 同量纲 | 中位 ρ | 最低 ρ | 中位 \|Δ\| | 退化篇数 |
|---|---|---|---|---|---|---|
| `whitespace.total_ratio` | `non_ink_ratio` | 否 | **0.5833** | 0.2381 | 0.7379 | 0/12 |
| `whitespace.trailing_ratio` | `bottom_blank` | 是 | None | None | 0.045 | **12/12** |
| `balance.visual_centroid_y` | `centroid_y` | 是 | **0.1852** | -0.6667 | 0.0223 | 0/12 |

### 2.3 两个真结论（都不是「两套工具链分歧」）

1. **`whitespace.trailing_ratio` 在排满的正文页上没有取值**：整篇 8 页窗口里矢量侧
   恒为 0（12/12 篇秩相关**退化**，代码里显式标 `degenerate/constant_side` 而不是
   只给一个 `None`）。全库 10415 页里该量非零仅 **6.58%**；E3 在 60 篇/765 页上
   量到 6.01%。→ 这是**该指标自身的可辨识性问题**（只在末页/稀疏页有值），
   与两条测量路径是否一致无关。该对因此应降级为「仅报告」。
2. **像素侧 `bottom_blank` 系统性高约 0.045**：因为像素层把**页码带**也算进"页尾
   留白"（最后一行墨迹以下是整页高度），而矢量层只在版心内算。两者量纲虽同为
   比例，但**分母/口径不同**，做绝对差比较会得到这个系统性偏置。

`total_ratio ↔ non_ink_ratio` 排序一致性中等（中位 ρ 0.58，最低 0.24），
方向一致但绝对值不可比（口径不同）；`visual_centroid_y ↔ centroid_y` 排序一致性弱
（中位 ρ 0.19，最低 -0.67）——矢量侧只看版心内文本/图，像素侧看整页墨迹，
**图多、跨栏浮动体多的页上两者分歧最大**（`worst` 列表逐页可见）。

### 2.4 局限

- 两条路径读的是**同一批 PDF**：只验证「渲染/解析链路不同带来的量取差异」，
  不构成两套完全独立的工具链互证。
- 未做栅格化 DPI 的敏感性分析（阶段 5 的 12.4 只做过 50→200 漂移 = 0，那是**同一
  路径内**的稳定性，不是此处跨路径一致性）。

---

## 3. E3 论文级报告（回应阶段 7 局限 L4：池化稀释）

### 3.1 方法

阶段 7 记录的局限 L4：页级池化会把「长论文里少数几页很差」稀释掉。
E3 因此**按论文**聚合档案判定（每篇一个 A_profile / D² / 异常页数），
并与页级池化口径并列报告。

### 3.2 结果（60 篇真实论文，复用缓存页指标，λ=0）

- 论文级 `A_profile` 中位 **0.7664**，P90 **1.3885**。
- 页级损失池化中位：`alignment.center_var` / `balance.d_mid` /
  `balance.visual_centroid_y` / `density.coverage_text` / `ratio.fig_text` /
  `whitespace.total_ratio` 均为 **0.0**（绝大多数页在带内，损失为 0）。

原始量在语料上的**可辨识性**（非空且非零的页占比，60 篇 / 765 页）：

| 原始量 | 有效页数 | 非零页数 | 非零占比 |
|---|---|---|---|
| `balance.d_mid` | 765 | 757 | 0.9895 |
| `balance.visual_centroid_y` | 765 | 765 | 1.0 |
| `density.coverage_text` | 765 | 759 | 0.9922 |
| `ratio.fig_text` | 759 | 311 | 0.4097 |
| `whitespace.total_ratio` | 765 | 764 | 0.9987 |
| `whitespace.trailing_ratio` | 765 | 46 | **0.0601** |

→ 这张表就是 E2 第 1 条结论的独立佐证（同一结论、不同抽样），也顺手给出了
`ratio.fig_text` 的稀疏程度（41%）。

### 3.3 局限

- E3 只改**报告口径**：不改验收、不改 λ、不参与任何决策的门槛。
- 论文级聚合目前用「论文内页级损失的中位/ P90 合成」，**未做**论文级的
  人类排序验证（同阶段 5 的 12.5，数据未采集 → null）。

---

## 4. 一句话总结（按实际测量值）

- **E1**（4 篇真编译闭环）：A_defect 对源码级退化**敏感**（单调 3/4、可见 3/4），
  闭环能把退化稿的 A 拉回 ≤ 干净稿（3/4）、且都 ≤ 自身退化态（4/4）；
  但 **`paper-real` 上不单调、修复不完全**，且 **影子 A_profile 只 1/4 同向**。
- **归因（1.5）**：`neurips-real` 的 deg1/deg2 在**渲染层完全无效**（注入的 `\vspace`/`\newpage`
  在分栏断页处被 TeX 丢弃），而 A_defect 看源码所以会动——**A_defect 看源码+渲染，
  A_profile 只看渲染且只测「常态偏离」**；`demo` 上 `\vspace` 甚至让 A_profile **下降**。
  → 结论：**λ>0 之前必须先拆开“缺陷敏感”与“常态偏离”**。
- **`paper-real` 修复不完全的原因**：`deg3` 轨迹里「[H]→[tbp]」让 **A 降了**（17.5→16.0）
  但 I 升到 2.8，按 `total=L·1e6+A+I` 被回滚；且 `vspace_rm`/`local_font` 一直被 blocked。
- **E2**：两条测量路径在**排序**上方向一致（整页留白 ρ≈0.58、纵向重心 ρ≈0.19），
  但**绝对量不可比**；顺带量到一个指标可辨识性问题（`trailing_ratio` 在全库 93.4% 的页上无取值）。
- **E3**：论文级口径可用（A_profile 中位 0.7664 / P90 1.3885），
  并量化各原始量覆盖率：`trailing_ratio` 6.0%、`fig_text` 41.0%、其余 ≥99%。
- **λ 仍为 0**：以上都不改变文档、不改变判定；λ>0 需先解决 A_profile 的敏感性
  （E1-③）+ 人类成对比较数据（阶段 7 步骤三）+ 用户审批。

---

---

## 5. 依据归因做的两处修复（2026-10-01）

### 5.1 （a）验收口径：A 优先，I 只做 tie-break

位置：`texopt/core.py::Optimizer._accept`（现返回 `(是否接受, 理由)`，理由进 `state.json` 与报告）。

新优先级：**L 违规数 → 压页阶段页数 → A 严格改善即接受 → 总分（含 I）tie-break**。
关键变化：旧口径用 `total = A + I` 一刀切，把“降 A 但增干预”的真修复也拒了
（1.5-A 里的 `paper-real` deg3）。现在每接受一步 **A 严格下降或 L 改善**，
“A 单调”成了闭环的不变量，比旧口径更好审计。松弛回拉（A 不变、I 下降）仍然保留。

回归锁：`tests/run_tests.py::acceptance_tests()`（8 项，含 E1 的真例）。

<!-- E1_RERUN_START -->
（E1 重跑结果待回填：新口径下 `paper-real` 的 A/I/页数变化）
<!-- E1_RERUN_END -->

### 5.2 （b）λ 前置门：把“缺陷敏感”与“常态偏离”拆开

问题本质（1.5-B）：A_profile 的每一维都是“离会议常态的**带外**损失”，带内恒为 0。
于是它对两类东西天然无梯度：①渲染上无效果的退化（源码里有、页面上一模一样）；
②“常见但难看”的版面（带内）。既然它测的是**常态偏离**，就不能直接拿它当
“排版质量”的奖励信号。

修复分两层：

1. **E4 缺陷敏感性检验**（`texopt/evalexternal.py::sensitivity_sweep`，
   入口 `tools/eval_external.py --only e4`）：用 E1 的 4 个**源码级**退化档 + **真编译**
   （每档只编一次，不跑闭环），逐维检查 A_profile 到底动不动；
   产出 `metrics/profiles/profile_sensitivity.json`（`lambda_eligible` / `blind_dims`）。
2. **代码强制的前置门**（`texopt/shadow.py::assert_lambda_allowed`，在
   `Optimizer.__init__` 调用）：**λ>0 且未过门 → 直接报错拒绝**（λ=0 不受影响）。
   门槛是“每维都得有响应”，不是打分：没证据就不允许把它变成优化目标。

<!-- E4_RESULT_START -->
结果（2026-10-01，4 篇 × 5 档，整段 619.6s）：

| 维 | 响应篇数 | 单调篇数 | 中位 Δ | 判定 |
|---|---|---|---|---|
| `balance.d_mid` | 4/4 | 2 | 1.4686 | responds |
| `balance.visual_centroid_y` | 4/4 | 1 | 2.8365 | responds |
| `density.coverage_text` | 4/4 | 1 | 0.9037 | responds |
| `whitespace.total_ratio` | 4/4 | 1 | 1.7125 | responds |
| `alignment.center_var` | 1/4 | 2 | 0.0 | **blind** |
| `ratio.fig_text` | 0/2 | 1 | 0.0 | **blind** |

**门禁结论：`lambda_eligible = false`**（2 个维对源码级退化无响应：
`alignment.center_var`、`ratio.fig_text`）。
另一点同样重要：即使「响应」的那 4 个维，**档间单调性也只有 1-2/4 篇**——
说明 A_profile 对退化的响应不只是“有些维看不见”，而是**整体不够稳定**。

→ 所以现在即使有人把 `aesthetic_lambda` 设成 >0，也会在 `Optimizer.__init__`
直接被代码拦下（`shadow.assert_lambda_allowed`），直到这两件事被真正修好：
补上能照亮盲维的注入项（或给它们补缺陷项子分数），并让响应在档间单调。
<!-- E4_RESULT_END -->

### 5.3 两个修复的联带效果

- 验收口径变了 → 所有闭环结果都要重跑一遍才能引用（E1 已重跑，见 6.1）。
- λ 仍然恒为 0（影子）；现在即使有人把 `aesthetic_lambda` 设成 >0，也会被代码拦下，
  直到 E4 的敏感性被真正修好（比如给每维补上缺陷敏感的注入项，或引入缺陷项子分数）。

复现：

```bash
cd /mnt/d/桌面/texopt
python3 tests/run_tests.py --full                       # 含 acceptance_tests + s8
cd datasets/conf-specs
python3 tools/eval_external.py --only e4                 # E4（真编译，约 10-15 分钟）
cat metrics/profiles/profile_sensitivity.json           # lambda_eligible / blind_dims
```

## 6. 复现命令


```bash
cd /mnt/d/桌面/texopt/datasets/conf-specs

# E1 端到端退化（真编译；每篇 干净 + 4 档，约 30-60 分钟）
python3 tools/eval_external.py --only e1 --e1-levels 4
python3 tools/eval_external.py --only e1 --e1-docs demo-fixture --e1-levels 2   # 快速自检（约 3 分钟）
python3 tools/eval_external.py --list-docs                                      # 看可用文档

# E2 第二套工具链（12 篇 × 8 页，dpi 50，约 2-3 分钟）
python3 tools/eval_external.py --only e2 --e2-papers 12 --e2-max-pages 8 --e2-dpi 50

# E3 论文级报告（离线，秒级）
python3 tools/eval_external.py --only e3 --e3-papers 60

# E1 归因：A_profile 逐维分解（每个退化档只编译一次，不分档跑闭环；约 5-8 分钟）
python3 tools/profile_attr.py demo neurips issues

# 三段结果合并写入 metrics/profiles/eval_external.{json,md}
cd /mnt/d/桌面/texopt && python3 tests/run_tests.py --full   # 含 stage8_tests（纯计算，不真编译）
```
