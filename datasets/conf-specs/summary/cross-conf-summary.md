# 跨会议排版规范总结（人工汇总）

> 数据底座见 `conferences/*.json`。本文件是**结论层**：把 16 个会议的规则对比成可执行的判断，
> 并指出哪些可以抽象为 texopt 的通用规则。自动生成的速查表在 `summary/cross-conf-table.md`，
> 可执行的规则清单在 `summary/texopt-generalizable-rules.json`。
>
> 铁律：本文件的每条结论都能回溯到 `conferences/*.json` 的 `evidence`（官方来源原文引文）或
> `patterns/*.json` / `samples/*.jsonl`（真实论文实测值）。做不到回溯的写法一律不写。

## 0. 覆盖范围与证据分级

覆盖 16 个会议：NeurIPS、ICML、ICLR、ACL、EMNLP、CVPR、ICCV、ECCV、AAAI、IJCAI、SIGGRAPH、KDD、WWW、OSDI、SOSP、NSDI。

每会议数据分三层，互不混淆（对应任务要求的“硬性约束 / 推荐规范 / 统计规律”）：

| 层级 | 位置 | 含义 | confidence |
|---|---|---|---|
| 硬性约束 | `hard_constraints` | 官方明文，违反=不合规 | `official` |
| 模板隐含 | 同上 | 从官方 `.sty/.cls` 源码读出（无明文文字） | `template-implied` |
| 推荐规范 | `recommended` | 官方“期望/建议”，非强制 | `official` |
| 统计规律 | `statistics` / `samples/*.jsonl` / `patterns/*.json` | 真实论文 PDF 的**实测分布**（不是规则） | `inferred` |

自动闸门：`tools/validate.py` 会逐字校验每条 `evidence.quote` 是否真出现在归档原文里。
**全库 16 个会议当前 0 错误 0 提示**——即每条引文都能在 `sources/raw/*.txt` 里找到原句。

## 1. 硬性要求的跨会议对比（结论）

| 维度 | 结论 |
|---|---|
| 页数上限 | 7~14 页不等：AAAI/SIGGRAPH/IJCAI=7，CVPR/ICCV/ACL/EMNLP/ICML/KDD/WWW=8，NeurIPS=9，ICLR=10（6–10 区间），OSDI/NSDI/SOSP=12，ECCV=14（LNCS） |
| 参考文献是否计页 | **15/16 不计入**；唯一例外是 IJCAI（计入） |
| 附录 | 多数允许且不计页；CVPR/ICCV 类“附录在补充材料”、NeurIPS/ICML 允许随正文但另计 |
| 纸张 | letter 13 个；a4 3 个（ACL/EMNLP/SOSP）；ECCV 为 LNCS 155×235mm |
| 栏数 | 2 栏 13 个；**单栏：NeurIPS、ICLR、ECCV(LNCS)** |
| 正文字号 | 9pt（ACM 三件套 KDD/WWW/SIGGRAPH）；10pt（多数）；11pt（ACL/EMNLP） |
| 匿名 | 16/16 双盲 |
| 录用后加页 | 多数 +1 页（NeurIPS/ICML/ICLR/SIGGRAPH 等），OSDI +2 页；AAAI/IJCAI 无加页 |
| 参考文献风格 | 与模板绑定：natbib(NeurIPS)、acl_natbib(ACL/EMNLP)、ACMReferenceFormat(KDD/WWW/SIGGRAPH)、splncs04(ECCV)、author-year(其余 ACM 外) |
| 强制 checklist | NeurIPS、AAAI 等明文强制，且不计页 |

**关键教训（避免把过时规则当现行规则）**：`history` 显示多条规则发生过反转，例如
KDD 2022「9 页含参考文献」→ 2023「9 页不含参考文献」→ 2024「8 页正文 + 附录另计」；
NeurIPS 2020 为 8 页 → 2021 起 9 页；ICLR 2021 为 8 页 → 2025 改为「6–10 页区间，11 页直接 desk reject」。
因此 texopt 的页数约束必须带“届次”语义，不能只存一个数字。

## 2. 真实论文的统计规律（实测，非规则）

统计口径：`tools/measure_pdf.py` 从真实录用论文 PDF 的**字形级包围盒**量取（可复现、可追溯），
每会议 5~8 篇样本，逐篇结果在 `samples/<id>.samples.jsonl`，聚合在 `patterns/*.json`。

要点：
- **满宽图是常态**：单栏会议图宽中位数≈版心宽的 0.98，双栏会议的满宽图占比同样很高 → 缩图动作风险大。
- **题注字号**：实测与正文同号或小 1pt（NeurIPS 10/10pt、ACL 11/10pt）→ 不能用“题注必须更小”当规则。
- **版面密度**：双栏会议约 100~122 行/页，单栏约 55~65 行/页；信息密度量级稳定，可作为 A 项归一化基准。
- **图表公式密度**：各会议差异大（如 NeurIPS 样本 图≈9.7/篇、表≈6.8/篇、公式≈8/篇），
  说明“优化幅度”的合理区间应按会议分别取，而不是一刀切。

（具体数值以 `patterns/float_patterns.json`、`patterns/layout_patterns.json` 与 `summary/cross-conf-table.md`
的自动表为准——本文件不复制数字，避免与数据源不一致。）

## 3. 哪些规则可以抽象为 texopt 的通用规则

完整清单（含证据指针与落到 texopt 的动作）见 `summary/texopt-generalizable-rules.json`。摘要：

**L 类（硬约束，不可用审美收益交换）**
1. 页数上限是「正文页」而非总页数；参考文献/附录多数不计入 → 压页不得动参考文献。
2. 官方模板几何（字号/边距/纸张/栏数）是硬约束，擅自改动可被拒稿 → `allow_geometry_tune` 默认关闭，
   压页优先纯排版手段（间距、浮动体、孤行寡行、列表/标题间距）。
3. 双盲 → 优化不得引入/恢复任何身份信息（含页眉、元数据）。
4. 纸张与栏数固定（letter/a4；1 或 2 栏）→ 编译后做一致性校验。
5. 强制 checklist / impact statement 段不可删除、不可压缩。

**A 类（排版质量/审美代理目标）**
6. 满宽图是常态 → 「缩图」只在“视觉上确实过大”时触发（高度占比 + 满宽双条件）。
7. 题注字号相对正文的偏移量落在实测区间即可，不设固定“更小”要求。
8. 图题位置（在下）跨会议一致；**表题位置相反**（CVPR/NeurIPS/ECCV 在上，ICCV/ACL/EMNLP/IJCAI 在下）
   → 必须按目标会议取值。
9. overfull/underfull、vbox（孤行寡行代理）、不稳定浮动参数 `[h]`、超宽图表是主要可修复缺陷。
10. 版面密度用各会议实测值做归一化基准，而非全局常数。

**R 类（requirements 模块路线图）**
11. `columns`（16/16 缺失）、`page_limit_scope`（14/16）、`paper_size`（16/16）、
    `asymmetric_margins`（9/16）、`caption_position_policy`（6/16），
    以及匿名/checklist/页码/附录政策等校验字段。

## 4. 已知局限（诚实声明）

- **页边距/栏宽**来自 PDF 实测与模板源码换算，含页眉页脚占位差异，不确定度约 ±2pt（±0.7mm）；
  每篇实测结果里都带 `warnings`。
- **统计规律是样本分布，不是规则**：每会议 5~8 篇，用来给量级与区间，不能当阈值明文。
- **样本归属**：优先用官方 proceedings / 程序页 / accepted 列表证明；ACM DL 与 OpenReview 在本机
  有访问限制（403/挑战页），相关会议改用 arXiv 落地页 comment 字段 + 官方列表双证据，
  个别样本（如 ICLR 某篇）arXiv comment 未写会议名，归属以官方 poster 页为准（已在该条 note 标注）。
- **逐年变化**：AAAI 2022 及更早的官方页面已被站点重写，`history` 只能覆盖 2023–2025；
  ICML 2021 之后才可确证页数规则。这些空白记录在各会议 JSON 的 `open_questions` 里，未做推测。
- **字体**：部分会议官方未明文字体，仅有字号/几何；`body_font_family` 只在有模板证据的会议填写。
- **计数类指标（图/表/公式/参考文献条数）可靠性低于几何类指标**：它们靠题注/行首正则从抽取文本里数，
  对“整页 Form XObject”类 PDF（ACL/EMNLP）与 LNCS 类 PDF（ECCV）明显偏低（例如 ECCV 实测 1.0 条/篇），
  对含大量数学符号的 PDF 会偏高（如 ICML 公式计数）。**这些数字只能看量级，不要当阈值或优化目标**；
  几何类指标（纸张、栏数、版心宽、栏间距、字号、页边距）是字形级测量，可靠得多。
- **栏数校验已对齐**：16 个会议的样本实测栏数与官方模板栏数一致，唯二例外是 SOSP/WWW 各 1 篇
  arXiv 版样本（该版本本身是单栏），已在样本 note 里注明，统计时以官方模板为准。
