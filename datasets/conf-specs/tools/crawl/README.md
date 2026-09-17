# tools/crawl —— 论文样本爬取（与既有 107 篇同一格式）

新增论文样本的完整链路。设计目标只有一个：**新加的样本在格式、命名、溯源上与既有 107 篇完全一致**，
可以被 `validate.py` / `check_sample_links.py` / `build_dataset.py` / 模板链原样消费。

```
官方索引页 ──venues.py──▶ candidates/<conf>.jsonl ──add_samples.py──▶
    sources/raw/<src-id>.html/.txt + sources/fetch_log.jsonl   （归档，带 sha256）
    conferences/<cid>.json → sources[]        （kind=sample-paper，条目由 mk_source.py 生成）
    samples/<cid>.samples.list.json → papers[]（sample_id/venue/url/pdf_url/evidence_source_id/note）
        │
        ├─ validate.py           逐字溯源校验（必须 0 error）
        ├─ check_sample_links.py PDF 直链可用性（%PDF 魔数校验，带重试）
        ├─ fix_links.py          坏链体检/自动修复/摘除（写回上方两个数据文件）
        └─ build_dataset.py      下载 PDF → 几何测量 → statistics/patterns/texopt-templates
```

## 一条命令链条

```bash
cd /mnt/d/桌面/texopt/datasets/conf-specs

# 0) 一次性：准备 PDF 依赖（本机无 pip，走纯 wheel 解包）
bash tools/bootstrap_py.sh

# 1) 抓候选清单（每会一条；索引页自动归档为 src-<conf>-<year>-proceedings）
python3 tools/crawl/venues.py --conference neurips --years 2024,2025 --limit 30
python3 tools/crawl/venues.py --conference icml    --years 2024,2025 --limit 30
python3 tools/crawl/venues.py --conference cvpr    --years 2024,2025 --limit 30
python3 tools/crawl/venues.py --conference iccv    --years 2023,2025 --limit 30
python3 tools/crawl/venues.py --conference wacv    --years 2024,2025 --limit 30
python3 tools/crawl/venues.py --conference acl     --years 2024,2025 --limit 30
python3 tools/crawl/venues.py --conference emnlp   --years 2024,2025 --limit 30
python3 tools/crawl/venues.py --conference naacl   --years 2024,2025 --limit 30
python3 tools/crawl/venues.py --conference ijcai   --years 2024,2025 --limit 30
python3 tools/crawl/venues.py --conference aaai    --years 2024,2025 --limit 30
python3 tools/crawl/venues.py --conference eccv    --years 2022,2024 --limit 30
python3 tools/crawl/venues.py --conference osdi    --years 2024 --limit 20
python3 tools/crawl/venues.py --conference nsdi    --years 2024,2025 --limit 20

# 2) 入库（归档落地页 + 生成 sample-paper 来源 + 追加样本；可中断，重跑续跑）
python3 tools/crawl/add_samples.py --conference neurips --limit 30
# …其余会议同上，逐个替换 --conference

# 3) 闸门（不通过就别继续）
python3 tools/validate.py                 # 必须 错误 0
python3 tools/check_sample_links.py       # 不可用链接 0（000 会自动重试 2 次）
# 若仍有不可用：先体检再修
python3 tools/crawl/fix_links.py          # 预览
python3 tools/crawl/fix_links.py --apply  # 命中可修的直链就写回数据文件

# 4) 测量 + 统计 + 生成 texopt 模板（先按会议跑，最后可全量重跑）
python3 tools/build_dataset.py --only neurips,icml,cvpr,iccv,wacv,acl,emnlp,naacl,ijcai,aaai,eccv,osdi,nsdi
# python3 tools/build_dataset.py          # 全量 16 会一起重算

# 5) 模板链 + 安装进 texopt
python3 tools/analyze_templates.py
python3 tools/build_templates.py
python3 tools/validate_templates.py
python3 tools/check_conference_integration.py
tools/install_templates.sh --apply
```

## 支持的会议（Tier A：官方索引页一页拿全量直链）

| 会议 | 数据源 | 说明 |
|---|---|---|
| neurips | proceedings.neurips.cc | abstract 页 + Paper PDF 成对，按 hash 配对 |
| icml | proceedings.mlr.press | 卷号内置（2023 v202 / 2024 v235 / 2025 v267），可用 `--volume` 覆盖 |
| cvpr / iccv / wacv | openaccess.thecvf.com | `<CONF><YEAR>?day=all`，html 页与 papers PDF 按 slug 配对 |
| acl / emnlp / naacl / coling | aclanthology.org | 卷名内置，可用 `--volume 2024.acl-long` 覆盖；自动跳过 x.0 整卷前置页 |
| ijcai | ijcai.org/proceedings | paper_wrapper → 标题 + `NNNN.pdf` |
| aaai | ojs.aaai.org | OJS 归档分页 → `AAAI-<yy>` 期号 → 论文页 + `pdf` galley（默认只要 Technical Tracks 主会，`--track all` 含 special track） |
| eccv | ecva.net/papers.php | ECVA 官方开放索引，2018–2024 共一页；`-supp.pdf` 不算论文 |
| osdi / nsdi / atc / fast / security | usenix.org | 索引页只有 presentation 链接，标题与 PDF 从落地页取（每篇多一次请求） |

**暂未覆盖（Tier B）**：iclr、kdd、www、sosp、siggraph。
实测原因（2026-09-17 逐个探过）：ICLR 的 OpenReview `api2`/`api`/`pdf?id=` 全部 403（Cloudflare），
站点是 JS SPA，只能从 `iclr.cc/virtual/<year>/papers.html` 拿到清单；KDD/WWW/SOSP/SIGGRAPH 的
论文集只在 ACM DL，`dl.acm.org/doi/...` 与 `/doi/pdf/...` 均 403，无官方开放镜像。这两类需要改走
清单（iclr.cc / OpenAlex / dblp）+ PDF（OpenAlex `best_oa_location` → arXiv，见 `tools/oa.py`）。
注意 dblp 有流量反爬（连打几个请求后会返回 Anubis PoW 挑战页），要用得低频。
给某会议加 adapter 只需在 `venues.py` 里加一个 `adapt_*` 函数并登记进 `SPECS` / `ADAPTERS`，
再在 `styles.py` 登记 venue/src 命名（见下）。

## 关键约定

- **命名一致性**：`styles.py` 是 venue 字符串与 `src-id` 模板的单一来源，按会议登记既有写法
  （如 acl 用 `src-acl-2024-paper-348`、osdi 用 `src-osdi24-pres-<slug>`、icml 的 venue 用会议全称；
  aaai 用 `venue="AAAI-25"` + `src-s-aaai-2025-00N`；eccv 用 `venue="ECCV 2024"` + 共享来源
  `src-eccv-papers-list`）。新样本因此不会与既有样本出现两套命名。
  **共享来源**：ECCV 的所有样本证据就是 ECVA 索引页这一页，`styles.shared_src()` 会识别这种
  模板（不含 `{nnn}/{anth}/...` 占位符），`add_samples.py` 遇到已存在的共享来源就复用它、
  不为每篇重复抓同一页。
- **压缩响应**：`common.get_text()` 会自己解 gzip/deflate（ojs.aaai.org 无视
  `Accept-Encoding: identity` 一律回 gzip）；`fetch_source.sh` 的 curl 也带 `--compressed`，
  否则归档下来的是 gzip 二进制，`totext.py` 抽不出文本。
- **编号不覆盖**：`sample_id = s-<cid>-<year>-<NNN>`，NNN 从该（会议, 年份）已有最大值 +1 开始。
- **可中断可续跑**：每入库一篇即原子落盘；重跑自动跳过已存在的 pdf_url/标题/src-id。
- **溯源不许手抄**：`sha256/fetched_at/http_status/raw_file` 一律由 `fetch_source.sh` →
  `mk_source.py` 从 `sources/fetch_log.jsonl` 读出。
- **礼貌抓取**：默认每域名 2.0s 间隔（`--sleep` 或 `CRAWL_INTERVAL` 可调），429/5xx 指数退避，
  其他 4xx 直接跳过该条。`--limit` 用**均匀抽样**（等间隔取样），避免只取到字母序靠前/单一主题的论文。
- **PDF 不入库**：PDF 只落 `sources/raw/pdfs/`（已被 `.gitignore` 忽略），仓库里只留链接 + 测量结果。

## 常用参数

```bash
python3 tools/crawl/venues.py --list                 # 支持的会议
python3 tools/crawl/venues.py -c cvpr --year 2024 --limit 5 --no-archive-index
python3 tools/crawl/venues.py -c aaai --year 2025 --limit 5          # 25 期/约 3000 篇，约 1.5 分钟
python3 tools/crawl/venues.py -c aaai --year 2025 --track all --limit 5   # 连 special track 一起收
python3 tools/crawl/venues.py -c eccv --year 2024 --limit 5          # 全届一页，约 10 秒
python3 tools/crawl/add_samples.py -c acl --limit 5 --dry-run     # 只看计划，不联网不写文件
python3 tools/crawl/add_samples.py -c aaai --year 2025 --limit 5
python3 tools/crawl/add_samples.py -c eccv --year 2024 --limit 5
python3 tools/crawl/add_samples.py -c osdi --year 2024 --limit 5  # 只入某年
```

## 坏链怎么办（`fix_links.py`）

先看清是**哪一类**问题，三类处理方式不同：

| 现象 | 含义 | 处理 |
|---|---|---|
| `000`（无 content-type） | 本机网络抖动（raw.githubusercontent 在部分网络下时通时断） | 重跑即可；`check_sample_links.py --retries 3` 会重试 |
| `404` + `text/html` | PDF 直链规则变了（例如 neurips 非主会轨道的命名） | `fix_links.py --apply` 按规则重推直链 |
| `200` + `[非 PDF!]` | 拿到的是 HTML（重定向/落地页），不是 PDF | 同上；必要时 `--drop` 摘除 |

```bash
python3 tools/crawl/fix_links.py                       # 全量体检（不改）
python3 tools/crawl/fix_links.py -c neurips --apply     # 修 neurips
python3 tools/crawl/fix_links.py --drop s-neurips-2025-001,s-neurips-2025-002 --apply
```

它会同时改写 `samples/<cid>.samples.list.json` 与 `conferences/<cid>.json` 里对应
`sample-paper` 来源的 `pdf_url`，并输出 `summary/link-repair-report.md`。

## 防呆（默认开启）

- `venues.py` 选出条目后会逐条 Range 探测 pdf_url，404/非 PDF 的直接丢弃（`--no-verify-pdf` 关闭）
- `add_samples.py` 在归档落地页之前先探测 pdf_url，坏链不入库（`--no-verify-pdf` 关闭）
- `--track`（neurips 专用）默认只取主会轨道 `Conference`；索引里没有主会轨道时会明确提示
  （例如 2025 主会论文集尚未发布时只有 `Creative_AI_Track`）

## 耗时参考（单机串行）

- 抓候选清单：每个会议每年 2–5 秒（usenix 因为要逐篇取落地页，20 篇约 1–2 分钟；
  aaai 要先翻归档分页再逐期抓论文表，2025 年 25 期约 3000 篇 ≈ 1.5 分钟；eccv 一页拿全、≈10 秒）
- 入库：每篇 1 次请求 ≈ 2–3 秒（30 篇约 1–2 分钟）
- 测量：每篇下载 + pdfminer 解析 ≈ 20–60 秒（30 篇约 15–30 分钟/会议）

建议**按会议分批**推进：跑完一个会议立刻 `validate.py` + `check_sample_links.py`，再跑下一个。
