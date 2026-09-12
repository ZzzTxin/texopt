# BRIEF_research.md —— 会议排版规范调研作业书（子代理用）

本文件是**作业契约**。请一次性完整读完再动手。所有产出必须满足这里的格式与溯源要求，
因为会有自动闸门（`tools/validate.py`）逐字校验你写的每一条引文。

## 0. 背景（为什么做）

`texopt` 是「学术论文整体排版优化智能体」（浙大 SRTP 项目）。它需要一份
**计算机顶会排版规范数据集**作为 `requirements`（要求规格）与 `perception`（感知）
模块的数据底座：给定期刊/会议，agent 要知道「什么是硬性要求、什么是推荐、实际论文
长什么样」，从而生成优化规则。

铁律：**所有结论必须可追溯到官方规范或具体论文样本，禁止凭经验臆测**。

## 1. 你的产出（只写这些文件，不要碰别人的）

假设你负责会议集合 `{CONF_IDS}`（形如 `neurips icml iclr aaai`）：

| 文件 | 内容 |
|---|---|
| `conferences/<id>.json` | 每个会议一个，结构见 `schema/KEY_VOCAB.md` 与 `schema/conference.schema.json` |
| `samples/<id>.samples.list.json` | 每个会议 5~8 篇真实论文样本清单（**只列链接与元数据，不要测量 PDF**） |
| `sources/raw/<src-id>.*`、`sources/raw/<src-id>.txt` | 由 `tools/fetch_source.sh` 自动生成，勿手改 |
| `sources/fetch_log.jsonl` | 由脚本自动追加（多代理并行会追加到同一文件，正常） |

**不要修改** `tools/`、`schema/`、其他会议的 JSON。**不要**运行 `tools/measure_pdf.py`
（PDF 量化由主代理统一跑，避免并发冲突）。

## 2. 每个会议要做的事

### 2.1 找并归档来源（至少覆盖）

1. **当前届官方 author guidelines / submission instructions / CFP 页面**（1~3 个页面）
2. **官方 LaTeX 模板本体**（`.sty`/`.cls`，或官方 zip 里的说明文件；可在 CTAN / Overleaf / 官方站点 / 会议 GitHub 找到）——用于 `template-implied` 条目
3. **近 3~5 届的同类页面**（做 `history`：页数上限、匿名政策、参考文献是否计页等逐年变化）
4. **每篇样本论文的落地页**（arXiv abs 页 / ACL Anthology / OpenReview forum 页）——用于证明样本确属该会议

归档命令（在任意目录都能跑，脚本自己定位数据根）：

```bash
cd /mnt/d/桌面/texopt/datasets/conf-specs
tools/fetch_source.sh src-neurips-2025-cfp  https://neurips.cc/Conferences/2025/CallForPapers
tools/fetch_source.sh src-neurips-2025-sty  https://media.neurips.cc/Conferences/NeurIPS2025/Styles.zip sty
tools/fetch_source.sh src-iclr-2025-guidelines https://iclr.cc/Conferences/2025/AuthorGuide
python3 tools/totext.py sources/raw/src-neurips-2025-cfp.html | head -80   # 看文本
grep -i -n "page limit" sources/raw/src-neurips-2025-cfp.txt              # 找逐字引文
```

- `src-id` 命名：`src-<conf>-<edition或主题>-<kind>`，例如 `src-cvpr-2025-authorguidelines`、
  `src-acl-2024-stylezip`、`src-icml-2023-page-limit`。
- 若站点 403/JS 渲染，换官方镜像：CTAN（`https://mirrors.ctan.org/...`）、官方 GitHub、
  会议 proceedings 页、Springer/ACM/USENIX 官方页、OpenReview/ACL Anthology。
- **引文必须来自你归档的文本**：写完 JSON 后用 `grep` 复核。

### 2.2 写 `conferences/<id>.json`

严格按 `schema/KEY_VOCAB.md`：顶层字段、受控键名（不得自造）、
`hard_constraints` / `recommended` / `history` / `texopt_requirement_map` / `sources`。

硬性约束尽量覆盖（有则写、无则跳过并在 `open_questions` 说明）：

`page_limit_content`、`page_limit_total`、`references_counted`、`appendix_allowed`、
`appendix_counted`、`camera_ready_extra_pages`、`paper_size`、`columns`、`body_font_size_pt`、
`body_font_family`、`line_spacing`、`margins_mm`、`column_gap_mm`、`text_width_mm`、
`anonymity`、`page_numbering`、`title_format`、`abstract_max_words`、`bib_style`、
`section_numbering`、`figure_caption_position`、`table_caption_position`、
`float_placement_rules`、`checklist_required`、`supplementary_policy`、
`template_file`、`template_url`、`submission_system`。

要点：
- **页数要分清楚**「正文/技术内容上限」「参考文献是否计入」「附录是否计入」「录用后加页」，
  每年可能不同 —— 这正是 `history` 要记录的。
- 官方模板里的值（如 `\textwidth`、`\columnsep`、字号）标 `confidence: "template-implied"`，
  quote 用 `.sty/.cls` 里的原行；页边距只填**等效单边**页边距（换算写进 `note`）。
- 找不到明文证据的不要写；实在重要但只有间接证据，标 `"inferred"` 并在 note 写清依据，
  或放进 `open_questions`。
- `history` 覆盖近 4~6 年：每条 = 某年某个 key 的**当时取值** + 来源，例如 NeurIPS 页数从 8 → 9 页。

### 2.3 写 `samples/<id>.samples.list.json`

```json
{
  "conference": "neurips",
  "selection_rule": "近 2~3 年录用论文，能确证使用该会议官方模板（arXiv comment/会议页标注）",
  "papers": [
    {
      "sample_id": "s-neurips-2025-001",
      "title": "原标题",
      "venue": "NeurIPS 2025",
      "year": 2025,
      "url": "https://arxiv.org/abs/2501.12345",
      "pdf_url": "https://arxiv.org/pdf/2501.12345",
      "anthology_id": null,
      "evidence_source_id": "src-neurips-2025-sample-001",
      "note": "arXiv comment 字段写明 NeurIPS 2025"
    }
  ]
}
```

- `pdf_url` 必须是**可直接下载的 PDF 直链**（arXiv `/pdf/`、ACL Anthology `.pdf`、
  OpenReview `.../pdf`、USENIX `...pdf`），不要 landing page。
- 每个样本都要在 `conferences/<id>.json` 的 `sources[]` 里有一条
  `kind: "sample-paper"` 的来源（含 `url`、`pdf_url`、`venue`、`year`、`raw_file` 归档的落地页），
  `evidence_source_id` 指向它。样本要挑**排版有代表性**的（含图表、公式、算法、多栏浮动体），
  不要全是纯文字短文。
- 系统偏好/综述/超长附录论文也可以，但至少一半是常规研究论文。

### 2.4 自查（必须做，直到 0 error）

```bash
cd /mnt/d/桌面/texopt/datasets/conf-specs
python3 tools/validate.py conferences/<id>.json
```

它会逐字校验 evidence 引文是否真的在你归档的文本里。**error 必须清零**；
`提示`（warning）尽量清理。引文对不上就回去核对原文措辞（归一化只处理空白/连字符/引号）。

## 3. 质量要求

- 一个会议的 `hard_constraints` 至少 8 条，`sources` 至少 4 条（含官方指南 + 模板 + 样本落地页）。
- 每条 entry 的 `evidence.quote` 是**英文原文摘录**（逐字，可含少量上下文），
  不要改写、不要翻译、不要拼接隔得很远的句子。
- 引文太短（<15 字符）容易误匹配且无信息量；用能自证语义的句子/表格行/代码行。
- 若某会议同时有「投稿版/录用版（camera-ready）」，两个 scope 分别记录（`scope` 字段）。
- 写完在文件顶层 `open_questions` 里列出你**没能确认**的点（例如"ACM TAPS 对新版模板的页数规定未找到明文"）。
