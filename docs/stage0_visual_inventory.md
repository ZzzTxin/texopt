# 阶段 0 交付：visual.py 盘点 + 指标—现状—缺口表

> 对应《学术论文排版审美量化模型设计方案（修订版 v2）》第十五章「阶段 0」。
> 盘点对象：`texopt/`（`perceive.py` / `score.py` / `visual.py` / `engine.py`）。
> 结论一句话：**现有实现只覆盖"整页级像素量 + 全局缺陷计数"，审美方案里真正要用的"矢量/文本块层 + 分层统计"基本为零。**

## 1. 盘点范围与口径

| 证据层 | 实现位置 | 能提供什么 |
|---|---|---|
| 源码层 source | `perceive.parse_source()`、`scan_hygiene()` | 文档类/字号/geometry/栏数/fleqn、浮动体与位置参数、插图宽度表达式、tabular 区间、结构标记（toc/header/heading_color）、图指纹、卫生问题清单（行号级） |
| 日志层 log | `perceive.parse_log()` | overfull / underfull / vbox（O/U）/ 浮动体警告 / 表格超宽 / 其余 warning / 首个错误 |
| PDF 层 pdf | `engine.pdf_pages()`、`engine.content_pages()` | 真实页数（与日志交叉验证）、正文页数区间（pdftotext 定位参考文献首页） |
| 页面图像层 pixel | `visual.page_metrics()`、`page_proxy()`、`find_defects()` | 墨迹占比、上下空白、内容高度、最大空白带、最大内容带、左右空白、上下半墨迹比；6 类整页级视觉缺陷 |
| 评分层 | `score.aesthetic_score()`、`defect_penalty()`、`HYGIENE_WEIGHT`、`visual.DEFECT_WEIGHT` | 上述量的加权和（进 `A_defect`） |

注意：`visual.py` 里曾有两套并行的像素量 —— `page_metrics()`（Phase 2，已并入 A）与 `page_proxy()`（更早的实验性代理，**未并入 A**）。阶段 0 已把它们**合并**：`page_proxy()` 现在是 `page_metrics()` 的薄适配层，`visual_report()` 一次解析同时产出两者（详见第 6 节）。

## 2. 指标—现状—缺口表

图例：`extracted` 已有且口径合规 / `partial` 有代理或部分子项 / `placeholder` 已定义无实现 / `unavailable` 当前证据层拿不到。

### 2.1 Density 页面密度

| 方案指标 | 现状 | 位置 | v1 状态 | 缺口 / 下一步 |
|---|---|---|---|---|
| 页面灰度 G | 有 | `visual.page_metrics.ink_ratio` | extracted | 含图像暗像素污染 → 需区域遮罩分离 |
| 文本区墨迹率 | 无 | — | placeholder | 用 pdfminer 文本块 bbox 做遮罩 |
| 文字覆盖率 C_t | 无 | — | placeholder | 同上，分母改为统一 `A_usable` |
| 图覆盖率 C_f | 无 | — | placeholder | 用 `LTFigure`/`LTImage` bbox 面积 |
| 表覆盖率 C_tab | 无 | — | placeholder | 用 `LTLine`/`LTRect` 规则线聚类近似 |
| `A_usable` 定义 | 部分 | `perceive.text_area_mm()`（估版心）、`visual` 用页宽比例 | partial | 统一定义：去页边距/页眉页脚/页码/栏间距 |

### 2.2 Ratio 图文关系

| 方案指标 | 现状 | 位置 | v1 状态 | 缺口 / 下一步 |
|---|---|---|---|---|
| R_ft、R_vt | 无 | — | placeholder | 依赖 2.1 的三个覆盖率 |
| **浮动体→首次引用距离 d_float** | 无 | — | placeholder | 需 PDF 浮动体落点 + 源码 `\ref` 行号→页映射；工程量最大，放阶段 3 |

### 2.3 Balance 页面平衡

| 方案指标 | 现状 | 位置 | v1 状态 | 缺口 / 下一步 |
|---|---|---|---|---|
| 上/中/下三段密度 | 半 | `top_blank` / `bottom_blank` / `content_height`（非密度） | partial | 改三带密度，和为 1 |
| 左右密度 | 半 | `left_blank` / `right_blank`（是空白，不是密度比） | partial | 改左右密度比 |
| 视觉重心 y_c | 半 | `top_bottom_ratio`（粗代理，按墨迹不按元素） | partial | 元素面积加权重心（需元素 bbox） |
| 分栏平衡（双栏） | 无 | — | placeholder | 需栏检测；方案 6.4 要求按栏独立算 |
| 页间密度失衡 | 有 | `visual.find_defects.density_imbalance` | extracted | 已进 A（用 max/min 比，非 σ） |

### 2.4 Whitespace 留白

| 方案指标 | 现状 | 位置 | v1 状态 | 缺口 / 下一步 |
|---|---|---|---|---|
| 最大连续空白带 / 位置 | 有 | `visual.page_metrics.max_gap` / `max_gap_at` | extracted | 只有"最大一条"，无分类 |
| 五类留白（结构/边界/浮动体/异常/页末） | 无 | — | placeholder | 元素邻接规则（方案 7.2），阶段 3 核心 |
| 空白区域列表 regions | 无 | — | placeholder | 空白掩码连通域分解 |
| 空白门控（仅 anomalous 惩罚） | 无 | — | placeholder | 同上 |

### 2.5 Alignment 对齐

| 方案指标 | 现状 | 位置 | v1 状态 | 缺口 / 下一步 |
|---|---|---|---|---|
| 左右边界 | 有（单值） | `visual.left_blank` / `right_blank` | partial | 只给"最外侧"，无逐元素边界 |
| 边界方差 / 中心线方差 | 无 | — | placeholder | 需元素 bbox 序列（矢量层） |

### 2.6 Consistency 一致性

| 方案指标 | 现状 | 位置 | v1 状态 | 缺口 / 下一步 |
|---|---|---|---|---|
| 图表尺寸一致性 CV | 半 | `parse_source.graphics_width_expr`（原始表达式列表） | partial | 直接可算 CV，**成本最低、阶段 1 可先做** |
| caption 样式一致性 | 无 | — | placeholder | 需文本块字号/位置分析 |
| 字号 / 间距一致性 | 半 | `scan_hygiene` 检出 `size_switch`/`heading_size`/`list_spacing`（计数不是量） | partial | 由"检出"升级为"量" |
| 颜色使用一致性 | 半 | `source.has_heading_color`（布尔） | partial | 需颜色提取 |

### 2.7 Page Rhythm 页面节奏

| 方案指标 | 现状 | 位置 | v1 状态 | 缺口 / 下一步 |
|---|---|---|---|---|
| 相邻页密度差 ΔD、σ_D | 无 | — | placeholder | 由逐页 density 派生，阶段 2 自动获得 |
| 密度失衡缺陷 | 有 | `visual.find_defects` | extracted | 已进 A |

### 2.8 Readability 可读性

| 方案指标 | 现状 | 位置 | v1 状态 | 缺口 / 下一步 |
|---|---|---|---|---|
| 字号 font_pt | 有（全局） | `parse_source.font_pt` | extracted | 非页级 |
| 每行字符数 | 无 | — | placeholder | pdfminer 文本行宽度 + 字形数，可行 |
| 行距比 leading/字号 | 无 | — | placeholder | 需基线间距（文本行 y 序列） |
| 段落平均行数 | 无 | — | placeholder | 需段落切分 |

### 2.9 Micro-typography 微观排版

| 方案指标 | 现状 | 位置 | v1 状态 | 缺口 / 下一步 |
|---|---|---|---|---|
| overfull / underfull | 有（全局计数） | `perceive.parse_log` | partial | 未按页归属：日志 `[n]` 页码 → 页级映射 |
| vbox Overfull/Underfull | 有（全局计数） | `parse_log` | partial | 同上；这是孤行寡行的现存代理 |
| 连续连字 | 无 | — | unavailable | 宏包只缓解；需 badness 级信息，暂不做 |

### 2.10 Figure Quality 图件质量

| 方案指标 | 现状 | 位置 | v1 状态 | 缺口 / 下一步 |
|---|---|---|---|---|
| 有效 dpi / 缩放比 | 无 | — | placeholder | PDF 图 bbox 尺寸 vs 源码 `width` |
| 纵横比 | 无 | — | placeholder | 需图 bbox |

### 2.11 分层、统计与模型（方案第五、九、十、十一章）

| 方案要素 | 现状 | 位置 | v1 状态 | 缺口 / 下一步 |
|---|---|---|---|---|
| 页面角色 page role | 无 | — | placeholder | **阶段 1 第一优先**（规则 + 人工抽检） |
| 会议级 P10–P90 profile | 无 | — | placeholder | 阶段 2 |
| bootstrap CI / 可信度 | 无 | — | placeholder | 阶段 2 |
| role 分层聚合 | 无 | — | placeholder | 阶段 2（结构已在 `paper.by_role` 预留） |
| 相关性 / PCA 去冗余 | 无 | — | placeholder | 阶段 2 |
| 马氏距离异常检测 | 无 | — | placeholder | 阶段 4 |
| 带外损失 A_profile | 无 | — | placeholder | 阶段 4 |
| 权重校准 | 无 | — | placeholder | 阶段 7 |
| 局部 region 级异常 | 无 | — | placeholder | 阶段 3（现有只有整页级 6 类） |

### 2.12 数据与基础设施

| 要素 | 现状 | 位置 | 状态 | 缺口 |
|---|---|---|---|---|
| 论文数据集 | 608 篇 / 16 会议 | `datasets/conf-specs` | 可用 | 缺逐页指标缓存与 role 标注 |
| 来源溯源 | 归档 + 逐字回核 | `fetch_source.sh`、`validate.py` | 可用 | — |
| 矢量 / 文本块提取能力 | 工具就绪 | pdfminer.six 20260107 + pypdf 6.18.1（vendored，`~/.local/lib/texopt-tools`，经 `TEXOPT_TOOLS` 引入） | 可用 | 尚未接入 texopt 提取器 |
| 像素层渲染 | 有 | `visual.render_gray` / `render_pages`（pdftoppm） | 可用 | 50dpi 偏低；对齐/一致性类指标需 150–200dpi |
| 统一 schema | **阶段 0 新增** | `texopt/page_metrics.py` + `docs/page_metrics_v1.md` | 可用 | — |

## 3. 汇总

| 状态 | 数量（约） | 说明 |
|---|---|---|
| extracted | 7 | 都是"整页级像素量"或"全局缺陷计数" |
| partial | 12 | 有代理但口径不符（含图污染、单值代替方差、计数代替量） |
| placeholder | 20 | 方案的主力指标基本都在这里 |
| unavailable | 1 | 连续连字 |

**关键判断**：`visual.py` 的现有实现可以支撑"明显差"的粗判定（也是它进 A_defect 的依据），但**不足以支撑审美画像**——因为它一不区分文本/图/表，二不区分留白类别，三不分层、无统计分布、无多维异常。阶段 1-4 的工作量主要在矢量/文本块层，而不是继续加像素启发式。

## 4. 实测验证（阶段 0 跑通）

用真实论文 `examples/NeurlPS examples/main.pdf`（27 页）跑 `visual.analyze_pdf(dpi=50)` → `page_metrics.from_legacy_visual()`：

```
pages: 27   defects: 6   error: None
validate errors: []
roles_hist: {"unknown": 27}                     ← role 未标注，等阶段 1
aggregates: {"density.ink_ratio_page":
             {"median": 0.0944, "mean": 0.083204, "max": 0.1257,
              "p90": 0.11318, "n": 27}}
unknown_fields: 1390
coverage: density{partial:27} ratio{placeholder:27} balance{placeholder:27}
          whitespace{partial:27} alignment{placeholder:27}
          consistency{placeholder:27} readability{placeholder:27}
          microtype{placeholder:27} figure_quality{placeholder:27}
```

复现命令（产物可落在任意临时目录，不必提交）：

```bash
PYTHONPATH=~/.local/lib/texopt-tools python3 - <<'EOF'
import sys, os; sys.path.insert(0, ".")
from texopt import visual, page_metrics as PM
vis = visual.analyze_pdf("examples/NeurlPS examples/main.pdf", "_scratch/gray")
doc = PM.from_legacy_visual(vis)
PM.finalize(doc); print(PM.validate(doc), doc["paper"]["aggregates"])
PM.dump(doc, "_scratch/page_metrics.json")
EOF
```

说明：schema 校验通过；只有 3 类信息真正可用（`legacy`、`density.ink_ratio_page`、`whitespace.regions` 粗代理），其余全部落在 `placeholder` —— 与第 3 节的汇总一致。`unknown_fields=1390` 就是阶段 1-3 的开工清单。

## 5. 阶段 0 发现的问题与修复

跑回归套件时又挖出 4 个真问题，已一并修掉（均与阶段 0 的盘点/验证同源）。

### 5.1 工作副本命名三处不同步（真 bug，影响「模型在环」）

提交 `e35f304` 把工作副本从固定 `outdir/paper.tex` 改为**保留原文件名**，但漏改了三处：

| 位置 | 症状 | 修法 |
|---|---|---|
| `optimize.py` resume 探测 | 永远探测不到已有工作副本 → 每次 `--proposals` 都重跑确定性闭环、覆盖上一轮工作区 | 新增 `core.work_tex_path()`，统一由它给出路径 |
| `core.py` `_prepare_workdir` docstring | 文档说“建立 paper.tex 工作副本”，与代码不符 | 改为如实描述（保留原文件名，多文件工程的 `\input` 依赖文件名） |
| `tests/run_tests.py` `integration_mitl` | 硬编码 `outdir/paper.tex` → `FileNotFoundError`，**整个回归套件崩掉** | 改用 `opt.work_tex` |

已端到端验证：`--proposals --round 2` 现在能正确续跑（不再打印“未发现现有工作副本”）。

### 5.2 脏工作区污染 → 基线被误判「无法编译」

Windows 端会占用上一轮的 PDF/aux，导致调用方的 `shutil.rmtree(outdir, ignore_errors=True)` **静默失败**；旧 PDF 残留后新的编译无法覆写 → 基线 `per.ok=False` → 报 `FAILED`（而单独跑同一个靶子却正常）。

修法：`run()` 在非 resume 路径先调 `_clean_stale_artifacts()`，只删“<工作副本同名>的构建产物 + 固定报告文件”（不碰 `.tex`/`.bbl`/图片），删不掉的路径**如实写进 FAILED 原因**，不再静默。

### 5.3 测试遇到 FAILED 直接崩（KeyError 'l'）

`integration_case()` 在 `res["l"]` 上取值，而 `run()` 的 FAILED 分支返回 `{status, reason, first_error}`（无 `l`）→ `KeyError` 把整个套件带崩，反而掩掉了真正原因。改为先判 `status == "FAILED"` 并报干净 FAIL（带 reason），并对 FAILED 目录做**验证式清理**（`_clean_dir()`）。

### 5.4 像素量去重

`page_proxy()` 曾有一套独立 PGM 扫描实现，与 `page_metrics()` 重复且可能各自漂移。现改为薄适配层（字段改名），`visual_report()` 一次解析同产两者 —— 单一事实来源，顺带省掉一半 PGM 扫描。

### 5.5 回归结果

```
== 结果：102 通过 / 0 失败 / 5 跳过 ==
（5 项跳过：examples/ 靶稿缺失，非代码问题）
```

新增 7 条针对性回归：`fix/work-tex-path-keeps-name`、`fix/optimizer-work-tex-not-paper`、`fix/resume-detects-named-work-copy`、`fix/proxy-delegates-to-metrics`、`fix/stale-artifacts-cleaned`、`fix/stale-clean-keeps-sources`、`fix/stale-locked-reported`。

### 5.6 两个待你决定的问题（未动）

1. **`examples/` 靶稿丢失**：`demo.tex` / `issues.tex` / `aidtest.tex` / `propose_target.tex` / `fig_violation.tex` / `chaos.tex` / `nightmare.tex` 在当前工作区与 git 历史里都找不到（全盘搜索无果，且不在任何归档 zip 里），所以套件里 5 项只能 SKIP。建议：要么重建后**纳入 git**，要么把这几条改成内联靶稿（与单元测试同风格）。
2. **`_regress/` 既被 git 跟踪、又被测试跑完清空**：跑一次完整套件就会删掉仓库里的跟踪文件（本次已 `git checkout -- _regress` 还原）。建议加进 `.gitignore` 并 `git rm -r --cached _regress`，让 scratch 目录真的只是 scratch。

## 6. 阶段 0 结论与阶段 1 建议顺序

阶段 0 完成：盘点表 + schema（`page_metrics.v1`）+ 适配器 + 校验/聚合工具，全部可运行。

阶段 1 建议按"先便宜后昂贵"排：

1. **page role 标注器**（规则优先）——所有统计的前提，不做后面全白做。
2. ~~合并 `page_proxy` 与 `page_metrics`~~ —— **阶段 0 已完成**（见 5.4），阶段 1 无需再做。
3. **低成本的 partial → extracted**：`consistency.figure_width_cv`（源码已有表达式）、`microtype` 的按页归属（日志页码映射）、`balance` 三段密度、`readability` 行长（pdfminer）。
4. **文本块/矢量层提取器**（pdfminer 已就绪）：文本区遮罩、图/表面积、`A_usable` 精确定义、边界方差。
5. 全库 608 篇跑一遍提取 + 缓存 → 交给阶段 2 建 profile。

风险提示（写进阶段 1 验收）：50dpi 像素层做不了对齐/一致性类指标，这类指标必须走矢量层；若矢量层提取误差过大，按方案第十四章 R3 降权，而不是凑合。
