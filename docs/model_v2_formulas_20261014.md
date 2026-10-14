# texopt 评分模型 v2（2026-10-14 修订）

> **注（2026-10-14 晚，结构已升级到 v3）：** 模型已按用户意见重构为**三层**——
> 底层逻辑门（编译/PDF/页数/字号/边距/图表保真，必须满足、不评分）+ model1（M₁ = ρ·P + I）+ model2（M₂ = A_soft + λ·A_profile）。
> 新的公式、信号归属对照表与代码索引见 `model_v3_design_20261014.html`（或 `.md` 旁的 HTML 单文件版）。
> 本文保留为 v2 的公式底稿（其中 L 的定位已换成「底层逻辑门」，`l_violations` 已改名为 `gate_violations`）。

> 目的：把「两个数学公式」写成可读、可核对、可写进申报书的形式，
> 并落实 2026-10-14 的两条口径修正：
> ① 正文内容完整保留 **不再属于硬约束**；② 页数限制在**有要求时是 0/1 不可协商量，无要求时整个变量不存在**。
>
> 阅读建议：用支持 LaTeX 数学的编辑器打开（Typora / VS Code + Markdown+Math / Obsidian），
> 或直接看同名编译产物 `model_v2_formulas_20261014.pdf`。

---

## 0. 记号（两个公式共用）

| 记号 | 含义 |
|---|---|
| $x_0$ | 原稿（输入） |
| $x'$ | 候选稿 |
| $a=(a_1,\dots,a_n)$ | 施加的动作序列（`set_margin` / `set_fontsize` / `sanitize_float_specs` / …） |
| $R(x')$ | **整篇重编译后**的感知结果（页数、编译日志缺陷、页面图像指标） |
| $r$ | 要求规格 `Requirement`（模板或自定义 JSON） |
| $b=r.\text{page\_limit}$ | 页数上限；$b=\varnothing$ 表示「要求里没写页数」 |

**核心不变量**：所有量都是 $R(x')$ 的函数，也就是「先重编译、再全局重评」。
不存在对局部片段打分再拼起来的做法（局部最优 ≠ 全局最优）。

---

## 1. model1：可行性 + 干预代价

### 1.1 硬约束集合 $\mathcal{H}$（全部 0/1，不可协商）

只放**「一律不能触碰」**的项，共 4 类：

$$
\ell_{\text{compile}}(x') = 1-\mathbb{1}\big[R(x')\ \text{编译成功}\wedge \text{产出 PDF}\big]
$$

$$
\ell_{\text{page}}(x') =
\begin{cases}
\mathbb{1}\big[N_{\text{pages}}(x') > b\big], & b \ne \varnothing\\[2pt]
\boxed{\text{该维度不存在}}, & b = \varnothing
\end{cases}
\qquad\text{（← 你的第 2 条）}
$$

$$
\ell_{\text{spec}}(x') = \frac{1}{K}\sum_{j=1}^{K} \mathbb{1}\big[p_j(x') \ne p_j^{\text{req}}\big]
\quad\text{（字号 / 页边距 / fleqn / 目录 / 页眉：要求里点名了哪几项，}K\text{ 就是几项）}
$$

$$
\ell_{\text{fig}}(x') = \mathbb{1}\big[\ \text{图表指纹序列}(x') \ne \text{图表指纹序列}(x_0)\ \big]
$$

### 1.2 L 的完整定义（修订版）

$$
\boxed{\;
L(x') \;=\; \sum_{i \in \mathcal{H}} w_i\,\ell_i(x')
\;=\;
w_c\,\ell_{\text{compile}} + w_p\,\ell_{\text{page}} + w_s\,\ell_{\text{spec}} + w_f\,\ell_{\text{fig}}
\;}
$$

- 每一项 $\ell_i \in \{0,1\}$，**没有中间态**：页数超 0.2 页和超 5 页在 $L$ 里是同一件事。
- 若 $b=\varnothing$，$\ell_{\text{page}}$ 直接**不出现在求和里**（不是取 0，而是变量不存在）——
  代码里的写法就是 `if req.page_limit:` 一层门。
- 分数语义：$L$ 是「违反了几条不可协商项」，最小值为 0。

### 1.3 正文内容保留：从硬约束里拿掉（← 你的第 1 条）

**旧写法**（已废弃）：$\ell_{\text{content}} = 1-\mathrm{Keep}(x')$ 放在 $\mathcal{H}$ 里 ⇒
任何改动正文的动作都让 $x'$ 直接不可行 ⇒ 与后续「语义抛光」阶段天然冲突。

**新写法**：内容偏差变成一个**软项** $D_{\text{content}}$，进入代价侧，不进入可行性判定：

$$
\mathrm{Keep}(x') = \frac{\sum_{c}\min\big(n_c(x'),\,n_c(x_0)\big)}{\sum_{c}\max\big(n_c(x'),\,n_c(x_0)\big)},
\qquad
D_{\text{content}}(x') = 1-\mathrm{Keep}(x')
$$

其中 $n_c(\cdot)$ 是字符 $c$ 在「内容面文本」中的出现次数；「内容面文本」= 抽正文 →
扩展归一（抹掉排版命令可动面：浮动体参数、图宽、依赖长度参数、`\newpage`、`\noindent`、
字号乱标、表格列格式等）→ 空白折叠。即**只统计真正的文字内容**。
$D_{\text{content}}=0$ 表示内容面完全一致；注意这是**字符多重集 Jaccard 重合率**，
增删都会计入偏差（早期版本用「原文字符覆盖率」，加句会被误判为 0，已修正）。

代价侧权重 $\beta=$ `CONTENT_PENALTY` $=50$（强偏好：能不动就不动，但**不是**禁止）。
语义抛光阶段再加一道硬底线：$\mathrm{Keep}(x') \ge \kappa$（内容保留率下限，$\kappa$ 待定标）。

> 诚实边界：$D_{\text{content}}$ 是**改动幅度代理**，不是语义等价证明。
> 多重集重合率对「同义改写」是敏感的（会算成偏差），这符合我们「先保守、宁可多报」的取向。

### 1.4 I：干预代价（最小干预原则）

**结构代价**（代码 `intervention_cost()`）：

$$
I_{\text{struct}}(x') = 0.5\,|\Delta m| + 3.0\,|\Delta f| + 0.4\,N_{\text{float}} + 0.4\,N_{\text{width}}
$$

**完整代价项**（含内容软项，即总分里实际相加的量）：

$$
I(x') = I_{\text{struct}}(x') + \beta\,D_{\text{content}}(x'), \qquad \beta = \text{CONTENT\_PENALTY} = 50
$$

| 项 | 含义 | 现值 |
|---|---|---|
| $\Delta m$ | 页边距相对原稿的偏移（mm） | 系数 0.5 / mm |
| $\Delta f$ | 正文字号降档数 | 系数 3.0 / 档 |
| $N_{\text{float}}$ | 浮动体位置参数被改的处数（`[h]→[tbp]` 等） | 系数 0.4 / 处 |
| $N_{\text{width}}$ | 图片宽度表达式被改的处数 | 系数 0.4 / 处 |
| $\beta D_{\text{content}}$ | 正文改动幅度软项 | 系数 50 |

设计含义：**松弛方向天然便宜**。把参数从「压到极限」往回收，$I$ 自动下降，
所以达标后系统会自己把边距/字号拉回「最宽松且最优」的临界点。

### 1.5 可行性门 + 排序规则

$$
x' \text{ 可行} \iff L(x') = 0
\qquad;\qquad
J_1(x') =
\begin{cases}
+\infty, & L(x') > 0\\[2pt]
I(x'), & L(x') = 0
\end{cases}
$$

候选验收用**字典序**：先比 $L$（$0$ 优于任何正数），$L$ 相同再比 $I$。

> 与旧实现的等价性：现在是 `total = 1e6 * len(lv) + a + i`，那个 $10^6$ 就是「$+\infty$」的手写版。
> 语义上等价，但写成可行性门之后，公式可以进文档、权重不再需要「大到能掩盖 A 和 I」这种隐式约定。
> **本次改动已把语义换掉（内容项移出 + 软项），但没有删除 $10^6$ 这个实现细节**——
> 想彻底换成可行性门 + 字典序，是一个独立的小重构，可以单独做。

### 1.6 与「上一版连续化 L」的差异（你第 3 条问的那版）

上一版我把 $L$ 写成 $\sum_i w_i\ell_i$ 时，让 $\ell$ 是**连续**的（比如
$\ell_{\text{page}}=\max(0,N-b)/b$），并建议把内容项也连续化。你的两条意见直接否掉了它：

| 项 | 上一版（连续化） | 本版（修订后） | 依据 |
|---|---|---|---|
| 页数 $\ell_{\text{page}}$ | $\max(0,N-b)/b$，有梯度 | **0/1**，超了就不可行 | 你的第 2 条 |
| 正文内容 | 连续 $\ell_{\text{content}}$（仍在 $\mathcal{H}$） | **移出** $\mathcal{H}$，变软项 $\beta D_{\text{content}}$ | 你的第 1 条 |
| 编译/规范/图表 | 0/1 | 0/1（不变） | — |

### 1.7 一个必须写清楚的取舍：目标函数没有梯度了

页数改成 0/1 之后，$L$ **在页数维度上不提供任何搜索信号**（超 1 页和超 5 页同分）。
所以：

- **目标函数**：严格 0/1（按你的要求，不可协商）；
- **搜索启发式**：压页阶段单独用「还差多少」$\;g(x')=\max(0,N_{\text{pages}}(x')-b)$ 来**选动作方向**
  和**排序候选**（只影响「先试哪个动作」），并作为 advisory 输出给用户（「离达标还差 0.3 页」）；
- $g$ 绝不进入 $L$，也绝不参与最终验收——验收只认 $L=0$。

这样既保留了你要的「不可协商」，又不会让搜索退化成随机漫游。

---

## 2. model2：审美量化 A

### 2.1 总式

$$
\boxed{\;A(x') = A_{\text{defect}}(x') + \lambda\,A_{\text{profile}}(x')\;},
\qquad \lambda = 0 \ \text{(影子模式，当前默认)}
$$

> 说明：你说的「model2 可视化完整公式」就是这一条 + 下面 2.2 的七步；
> 它对应的**源代码位置见第 3 节**。$A$ 是**排版质量/审美代理**，不是人类审美评分。

### 2.2 $A_{\text{defect}}$：可检测缺陷（当前真正在生效的一层）

$$
\begin{aligned}
A_{\text{defect}} =\;& 1.0\,N_{\text{overfull}} + 0.6\,N_{\text{underfull}}
+ 1.0\,N_{\text{vboxOver}} + 1.4\,N_{\text{vboxUnder}}\\
&+ 1.6\,N_{\text{floatwarn}} + 1.2\,N_{\text{tabOverwide}} + 0.3\,N_{\text{warn}}
+ 1.0\,N_{\text{figOverwide}}\\
&+ 2.0\,\mathbb{1}[\text{质量宏缺失}]\\
&+ \sum_{fe}\Big(0.8\,\mathbb{1}[\text{spec 不稳定}] + 0.5\,\mathbb{1}[\text{spec}=H]\Big)
+ \sum_{h} w_{\text{hyg}}(h) + D_{\text{vis}}\\
&+ 2.5\,\mathbb{1}[\text{缺目录}] + 2.5\,\mathbb{1}[\text{缺页眉}] + 1.5\,\mathbb{1}[\text{未着色}]
\end{aligned}
$$

- $w_{\text{hyg}}$：源码卫生项权重表（`HYGIENE_WEIGHT`，按「可修性 × 影响度」定）；
- $D_{\text{vis}}$：页面图像层的视觉缺陷惩罚，
  $D_{\text{vis}}=\sum_d \text{weight}(d)\cdot\text{severity}(d)$，$d\in\{$giant\_content, stranded\_block, bottom\_blank, mid\_gap, near\_empty, density\_imbalance$\}$。

### 2.3 $A_{\text{profile}}$：与会议常态的偏离（影子模式，$\lambda=0$）

设页面 $p$ 的角色 $\text{role}(p)=r$，会议 $v$，栏数 $l$，取分层 $s=(v,r,l)$ 的统计档案
$\{m_i,\,s_i,\,[\text{lo}_i,\text{hi}_i],\,R,\,\delta,\,\text{ref}_i,\,d2_{\text{ref}}\}$（$m$=中位数，$s$=IQR，$R$=相关阵）：

1. 重尾变换：$\tilde x_i=\log(1+x_i)$（仅正比率类维度，如 `ratio.fig_text`）
2. 标准化：$z_i=\mathrm{clip}\big((\tilde x_i-m_i)/s_i,\,-4,\,+4\big)$
3. 带外损失（非单调、双向）：$\text{loss}_i = W_{\text{low}}\dfrac{\max(0,\text{lo}_i-\tilde x_i)}{s_i} + W_{\text{high}}\dfrac{\max(0,\tilde x_i-\text{hi}_i)}{s_i}$，$W_{\text{low}}=1.2>W_{\text{high}}=1.0$
4. 分项归一化：$\widehat{\text{loss}}_i=\min\!\big(\text{loss}_i/\text{ref}_i,\,20\big)$，$\text{ref}_i$ 取该档语料自身 P90
5. 马氏距离：$D^2=z^{\top}\Sigma^{-1}z$，$\Sigma=(1-\delta)R+\delta I$，$\delta$ 用 Ledoit–Wolf 解析式；$\widehat{D^2}=D^2/d2_{\text{ref}}$
6. 页 → 文档聚合（CVaR 式）：$\text{pool}(u)=0.5\cdot\text{topk}(u)+0.5\cdot\text{mean}(u)$，$k=\max(1,\mathrm{round}(0.05\,N_{\text{pages}}))$
7. 合成：

$$
A_{\text{profile}}=\frac{\sum_i w_i\,\text{pool}(\widehat{\text{loss}}_i) + w_M\,\text{pool}(\widehat{D^2})}{\sum_i w_i + w_M},
\qquad w_i\equiv 1\ (\text{未标定}),\ w_M=1
$$

### 2.4 诚实边界（写文档时必须带上）

- $A_{\text{profile}}$ 是**排序量**，不是人类审美评分；它只覆盖「第二层：常态偏离」，第三层主观偏好未建模；
- $A_{\text{defect}}$ 看**源码 + 渲染**，$A_{\text{profile}}$ 只看**渲染**，两者测的不是一回事，只能相加不能互相替代；
- $\lambda$ 标定未通过前置门之前恒为 0（影子模式只报告、不参与验收）。

---

## 3. 源代码位置对照表（你第 5 条要的）

仓库根：`/mnt/d/桌面/texopt/`（行号为 2026-10-14 修订后）

| 公式部件 | 文件 | 函数 / 常量 |
|---|---|---|
| $L$ 违规清单（硬约束判定） | `texopt/score.py` | `l_violations()` L309 |
| $L$ 的 $10^6$ 实现 / 合成 | `texopt/score.py` | `L_PENALTY` L36、`total_score()` L462 |
| 正文归一化 $\tilde B$、$\mathrm{Keep}$ | `texopt/score.py` | `_norm_body()`、`body_unchanged()` L213、`semantic_diff()` L194 |
| $D_{\text{content}}$ 软项（**本次新增**） | `texopt/score.py` | `content_deviation()` L420、`_content_text()` L414、`CONTENT_PENALTY` L39 |
| 页数口径（总页/正文页、临界判定） | `texopt/score.py` | `page_status()` / `judge_pages()` / `within_limit()` |
| $I$ 干预代价 | `texopt/score.py` | `intervention_cost()` L441 |
| $A_{\text{defect}}$ | `texopt/score.py` | `aesthetic_score()` L368、`HYGIENE_WEIGHT` L42 |
| $D_{\text{vis}}$（页面图像层） | `texopt/visual.py` | `visual_defects()` L416、`defect_penalty()` L423、`DEFECT_WEIGHT` L234、`analyze_pdf()` L386、`page_metrics()` L244 |
| $A_{\text{profile}}$ 第 1–5 步（档） | `texopt/aesthetic.py` | `class Detector` L336（`vector` L376 / `mahalanobis` L407 / `band_loss` L421 / `norm_loss` L451 / `norm_d2` L457 / `score_page` L464） |
| $A_{\text{profile}}$ 第 6 步（CVaR 聚合） | `texopt/aesthetic.py` | `pooled_agg()` L105、`topk_mean()`、`percentile()` |
| $A_{\text{profile}}$ 第 7 步（合成） | `texopt/aesthetic.py` | `evaluate_doc()` L633、`W_LOW/W_HIGH/W_D2` L43–45 |
| 马氏/收缩/卡方 | `texopt/aesthetic.py` | `corr_from_z()` L138、`lw_delta()` L164、`shrink()` L194、`chi2_sf()` L274、`chi2_isf()` L320 |
| 档案构建（语料 → 分层档案） | `texopt/aesthetic.py` | `build_block()` L481、`pick_detector()` L605 |
| 审美权重标定 | `texopt/weights.py` | `a_profile_from_parts()` L136、`weights_from_trials()` L241、`ablation_weights()` L264、`fit_bradley_terry()` L348、`accept_verdict()` L318 |
| 影子模式接入 | `texopt/shadow.py` | `evaluate_pdf()` L151、`snapshot()` L170、`gate_drop_dims()` L89 |
| 文档/口径 | `docs/` | `stage2_profile.md`（档案）、`stage4_aesthetic_profile.md`（$A_{\text{profile}}$）、`stage5_eval_protocol.md`（验收协议）、`stage6_shadow_integration.md`（影子接入）、`stage7_weight_calibration.md`（λ 标定）、`stage8_eval_external.md`（外部验证） |

---

## 4. 本次改动清单

1. **`Requirement.content_hard`（默认 `False`）** — 正文保留口径开关（`texopt/requirements.py`）。
2. **`score.py`**
   - 新增 `CONTENT_PENALTY = 50.0`、`_content_text()`、`content_deviation()`；
   - `l_violations()` 里的内容检查改为 `content_hard=True` 才生效；
   - `total_score()` 增加软项并返回 `d_content` / `content_preserved`；
   - D 的口径定为**内容面**（`_norm_body_ext` 归一 + 空白折叠）字符多重集 Jaccard，
     排版命令可动面不计入，增删均计偏差。
3. **`tests/run_tests.py`** — 新增 4 条内容口径回归用例（默认不进 L / 开关可回旧口径 / 偏差率 > 0 / 一致时为 0）。
4. 页数口径**无需改代码**：现有 `l_violations()` 里就是 `if req.page_limit:` 门 + 0/1 条目，
   已满足「有要求=不可协商、无要求=变量不存在」。
5. 已知小 bug（待修）：`aesthetic.py::evaluate_doc()` 报告里
   `norm_d2_top` 与 `norm_d2_p90` 同值、`dim_norm_top` 与 `dim_norm_p90` 同值，两列目前无区分意义。
