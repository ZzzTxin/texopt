# 计算机顶会论文排版规范数据集（texopt dataset）

给 texopt 的 **requirements（要求规格）/ perception（感知）/ optimization（优化）** 三个模块
提供数据底座：对每个会议，同时给出「官方硬性要求」「官方推荐做法」「真实论文里的统计规律」，
并且**每一条都能回溯到官方页面/模板或具体论文样本**。

覆盖 16 个会议：NeurIPS、ICML、ICLR、ACL、EMNLP、CVPR、ICCV、ECCV、AAAI、IJCAI、
SIGGRAPH、KDD、WWW、OSDI、SOSP、NSDI。

## 目录结构

```
datasets/conf-specs/
├── BRIEF_research.md          调研作业契约（产出、字段、溯源规则）
├── SUBAGENT_TASK.md           子代理作业单（可并行分派；含各会议列表页/PDF 直链规律）
├── schema/
│   ├── KEY_VOCAB.md           受控字段表（键名/单位/取值，唯一契约）
│   ├── conference.schema.json JSON Schema
│   └── EXAMPLE_conference.json 结构骨架示例
├── conferences/<id>.json      ★规范层：hard_constraints / recommended / history / sources / texopt 映射 / statistics
├── years/<id>.history.json    逐年规范变化（由 build_dataset.py 生成）+ 过时风险提示
├── samples/
│   ├── <id>.samples.list.json 样本清单（调研写入：论文链接与元数据）
│   ├── <id>.samples.jsonl     ★实测层：每篇一行，含 PDF 几何测量结果
│   └── _measurements/*.json   单篇测量缓存（可重跑、可追溯）
├── patterns/
│   ├── float_patterns.json    figure/table/浮动体的尺寸·位置·题注统计
│   └── layout_patterns.json   公式/算法/参考文献/脚注等版面元素密度与风格
├── summary/
│   ├── cross-conf-table.md    自动生成：跨会议硬性要求 + 实测统计速查表
│   ├── cross-conf-summary.md  ★人工汇总：跨会议对比结论 + 可抽象为 texopt 通用规则的清单
│   ├── texopt-generalizable-rules.json  ★可执行规则（L/A/R 分层，每条带证据指针）
│   └── sample-link-check.md   自动生成：样本 PDF 直链可用性检查
├── texopt-templates/<id>.json 直接可被 texopt `--template <id>` 使用的要求文件
│                              （用 tools/install_templates.sh 安装进 texopt/templates/）
├── sources/
│   ├── raw/<src-id>.*         全部原始来源归档（html/sty/pdf 原样保存）
│   ├── raw/<src-id>.txt       归档文本（引文逐字校验用）
│   ├── raw/pdfs/              样本论文 PDF 缓存
│   └── fetch_log.jsonl        抓取日志（url/http 状态/sha256/时间）
└── tools/                     抓取、抽取、测量、校验、汇总脚本
```

## 三级证据强度（对应任务要求的「硬性 / 推荐 / 统计规律」）

| 层级 | 存放位置 | 含义 | confidence 取值 |
|---|---|---|---|
| 硬性约束 | `conferences/*.json → hard_constraints` | 官方明文规定，违反=不合规（页数、纸张、栏数、字号、匿名等） | `official` |
| 模板隐含 | 同上 | 官方模板源码/编译结果读出的值（无明文文字，如 `\columnsep`） | `template-implied` |
| 推荐规范 | `conferences/*.json → recommended` | 官方“建议/期望”表述，非强制（题注位置、浮动体位置偏好等） | `official` / `inferred` |
| 统计规律 | `conferences/*.json → statistics`、`samples/*.jsonl`、`patterns/*.json` | **实测**真实论文得到的分布（均值/中位数/分位），不是规则 | `inferred` |

## 溯源机制（“不许凭经验臆测”是机器强制的）

1. 每个来源先用 `tools/fetch_source.sh` 归档：原始文件 + 文本 + `sha256` + `http_status` + 抓取时间
   写入 `sources/fetch_log.jsonl`。
2. 每条约束的 `evidence.quote` 必须是该来源归档文本里的**逐字原文**。
3. `tools/validate.py` 会逐条核对引文是否真的能在归档里找到，并检查字段/键名/引用完整性；
   **error 不为 0 的数据视为不可用**。
4. PDF 统计量全部由 `tools/measure_pdf.py` 从真实稿件的几何信息算出（pdfminer 字形级包围盒），
   方法、近似误差写进 `method`/`warnings`，不做主观打分。

## 工具用法

```bash
cd datasets/conf-specs
bash tools/bootstrap_py.sh                      # 准备 pure-python PDF 依赖（无 pip 环境）
tools/fetch_source.sh src-cvpr-2025-guidelines https://cvpr.thecvf.com/...   # 归档来源
python3 tools/totext.py sources/raw/xxx.html    # 归档 → 纯文本
python3 tools/mk_source.py <src-id> --kind official-guidelines --title "..."  # 生成 Source 条目（sha256 自动取自日志）
python3 tools/oa.py "Paper Title"               # 经 OpenAlex 找论文 arXiv/PDF（arXiv API 本机限流时的替代）
python3 tools/measure_pdf.py <pdf|url> --pages=25      # 单篇 PDF 几何量化（JSON）
python3 tools/check_sample_links.py             # 校验 samples 里所有 pdf_url 是否可下载（含 %PDF 魔数）
python3 tools/validate.py                       # 全量溯源/结构校验（含样本归属交叉校验）
python3 tools/build_dataset.py --only cvpr      # 汇总：测量→统计→逐年→模式→模板→速查表
tools/install_templates.sh --apply              # 把 texopt-templates/*.json 安装进 texopt/templates/
```

## 与 texopt 模块的对接

| texopt 模块 | 用到的数据 | 用法 |
|---|---|---|
| `requirements`（要求规格） | `texopt-templates/<id>.json`（由 `conferences/*.json → texopt_requirement_map` 生成） | 直接 `--template <id>`；未覆盖的官方硬要求列在 `unsupported_constraints`，作为 Requirement 字段扩展的路线图 |
| `perception`（感知） | `patterns/*.json`、`conferences/*.json → statistics` | 作为检测阈值与“合理区间”（如题注字号应比正文小 0~1pt、满宽图占比、栏间距典型值、行密度） |
| `optimization`（优化） | `hard_constraints`（L 硬约束）、`recommended` + `patterns`（A 质量/审美代理目标） | L 项直接作为硬约束；A 项的目标区间来自实测统计而非拍脑袋 |
| `score`（评分） | 同上 | 统计分布给出 A 项的归一化基准 |

### 模板设计与接入（2026-09-12）

| 产物 | 说明 |
|---|---|
| `schema/template.schema.json` | 会议模板统一 Schema（16 会议结构一致、取值不同） |
| `templates-v2/<id>.json` | 16 个会议模板（逐字段带 basis 与来源） |
| `summary/template-design-report.md` / `template-matrix.md` | 模板设计报告与速查表 |
| `summary/texopt-integration-report.md` | **模板 → texopt 的接入现状**：已接入字段、未接入字段及原因 |
| `analysis/template-inputs.json`、`analysis/anomalies.md` | 稳健统计（median/P25/P75）与异常清单 |
| 生成工具 | `tools/analyze_templates.py` → `build_templates.py` → `validate_templates.py`；`tools/check_conference_integration.py` |

接入方式（texopt 侧，不为任何会议写单独代码）：

```bash
python3 optimize.py paper.tex --conference aaai   # 读 templates-v2/aaai.json
python3 optimize.py --list-conferences            # 列出 16 个会议
```

- **官方硬约束**（`hard_constraints`，confidence=official/template-implied/inferred）→ texopt 的 **L 硬约束**（页数/字号/边距下限/浮动体规范/公式居中），用于判「是否违规」；
  页数上限默认按**正文页口径**（`pdftotext` 定位参考文献首页，参考文献不计）；边距按**下限**语义（低于才判违规）。
- **真实论文统计**（`density_targets` / `*_observed` / `position_prior`，basis=sample-stat）→ 只做「排版是否合理」的参考核对
  （`texopt/conference.py::reasonableness`，写进报告与 `state.json`），**不进 L、不参与 A 打分**。
- **接不上的字段**（栏数/纸张/字体族/匿名/checklist/题注位置等）→ 逐条登记在 `summary/texopt-integration-report.md`，不强行接入。

## 维护

- **新增会议**：按 `BRIEF_research.md` 产出 `conferences/<id>.json` + `samples/<id>.samples.list.json`，
  跑 `validate.py` 与 `build_dataset.py`。
- **新增年份**：在 `history` 追加条目（含该年官方来源），并在 `current_edition` 更新；
  `years/*.history.json` 会重算并给出「过时风险」提示——避免把旧规则当现行规则。
- **新增字段**：先改 `schema/KEY_VOCAB.md`（受控表），再改 `tools/validate.py` 的 `ALLOWED_KEYS`。

## 已知局限（诚实声明）

- 页边距/栏宽的 PDF 实测含页眉页脚占位差异，不确定度约 ±2pt（±0.7mm），见每篇的 `warnings`。
- 图表编号、参考文献条数按题注/行首正则统计，双栏跨栏文本会略有误差，均标为计数近似。
- 部分会议（如 SIGGRAPH/TAPS、ACM 系列）规则散落在多个页面与模板注释里，
  `open_questions` 字段记录了本次未能确认的点。
- 统计规律是**样本的分布**，不是规则；样本量每会议 5~8 篇，只用于给出量级与区间。

## 工程注意（踩过的坑）

- **子代理/agent run 默认超时 600s**：分派调研任务时每个子代理不超过 2~3 个会议，
  否则会在 10 分钟处被中止（本项目的会议规范层分 5 个子代理并行完成）。
- **整页被包进一个 Form XObject 的 PDF**（ACL Anthology 2025 等）：pdfminer 不会对
  Form 内部做行分组，`measure_pdf.py` 因此内置**字符级回退分组**（按基线成带、按水平
  间隔切栏），否则这些会议的几何量会测成空。
- **栏检测**必须用行首簇的“模态”而不是均值/最小值作候选点，并用“行尾落在候选点之前”
  的行占比来判定左栏（段落缩进会把左栏行首推离版心左沿，用行首定义会误判成单栏）。
- **arXiv API（export.arxiv.org）与 OpenReview（api2/openreview.net）在本机不可用**
  （限流 / 403 挑战页）；改用 arXiv HTML 搜索页、`arxiv.org/abs/<id>` 落地页、OpenAlex API。
- 样本 PDF 直链用 `tools/check_sample_links.py` 逐条验证（含 `%PDF` 魔数），避免“链接看起来对但 404”。
