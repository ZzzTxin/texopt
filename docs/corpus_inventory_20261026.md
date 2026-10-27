# 语料层 Step 1：数据清单与已做分析（2026-10-26）

> 语料：`paperfit-bench-originals` 的 200 篇已录用 arXiv 原件（10 会 × 20 篇）
> 编译：Windows TeX Live 2024，8 路并行，两层 pdflatex，26 分钟，**200/200 成功，0 失败**
> 缓存：`/mnt/d/texopt-corpus/`（`pdf/` 2180 MB、`log/`、`rows_originals.jsonl`、`corpus_stats.json`）
> 脚本：`tools/corpus_build.py`（采集）、`tools/corpus_analyze.py`（汇总）

---

## 表 1　采集了什么（每篇 1 行，每页 1 条）

| 分组 | 字段 | 粒度 | 来源 | 覆盖 |
|---|---|---|---|---|
| 标识 | `case_id` / `venue` / `paper_id` / `main_tex` / `main_tex_used` / `n_tex` | 篇 | MANIFEST.jsonl | 200/200 |
| bench 元数据 | `column`(single 122 / double 78) / `target_pages` / `profile`(easy/medium/hard) / `documentclass` | 篇 | bench/cases.jsonl | 200/200 |
| 编译 | `compile_ok` / `compile_rc` / `seconds`（中位 38.4 s）/ `pdf_bytes`（合计 2.18 GB） | 篇 | 实测 | 200/200 |
| 规模 | `pages`（合计 3898 页，篇均 19.5） | 篇 | mutool 渲染页数 | 200/200 |
| 缺陷计数 | `defects.overfull` / `underfull` / `vbox_over` / `vbox_under` / `floatwarn` / `warn` / `errors` / `macros_missing` / `float_H` | 篇 | 编译日志正则 | 200/200 |
| 缺陷幅度 | `amplitude.raw_overfull_pt_*`（最大/均值/全量列表）、`raw_vbox_pt_max`、`raw_underfull_badness_max`、`perceive_*`（旧口径对照） | 篇 | 日志正则 | 977 条 overfull / 2280 条 underfull |
| 日志样本 | `warn_samples`（前 5 条未去重警告原文） | 篇 | 日志 | 200/200（篇均 78.9 条） |
| 页面像素 | `ink_ratio`、`top_blank`、`bottom_blank`、`content_height`、`max_gap`(+`_at`)、`band`(+`_at`)、`left_blank`、`right_blank`、`top_bottom_ratio` | 页 | mutool 40 dpi 灰度 PGM + `texopt.visual.page_metrics` | 3898/3898 页，0 缺失 |

## 表 2　分析了什么（6 组）

| # | 分析项 | 统计量 | 分组维度 | 关键结果 | 用途 |
|---|---|---|---|---|---|
| 1 | 论文规模 | mean、P10/P25/P50/P75/P90/P95、max、超 target 篇数 | 全局 + 10 会 | 篇均 19.5 页，P50 16.5，max 61；**126/200 超 target_pages** | 校页数 gate：须区分正文页与含附录页 |
| 2 | 缺陷频率 | 出现率、篇均、每 10 页、非零篇 P50/P90、max | 全局 + 10 会 + 2 栏 | overfull 71.0%/4.88；underfull 73.5%/11.40；vbox_over 14.5%/0.44；vbox_under 79.0%/4.55；floatwarn 47.0%/1.97 | `wᵢ` 的**频率分母**（会议容忍度） |
| 3 | 缺陷幅度 | P50/P90/P95/max/mean；badness 顶格比例 | 全局 | overfull pt P50 4.19 / P90 16.4 / max 269；vbox_over pt P50 2.79；underfull badness **38.1% 顶格 10000** | 把线性计数换成幅度加权/饱和曲线 |
| 4 | 软指标分位 | P5/P25/P50/P75/P95/max | 全局 + 2 栏 | ink_ratio P50 0.120、P95 0.209；bottom_blank P95 0.161；band P95 0.055 | `A_soft` 理想带的**数据来源** |
| 5 | 现有带命中率 | 低于下界/高于上界/带内 %、语料 P10–P90 | 8 个 `SOFT_BANDS` | ink_ratio 22.2% 越上界；max_gap 18.6%；top_bottom_ratio 20.0%；**band 94.7% 低于下界** | 判定哪些带要改、哪个指标口径坏了 |
| 6 | 卫生与工程 | microtype 缺失率、`[H]` 使用、编译耗时 | 全局 | microtype 缺失 **56.0%**；`float_H` 统计口径错（数在日志上，应为源码） | 校“质量宏缺失”权重 2.0 是否合理 |

## 表 3　采集了但这一步**没有**分析（明确留白）

| 数据 | 现状 | 下一步归属 |
|---|---|---|
| `warn`（篇均 78.9 条、已去重） | 只存了前 5 条样本 | 需按类型归一（undefined ref / unused option / hyperref 等）后再定权重，属 Step 2 |
| `errors`（仅 1 篇有 1 条） | 只计数 | 可忽略，但要在报告里说明 |
| `band_at` / `max_gap_at`（纵向位置） | 已采未统计 | Step 2 修 `band` 定义时一起看 |
| 页角色分层（首页 / 参考文献 / 附录） | 未做 | 影响理想带是否该分角色，Step 2 |
| 按会 × 栏的软指标分位 | 只做了全局与分栏 | 每组 ~8 篇，样本太薄，等扩充语料 |
| 正文页 vs 附录页的缺陷密度 | 未拆 | 与页数 gate 一起做 |
| `float_H` 真实使用率 | 统计写错 | 重数源码，Step 2 |

## 三个已确认的口径 bug（Step 2 待修）

1. `Underfull \vbox` 报 `(badness N)` 不含 pt；旧正则 `(Npt too short)` 永不匹配 → 曾误判 vbox_under 全 0（实际 79%）。
2. `perceive.parse_log()` overfull 正则要求 `in paragraph at lines`，漏 `detected at line N`，漏检约 10%。
3. `band` 指标实测 P95 = 0.055，与旧带 (0.05, 0.35) 差 1–2 个数量级，定义需重做。
