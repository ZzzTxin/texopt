# 审美量化模型（model2：A_soft + A_profile）

> 本目录只讲**审美量化这一块**：页面怎么量、怎么打分、怎么标定、怎么验证、哪里还不靠谱。
> 主流程（gate / model1 / 闭环优化）见仓库根目录 `README.md`。

## 1. 它是什么，在系统里的位置

```
                         ┌──────────── model2（本 README 的主体）─────────────┐
整篇重编译后的 PDF ──►   │  A_soft    : 绝对软指标（页密度/留白/重心…）        │
                        │  A_profile : 相对偏离（与同会议·同角色语料档案比）   │
                        └───────────────┬───────────────────────────────────┘
                                        │  M2 = A_soft + λ·A_profile（λ = 0）
                                        ▼
                 验收：字典序 (|gate|, M1, M2) —— M2 只在 M1 持平时作 tie-break
```

两点必须说清楚：

- **λ 恒为 0**（`texopt/shadow.py: LAMBDA`）。`A_profile` 目前只出现在报告与
  `state.json` 快照里，**不参与任何接受/回滚判定**；`shadow.assert_lambda_allowed`
  在代码层拦截 λ>0（需人类标定 + 审批）。
- `A_soft` 与 `A_profile` 都是**版面缺陷量 / 常态偏离量**，不是人类审美评分。
  系统不声称"审美最优"，只保证"评分可复现、方向可验证、退化会变差"。

两条数据通路，别混用：

| 通路 | 入口 | 粒度 | 用途 |
|---|---|---|---|
| 像素层（在线） | `texopt/visual.py`：PDF → 50dpi 灰度页图 → 行列墨迹统计 | 页 | 闭环里实时算 `A_soft` |
| 矢量/文本层（离线） | `texopt/extract.py`：pdfminer 文本行/字形/图框 → `page_metrics.v1` | 页（分层 role） | 建档案、标定、协议评测 |

## 2. 诚实边界（先看这段，再看数字）

1. `A_soft` 来自**渲染层像素统计**，不是语义理解：它不知道那张大图是好图还是坏图。
2. `A_profile` 只测"与同档语料的偏离"，**不测"缺陷"**——它天生对源码级退化不敏感
   （阶段 8 E1 实测：4 篇里 0/4 与 `A_defect` 同向），这正是 λ 保持 0 的直接证据。
3. 与人的一致性是**有限证据**：20 页排序 Spearman 0.46、12 对成对比较；
   Spearman 0.46 在 n=20 时标准误约 ±0.2，不能当作"接近人类审美"的强结论。
4. 部分指标已被证伪/降级：`band` 权重直接置 0（语料仅 5% 落在"正常带"内）；
   `whitespace.trailing_ratio` 在排满的正文页上无取值（全库仅 6.58% 非零），
   代码里显式标 `degenerate`。

## 3. 快速开始

```bash
cd /mnt/d/桌面/texopt

# ① 只跑影子评估（λ=0，只出报告，不改文档）
python3 optimize.py examples/demo.tex --shadow-only
#    -> workbench/aesthetic_shadow.md / aesthetic_shadow.json

# ② 正常优化（默认带影子观测，可用 --no-aesthetic-shadow 关掉）
python3 optimize.py examples/demo.tex

# ③ 结构化审美体检（指标精度 / 日志覆盖率 / 语料区间）
python3 tools/detector_check.py --only all      # -> workbench-detector/report.md

# ④ 回归（含 s6 开关影子判定一致性、s12 权重 artifact 漂移检查）
python3 tests/run_tests.py
```

## 4. 数据模型：`page_metrics.v1`

定义在 `texopt/page_metrics.py`（只定义 schema 与校验，不做提取）。每页强制带
`role`（统计必须分层），每个指标组带 `status`
（`extracted` / `partial` / `placeholder` / `unavailable`）与 `provenance`
（vector / text / pixel / log）。

| 组 | 关键字段 | 主要来源 | 现状 |
|---|---|---|---|
| `units` | `page_w_mm` / `usable_w_mm` / `columns` | vector | extracted（版心 `A_usable` 由正文尺寸行测出，双栏=两栏面积之和，栏间距不计） |
| `density` | `ink_ratio_text`、`coverage_text/figure/table/other` | vector+text（pixel 可选） | extracted；表格覆盖是"题注锚定浮动区"近似，不解析表格结构 |
| `ratio` | `fig_text`、`figtab_text` | vector | extracted |
| `balance` | `d_top/d_mid/d_bot`、`left_right`、`visual_centroid_y` | vector | extracted |
| `whitespace` | `total_ratio`、五类占比、`regions` | vector（4pt 网格掩码） | extracted（阶段 3 起结构化） |
| `alignment` | `left_var` / `right_var` / `center_var` | text | extracted |
| `consistency` | `figure_width_cv` / `caption_style_cv` | vector | partial |
| `readability` | `chars_per_line_mean`、`leading_ratio`、`font_pt` | text | extracted（`leading_ratio` 零膨胀，未过门槛） |
| `microtype` | overfull / underfull / vbox | log | 语料 PDF 无日志 → `unavailable`（线上优化有日志才可用） |
| `figure_quality` | `min_effective_dpi`、`aspect_outliers` | vector | partial |

## 5. `A_soft`：绝对软指标（平滑目标形式）

实现在 `texopt/score.py`（`SOFT_SPEC` / `soft_metric_loss` / `aesthetic_score`）。

### 5.1 公式

```
d    = |x - t| / s_side            （比值类指标先取对数：log(x/t)）
loss = w · (1 - exp(-d²/2))        （≤ w，目标处 0，两侧严格单调，无平台区）
单指标页级聚合 = 0.5·top(k) + 0.5·mean(all)      k = max(1, round(5%·页数))
A_soft = Σ 单指标聚合
```

- `t`：3898 页已录用语料里该指标的**中位数**；`s`：`t` 到 p5（下侧）/ p95（上侧）的距离。
- 一侧 `s=None` 表示**该侧不罚**（如 `ink_ratio` 上侧不罚：满版/整页图不是缺陷）。
- 单指标损失封顶 `SOFT_LOSS_CAP = 3.0`，极端页吃不掉全部权重。
- 聚合取「最差 5% 的均值 + 全体均值」各半：既对局部异常页敏感，又不被单页主导。

### 5.2 现行参数（`SOFT_SPEC`）

| 指标 | t | s_low | s_high | w | 方向依据（20 页人工排序） |
|---|---|---|---|---|---|
| `ink_ratio` | 0.120 | 0.076 | — | 1.0 | ρ=+0.50：人偏好"更满"，只罚过空 |
| `bottom_blank` | 0.066 | 0.025 | — | 0.8 | ρ=+0.42：多留白不罚，只罚贴边 |
| `top_blank` | 0.079 | 0.047 | 0.039 | 0.5 | 两侧都罚 |
| `max_gap` | 0.100 | — | 0.244 | 1.4 | 只罚大片空洞（唯一人工验证有效的量） |
| `band` | 0.004 | 0.030 | 0.051 | **0.0** | 阶段 9 判暂缓：语料仅 5% 在带内 |
| `left_blank` | 0.091 | 0.022 | 0.130 | 0.4 | 两侧都罚 |
| `right_blank` | 0.115 | 0.036 | 0.100 | 0.4 | 两侧都罚 |
| `top_bottom_ratio` | 1.031 | 0.515 | 1.292 | 1.0 | 对数空间，尺度 = log(p5/p50)、log(p95/p50) |

### 5.3 为什么不是"带内一律 0"

旧形式 `loss = W·max(0, lo-x)/N + W·max(0, x-hi)/N` 在带内恒为 0，导致
**20 页里 8 页总分为 0**、排序信号被抹平；且把"过满"当缺陷，与人偏好相反。

| 口径 | 旧（带形式） | 新（平滑目标） |
|---|---|---|
| 20 页人工排序 Spearman | 0.3146 | **0.4586** |
| 总分恰为 0 的页 | 8/20 | **0/20** |
| 不同总分个数 | 12 | **20** |

`SOFT_BANDS` 仍保留，但**只用于报告口径**（带命中率），不参与打分。

## 6. 页面视觉缺陷（像素层，单独检测）

`texopt/visual.py: page_metrics()` 逐页量：`ink_ratio`、`content_height`、
`top_blank`、`bottom_blank`、`max_gap`(+`max_gap_at`)、`band`、`left_blank`、
`right_blank`、`top_bottom_ratio`。

`find_defects()` 的判据（阈值取"明显差"的粗档）：

| 缺陷 | 判据 | severity |
|---|---|---|
| `giant_content` | `band ≥ 0.40`（单块内容占 ≥40% 页高） | high |
| `bottom_blank` | `≥0.35` / `≥0.25 且 ink>0.01` | high / moderate |
| `mid_gap` | `max_gap ≥ 0.28` 且位置在页中段（0.15–0.85）；`≥0.50` 升 high | moderate / high |
| `stranded_block` | `ink ≤ 0.06` 且 `band ≥ 0.05` 且底空 ≥0.30 | high |
| `near_empty` | `ink ≤ 0.02` | high |
| `density_imbalance` | 页间密度相差 ≥10 倍或 ≥30 个百分点 | moderate |

> **归属必须说清楚（代码为准）**：
>
> 1. 进 **M1 的 P**：`stranded_block`（1.2）、`near_empty`（0.6），× severity 系数
>    （`VISUAL_DEFECT_M1` + severity high=1.0 / moderate=0.6）。
> 2. 进 **M2 的 A_soft**：`bottom_blank` / `max_gap` / `ink_ratio` 等像素软指标——
>    走第 5 节那张 `SOFT_SPEC` 表，**不是**下面这张缺陷权重表。
> 3. 只做**出口门控**：任何 `high` 级缺陷 → 直接 `NEEDS_REVIEW`，不判 DONE。
>
> `visual.DEFECT_WEIGHT`（`giant_content` 1.5 等）目前只被 `defect_penalty()` 使用，
> 而该函数除测试外未接入评分——属历史口径，保留待重接；**不要**把它当成现行权重。

## 7. 分层：页面角色与留白分类

**角色**（`texopt/roles.py`，规则优先、可解释）：`title` / `section-head` / `body` /
`math-heavy` / `figure-page` / `table-page` / `references` / `appendix` / `last-page` /
`unknown`；正交信息（是否末页、章节起始、整页浮动）放在 `role_flags`，参考文献/附录
是**跨页状态机**。理由：整页图/表的密度与文字页完全不可比，必须"同类比同类"。

**留白五类**（`texopt/whitespace.py`）：`structural` / `boundary` / `float` /
`trailing` / `anomalous`。铁律：只有「尺寸超阈」**且**「无任何结构解释」才计
`anomalous`，其余四类是版式特征、**不惩罚**（White Space ≠ Bad Space）。

## 8. `A_profile`：档案 + 马氏距离 + 带外损失（λ=0）

```
A_profile = Σ w_i · norm(loss_i) + w_M · norm(D²)
loss_i    = 非单调带外损失（只有落到目标带外才罚）
D²        = 分层内马氏距离（稳健中心 + 收缩协方差，Ledoit-Wolf 解析式 δ）
```

- **档案**：`datasets/conf-specs/metrics/profiles/aesthetic_profile.json`
  （`aesthetic_profile.v1`，`profile_version = v2`，built_from：**608 篇 / 10538 页**）。
  三级：`venue_role`（主用）/ `role`（跨会议通用）/ `venue`（仅参考）。
- **可信度**：`n_papers ≥ 36 → high`，16–35 → `medium`，≤15 → `low`；
  **low 档不参与异常判定**，只作参考。
- **统计口径**：分位按**页**取；CI 用**按论文聚类的 bootstrap**（重采样论文而非页，
  否则同篇页高度相关会把 CI 假性收窄）。
- **去冗余**：Spearman |ρ| ≥ 0.8 的指标并查集聚组，每组只留一个代表。
- **单调性**：带外损失**非单调**——区间内不罚，超出才罚，避免"越居中越好"的伪目标。
- **权重**：阶段 7 标定（`weights.py`），验收要求"退化单调性不劣化 **且** 中位判别间隔
  严格变大"才 `applied=true`；人类 8 对数据把强权重拉回接近等权
  （`balance.d_mid` 2.65 → 0.70），因此当前权重主要来自消融拟合。

## 9. 标定与验证：每一层都问过"凭什么是这个数"

| 阶段 | 做了什么 | 结论 / 数字 |
|---|---|---|
| 0-1 | `page_metrics.v1` schema；角色标注 + 全库提取 | 608 篇 / 10538 页（`metrics/pages/`） |
| 2 | 审美档案（venue×role 正常范围 + CI + 可信度）+ 去冗余 | `profile_version=v2`；8 维马氏空间 |
| 3 | 留白结构化（五类 + region）+ 页眉页脚识别 | `whitespace.py`；`anomalous` 需"超阈且无结构解释" |
| 4 | 马氏距离 + 带外损失 `A_profile`（λ=0 影子） | `aesthetic.py`；只报告不判定 |
| 5 | 评测协议 12.1–12.6 | 见下表 |
| 6 | 影子接入 `score`/`core`（λ=0 观测钩子） | 开关影子，`status`/`accepted`/`M1`/页数逐项相同 |
| 7 | 权重校准（消融 + BT + 聚类 bootstrap） | 中位判别间隔 0.1157 → **0.1506**；`applied=true` |
| 9 | 检测器体检（量得准 / 认得全 / 区间对不对） | 像素误差 ≤1 像素行；日志漏检 8.7%/4.6% 修掉；`band` 判暂缓 |
| 10 | `A_soft` 改平滑目标形式 | Spearman 0.3146 → **0.4586**；并列 0/20 |
| 10b | 成对比较验收（12 对二选一，替代 20 页排序） | 12 题里 ≥10 对命中才算 p<0.05 |
| 11 | 缺陷严重度标定（15 题圆桌轮转 + BT + Jeffreys 先验） | 3 轮设计秩相关 0.880（5 轮 0.956、7 轮 0.989） |

### 阶段 5 协议结果（自洽性，不等于"与人类审美一致"）

| 检验 | 结果 |
|---|---|
| 12.1 负样本注入 | A 单调上升 100%（严格零回落 96.3%）；退化页定位 96.3% |
| 12.2 假阳率 | 卡方阈值 15.9%（重尾）→ 改**经验校准 5.71%**（目标 5%） |
| 12.3 会议可分性 | 1-NN 留一 0.529（随机 0.091），置换 p=0.0099 |
| 12.4 稳定性 | 重复测量完全一致；DPI 50→200 漂移 0 |
| 12.5 人类相关性 | **未采集 → 如实 null**（后来用阶段 10/10b 的小样本补了方向性证据） |
| 12.6 逐维门槛 | **6/8 维通过**；未过：`readability.leading_ratio`、`density.coverage_table`（只作报告项） |

### 外部验证里两条负面结果（必须保留）

- **E1**（4 篇真编译闭环）：`A_defect` 对退化敏感（单调 3/4、可见 3/4），
  但**影子 `A_profile` 0/4 同向**——A_profile 只看渲染且只测常态偏离，
  源码级退化会被 TeX 在断页处吞掉，A_profile 逐位不变。
- **E2**（12 篇真实论文前 8 页）：整页留白 ρ 中位 0.58、纵向重心 0.19；
  绝对值不可跨口径比。且 `whitespace.trailing_ratio` **12/12 篇秩相关退化**，
  全库 10415 页仅 6.58% 非零 → 该指标可辨识性问题，已在代码里标 `degenerate`。

## 10. 复现命令

```bash
cd /mnt/d/桌面/texopt

# 全库指标提取（矢量/文本层；--pixels 追加像素层，慢很多）
python3 datasets/conf-specs/tools/extract_metrics.py --limit 20 --venues cvpr

# 重算档案（分位 + 聚类 bootstrap；--no-ci 跳过）
python3 datasets/conf-specs/tools/build_profile.py \
    --pages datasets/conf-specs/metrics/pages \
    --out datasets/conf-specs/metrics/profiles/aesthetic_profile.json

# 协议评测 12.1-12.6（--render 额外做渲染层注入 + 重编译稳定性）
cd datasets/conf-specs
python3 tools/eval_protocol.py --pages-n 80 --perms 100
python3 tools/eval_protocol.py --only gate          # 只重算门槛，秒级

# 权重校准（消融 80 组 + bootstrap 200）
python3 tools/calibrate_weights.py --trials 80 --bootstrap 200 --apply

# 人工数据：成对比较 / 严重度
python3 tools/make_pair_sheet.py --build
python3 tools/make_pair_sheet.py --import answers.json
python3 tools/make_severity_sheet.py --build
python3 tools/apply_severity_weights.py --check     # 代码 ↔ artifact 漂移校验

# 外部验证与归因
python3 tools/eval_external.py --only e2 --e2-papers 12 --e2-max-pages 8 --e2-dpi 50
python3 tools/profile_attr.py demo neurips issues   # A_profile 逐维分解
```

## 11. 文件与产物索引

| 路径 | 作用 |
|---|---|
| `texopt/page_metrics.py` | `page_metrics.v1` schema + 校验/序列化/聚合 |
| `texopt/extract.py` | PDF（矢量/文本层）→ `page_metrics.v1`；版心 `A_usable` 测量 |
| `texopt/roles.py` | 页面角色规则器（含跨页状态机） |
| `texopt/whitespace.py` | 空白掩码连通域 + 五类留白 + region 列表 |
| `texopt/profile.py` | 档案构建（分位 / 聚类 bootstrap / Spearman / PCA，纯标准库） |
| `texopt/aesthetic.py` | 马氏距离 D² + 带外损失 `A_profile` |
| `texopt/visual.py` | 在线像素层：PDF→页图→`page_metrics`→`find_defects` |
| `texopt/score.py` | `SOFT_SPEC` / `soft_metric_loss` / `aesthetic_score`（→ M2） |
| `texopt/shadow.py` | 影子评估（λ=0）+ `eval_gate.json` 门槛剔除 |
| `texopt/evalproto.py` | 协议 12.1–12.6 |
| `texopt/weights.py` | 权重校准（消融 / BT / 验收） |
| `datasets/conf-specs/metrics/pages/` | 全库页级 `page_metrics.v1`（608 篇） |
| `datasets/conf-specs/metrics/profiles/` | `aesthetic_profile.json` + 敏感性分析 |
| `datasets/conf-specs/workbench-eval/eval_gate.json` | 门槛结果（影子自动加载） |
| `metrics/severity_weights_applied.json` | 严重度标定落库（P 权重用） |
| `docs/stage{0..12}_*.md` | 每个阶段的完整口径、数字与局限 |

## 12. 已知局限与下一步

1. **λ 仍为 0**：`A_profile` 不进验收。要开 λ>0，先得把"缺陷敏感"与"常态偏离"拆开
   （阶段 8 已证明当前实现两者混淆）。
2. **`band` 权重为 0**：语料里只有 5% 落在旧"正常带"内，量本身不可用，待重定义后再启用。
3. **`trailing_ratio` 退化**：排满的正文页上无取值，需换口径（或仅在末页/栏末使用）。
4. **两个维度没过门槛**（`readability.leading_ratio`、`density.coverage_table`）：
   只能作报告项，不能进 A。
5. **人类数据太少**：8 对（权重）、20 页排序、12 对成对比较、15 题严重度。
   建议成对比较攒到 ≥30 对再谈"与人类偏好一致"。
6. **在线/离线两套口径**（像素层 vs 矢量层）**不可直接比绝对值**，只能比方向
   （E2 已验证方向一致、绝对值不可比）。
