# page_metrics.v1 —— 页面级指标数据结构规范

> 阶段 0 交付物之二。配套代码：`texopt/page_metrics.py`（仅数据结构 + 校验 + 聚合 + 旧输出适配，**不做提取、不接入 A 分**）。
> 设计依据：《学术论文排版审美量化模型设计方案（修订版 v2）》第六、七、八章。

## 1. 目的与边界

`page_metrics.v1` 是审美量化模型的**统一落盘 schema**。阶段 1-4 的所有提取器、profile 构建与异常检测都读写同一份结构，避免各阶段各自发明字段。

明确边界：

- 这里定义的是**版面特征与常态偏离的载体**，不是人类审美评分。
- 阶段 0 只交付结构与规范；`visual.py` 能算的映射进来（`extracted`/`partial`），其余为 `placeholder`。
- 不允许把 `placeholder` 上报为"已实现"——`meta.unknown_fields` 会自动列出未填字段，作为阶段 1 的待办清单。

## 2. 顶层结构

```
{
  "schema": "page_metrics.v1",
  "extractor_version": "0.1.0",
  "profile_version": null,           // 阶段 2 起写入（venue+year+layout 版本）
  "doc":    { ... },                 // 文档元信息与渲染环境
  "pages":  [ page, ... ],           // 页面级指标（强制带 role）
  "paper":  { ... },                 // 论文级聚合（分层）
  "meta":   { "notes": [...], "unknown_fields": [...] }
}
```

### 2.1 `doc`

| 字段 | 类型 | 含义 |
|---|---|---|
| `pdf` / `tex` | str\|null | 源文件路径 |
| `venue` / `year` | str\|null / int\|null | 目标会议与届次（profile 分层键） |
| `layout` | str\|null | `onecolumn` / `twocolumn`（profile 分层键） |
| `pages` | int\|null | 总页数 |
| `render.tool` / `render.dpi_pixel` | str\|null / int\|null | 渲染器与像素层 dpi（复现性所必需） |
| `generated_at` | str\|null | ISO 时间戳 |

### 2.2 `pages[]`

每页一个对象，**强制携带 `role`**（分层条件化的前提，方案第五章）。

| 字段 | 类型 | 含义 |
|---|---|---|
| `page` | int(≥1) | 页码（1-based），全文档唯一 |
| `role` | enum | `title` / `section-head` / `body` / `math-heavy` / `figure-page` / `table-page` / `references` / `appendix` / `last-page` / `unknown` |
| `role_confidence` | float\|null | 角色判定置信度（阶段 1） |
| `role_source` | str\|null | `rule` / `manual` / `model` |
| `units` | obj | 页面与版心几何（mm）：`page_w_mm`、`page_h_mm`、`usable_w_mm`、`usable_h_mm`、`columns` |
| `legacy` | obj | `visual.py` 旧字段原样保留，供回归对比，非正式字段 |

指标组（每组含 `status`）：

| 组 | 证据层 | 内容 |
|---|---|---|
| `density` | pixel（阶段 2 起升级 text/vector） | `ink_ratio_page`、`ink_ratio_text`、`coverage_text/figure/table/other` |
| `ratio` | vector | `fig_text`、`figtab_text` |
| `balance` | pixel | `d_top/d_mid/d_bot`、`left_right`、`visual_centroid_y`、`per_column[]`（双栏按栏算，方案 6.4） |
| `whitespace` | vector | `total/structural/boundary/float/trailing/anomalous_ratio` + `regions[]` + `n_regions`/`n_fragments`/`n_anomalous`/`max_anomalous_height_ratio`（方案第七章，阶段 3 起 `status=extracted`） |
| `alignment` | vector | `left_var`、`right_var`、`center_var`、`n_elements` |
| `consistency` | vector | `figure_width_cv`、`caption_style_cv` |
| `readability` | text | `chars_per_line_mean`、`leading_ratio`、`font_pt`、`para_lines_mean` |
| `microtype` | log | `overfull`、`underfull`、`vbox_overfull`、`vbox_underfull` |
| `figure_quality` | vector | `min_effective_dpi`、`aspect_outliers` |

### 2.3 `whitespace.regions[]`（空白区域）

| 字段 | 类型 | 含义 |
|---|---|---|
| `bbox` | [x0,y0,x1,y1]\|null | PDF pt，原点左下 |
| `area_ratio` | float\|null | 面积 / `A_usable` |
| `height_ratio` | float\|null | **区域内最长的一条「整行全空」连续带**高度 / 版心高（不是 bbox 高：L 形/环形区域的 bbox 高会虚高到 1.0） |
| `class` | enum | `structural` / `boundary` / `float` / `trailing` / `anomalous` / `unknown` |
| `adjacent` | [str] | 邻接/证据标签：`heading` / `float` / `caption` / `paragraph` / `spacing` / `boundary:left|right|top` / `column-end` / `doc-end` / `section-end` / `page-continue` / `text-continues` / `title-page` / `unexplained` |
| `confidence` | float\|null | 分类置信度 |

门控（方案 7.4）：只有 `class=anomalous`（**全宽连续空白带**超阈 **且** 无结构解释 **且** 上方有内容夹住）才进入惩罚项；其余四类只作画像特征。

阶段 3 的口径补充：
  * `regions` 只列 `area_ratio ≥ 0.004`（0.4% 版心）的区域；更小的碎片（行距/字距噪声）不单列，
    但其面积**计入 `structural_ratio`**，因此恒有 `Σ 五类比率 == total_ratio`（可与覆盖率互补量逐页互校）。
  * `total_ratio` = 版心内空白格的完整量（与提取层的「内容并集」互补，误差仅来自 4pt 网格量化）。
  * 分类尺度用「整行全空带」（该行在两个栏范围内都没有内容格），因此居中标题旁、浮动体旁的
    L 形/窄条空白不会产生虚高的「高度」。

### 2.4 `paper`

| 字段 | 类型 | 含义 |
|---|---|---|
| `n_pages` | int\|null | 页数 |
| `roles_hist` | obj | role → 页数分布 |
| `float_ref_distance` | obj | `{mean, max, n}`：浮动体到首次引用距离（方案 6.3） |
| `aggregates` | obj | `"<组>.<指标>" → {median, mean, max, p90, n}` |
| `by_role` | obj | `role → 同上`（**分层聚合**，主判据来源） |
| `status` | enum | 聚合状态 |

聚合口径（方案第八章）：同时给 `median/mean/max/p90`——整体画像用 `median`，异常判定用 `max`/`p90`（最差页）。

## 3. status 取值

| 值 | 含义 |
|---|---|
| `extracted` | 现有实现可算出，且口径已符合 v1 定义 |
| `partial` | 只有代理量或部分子项（如 `ink_ratio_page` 含图像污染） |
| `placeholder` | 字段已定义、尚无实现 |
| `unavailable` | 当前证据层无法获得，需新提取手段 |

## 4. 校验与工具函数

| 函数 | 作用 |
|---|---|
| `validate(doc)` | 结构校验（schema 名、页码唯一、role 合法、各组存在且有合法 status），返回问题清单 |
| `missing_fields(doc)` | 列出仍为 `None` 或 `placeholder` 的字段路径 |
| `summarize_pages(pages)` | 页面列表 → `(paper.aggregates, by_role)` |
| `finalize(doc)` | 回填 paper 聚合、role 直方图、未知字段清单（可重复调用） |
| `from_legacy_visual(vis, roles=...)` | 把 `visual.analyze_pdf()/visual_report()` 输出适配为 v1 |
| `coverage_report(doc)` | 各指标组的 fill/placeholder 统计（阶段 0 缺口盘点用） |
| `dump(doc, path)` / `load(path)` | UTF-8 JSON 读写（中文不转义，缩进 2） |

## 5. 阶段 0 的实际填充情况

以 `examples/demo.tex` 编译产物跑通后（见 `docs/stage0_visual_inventory.md` 第 4 节实测）：

- `legacy`、`density.ink_ratio_page`、`whitespace`（五类 + regions）→ 可用（`extracted`/`partial`）
- `ratio` / `balance` / `alignment` / `consistency` / `readability` / `figure_quality` / `role` → **阶段 1 起已 `extracted`**（本节为阶段 0 的历史记录）
- `whitespace` 五类留白 + `regions` → **阶段 3 起 `extracted`**（见 `docs/stage3_whitespace.md`）
- `float_ref_distance`（浮动体—首次引用距离）→ 仍 `placeholder`，需 cross-ref 解析（阶段 4+）
- `microtype` → 数据已在 `score.py`/`perceive.py`（日志层）算过，但**未按页落盘**，需阶段 1 的页级归属（日志里的 `[n]` 页码 → 页级映射）

## 6. 版本演进约定

- 字段只增不删；语义变更必须升 `schema` 版本。
- `legacy` 子对象在 `page_metrics.v2` 中移除（阶段 2 起新提取器取代旧像素量）。
- `profile_version` 与 `schema` 版本独立：前者随会议档案更新，后者随字段结构更新。
