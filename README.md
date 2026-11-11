# texopt —— 论文整体排版优化 Agent

输入一篇 `.tex` 和一份「要求规格」（期刊/会议模板、页数上限、自定义规则），
输出一篇**门禁通过、全局评分单调不劣化、正文一字不改**的优化稿，以及可审计的报告
（每一步的全局评分轨迹、接受/回滚理由、残余问题与建议）。

> 定位（不变）：做的是**论文整体排版优化**。Page Limit 只是要求规格里的一个可选字段，
> 不是系统主体；纯排版手段穷尽后才允许语义抛光（Phase 6，尚未实现）。
>
> 术语诚实性：`A_soft` 是**可复现的版面缺陷量**，不是"人类审美评分"；内容校验是
> **严格归一化文本保持检查**，不声称"证明语义等价"；系统**不声称全局最优**，
> 只保证"字典序单调不劣化 + 有界收敛"。

模型版本 **v3**（gate + model1 + model2 两线分离），当前进度 **阶段 16**（2026-11-02）。

---

## 目录

1. [当前状态](#1-当前状态2026-11-11阶段-16)
2. [定位与边界](#2-定位与边界)
3. [设计原则：规则 / 算法 / 模型 / 编译器](#3-设计原则规则--算法--模型--编译器)
4. [打分：gate + 两条线](#4-打分gate--两条线)
5. [闭环与验收](#5-闭环与验收)
6. [动作体系（28 个白名单动作）](#6-动作体系28-个白名单动作)
7. [要求对接：模板 / 会议 / 自定义](#7-要求对接模板--会议--自定义)
8. [感知层](#8-感知层)
9. [模型在环（Model-in-the-loop）](#9-模型在环model-in-the-loop)
10. [单页诊断：局部 vs 整体](#10-单页诊断局部-vs-整体)
11. [输出状态](#11-输出状态)
12. [标定链与实验资产](#12-标定链与实验资产)
13. [仓库结构与数据策略](#13-仓库结构与数据策略)
14. [测试与回归](#14-测试与回归)
15. [已知局限](#15-已知局限)
16. [下一步](#16-下一步)
17. [文档索引](#17-文档索引)

---

## 1 当前状态（2026-11-11，阶段 16）

| 项 | 现状 |
|---|---|
| 模型 | **v3**：底层逻辑 gate（一票否决）+ `M1 = ρ·P + I` + `M2 = A_soft + λ·A_profile`，验收**严格字典序 `(|gate|, M1, M2)`** |
| 关键参数 | `ρ = 15`（人工无差异点标定，区间约 [5,32]）；P 的 11 项里 **7 项**统一到 `w = c*/ρ`（口径 A），4 项仍为先验；`β = 50`；`λ = 0`（A_profile 只报告，不参与验收） |
| 闭环 | 感知 → 候选动作 → 整篇重编译 → 全局重评 → 接受/回滚；gate 有违规先跑**定向修复**（含阶段 15 的「暂存链」），失败才 `BLOCKED_GATE` |
| 回归 | `python3 tests/run_tests.py` → **332 通过 / 0 失败 / 0 跳过**（2026-11-11 全量实测，约 18 分钟） |
| 代码量 | `optimize.py` + `texopt/*.py` 共 24 个文件、约 **1.31 万行**（纯标准库 + TeX 工具链） |
| 仓库 | 跟踪 **477 个文件 / 15MB**；`paperfit-bench-originals`、`sources/raw`、`metrics/pages`、`workbench-*` **不入库**（策略见 §13） |
| 语料 | 版面档案 200 篇已录用论文 / 3898 页；评测语料 608 篇 / 10538 页 |
| 尚未做 | `λ>0` 参与验收、SOFT_SPEC v2 落地、语义抛光（Phase 6）、跨文档类模板迁移、历史版本存档、`fig_overwide` 权重标定、第二评分人 |

---

## 2 定位与边界

**做**

- 按目标期刊/会议/自定义要求，把一篇能编译的论文排到"合规 + 版面更干净"。
- 修的是**版面面**：页边距、字号档、浮动体位置参数、图宽、表格列宽、断行质量宏、
  手动分页/过大 `\vspace`/行内字号乱标、标题字号、列表间距、页眉、目录、标题着色。
- 每改一处都**整篇重编译**，用全局评分仲裁；变差就回滚，并把这件事写进报告。

**不做**

- 不改正文文字/词序/标点/公式/引用/标签/图表内容与图文件，不改注释，不换文档类。
- 不为了"看起来优化成功"伪造结论：修不动就 `NO_IMPROVEMENT` / `EXHAUSTED` 并给建议。
- 不把 LLM 当万能修理工：LLM 只能提**白名单动作**，执行与验收全在程序侧。

内容校验口径：正文区域**归一化后**逐字符比较；属于"排版面"的 token
（手动分页、过硬 `\vspace`、行内字号、断词点 `\-`、列表间距选项、表格环境名/列格式、
浮动体位置参数、插图宽度）允许被确定性动作删改，不判违规。阶段 12 起，正文硬改动
属 gate 的**不可修复项** → 直接 `BLOCKED_GATE`。

---

## 3 设计原则：规则 / 算法 / 模型 / 编译器

> **规则负责底线，算法负责搜索，模型负责复杂判断，编译器负责现实验证。**

| 层次 | 问题类型 | 决策者 | 例子 |
|---|---|---|---|
| **Level 1** | 硬性约束/明确规则 | 确定性程序 | 能不能编译、页数、字号、边距下限、fleqn、正文是否被改 |
| **Level 2** | 可检测 + 可量化 | 感知 + 评分 + 候选搜索 | overfull/underfull、vbox（孤行寡行代理）、浮动体警告、超宽图表、不稳定 float spec |
| **Level 3** | 复杂整体布局判断 | LLM（模型在环） | 留白是否过大、视觉重心、图浮到哪/多大、图文关系 |

Level 1 直接改并复查，不调用 LLM；Level 2 走闭环搜索；Level 3 由 LLM 提结构化提案，
程序执行-编译-重评，变好保留、变差回滚，再把新状态交回 LLM。

---

## 4 打分：gate + 两条线

```
排序（严格字典序）：(|gate|, M1, M2)

gate  底层逻辑：必须满足，不满足 = 不可行，不产生分数
M1 = ρ·P + I                model1（主）：缺陷量与干预代价，越小越好
M2 = A_soft + λ·A_profile   model2（审美）：λ 默认 0，A_profile 只报告
```

验收口径：**M1 变差一律否决**，M2 再小也不补偿；M1 完全持平时 M2 才作 tie-break。
旧的 `total = L_fail×1e6 + A + I` 已废弃（见 `docs/stage12_gate_exit_two_lines_20261030.md`）；
老术语对照：`L` → gate、`A` → M2（A_soft）、`P` 与 `I` 合成 M1。

### 4.1 gate（一票否决）

| 项 | 判据 |
|---|---|
| 编译 / 渲染 | 能否产出 PDF（超时强杀、错误率上限） |
| 内容完整 | 正文归一化 diff 为空（硬改动 = 不可修复） |
| 页数 | 有要求时按**正文页口径**（pdftotext 定位参考文献首页 k，仅 k−1 超限才判违规） |
| 硬性规范 | 要求点名的字号、页边距下限、公式居中（fleqn）、目录/页眉 |
| 图形保真 | 图必须来自原 PDF 裁切，不接受重绘 |

### 4.2 `M1 = ρ·P + I`

`P`（页面缺陷，半硬性，带逐项比重）：

| 缺陷 | 权重 | 来源 |
|---|---|---|
| overfull（正文行溢出） | 1.696 | 无差异点 c\*=11.5 |
| vbox_under（垂直欠满，孤行寡行代理） | 1.033 | c\*=7.0 |
| floatwarn（浮动体被强改） | 1.033 | c\*=7.0 |
| tab_overwide（表格超宽） | 1.033 | c\*=7.0 |
| spec_H（`[H]` 强排） | 1.033 | c\*=7.0 |
| underfull（正文行欠满） | 0.737 | c\*=5.0 |
| vbox_over（垂直溢出） | 0.737 | c\*=5.0 |
| fig_overwide（图片超宽） | 1.0 | 先验（未标定） |
| macros_missing（断行质量宏缺失） | 2.0 | 先验（人不可判） |
| unstable_spec（浮动参数不稳定） | 0.8 | 先验（人不可判） |
| warn（其余编译 Warning） | 0.3 | 先验（人不可判） |

另有源码卫生项（`HYGIENE_WEIGHT`，手动分页 1.0、标题字号 0.8、过大 vspace/列表间距/
长词/图片过大 0.6、行内字号 0.5 等）与页面图像层缺陷中属"结构/放置"类的
（`VISUAL_DEFECT_M1`：内容孤立 1.2、近乎空白页 0.6）。

`I`（干预代价，越小越好）：`I = I_struct + β·D_content`

- `I_struct`：页边距偏离 mm（0.5/mm）、字号降档（3.0/档）、被改浮动体参数/图宽处数。
- `D_content`：正文改动幅度（默认 0；`β = 50` 是强偏好，不是硬约束）。

### 4.3 `M2 = A_soft + λ·A_profile`

`A_soft` 用**平滑目标形式**：每个指标给目标 `t`（已录用语料中位数）与两侧尺度 `s`，

```
d = |x − t| / s_side        loss = w · (1 − exp(−d²/2))    ≤ w
```

目标处为 0、两侧严格单调、有平台区取消、有界封顶（`SOFT_LOSS_CAP = 3.0`）。

| 指标 | 目标 t | 单侧 | w | 说明 |
|---|---|---|---|---|
| `max_gap` | 0.100 | 只罚大洞 | 1.4 | 唯一经人工验证有效的量 |
| `ink_ratio` | 0.120 | 只罚过空 | 1.0 | 满版/整页图不是缺陷 |
| `top_bottom_ratio` | 1.031 | 双侧（对数空间） | 1.0 | 上下失衡 |
| `bottom_blank` | 0.066 | 只罚贴边 | 0.8 | 多留白不罚 |
| `top_blank` | 0.079 | 双侧 | 0.5 | |
| `left_blank` / `right_blank` | 0.091 / 0.115 | 双侧 | 0.4 / 0.4 | 阶段 16 判定为冗余项，待 v2 处理 |
| `band` | 0.004 | 双侧 | 0.0 | 阶段 9 判暂缓（阈值型，连续分无效） |

`A_profile`（与同会议·同角色·同栏数语料档案的马氏距离带外损失）在 **λ = 0** 时
只写报告、不参与任何判定，`shadow.assert_lambda_allowed` 在代码级拦 `λ>0`。

阶段 16 体检结论（`docs/stage16_model2_metrics_20261102.md`）：8 项里 3 项是准常数
（`bottom_blank`/`left_blank`/`right_blank`，占原分值 33%）、1 项阈值型（`band`）、
4 项保留但需改口径（`ink_ratio` 按角色分层、`max_gap` 排除末页自然留白）。
v2 草案（3 连续 + 1 阈值 + 角色门控）**尚未落地**，见 §16。

### 4.4 标定链：每个数字从哪来

| 参数 | 口径 | 题量 | 产物 |
|---|---|---|---|
| `ρ = 15` | 人工无差异点：缺陷保留 vs 修好+代价 c（三选一含"无差异"） | 两轮 15 题 + 6 题一致性复核（6/6） | `metrics/rho_tradeoff_20261031.json` |
| P 的 7 项权重 | `w = c*/ρ`，再按口径 A（总权重和不变）缩放 | 两轮 33 题（含 4 道空题全对） | `metrics/pweight_applied_20261102.json` |
| 其余 5 项 | 阶段 11「人判严重度 ÷ 语料频率」或先验拍值 | 15 题圆桌轮转 + BT | `metrics/severity_weights_applied.json` |
| `A_soft` 目标/尺度 | 已录用语料分位数（200 篇 / 3898 页） | — | `metrics/soft_identifiability_20261102.json` |

漂移校验：`python3 tools/pweight_combine.py --check`、`python3 tools/apply_severity_weights.py --check`
（代码常量 ↔ artifact 双向比对）。

---

## 5 闭环与验收

```
baseline 感知（源码 L1 / 日志 L2 / PDF L3）
  └─ gate 不过 → 定向修复（只做能修 gate 的动作；单步不达标进「暂存链」）
       └─ 达标 → 进入常规优化
  └─ gate 过 → 枚举候选动作 → 逐个试：
       应用 → 整篇重编译 → 全局重评 → 字典序变好才接受，否则回滚
  └─ 连续 min_stall_rounds（默认 2）轮无改善 → 收尾、出报告
```

**全局性（局部最优 ≠ 全局最优）**：每个候选修复都要先整篇重编译再全局重评——修好第 3 页
孤行却弄坏第 7 页浮动体的改动会被判负回滚。压页阶段放宽为"页数不增"以吃组合收益，
达标后自动把参数拉回"最宽松且最优"的临界点（松弛天然发生）。

**连档压页（阶段 15 修复）**：TeX 断页是台阶式的，收一档边距常不兑现。旧逻辑要求每个
单步都严格减页 → "连收两档才减一页"被永久挡死。现改为**暂存链**：不增页的单步可暂存，
后续兑现则整链提交；超过 `gate_repair_plateau = 3` 档仍未兑现则整链回滚到链首。

---

## 6 动作体系（28 个白名单动作）

`texopt/actions.py` 实现、`texopt/whitelist.py` 注册（动作名 + 参数校验 + level）。
全部**幂等、可回滚**，且没有任何一条能绕过全局评分。

| 类别 | 动作 |
|---|---|
| 版心 / 字号（仅 `--tune-geometry` 授权） | `set_margin`、`set_fontsize` |
| 浮动体 | `sanitize_float_specs`、`set_float_spec` |
| 图 | `normalize_fig_width`、`set_fig_width`、`reduce_oversized_figures`、`shrink_oversized_figures` |
| 表 | `fix_table_width`（改 tabularx 自适应列宽，不 resizebox） |
| 断行 / 间距 | `inject_quality_macros`、`add_hyphenation_points`、`break_long_urls`、`reduce_list_spacing`、`remove_excessive_vspace`、`normalize_parskip`、`balance_pages` |
| 卫生 / 结构 | `remove_manual_pagebreak`、`normalize_local_font_size`、`normalize_heading_size`、`normalize_title`、`normalize_header`、`drop_fleqn`、`insert_toc`、`add_header`、`color_headings`、`strip_reading_aids`、`remove_warning_boxes`、`remove_mid_multicols` |

查看可用动作：`python3 optimize.py --list-actions`。

---

## 7 要求对接：模板 / 会议 / 自定义

优先级：**会议/期刊模板 < `--require` 要求文件 < `settings.json` < CLI 参数**。
字段全部可选，缺省 = 不约束、不干预（尊重原稿）。

| 来源 | 内容 |
|---|---|
| 内置/外置模板（`templates/`，17 个） | `ieee` / `acm` / `acm-full` / `springer-llncs` / `custom` / `report` + 数据集生成的会议风格 |
| 会议模板（`--conference`，16 个） | NeurIPS / ICML / ICLR / ACL / EMNLP / CVPR / ICCV / ECCV / AAAI / IJCAI / SIGGRAPH / KDD / NSDI / OSDI…（`datasets/conf-specs/templates-v2/*.json`） |
| 自定义 | `--require my-reqs.json`：任意详细规则，可叠加模板 |

会议模板的投影方式（`texopt/conference.py`，不为任何会议写单独代码）：

- `hard_constraints` → **gate**（页数、字号、边距下限、公式居中）
- `geometry.margin_floor_mm` 只作**下限**：低于才判违规，高于不干预
- `float_policy` / `overwide_fig_threshold_mm` → 浮动体目标档与超宽阈值
- `density_targets` / `*_observed` / `position_prior`（sample-stat）→ 只做"合理性参考"
  （写进报告与 `state.json`），**不进 gate、不进 A**
- 消费不了的字段（栏数、纸张、字体族、匿名、checklist…）→ 逐条登记，不硬接

---

## 8 感知层

| 层 | 模块 | 内容 |
|---|---|---|
| L1 源码 | `perceive.py` | documentclass/字号/geometry/双栏/fleqn/浮动体/图宽/tabular 区间 + 卫生检查（标题字号、行距、页眉、中途双栏、超大图、窄表…） |
| L2 日志 | `perceive.py` | overfull / underfull / vbox / 浮动体警告 / 编译错误 |
| L3 PDF | `engine.py` | 页数、SyncTeX 源码行→页归因、参考文献首页定位（正文页口径）、原图裁切 |
| 视觉 | `visual.py` | PDF→逐页灰度图；`ink_ratio`、`top_bottom_ratio`、`bottom_blank`、`max_gap`、`band`、`left/right_blank` 等；`find_defects` 给视觉缺陷；`pixel_role()` 像素角色代理（near-empty/sparse/dense/body） |
| 留白结构 | `whitespace.py` | 五类留白 + region 列表 + 页眉页脚识别 |

`Perception` 是唯一的结构化输入，后续打分、候选、报告全部基于它。

---

## 9 模型在环（Model-in-the-loop）

```
# ① 跑确定性闭环，并输出请求包
python3 optimize.py paper.tex --target 6 --emit-request
#    -> workbench/{paper.tex, report.md, state.json, advisory.json,
#                 llm_request.json, pages/page-*.png, visual.md}

# ② LLM 读 llm_request.json，产出 proposals.json（结构化提案）

# ③ 程序逐条执行：白名单校验 → 应用 → 编译 → 全局验收 → 变差回滚 → 下一轮
python3 optimize.py paper.tex --proposals proposals.json --round 2
```

- LLM **只提方案**，不直接改文件、不跑 shell；提案命中不了白名单 → `BLOCKED`。
- 每轮都会重新发射请求包（`round+1`），LLM 看到的是**刚编译出来的真实状态**。
- 协议实现：`texopt/proposal.py`（`build_request` / `parse_proposals`）+ `core.apply_proposals`。

---

## 10 单页诊断：局部 vs 整体

`texopt/page_score.py` 把缺陷按 SyncTeX 归到具体页，给三种读法：**页均 / 最差 k 页 / 单页峰值**，
并标注每页像素角色。写入 `state.json.page_diagnostics` 与报告的「逐页诊断」表。

**它只做归因，不改判定口径**：ρ、14 项 c\*、M1/M2 聚合全部原样——所以阶段 13/14 的标定
继续有效。目的只有一个：回答"哪一页最差、差在哪"，供人复核与 Level-3 判断。

---

## 11 输出状态

| 状态 | 含义 |
|---|---|
| `BLOCKED_GATE` | gate 有违规（含不可修复项，或定向修复失败）；报告单列修改建议，标「可排版修复 / 需人工源码修改」 |
| `DONE` | gate 全过，且本轮有 ≥1 个被接受的动作 |
| `CONVERGED` | gate 全过，且没有可动的候选动作（文档本身没问题） |
| `NEEDS_REVIEW` | gate 全过但仍有 high 级视觉缺陷（或 M2 超 `done_max_m2`） |
| `NO_IMPROVEMENT` | gate 全过、有候选，但没有任何一个能改善评分（已全部回滚） |
| `EXHAUSTED` | 排版手段用尽仍缺 gate（通常超页）；给差距与语义抛光建议 |
| `FAILED` | 基线无法编译 / 环境缺失；报告给首个编译错误 |

`gate = 0` 不等于"已优化"：阶段 12 起 gate 违规甚至不产生分数。

---

## 12 标定链与实验资产

标定/体检阶段（每个都有 artifact 与文档，工具可复算）：

| 阶段 | 内容 | 状态 |
|---|---|---|
| 0-2 | 指标盘点、页级提取（608 篇/10538 页）、审美档案（venue×role 正常范围） | 完成 |
| 3-4 | 留白结构化（`whitespace.py`）、马氏距离 + `A_profile`（λ=0 影子） | 完成 |
| 5-6 | 评测验收协议 12.1-12.6（门槛 6/8 维通过）、影子接入 `score`/`core` | 完成 |
| 7 | 权重校准（消融 + bootstrap CI + BT）：80 组试验，判别间隔 0.1157 → 0.1506 | 完成（人类数据 8 对，建议攒到 ≥30 对） |
| 8 | 外部验证 E1/E2/E3（真实论文端到端退化、双测量路径、论文级聚合） | 完成（两条负面结果如实记录） |
| 9 | 检测器体检：`band` 判暂缓、`trailing_ratio` 标 `degenerate` | 完成 |
| 10-10b | `A_soft` 从"带内恒 0"改为平滑目标：排序 Spearman 0.31 → 0.46，并列 8/20 → 0/20 | 完成 |
| 11 | 严重度标定：15 题圆桌轮转 + BT + Jeffreys 先验 | 完成 |
| 12 | gate 退出 + 两线分离：`(gate, M1, M2)` 字典序，gate 违规不再折算罚分 | 完成 |
| 13 | `ρ` 无差异点重标定：0.341 → **15**（区间 [5,32]） | 完成 |
| 14 | P 权重"同一把尺子"：`w = c*/ρ`，7 项统一，口径 A 缩放 | 完成 |
| 15 | 连档压页暂存链 + 单页/整篇分层诊断（`page_score.py`） | 完成 |
| 16 | model2 指标可辨识性/敏感性双体检 + 像素角色代理 | 完成（v2 未落地） |

资产位置：`metrics/*.json`（标定结论）、`tools/*.py`（生成这些结论的脚本）、
`docs/stage*.md`（每阶段的结论、方法与局限）。`docs/scoring/README.md` 与
`docs/aesthetic/README.md` 分别是打分模型与审美量化的专题说明。

---

## 13 仓库结构与数据策略

```text
texopt/
├── optimize.py              # CLI 入口（只做参数编排，不含算法）
├── texopt/
│   ├── core.py              # 决策主循环 + gate 定向修复 + 模型在环执行
│   ├── engine.py            # 唯一碰外部程序的模块：编译/数页/裁图/日志
│   ├── perceive.py          # 感知层 L1/L2/L3
│   ├── actions.py           # 28 个确定性动作（只动排版面）
│   ├── whitelist.py         # 动作白名单 + 参数校验（LLM 唯一可请求面）
│   ├── proposal.py          # 请求包 / 提案协议
│   ├── score.py             # gate + M1 + M2 + 字典序验收
│   ├── page_score.py        # 单页归因（mean/topk/peak），不改口径
│   ├── visual.py            # PDF→页图、页面像素指标、缺陷判定、角色代理
│   ├── whitespace.py        # 留白结构化
│   ├── aesthetic.py / shadow.py / profile.py / weights.py / evalproto.py / evalexternal.py
│   ├── conference.py        # 会议模板加载与投影
│   ├── requirements.py      # 要求规格模型（模板/自定义合并）
│   ├── advise.py            # 残余问题 → 结构化建议
│   └── roles.py / extract.py / page_metrics.py   # 语料侧页级指标
├── templates/               # 期刊/会议要求预设（17 个 json）
├── settings.json            # 默认要求与运行参数
├── metrics/                 # 标定结论（ρ / P 权重 / 严重度 / 指标体检）
├── tools/                   # 标定与体检脚本（21 个）
├── docs/                    # 阶段文档 + PROJECT_MAP + 专题 README + 汇报 PDF
├── examples/                # 靶子稿（demo/issues/chaos/nightmare/…，含重建脚本）
├── tests/run_tests.py       # 单元 + 端到端闭环 + 模型在环往返
├── skills/latex-opt/        # OpenClaw 技能说明
└── workbench/               # 运行产物（工作副本/PDF/报告/状态/请求包/页面图）
```

**数据策略**：语料与实验产物**只在本地**，不入版本控制。原因：可重算、体积大、
`/mnt/d` 9p 文件系统上 `git status` 会慢到分钟级。

| 目录 | 体积 | 为何不入库 | 如何重建 |
|---|---|---|---|
| `paperfit-bench-originals/` | 5.8G | 真实论文原件（PDF） | 重新抓取 |
| `datasets/conf-specs/sources/raw/` | 2.8G / 2111 文件 | 官方规范 HTML/TXT 快照 + PDF | 溯源记录在 `sources/fetch_log.jsonl` |
| `datasets/conf-specs/metrics/pages/` | 64M / 608 json | 页级测量结果 | `datasets/conf-specs/tools` 里的 measure 脚本 |
| `workbench-*/` | ~150M | 标定/实验工作区（页面图、编译产物、作答表） | 对应 `tools/make_*.py --build` |
| `.git` 内部 | — | — | 当前仓库 34MB，跟踪 15MB / 477 文件 |

`metrics/profiles`（2.4MB，运行时审美档案）与 `metrics/index.json` **保留入库**，
否则新克隆跑不了影子评估。

---

## 14 测试与回归

```bash
python3 tests/run_tests.py            # 单元 + 常用靶子闭环 + 模型在环往返（当前 332 项）
python3 tests/run_tests.py --full     # 含 chaos/nightmare 大靶子
python3 tests/run_tests.py --list     # 看分组
```

测试只写 `_regress/`（Windows 盘符下），跑完自动清理；`examples/` 里的靶子只读。

常用入口：

```bash
python3 optimize.py examples/issues.tex                  # 纯质量模式（4 类可修问题）
python3 optimize.py examples/chaos.tex                   # 12 类埋雷
python3 optimize.py examples/demo.tex --target 5 --tune-geometry
python3 optimize.py paper.tex --conference neurips       # 会议模板
python3 optimize.py paper.tex --template acm --require my-reqs.json
python3 optimize.py --list-templates / --list-conferences / --list-actions
```

标定与体检工具（离线、可复算，artifact 已入库）：

```bash
python3 tools/pweight_combine.py --check          # P 权重：代码 ↔ artifact 漂移
python3 tools/apply_severity_weights.py --check   # 严重度权重漂移
python3 tools/rho_ab_compare.py --rhos 0.341,15   # ρ 重标定前后行为对照（真编译，约 40 分钟）
python3 tools/soft_identifiability.py             # model2 指标可辨识性（语料侧）
python3 tools/soft_sensitivity.py                 # model2 指标敏感性（坏版面变体）
python3 tools/detector_check.py --only all        # 指标精度 / 日志覆盖率 / 语料区间
```

---

## 15 已知局限

- **单人评分**：ρ、P 权重、严重度全部来自同一位评分人；每个缺陷只有 2-3 个代价档。
- **5 项未标定**：`fig_overwide`、`warn`、`macros_missing`、`unstable_spec` 仍是先验值。
- **model2 指标瑕疵**（阶段 16）：3 项准常数（占分值 33%）、`band` 阈值型、`ink_ratio`
  需按角色分层、`max_gap` 需排除末页自然留白 → v2 未落地前 A_soft 有噪声。
- **无差异带分辨率不足**：六类缺陷的 c\* 落在同一带内，阶梯只能到 [2,4,6]/[8,15]。
- **修复手段有上限**：超宽表格只报告不自动改的情形、孤行寡行只有 vbox 代理、
  跨文档类模板迁移未做；语义抛光（Phase 6）未实现。
- **A_profile 不能决策**：`λ = 0` 且代码级拦截 `λ>0`（阶段 8 E4：2 个维对退化无响应）。
- **环境绑定**：文档必须在 Windows 真实盘符路径下（`/mnt/c`、`/mnt/d`），
  Windows TeX 引擎无法写 WSL 原生文件系统；9p 盘上 git 与大语料扫描慢属正常。
- **不声称全局最优**：只保证"字典序单调不劣化 + 有界收敛"，收敛点依赖候选动作集。

---

## 16 下一步

1. **实现 SOFT_SPEC v2**（3 个连续指标 + 1 个阈值型 + 位置条件 + 角色门控），
   A 量级按 ×1.618 锚定（待 BT 标定替换）。
2. **30 对配对表做 BT 权重标定**（需人工作答，约 20-30 分钟），题目围绕会打架的场景：
   大洞 vs 排满但失衡、稀疏 vs 过密。
3. 改前/改后命中率 **A/B + 负样本单调性 + Spearman** 三重复核。
4. `fig_overwide` 构造与标定；引入第二评分人复核 ρ 与 P 权重。
5. `λ>0`（A_profile 参与验收）需人类标定 + 用户审批后才解禁。
6. Phase 6 语义抛光（受内容保留率下限约束），历史版本存档。

---

## 17 文档索引

| 文档 | 内容 |
|---|---|
| `docs/PROJECT_MAP.md` | **项目地图**：每个文件/目录装什么、起什么作用、被谁用 |
| `docs/scoring/README.md` | 打分模型完整口径（gate/M1/M2、权重来源、字段、局限） |
| `docs/aesthetic/README.md` | 审美量化（A_soft / A_profile、标定、与人的一致性） |
| `docs/stage0…stage16_*.md` | 每个阶段的结论、方法、负面结果 |
| `docs/scoring_report_20261102.pdf` | 打分评价体系阶段汇报（HTML 单文件版同目录） |
| `skills/latex-opt/SKILL.md` | 模型在环的调用方式（OpenClaw 集成） |
