# 会议排版模板设计报告（16 会议 · 数据驱动）

> 任务：基于 `datasets/conf-specs/` 的既有数据（官方规范 + 历年变化 + 真实论文实测），为 16 个会议分别设计可供
> texopt 使用的排版模板。**不新增任何凭经验手写的规则**：每个数值都由脚本按固定规则从数据算出，并登记
> `basis`（official / template-implied / inferred / sample-stat / derived）。
>
> 本次**未修改 texopt 的 Python 核心代码**（`optimize.py`、`texopt/*.py` 未动），只在 `datasets/conf-specs/` 内
> 新增数据与工具。

---

## 0. 交付物与复现

| 交付物 | 路径 | 说明 |
|---|---|---|
| 统一模板 Schema | `schema/template.schema.json` | 16 会议共用结构（JSON Schema draft-07） |
| 16 个会议模板 | `templates-v2/<id>.json` | 按 Schema 生成，逐字段带来源与可信度 |
| 跨会议速查表 | `summary/template-matrix.md` | 自动生成 |
| 稳健统计原始输出 | `analysis/template-inputs.json` | 每会议 median/P25/P75 + 异常清单 |
| 异常清单 | `analysis/anomalies.md` | 逐样本异常与保留的冲突 |
| 分析脚本 | `tools/analyze_templates.py` | 从原始测量重算稳健统计（不用均值） |
| 生成脚本 | `tools/build_templates.py` | 数据 → 16 模板 |
| 校验脚本 | `tools/validate_templates.py` | 按 Schema 校验 16 模板（0 失败） |

复现：

```bash
cd /mnt/d/桌面/texopt/datasets/conf-specs
python3 tools/analyze_templates.py    # 统计
python3 tools/build_templates.py      # 生成 templates-v2/
python3 tools/validate_templates.py   # 校验（16/16 OK）
```

---

## 1. 统一模板 Schema

`schema/template.schema.json` 固定 15 个顶层字段，16 个会议结构完全一致、只有取值不同：

| 块 | 内容 |
|---|---|
| `id` / `conference` / `edition` / `family` | 会议标识与届次 |
| `data_basis` | 样本量、测量方法、`robust_stats_only=true` |
| `sources` | 官方来源 id、样本 PDF 直链、引用到的通用规则 id、分析文件 |
| `traceability` | `field_basis`：**每个数值字段的 basis 逐条登记** |
| `hard_constraints` | 官方硬性约束，逐项带 `confidence`、`compliance_impact`（reject-risk / desk-check / informational）与逐字引文 |
| `geometry` | 纸张、页宽高、栏数、栏宽、栏间距、版心、四边边距、`margin_floor_mm`、实测 observed 分布 |
| `typography` | 正文字号/字体、行距、题注字号、图/表题注位置、题注对齐实测 |
| `float_policy` | `float_spec` 目标档、图宽典型分布（含 >1 的语义说明）、满宽图占比、位置先验、官方浮动体规则 |
| `density_targets` | 图/表/公式/算法/脚注/参考文献/行数 的每篇与每页稳健分布 + `reliable` 标记 |
| `optimization_policy` | `priority`（3–5 条，带 why 与证据）、`avoid`、`actions`（映射白名单动作参数）、`unsupported`、`applicable_rules` |
| `confidence` | 样本量分级、`reliable_fields` / `unreliable_fields`、`conflicts` |
| `texopt_flat` | 投影到当前 texopt `Requirement` 字段的扁平值（可直接被 requirements 模块消费） |

**四级 basis（严格区分，不得互相冒充）**

| basis | 含义 | 允许出现在 |
|---|---|---|
| `official` | 官方指南/CFP/模板说明的明文字面值 | `hard_constraints`、少量 typography |
| `template-implied` | 从官方 `.sty/.cls` 源码读出（无文字明文） | 同上 |
| `inferred` | 官方无明文，模板行为 + 样本实测一致的多源推断 | 同上 |
| `sample-stat` | 真实论文 PDF 实测的稳健统计（median/P25/P75），**不是规则** | `density_targets`、`observed`、题注实测 |
| `derived` | 由前述值按固定公式推导（如栏宽 =(版心−栏间距)/2） | geometry/float_policy 的换算值 |

铁律（已在 Schema 与生成器中强制执行）：

1. `sample-stat` 与 `derived` **永不进入 `hard_constraints`**；
2. 统计量一律用 median / P25 / P75（`analyze_templates.py` 从 107 份单篇测量重算，不使用 `patterns/*.json` 里的均值）；
3. 样本数 ≤6 → `confidence.level = low`，7–9 → medium；`low` 的 sample-stat 只作参考区间；
4. 冲突**保留并写明原因**，不修改原始数据、不强行统一。

---

## 2. 从数据到字段：生成规则

`tools/build_templates.py` 使用的全部推导规则（可审计）：

| 模板字段 | 取值规则 |
|---|---|
| `geometry.page_size` | `hard_constraints.paper_size`（official / template-implied）；**ECCV 特判为 LNCS 155×235mm**（官方 splncs04），实测 letter 作为冲突保留 |
| `page_width_mm` / `page_height_mm` | 标准纸张表换算（derived）：letter 215.9×279.4、a4 210×297、LNCS 155×235 |
| `geometry.columns` | `hard_constraints.columns`，缺失时取样本众数（sample-stat） |
| `geometry.text_width_mm` | 官方 `text_width_mm`；缺失则 页宽 − 左右边距（derived，如 EMNLP=210−25−25=160mm）；再缺失取实测 median |
| `geometry.column_width_mm` | (版心宽 − 栏间距)/2（derived） |
| `geometry.margins.*` | 官方 `margins_mm`；缺失用实测 median 并标 sample-stat |
| `geometry.margin_floor_mm` | 四边最小值（derived，texopt 压页下限） |
| `typography.body_font_pt` | 官方字号档；同时附实测 median 作交叉校验，不一致写入 conflicts |
| `typography.caption_font_pt` | 实测 median（sample-stat） |
| `typography.caption_position` | official / recommended；无明文则 `null`（数据缺口，不臆测） |
| `float_policy.float_spec` | 固定 `tbp`（derived）：texopt 白名单 `sanitize_float_specs` 的目标档，`[h]/[h!]` 属不稳定写法（通用规则 A-04） |
| `float_policy.figure_width.overwide_threshold_mm` | = 版心全宽（derived），即 `normalize_fig_width` 的阈值，保守避免误伤跨栏图 |
| `density_targets.*` | 实测 median / P25 / P75 / min / max + 每页密度；逐项给 `reliable` |
| `optimization_policy.priority` | **信号打分**后排序取前 5：页数余量（limit−content_pages）、图密度、满宽图占比、表密度、公式密度、版心宽、边距可压缩性；每项 why 里回填该会议的实际数值 |
| `confidence` | 样本量分级 + 逐字段可靠性清单 + 保留的冲突 |

对比旧版 `templates/*.json`（9 个字段的扁平手写值）：新模板不再手填常数，`hard_constraints`、几何、密度、
优化方向全部可从数据复算；但**两者数值高度一致**（例：AAAI 页数 7 / 10pt / 19.05mm 边距在新模板中同样出现，
且能给出出处：官方排版说明明文 page limit 7、`aaai25.sty` 10pt、边距 19.05mm）。

---

## 3. 16 个会议模板设计

> 每节格式：**官方硬约束（L）** / **实测核心特征** / **texopt 最值得优化的方向（来自 `optimization_policy.priority`）** /
> **可信度**。数值均取 `templates-v2/<id>.json`。速查表见 `summary/template-matrix.md`。

### 3.1 NeurIPS（NeurIPS 2025，ml）
- **L**：正文 9 页（参考文献/checklist/技术附录不计，录用 +1 页）；letter；**单栏**；10pt；边距 上下 1in、左右 1.5in（左右远宽于上下）；双盲；强制 checklist。
- **实测**：正文页中位 10.5，版心 139.7mm，图 8.5 张/篇（1.0/页）、表 6.5、公式 8；满宽图占 0.80，全宽浮动体 **top 69%**；单栏文献 55 条。
- **优化方向**：① L 合规（页数/字号/边距/单栏）② 压页（实测正文已近/超 9 页口径）③ 浮动体推向页顶（top 68.6%、mid 19.6%）④ 公式居中与编号一致（1.15/页）⑤ 表格宽度（0.76/页，booktabs 无竖线）。
- **可信度**：low（n=6）。`content_pages`、`figures/tables/equations` 可靠；`refs` 可用；`fig_width_frac` 有个别 >1（1.021）。

### 3.2 ICML（ICML 2025，ml）
- **L**：正文 8 页（录用 +1）；letter；**双栏**（栏间距 6.35mm）；10pt；边距 左右 22.2mm / 上下 25.4mm；双盲；含 impact statement。
- **实测**：正文页中位 9；版心 171.45mm、栏宽 82.5mm；**公式密度最高档 4.66/页（43 个/篇）**；图 13.5 张/篇（1.35/页）；满宽图 0.57。
- **优化方向**：① L 合规 ② **公式排版（居中/编号/超宽公式）** ③ 压页 ④ 浮动体位置 ⑤ 图宽归一与跨栏判定。
- **可信度**：low（n=6）。`refs` **不可用**（author-year 长作者列表漏检，中位 2）；`fig_width_frac` 不可靠（双栏）。

### 3.3 ICLR（ICLR 2025，ml）
- **L**：正文 **6–10 页区间**（第 11 页 desk reject；无录用加页）；letter；**单栏**；10pt；边距同 NeurIPS（左右 1.5in）；双盲。
- **实测**：正文页中位 11；图 8.5 张/篇、表 4.5、公式 14；全宽浮动体 top 74%；满宽图 0.49。
- **优化方向**：① L 合规（注意是区间，不是单一上限）② 压页 ③ 浮动体位置 ④ 公式 ⑤ **窄版心断行质量**（版心 139.7mm，行短词长，overfull/连字符优先）。
- **可信度**：low（n=6）。`refs` 不可用；`content_pages` 口径含参考文献首页。

### 3.4 ACL（ACL 2025，nlp）
- **L**：正文 8 页（长文；短 4 页），参考文献/附录不计，录用 +1；**a4**；**双栏** 6mm 栏间距；**11pt Times Roman**；**四边 25mm**；双盲；Responsible NLP checklist。
- **实测**：正文页中位 10；版心 160mm、栏宽 77mm；**表 11 张/篇、1.0/页**；公式极少（0.1/页）；全宽浮动体 top 40% / bottom 38%（顶底并重）。
- **优化方向**：① L 合规 ② 压页（边距 25mm 已无压缩余地，须靠浮动体/间距）③ 浮动体位置（顶底并重，别一律推顶）④ **表格宽度治理** ⑤ 图宽归一与跨栏判定。
- **可信度**：medium（n=7）。`refs` 不可用（7，伪影）；`fig_width_frac` 全列 ≈1.31（跨栏合并）；样本 s-acl-2025-002 正文实测 9pt 与官方 11pt 不符（冲突保留）。

### 3.5 EMNLP（EMNLP 2025，nlp）
- **L**：与 ACL 同源（`acl.sty`）：8/4 页、参考文献与附录不计、a4、双栏、11pt、25mm 边距、双盲、checklist。
- **实测**：正文页中位 9；**表 14 张/篇（1.56/页，16 会议最高）**；图 6 张/篇；全宽浮动体 top 31% / bottom 44%（底部最多）。
- **优化方向**：① L 合规 ② 压页 ③ **表格宽度治理（首要，密度最高）** ④ 浮动体位置（底部偏多，需防底部堆叠）⑤ 图宽归一与跨栏判定。
- **可信度**：medium（n=7）。`refs`、`fig_width_frac` 同 ACL 不可用。

### 3.6 CVPR（CVPR 2025，cv）
- **L**：正文 8 页（含图；仅参考文献额外），录用不加页；letter；双栏 7.94mm；10pt Times；边距 左右 20.6mm / 上 25.4 / 下 28.6；双盲；正文不允许附录（附录走补充材料）。
- **实测**：正文页中位 9；版心 174.6mm、栏宽 83.3mm；图 6.5 张/篇；**表题在表格上方**（图题在下）；全宽浮动体 **top 79%**；文献 51.5 条（数字式，可靠）。
- **优化方向**：① L 合规 ② 压页 ③ 浮动体推向页顶 ④ 图宽归一与跨栏判定 ⑤ 表格宽度治理。
- **可信度**：medium（n=8）。`refs` 可靠；`fig_width_frac` 不可靠（8/8 样本 ≈1.236 = 整页宽合并）。

### 3.7 ICCV（ICCV 2025，cv）
- **L**：8 页正文 + 仅参考文献额外；letter；双栏；10pt；边距同 CVPR；双盲；OpenReview（2025 起）。
- **实测**：正文页中位 9；图 6 张/篇、公式 8；**表题在表格下方（与 CVPR 相反）**；全宽浮动体 **top 88%**（16 会议最高之一）；文献 66.5 条。
- **优化方向**：① L 合规 ② 压页 ③ 浮动体推向页顶 ④ 图宽归一 ⑤ 表格宽度治理。
- **可信度**：medium（n=8）。`refs` 可靠；`fig_width_frac` 不可靠。

### 3.8 ECCV（ECCV 2026，cv）
- **L**：**LNCS 14 页**（含图，参考文献额外）；单栏 **CMR 字体**；**版心 122mm（16 会议最窄）**；送审版 geometry 裁剪、四边约 12mm；双盲；正文禁附录。
- **实测**：正文页中位 15（口径为参考文献首页之前，故比 14 多 1）；图 6 张/篇；全宽浮动体 top 96%；**refs 实测 0–2（完全失真）**。
- **优化方向**：① L 合规 ② 压页 ③ 浮动体位置 ④ **窄版心断行质量（122mm 最窄，断行最易恶化）** ⑤ **边距可压缩空间极小（12mm），压页须转向字号档/行距/浮动体与列表间距**。
- **可信度**：low（n=6）。`refs` 不可用（见 §5.1）；页面规格官方 LNCS vs 实测 letter 冲突保留。

### 3.9 AAAI（AAAI-25，ai）
- **L**：技术内容 **7 页** + 仅参考文献加页；letter；双栏 9.52mm；10pt；边距 左右/上 19.05mm、下 31.75mm；**图题与表题都在下方**；强制 checklist；双盲。
- **实测**：正文页中位 8；版心 177.8mm、栏宽 84.1mm；图 6.5 张/篇；全宽浮动体 top 89%；满宽图 1.0（跨栏合并所致）。
- **优化方向**：① L 合规 ② 压页 ③ 浮动体推向页顶 ④ 图宽归一与跨栏判定 ⑤ 边距压缩余量小（19.05mm）。
- **可信度**：low（n=6）。`refs` 不可用（中位 20，偏低）；`fig_width_frac` 不可靠。

### 3.10 IJCAI（IJCAI 2025，ai）
- **L**：总 9 页 = 正文 7 + 参考文献 2（**16 会议中唯一参考文献计页**），录用后可付费加页 ≤2；letter；双栏 6.35mm；10pt Times；边距同 AAAI；双盲；CMT。
- **实测**：正文页中位 8；图/表各 3 张/篇（密度较低）、公式 6；全宽浮动体 top 82%；**表题在下方**。
- **优化方向**：① L 合规（**参考文献计页**，压页时不得压缩参考文献——与其余 15 会相反）② 压页 ③ 浮动体推向页顶 ④ 图宽归一 ⑤ 表格宽度治理。
- **可信度**：medium（n=7）。`refs` 不可用（伪影）；`fig_width_frac` 不可靠。

### 3.11 SIGGRAPH（SIGGRAPH 2025，graphics）
- **L**：会议论文 ≤7 页（不含参考文献与纯图页 ≤2），journal-only 不限；录用 +1（"at most 10 pages plus references"）；letter；双栏 8.47mm；**9pt**；边距 18.34mm；完全双盲；页码带 paper ID。
- **实测**：正文页中位 10；**图 12 张/篇**（1.0/页）、表仅 1 张/篇；公式 8；全宽浮动体 top 52% / bottom 26% / mid 22%（分布最均匀）。
- **优化方向**：① L 合规 ② 压页 ③ 浮动体位置（分布均匀，**不应强制全部推顶**，重点是消除页面中部浮动体）④ 公式排版 ⑤ 图宽归一与跨栏判定。
- **可信度**：medium（n=7）。`refs` 不可用；9pt 正文下断行更敏感。

### 3.12 KDD（KDD 2025，data）
- **L**：投稿 8 页正文 + 参考文献/附录不限；camera-ready 12 页（9 正文 + 参考文献/附录 ≤3）；letter；双栏 8.47mm；**9pt**（acmart sigconf）；边距 19.05/20.11/25.75mm；双盲；ACM 参考文献格式。
- **实测**：正文页中位 9；图 5 张/篇、表 4、**公式 10 个/篇（1.06/页）**；全宽浮动体 top 84%；满宽图仅 0.026（acmart 图多为栏内）。
- **优化方向**：① L 合规 ② 压页 ③ **公式排版** ④ 浮动体位置 ⑤ 表格宽度治理。
- **可信度**：low（n=6）。`refs` 可靠（53）；`fig_width_frac` 不可靠。

### 3.13 WWW（WWW 2026，data）
- **L**：投稿 8 页正文，总计 ≤12（参考文献不计入 8 但计入 12）；letter；双栏；9pt；边距同 KDD；双盲；OpenReview。
- **实测**：正文页中位 9；**公式 23 个/篇（2.56/页，16 会议最高）**、表 8 张/篇；满宽图 0.125。
- **优化方向**：① L 合规 ② 压页 ③ **公式排版（密度最高）** ④ 表格宽度治理 ⑤ 浮动体位置。
- **可信度**：medium（n=7）。`refs` 可靠（54）；样本 s-www-2024-004 单栏/12pt/26 页属特例（冲突保留）。

### 3.14 OSDI（OSDI '25，systems）
- **L**：技术内容 12 页（参考文献另计不限），录用 14 页（+2）；letter；双栏 8.38mm；10pt；边距 左右 19.05mm / 上下 25.4mm；双盲；USENIX 模板。
- **实测**：正文页中位 15（样本多为 camera-ready 含附录，口径差异）；**图 14 张/篇**（1.03/页，图密集）、表 2 张/篇、**公式 0**；全宽浮动体 **top 100%**；文献 93.5 条（16 会议最多）。
- **优化方向**：① L 合规 ② 压页 ③ **浮动体推向页顶（top 100%，收益最确定）** ④ 图宽归一与跨栏判定 ⑤ 边距压缩余量小（19.05mm）；**公式不是改进面（实测 0）**。
- **可信度**：low（n=6）。`refs` 可靠；样本 content_pages 含附录，与 12 页上限不可直接比。

### 3.15 SOSP（SOSP 2025，systems）
- **L**：12 页正文（参考文献不计）；纸型官方写 **"a4 or letter"**（需与目标模板确认）；双栏 8mm；10pt；边距 ~18.8/19/21.9/26.1mm；双盲；**模板血统按官方 CFP 为 ACM SIGPLAN `acmart`（非 USENIX）**。
- **实测**：正文页中位 14；**图 17 张/篇（1.2/页，16 会议最高）**、表 3 张/篇、公式 0；全宽浮动体 top 89%；文献 79 条。
- **优化方向**：① L 合规 ② 压页 ③ 浮动体推向页顶 ④ 图宽归一与跨栏判定 ⑤ 边距压缩余量小（18.8mm）。
- **可信度**：medium（n=7）。7 个样本中 6 个实测 letter 与官方"a4 or letter"并存（冲突保留）；`refs` 可靠。

### 3.16 NSDI（NSDI '25，systems）
- **L**：技术内容 12 页（参考文献另计），最终稿同 12 页（+0）；letter；双栏 8.38mm；10pt；边距同 OSDI；双盲；USENIX 模板。
- **实测**：正文页中位 14；图 13 张/篇（0.93/页）、表 1 张/篇、公式 2；全宽浮动体 top 82%；文献 58 条。
- **优化方向**：① L 合规 ② 压页 ③ 浮动体推向页顶 ④ 图宽归一与跨栏判定 ⑤ 边距压缩余量小（19.05mm）。
- **可信度**：medium（n=7）。`refs` 可靠；样本 content_pages 口径差异同 OSDI。

---

## 4. 跨会议横向结论

| 维度 | 结论（全部可从 `hard_constraints` 回溯） |
|---|---|
| 正文页上限 | 7（AAAI/IJCAI/SIGGRAPH）、8（CVPR/ICCV/ACL/EMNLP/ICML/KDD/WWW）、9（NeurIPS）、10 区间（ICLR）、12（OSDI/SOSP/NSDI）、14 LNCS（ECCV） |
| 参考文献计页 | 15/16 不计；**IJCAI 唯一计入**（总 9 = 7+2） |
| 纸张 | letter 13；a4 3（ACL/EMNLP/SOSP 或 letter）；ECCV = LNCS 155×235mm |
| 栏数 | 单栏 3：NeurIPS、ICLR、ECCV；其余 13 为双栏 |
| 正文字号 | 9pt：SIGGRAPH/KDD/WWW（ACM）；11pt：ACL/EMNLP；其余 10pt |
| 边距下限 | 12mm（ECCV）→ 18.34（SIGGRAPH）→ 19.05（ACM/USENIX 系）→ 20.6（CVPR/ICCV）→ 22.2（ICML）→ 25.0/25.4（ACL 系与 NeurIPS/ICLR） |
| 题注位置 | 图题一律在下；表题：CVPR/NeurIPS/ECCV 在上，ICCV/ACL/EMNLP/IJCAI/AAAI 在下，其余官方无明文 |
| 浮动体位置 | 全宽浮动体 top 占比 0.31（EMNLP）~1.0（OSDI）；**除 ACL/EMNLP/SIGGRAPH 外都明显偏顶部** |
| 密度量级 | 图：0.4–1.35/页；表：0.07–1.56/页；公式：0（OSDI/SOSP）–4.66 个/页（ICML） |

---

## 5. 数据异常与可信度说明

### 5.1 任务点名的三项检查

**(a) ECCV 的 `refs_per_paper` 测量异常 —— 确认是测量伪影，不是真实数据**

- `measure_pdf.py` 只认两种引用格式：`[n]` 数字引用，或"行首 `Surname,` 后 240 字符内出现年份"的作者-年式。
- ECCV/LNCS 的参考文献是 **`1. Author, A.: Title. In: ...(year)`** 形式（编号+点号，不是方括号），且长作者列表把年份推到 240 字符之外。
- 直接抽取样本 PDF 文本可证：`References\n1. Attardo, S.: A primer for the linguistics of humor...(2008) 2 / 2. Billig, M.: ... (2005)` —— 参考文献确实存在，只是没被正则命中。
- 影响：**ECCV 的 refs 实测为 0/0/1/2/1/2，中位 1**，该字段在模板中标记 `reliable=false` 并排除出所有结论。同类伪影还出现在 ICML(2)、ICLR(4.5)、ACL(7)、EMNLP(10)、IJCAI(2)、SIGGRAPH(3)、AAAI(20，偏低) —— **凡 author-year 风格、作者列表长的会议都受影响**，这 8 个会议的 `density_targets.refs` 均标不可靠，且 `avoid` 里写明"不得以 refs_per_paper 为目标"。

**(b) `figure width > 1` 是否表示跨栏图片 —— 是，且更准确地说表示"图块 ≈ 整页宽"**

- 分母是**版心全宽**（双栏 = 两栏 + 栏间距）。把超 1 的比值乘回版心宽，得到的是**页面宽度**：

| 会议 | fig_width_frac 中位 | ×版心宽 | 页面宽 |
|---|---|---|---|
| ACL | 1.309 | 595.4pt | 595.3（A4） |
| EMNLP | 1.306 | 595.3pt | 595.3（A4） |
| CVPR/ICCV | 1.236 | 611.8pt | 612（letter） |
| AAAI | 1.214 | 611.9pt | 612 |
| IJCAI | 1.214 | 611.9pt | 612 |
| SIGGRAPH | 1.129 | 612.1pt | 612 |
| KDD | 1.131 | 571.6pt | 612 |
| NeurIPS（单栏） | 1.021 | 405.6pt | 612（版心 397pt） |

- 结论：双栏会议的 `fig_width_frac>1` **是跨栏/整页图块被 `merge_boxes` 合并后的伪影**，既不能当"超宽违规"（会误压合法跨栏图），也不能当"典型图宽"（会把栏内图拉大）。
- 处理：双栏会议的 `float_policy.figure_width.typical_frac` 一律标 `reliable=false`；速查表加 `*`；模板改用"版心宽/栏宽"绝对值表达图宽约束，并在 `float_policy.notes` 写明需视觉层（Phase 4）区分栏内图/跨栏图后才可细化。

**(c) `content_pages` 与官方页数上限不一致 —— 保留冲突，不强行统一**

- `content_pages` 的口径是"参考文献首页之前（含该页）"，而官方上限是"正文/技术内容页"，两者不可直接等同；少数样本还把附录并入了正文区。
- 实测中位数普遍比官方上限 **高约 1 页**（CVPR 9 vs 8、ACL 10 vs 8、NeurIPS 10.5 vs 9），OSDI/NSDI/SOSP 甚至高 2–3 页（样本为含附录的 camera-ready）。
- 处理：模板的 L 约束一律取**官方值**，实测值只进 `density_targets.content_pages` 与 `confidence.conflicts`（类型 `content_pages_vs_official_limit`），并写明"真实余量需按目标模板重编译确认"。

### 5.2 其他异常（逐样本，全部保留在 `analysis/anomalies.md`）

| 类型 | 样本 | 说明与处理 |
|---|---|---|
| `content_pages_implausible` | neurips-2024-004(=2)、acl-2025-003(=2)、sosp-2025-003(=1) | 正文页定位失败；仅标记，中位数由其余样本给出 |
| `columns_mismatch` | www-2024-004、sosp-2025-002 | 实测 1 栏 ≠ 官方 2 栏（整页跨栏图导致行首聚类偏移）；不影响会议级结论 |
| `paper_size_mismatch` | sosp 6/7 样本 letter vs 官方"a4 or letter" | 官方允许多纸型；按官方值并在 `page_size.note` 说明 |
| `body_font_mismatch` | acl-2025-002(9pt)、www-2024-004(12pt) | 单样本偏离官方档；按官方值，样本仅作观测 |
| `refs_zero` | neurips-004、iclr-006、eccv-001/002 | 见 5.1(a) |

### 5.3 系统性不可靠字段（已在每个模板 `confidence.unreliable_fields` 列出）

| 字段 | 不可靠会议 | 原因 |
|---|---|---|
| `density_targets.refs` | icml、iclr、acl、emnlp、eccv、ijcai、siggraph、aaai | 引用正则不适配 author-year/长作者列表（伪影） |
| `float_policy.figure_width.typical_frac` | 全部 13 个双栏会议 | 跨栏/整页图块合并（见 5.1(b)） |
| `density_targets.lines_per_page` | 全部 16 | 定义=正文页总行数/页数（双栏为两栏之和），噪声大、跨栏不可比；仅同会议内参考 |
| `density_targets.footnotes` | 全部 16 | 脚注检测依赖页底小字号+标记，样本多为 0，无统计意义 |
| `typography.caption_position` | icml、iclr、siggraph、kdd、www、osdi、sosp、nsdi | 官方无明文，测量层未实现题注位置检测；**留 `null` 不臆测**（数据缺口） |

### 5.4 可信度分级

| 级别 | 会议 | 含义 |
|---|---|---|
| medium（n=7–8） | ACL、EMNLP、CVPR、ICCV、IJCAI、SIGGRAPH、WWW、SOSP、NSDI | sample-stat 可用作参考区间 |
| low（n=6） | NeurIPS、ICML、ICLR、ECCV、AAAI、KDD、OSDI | sample-stat **仅作弱参考**，不得升格为规则；已写入各模板 `confidence.notes` |

### 5.5 已知数据缺口（未做，不假装做了）

1. **图/表题注位置**未在测量层检测（8 个会议官方也无明文）→ `typography.caption_position` 为 null；
2. **栏内图 vs 跨栏图**无法从 PDF 几何区分 → 需页面图像视觉层（texopt Phase 4 已规划未实现）；
3. **content_pages 与附录边界**未分离 → 与官方上限的口径差保留为冲突；
4. **像素级孤行寡行 / 留白审美**未实现（texopt 现有代理为编译日志 vbox + 断行质量宏）；
5. 样本量 6–8 篇/会议，覆盖「不同版面结构」但不足以估计长尾分布。

---

## 6. 与 texopt 的对接

每个模板末尾的 `texopt_flat` 是**投影到当前 texopt `Requirement` 字段**的扁平值，可直接被 `texopt/requirements.py`
读取（字段语义见 `templates/README.md`）：

```json
"texopt_flat": {
  "page_limit": 8, "font_pt": 10, "margin_mm": 20.6, "float_spec": "tbp",
  "overwide_fig_threshold_mm": 174.6, "eq_fleqn_allowed": false, "enable_quality_macros": true
}
```

- `page_limit` = 官方正文页上限；`font_pt` = 官方字号；`margin_mm` = `margin_floor_mm`（四边最小值）；
  `overwide_fig_threshold_mm` = 版心全宽；`float_spec` = `tbp`；`eq_fleqn_allowed=false`（官方模板公式居中）。
- 本次**未**改动 `templates/` 目录与任何核心代码；如需把新模板接入 `python3 optimize.py --template <id>`，
  建议后续用一次性投影脚本从 `templates-v2/*.json` 生成 `templates/<id>.json`（本次不执行，等确认）。
- 当前 `Requirement` 表达不了、但官方明文约束的字段（来自 `texopt_requirement_map.unsupported_constraints` 与通用规则 R-01~R-06）：
  **栏数、页数语义（正文页 vs 总页）、纸张尺寸、非对称边距、题注位置、匿名/checklist/页码/附录/参考文献风格/投稿系统**。
  这些已逐会写在模板的 `optimization_policy.unsupported` 中，供 requirements 模块后续扩展。

---

## 7. 后续建议（按性价比排序）

1. **修 refs 检测**（正则增加 LNCS/author-year 变体）→ 解锁 8 个会议的引用密度指标；
2. **修图宽测量**（按栏判定，或标出跨栏框）→ 双栏 13 会的图宽策略才能真正落地；
3. **实现题注位置检测**（上图题/下表题）→ 补齐 8 个会议的 typography 缺口；
4. **给 Requirement 加 columns / paper_size / margin 四边**（R-01/R-03/R-04）→ 模板才能无损投影；
5. **扩样本到 ≥12 篇/会议**并把 low 级会议提到 medium。
