# SUBAGENT_TASK.md —— 子代理作业单（会议排版规范数据集）

数据根目录（所有命令都先 `cd` 到这里）：

```
/mnt/d/桌面/texopt/datasets/conf-specs
```

先读这两个文件，它们是契约：

1. `BRIEF_research.md` —— 作业书（产出、字段、溯源规则）
2. `schema/KEY_VOCAB.md` —— 受控字段表（唯一字段字典，禁止自造键名）

样板（照它的结构和粒度写）：

- `conferences/neurips.json`（16 条 hard_constraints / 5 条 recommended / 13 条 history / 15 条 sources）
- `samples/neurips.samples.list.json`（6 篇样本）

## 你要交付什么

对你负责的每个会议 `<id>`：

1. `conferences/<id>.json` —— 规范层（硬性约束 / 推荐规范 / 逐年变化 / texopt 映射 / 来源）
2. `samples/<id>.samples.list.json` —— 5~8 篇真实论文样本清单（只列链接与元数据）
3. 需要的新来源用 `tools/fetch_source.sh` 抓取归档（原始文件 + .txt + 日志）
4. 自查：`python3 tools/validate.py conferences/<id>.json` → **错误必须为 0**

## 硬性规则（会被自动闸门检查）

- 每条约束的 `evidence.quote` 必须是**你归档的 .txt 原文里的逐字英文摘录**（validate.py 会逐字核对）。
  引文务必来自该 source 的 `raw_file` 对应文本；写完用 `grep` 复核。
  提醒：归档的 HTML→文本里，标点前可能被插入空格（如 `pages ,`），**引用时避开这种片段**。
- `sources[]` 里每个 `sample-paper` 必须：`kind="sample-paper"`，带 `pdf_url`（**PDF 直链**）、`venue`、`year`，
  且其归档页文本里确实出现该会议名（validate.py 会给提示）。
  → 证明“这篇论文确属该会议”的证据 = 官方 proceedings/程序/accepted 列表页，或 arXiv 落地页 comment 字段。
- `hard_constraints` 至少 8 条，`sources` 至少 4 条。
- 只写你负责的会议文件。**不要改** `tools/`、`schema/`、`README.md`、`BRIEF_research.md`、别人的 `conferences/*.json`。
- **不要运行** `tools/measure_pdf.py` 或 `tools/build_dataset.py`（主代理统一跑，避免并发）。

## 工具

```bash
cd /mnt/d/桌面/texopt/datasets/conf-specs

tools/fetch_source.sh src-<conf>-<edition>-<kind> <url> [html|pdf|sty]   # 抓取归档
python3 tools/totext.py sources/raw/xxx.html | head -80                  # 看归档文本
grep -i -n "page limit" sources/raw/src-xxx.txt                          # 找逐字引文
python3 tools/mk_source.py <src-id> --kind <kind> --title "..." \
    --note "..." [--pdf-url U --venue "XXX 2024" --year 2024]            # 生成 Source JSON（sha256 自动取自日志，禁止手抄）
python3 tools/validate.py conferences/<id>.json                          # 自查（必须 0 错误）
```

`mk_source.py` 的 `--kind`：`official-guidelines|official-template|style-source|sample-paper|third-party`。
多个 id 用逗号分隔会输出 JSON 数组。

## 已有的归档来源（优先复用，别重复抓）

先 `ls sources/raw/ | grep <conf>` 看有没有现成的页/模板/程序列表。已知大致覆盖：

- icml：2021–2025 cfp/authorinstructions + 2025 sty
- iclr：2020–2025 cfp/authorguide + 2025 sty
- aaai：2022–2025 cfp/subinstructions + 2025 sty/formatting
- acl / emnlp：2022/2023/2024/2025 cfp + acl.sty + natbib.bst + ACL Anthology 卷页（2023/2024/2025 的 acl-long、emnlp-main）
- ijcai：2023–2025 proceedings 列表页 + 2024/2025/2026 sty + authorskit
- cvpr：2022–2025 authorguidelines + 2025 sty/模板；iccv：2021/2023/2025 authorguidelines；eccv：2022/2024/2026 指南 + LNCS/splncs04
- siggraph：2022–2025 TP 页 + 若干 arXiv 样本页
- kdd：2022–2025 cfp/researchtrack + acmart/ACMReferenceFormat
- www：2022/2023/2024/2026 researchtrack + 2024 accepted 列表
- osdi / sosp / nsdi：2023–2025 cfp + program/accepted 列表；osdi24/nsdi24 还有若干 presentation 页

## 样本论文怎么找、怎么证明（重点，别凭记忆）

**首选：会议的官方论文列表页**（论文出现在里面即证明录用）

| 会议族 | 列表页 | PDF 直链规律 |
|---|---|---|
| NeurIPS | `https://proceedings.neurips.cc/paper_files/paper/<year>` | `/file/<hash>-Paper-Conference.pdf` |
| ICML | `https://proceedings.mlr.press/v<vol>/` | 页内 `href` 指向 `.pdf` |
| ICLR | `https://iclr.cc/virtual/<year>/papers.html`（或 accepted 列表页） | 需在页内找 |
| ACL/EMNLP | `https://aclanthology.org/volumes/<year>.<venue>-long/`（**已归档**） | `https://aclanthology.org/<anthology_id>.pdf` |
| CVPR/ICCV | `https://openaccess.thecvf.com/<CONF><year>`（列表/日程页） | `.../papers/<Title>_<CONF>_<year>_paper.pdf` |
| ECCV | `https://www.ecva.net/papers.php` | `.../papers/<...>.pdf` |
| AAAI | `https://ojs.aaai.org/index.php/AAAI/issue/archive` | ojs 论文页 |
| IJCAI | `https://www.ijcai.org/proceedings/<year>/`（**部分已归档**） | `https://www.ijcai.org/proceedings/<year>/<nnnn>.pdf` |
| KDD/WWW | ACM DL（常 403）→ 改用 arXiv 落地页 comment 字段或官方 accepted 列表 | arXiv `/pdf/<id>` |
| SIGGRAPH | ACM DL（常 403）→ arXiv 落地页 comment 字段 | arXiv `/pdf/<id>` |
| OSDI/SOSP/NSDI | `https://www.usenix.org/conference/<conf><yy>/technical-sessions` | `https://www.usenix.org/system/files/<conf><yy>-<slug>.pdf` |

**注意**：OpenReview API（api2.openreview.net）和 arXiv API（export.arxiv.org/api）在本机被限流/拦截，
不要依赖它们；改用上面的 HTML 页面抓取。arXiv `/abs/<id>` 页面可以正常抓。

选样原则：每会议 5~8 篇，**至少一半是常规研究论文**，尽量覆盖不同版面结构（含多图、多表、
公式密集、算法伪代码、附录、跨栏大图等），不要全是纯文字短文。样本 PDF 会被主代理统一量化，
你的任务是保证“链接可下载 + 归属可证”。

## 写 JSON 的要点

- 页数要分清：`page_limit_content`（正文上限）/ `references_counted` / `appendix_counted` /
  `camera_ready_extra_pages`，逐年写进 `history`。
- 模板里读出的值（字号、版心宽、栏间距、paper size）用 `confidence: "template-implied"`，
  quote 用 `.sty/.cls` 原行，`note` 里写换算（如 `0.75in = 19.05mm`）。
- `columns` 若官方无明文，可标 `"inferred"` 并在 note 说明依据。
- `texopt_requirement_map.requirement_fields` 只允许这些字段：
  `page_limit, font_pt, margin_mm, eq_fleqn_allowed, toc, running_header, heading_color,
  enable_quality_macros, float_spec, microtype, overwide_fig_threshold_mm, overwide_table_report,
  allow_geometry_tune, margin_min_mm, margin_step_mm, allow_fontsize_step, max_iterations, verbose`
  （表达不了的官方硬要求写进 `unsupported_constraints`）。
- `history` 每条的 `source_id` 必须在你 `sources[]` 里，年份升序。
- `open_questions` 里如实列出没查到的点（宁可承认未确认，也不要猜）。

## 完成标准

```bash
python3 tools/validate.py conferences/<你负责的每个 id>.json   # 错误 0
ls conferences/ samples/                                        # 文件都在
```

最后回报：每个会议的 hard/recommended/history/sources 条数、样本篇数、validate 结果、未解决的问题。
