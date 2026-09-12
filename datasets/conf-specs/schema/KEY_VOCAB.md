# KEY_VOCAB —— 受控字段表（数据集契约）

本文件是 `conferences/*.json` 的**唯一字段字典**。所有写入该目录的数据必须使用下列键名，
不得自造同义键（如 `pages` / `page_max` / `max_pages` 一律用 `page_limit_content`）。
新增键必须先在本文件登记，再使用。

## 0. 顶层结构

```jsonc
{
  "schema_version": "1.0",
  "id": "neurips",                 // 小写短 id，与文件名一致
  "name": "Conference on Neural Information Processing Systems",
  "abbr": "NeurIPS",
  "family": "ml",                  // ml | nlp | cv | ai | graphics | data | systems
  "official_site": "https://neurips.cc/",
  "current_edition": "NeurIPS 2025",
  "focus_editions": ["2022","2023","2024","2025"],
  "template_basis": {              // 论文模板的“血统”
    "class": "neurips_2025.sty",
    "inherits": "article",         // article | IEEEtran | acmart | acl_natbib | llncs | usenix
    "url": "..."
  },
  "hard_constraints": { "<key>": <Entry> },
  "recommended":      { "<key>": <Entry> },
  "statistics":       { "<metric>": <Stat> },
  "history":          [ <Change> ],
  "texopt_requirement_map": { ... },
  "sources": [ <Source> ],
  "open_questions": [ "..." ]
}
```

## 1. Entry（约束条目）

```jsonc
{
  "value": 9,                      // 标量 或 对象（如 margins_mm）
  "unit": "pages",                 // 标量必须有单位；无单位写 null
  "scope": "submission",           // submission | camera_ready | both | template_default
  "confidence": "official",        // official | template-implied | inferred
  "note": "技术内容上限；参考文献与附录不计入（见 evidence）",
  "evidence": [
    { "source_id": "src-neurips-2025-cfp", "quote": "原文摘录（英文原文，逐字）" }
  ]
}
```

- `official`：官方 author guide / CFP / 官方模板注释里的明文规定。
- `template-implied`：官方 `.sty/.cls` 源码或官方 PDF 编译结果里读出的值（无明文文字）。
- `inferred`：由样本测量或跨来源推断；**必须**在 note 里写明依据，不得无依据臆测。

## 2. hard_constraints / recommended 允许的键

| key | 类型 | unit | 说明 |
|---|---|---|---|
| `paper_size` | str | null | `letter` / `a4` |
| `columns` | int | null | 1 或 2 |
| `column_gap_mm` | num | mm | 栏间距 |
| `body_font_size_pt` | num | pt | 正文（正文主体）字号 |
| `body_font_family` | str | null | 如 `Times`、`Times New Roman`、`Nimbus Roman` |
| `line_spacing` | str | null | 如 `single` |
| `margins_mm` | obj | mm | `{"top":..,"bottom":..,"left":..,"right":..}` |
| `text_width_mm` | num | mm | 版心宽 |
| `text_height_mm` | num | mm | 版心高 |
| `page_limit_content` | int | pages | 正文/技术内容页数上限 |
| `page_limit_total` | int | pages | 总页数上限（含参考文献等） |
| `references_counted` | bool | null | 参考文献是否计入页数 |
| `appendix_allowed` | bool | null | 是否允许附录 |
| `appendix_counted` | bool | null | 附录是否计入页数 |
| `anonymity` | str | null | `double-blind` / `single-blind` / `none` |
| `title_format` | str | null | 标题大小写/字号/禁用的 LaTeX 命令等 |
| `abstract_max_words` | int | words | 摘要字数上限 |
| `bib_style` | str | null | `numeric-comp` / `author-year` / `ACMReferenceFormat` / `acl_natbib` / `IEEEtran` / `splncs04` |
| `template_file` | str | null | 官方模板主文件名 |
| `template_url` | str | null | 官方模板下载地址 |
| `camera_ready_extra_pages` | int | pages | 录用后可加页数 |
| `checklist_required` | bool | null | 是否强制提交 check list |
| `supplementary_policy` | str | null | 补充材料规则 |
| `page_numbering` | str | null | 送审稿是否加页码 |
| `float_placement_rules` | str | null | 官方对浮动体位置的明文要求 |
| `figure_caption_position` | str | null | `below` / `above` |
| `table_caption_position` | str | null | `below` / `above` |
| `section_numbering` | str | null | 如 `arabic`、`none`（ACL 风格无编号） |
| `submission_system` | str | null | OpenReview / CMT / START / HotCRP |
| `dual_submission_policy` | str | null | 双投政策要点（可选） |

## 3. Stat（统计量，来自真实论文样本测量）

```jsonc
{ "mean": 12.4, "median": 12.0, "p10": 8.0, "p90": 18.0, "n": 12,
  "unit": "per_page", "method": "tools/measure_pdf.py", "samples": ["s-neurips-2025-001"] }
```

只放**可测量**的指标：`pdf_pages`、`content_pages`、`figs_per_page`、`tables_per_page`、
`equations_per_page`、`full_width_float_frac`、`fig_width_frac_mean`（占版心宽比例）、
`caption_font_pt`、`body_font_pt_measured`、`margin_*_mm_measured`、`algorithms_per_paper`、
`code_listings_per_paper`、`footnotes_per_page`、`refs_per_paper`。

## 4. Change（逐年变化）

```jsonc
{ "key": "page_limit_content", "edition": "NeurIPS 2021", "year": 2021,
  "value": 8, "source_id": "src-neurips-2021-cfp",
  "note": "该年仍为 8 页；2022 起改为 9 页" }
```

`history` 里**必须**能看出「哪一年是什么规则、何时变了」，用来避免把过时规则当现行规则。

## 5. Source（来源）

```jsonc
{
  "id": "src-neurips-2025-cfp",           // src-<conf>-<edition|name>-<kind>
  "kind": "official-guidelines",           // official-guidelines|official-template|style-source|sample-paper|third-party
  "title": "NeurIPS 2025 Call For Papers",
  "url": "https://neurips.cc/Conferences/2025/CallForPapers",
  "fetched_at": "2026-09-12T10:30:00+08:00",
  "http_status": 200,
  "raw_file": "sources/raw/src-neurips-2025-cfp.html",
  "sha256": "<raw_file 的 sha256>",
  "note": "官方 CFP 页，含页数/匿名/双栏原文"
}
```

`sample-paper` 类来源额外带 `pdf_url`、`venue`、`year`、`anthology_id`（若有）。

## 6. texopt_requirement_map

```jsonc
{
  "requirement_fields": {            // 能直接映射到 texopt Requirement 的字段
    "page_limit": 9, "font_pt": 10, "margin_mm": 19.05,
    "float_spec": "tbp", "overwide_fig_threshold_mm": 120.0
  },
  "unsupported_constraints": [       // texopt 当前表达不了的官方硬要求 -> requirements 模块 roadmap
    { "key": "paper_size", "value": "letter", "why": "Requirement 无纸张尺寸字段" }
  ],
  "recommended_field_suggestions": [ // 建议新增的 Requirement 字段
    { "field": "columns", "type": "int", "example": 2, "rationale": "..." }
  ]
}
```

映射只允许「同一语义」；`font_pt` 只填官方**正文**字号，页边距只填**等效单边**页边距，
换算过程写进 note（如 `0.75in = 19.05mm`）。
