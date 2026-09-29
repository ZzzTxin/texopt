# 阶段 2 交付：审美档案（正常范围）+ 去冗余

> 对应设计方案第十五章「阶段 2」：建立 role × venue × year 的 profile（含 CI 与可信度）；
> 相关性 / PCA 去冗余。
> 代码：`texopt/profile.py`、`datasets/conf-specs/tools/build_profile.py`
> 产出：`datasets/conf-specs/metrics/profiles/{aesthetic_profile.json, redundancy.json, summary.md}`
> 测试：`tests/run_tests.py::stage2_tests()`（18 项）

## 1. 档案做了什么（一句话）

阶段 1 只知道"这篇论文每页的版面数字是多少"；阶段 2 把它变成
**"这类论文的这类页面，正常的版面长什么样"** —— 也就是给每个数字配上**正常区间**。

有了正常区间，程序才能说："这页的空白占 62%，而该会议正文页的正常范围是 12%~39%，
**这页偏空**"。这就是后面（阶段 4）自动判断"哪不正常"的唯一依据。

## 2. 档案结构

```json
{
  "schema": "aesthetic_profile.v1",
  "levels": {
    "venue_role": {           // 主档：会议 × 页面角色（统计与判定都用这一层）
      "cvpr|body": {
        "n_papers": 68, "n_pages": 812, "confidence": "high",
        "metrics": {
          "density.coverage_text": {
            "n": 812, "mean": 0.71,
            "p10": 0.51, "p25": 0.62, "p50": 0.72, "p75": 0.81, "p90": 0.87,
            "ci_p50": [0.70, 0.74], "ci_p90": [0.85, 0.89],
            "direction": "band"
          }, "...": {}
        }
      }
    },
    "role":  { "body": {...}, "references": {...} },   // 跨会议通用档（会议样本不足时回退）
    "venue": { "cvpr": {...} }                          // 会议内全角色（仅参考，不用于判定）
  },
  "built_from": { "papers": 608, "pages": 10538 }
}
```

每个指标带 `direction`：`band` = 有目标区间（过高过低都异常，如密度、留白），
`low` = 越低越好（如对齐方差、图表宽度变异）。这是阶段 4 做「带外损失」的输入。

## 3. 统计口径（必须说清，否则不可复现）

| 决策 | 做法 | 为什么 |
|---|---|---|
| 分位怎么算 | 按**页**取分位（线性插值），附 n | 判定是逐页做的 |
| 置信区间 | **按论文聚类的 bootstrap**：重采样的是**论文**，不是页 | 同一篇论文的页高度相关（同模板同字号），按页重采样会把 CI 假性收窄（这是层次数据的标准陷阱） |
| 重采样次数 | 300 次，固定随机种子（可复现） | — |
| 可信度分档 | 论文数 ≥36 high / 16–35 medium / ≤15 low | 与模板库的样本量分档一致；**low 档不参与异常判定** |
| 单栏/双栏 | **不合档**，只作为 doc 字段保留 | 栏数已在 venue 层体现（16 个会议固定栏数）；跨栏混档会污染分布 |

## 4. 去冗余（`redundancy.json`）

1. **Spearman 秩相关矩阵**（30 个指标两两），不假设线性、对离群稳健。
2. **|ρ| ≥ 0.8 的指标用并查集聚类**：同一组的指标在描述同一现象，阶段 4 只保留一个
   代表（否则同一现象会被扣多次分）。
3. **PCA**（对标准化后的指标；纯 Python Jacobi 特征分解，无 numpy 依赖）给出
   累积解释方差与主载荷，回答"到底几个维度才够描述版面"。

实测结论见第 6 节。

## 5. 用分布做的 3 项校准（阶段 1 遗留清单的落地）

### 5.1 角色阈值改为由分布定

| 角色 | 旧阈值（拍脑袋） | 新阈值（来自 608 篇实测） | 依据 |
|---|---|---|---|
| `figure-page` | 浮动覆盖 ≥ 0.50 且正文 < 0.25 | **浮动 ≥ 0.36 且正文 < 0.30** | 浮动覆盖 P95 = 0.364；正文覆盖 P25 = 0.515 |
| `table-page` | 表格覆盖 ≥ 0.40 | **表格覆盖 ≥ 0.16** | 表格覆盖 P99 = 0.164 |
| `math-heavy` | 数学字形 ≥ 0.35 | 不变 | 无分布证据，暂留 |

### 5.2 角色优先级调整：整页图/表提到参考文献、附录之前

**问题**：旧优先级里 references/appendix 压过一切，而预印本的附录常常整页是图
→ 全库只判出 **3 页** `figure-page`（都被附录吞了）。

**改法**：`title > figure-page > table-page > references > appendix > math-heavy
> section-head > last-page > body`，同时把结构信息挪到 `role_flags`：
`in-references` / `in-appendix` / `section-start` / `float-dominated` / `last-page`。

**理由**：角色存在的意义是让"同类可比"。整页图页的密度、重心与文字页完全不可比；
而"这页属于参考文献区"这个信息不丢，它落在 flags 上（状态照样继续传递）。

### 5.3 对齐指标按行类型拆分

**问题**：旧口径把悬挂缩进的参考文献、居中题注、公式行混在一起算行首方差，
中位 **14.8pt**（无意义，跨栏混算时甚至 130pt）。

**改法**：
* `left_var` / `right_var`：只用**满行**（右沿贴齐栏右沿、≥8 字符）→ 量"两端对齐的质量"；
* `center_var`：只用**短行**（未贴右沿、≥3 字符）相对栏中心的偏移 → 量"该居中的元素居中了没"；
* 新增 `n_full_lines` / `n_short_lines` 便于审计。

## 6. 实测（608 篇 / 10538 页）

> 本节由 `tools/build_profile.py` 自动回填（`--doc`，可用 `--no-doc` 关闭）。**不要手改本节**。

### 6.1 语料与角色分布（校准后）

- 语料：**608 篇 / 10538 页**，全部提取成功（ok=608 / failed=0）；双栏 **525** 篇 / 单栏 **83** 篇
- 页面角色分布（全部页面；右两列为阶段 1 校准前的对照）：

| 页面角色 | 页数 | 占比 | 阶段 1（校准前） | 变化 |
|---|---|---|---|---|
| body | 3350 | 31.8% | 3423 | -73 |
| appendix | 2677 | 25.4% | 2875 | -198 |
| references | 2569 | 24.4% | 2639 | -70 |
| section-head | 970 | 9.2% | 976 | -6 |
| title | 608 | 5.8% | 604 | +4 |
| figure-page | 256 | 2.4% | 3 | +253 |
| table-page | 106 | 1.0% | 16 | +90 |
| last-page | 2 | 0.0% | 2 | +0 |

关键变化：整页图 `figure-page` **3 → 256** 页、整页表 `table-page` **16 → 106** 页。原因见 5.2：旧优先级把 references/appendix 压在最前，预印本附录里的整页浮动图/表被全部吞掉；新优先级把 figure-page/table-page 提到它们之前，结构信息改由 `role_flags` 携带。

### 6.2 各会议 × 页面角色：样本量与可信度

档案主档共 **107** 个 `venue|role` 档（`role` 回退层 8 组、`venue` 参考层 16 组）。可信度：论文数 ≥36 high / 16–35 medium / ≤15 low；**low 档不参与异常判定**（阶段 4 回退到 `role` 层）。

| 档 | 篇 | 页 | 可信度 |
|---|---|---|---|
| emnlp|references | 45 | 449 | high |
| eccv|body | 36 | 411 | high |
| acl|references | 41 | 358 | high |
| nsdi|body | 44 | 332 | high |
| acl|body | 60 | 318 | high |
| emnlp|body | 64 | 312 | high |
| icml|body | 61 | 297 | high |
| iccv|body | 66 | 287 | high |
| cvpr|body | 66 | 286 | high |
| ijcai|body | 64 | 250 | high |
| neurips|body | 37 | 243 | high |
| aaai|body | 36 | 180 | high |
| iccv|references | 57 | 165 | high |
| nsdi|section-head | 45 | 140 | high |
| cvpr|references | 52 | 136 | high |
| iccv|section-head | 64 | 134 | high |
| ijcai|references | 62 | 127 | high |
| cvpr|section-head | 56 | 123 | high |
| ijcai|section-head | 55 | 102 | high |
| emnlp|section-head | 48 | 83 | high |
| acl|section-head | 42 | 72 | high |
| cvpr|title | 68 | 68 | high |
| iccv|title | 68 | 68 | high |
| acl|title | 67 | 67 | high |
| emnlp|title | 66 | 66 | high |
| ijcai|title | 66 | 66 | high |
| icml|section-head | 42 | 64 | high |
| icml|title | 62 | 62 | high |
| nsdi|title | 45 | 45 | high |
| neurips|title | 37 | 37 | high |
| aaai|title | 36 | 36 | high |
| eccv|title | 36 | 36 | high |
| icml|appendix | 35 | 681 | medium |
| neurips|appendix | 22 | 537 | medium |
| acl|appendix | 29 | 490 | medium |
| neurips|references | 26 | 416 | medium |
| icml|references | 35 | 393 | medium |
| emnlp|appendix | 26 | 360 | medium |
| osdi|body | 24 | 215 | medium |
| nsdi|appendix | 21 | 205 | medium |
| nsdi|references | 34 | 155 | medium |
| eccv|references | 32 | 119 | medium |
| osdi|section-head | 24 | 106 | medium |
| osdi|references | 22 | 105 | medium |
| neurips|figure-page | 22 | 68 | medium |
| aaai|references | 33 | 61 | medium |
| icml|figure-page | 20 | 60 | medium |
| acl|figure-page | 20 | 39 | medium |
| neurips|section-head | 22 | 33 | medium |
| eccv|section-head | 22 | 28 | medium |
| osdi|title | 24 | 24 | medium |
| cvpr|table-page | 16 | 19 | medium |
| cvpr|appendix | 15 | 86 | low |
| sosp|body | 7 | 82 | low |
| iclr|appendix | 5 | 79 | low |
| iccv|appendix | 11 | 70 | low |
| emnlp|figure-page | 14 | 53 | low |
| iclr|body | 6 | 44 | low |
| siggraph|body | 7 | 35 | low |
| eccv|appendix | 4 | 33 | low |
| www|appendix | 3 | 32 | low |
| www|body | 7 | 30 | low |
| sosp|references | 7 | 29 | low |
| kdd|body | 6 | 28 | low |
| sosp|section-head | 7 | 25 | low |
| aaai|section-head | 12 | 22 | low |
| sosp|appendix | 1 | 21 | low |
| kdd|appendix | 2 | 19 | low |
| www|section-head | 7 | 19 | low |
| ijcai|appendix | 3 | 17 | low |
| kdd|references | 4 | 17 | low |
| siggraph|appendix | 3 | 17 | low |
| iccv|table-page | 13 | 16 | low |
| iclr|references | 3 | 16 | low |
| www|references | 4 | 16 | low |
| aaai|appendix | 3 | 15 | low |
| osdi|appendix | 2 | 15 | low |
| ijcai|table-page | 12 | 14 | low |
| nsdi|table-page | 11 | 13 | low |
| emnlp|table-page | 6 | 11 | low |
| kdd|section-head | 5 | 10 | low |
| siggraph|section-head | 4 | 9 | low |
| cvpr|figure-page | 8 | 8 | low |
| aaai|table-page | 7 | 7 | low |
| acl|table-page | 6 | 7 | low |
| eccv|table-page | 6 | 7 | low |
| iccv|figure-page | 7 | 7 | low |
| siggraph|references | 4 | 7 | low |
| siggraph|title | 7 | 7 | low |
| sosp|title | 7 | 7 | low |
| www|title | 7 | 7 | low |
| iclr|title | 6 | 6 | low |
| kdd|title | 6 | 6 | low |
| neurips|table-page | 5 | 6 | low |
| siggraph|figure-page | 4 | 6 | low |
| iclr|figure-page | 3 | 5 | low |
| nsdi|figure-page | 5 | 5 | low |
| icml|table-page | 2 | 2 | low |
| osdi|figure-page | 2 | 2 | low |
| osdi|table-page | 2 | 2 | low |
| cvpr|last-page | 1 | 1 | low |
| eccv|figure-page | 1 | 1 | low |
| iclr|table-page | 1 | 1 | low |
| ijcai|figure-page | 1 | 1 | low |
| osdi|last-page | 1 | 1 | low |
| sosp|table-page | 1 | 1 | low |
| www|figure-page | 1 | 1 | low |

档的可信度分布：high 32 档，medium 20 档，low 55 档。

### 6.3 去冗余（|ρ| ≥ 0.8）

- 23 项指标中，有 **2** 组落在同一相关簇（并查集），阶段 4 每组只保留一个代表：
  - balance.d_bot / balance.d_top / balance.visual_centroid_y
  - density.coverage_figure / ratio.fig_text / ratio.figtab_text

相关性最强的前几对（完整表见 `profiles/redundancy.json` 与 `profiles/summary.md`）：

| 指标对 | Spearman ρ |
|---|---|
| density.coverage_figure|ratio.fig_text | 0.997 |
| ratio.fig_text|ratio.figtab_text | 0.908 |
| density.coverage_figure|ratio.figtab_text | 0.905 |
| balance.d_top|balance.visual_centroid_y | 0.899 |
| balance.d_bot|balance.visual_centroid_y | -0.857 |
| density.coverage_text|whitespace.total_ratio | -0.786 |

PCA（仅用 **774** 页（23 项指标全部非空的完整样本）；标准化后纯 Python Jacobi 特征分解）：**14 个主成分可达 90% 累积解释方差**。前 3 个主成分：

- PC1：解释 16.4%（累积 16.4%）｜主载荷：ratio.figtab_text(+0.392)，ratio.fig_text(+0.390)，density.coverage_figure(+0.370)，balance.visual_centroid_y(+0.369)
- PC2：解释 11.7%（累积 28.1%）｜主载荷：density.coverage_text(+0.382)，balance.visual_centroid_y(+0.353)，balance.d_bot(-0.347)，balance.left_right(-0.347)
- PC3：解释 8.9%（累积 37.0%）｜主载荷：whitespace.total_ratio(-0.392)，alignment.center_var(-0.391)，alignment.left_var(-0.331)，density.coverage_figure(+0.240)

读法：PC1 几乎完全是「浮动体占比 ↔ 图/文比」这一个轴；PC2/PC3 主要是「版面重心上下偏移」与「文本密度/留白」。即 20 多项几何指标背后只有少数几个独立维度，这也是去冗余能大幅压缩判定输入的依据。

### 6.4 代表档的正常区间（抽检）

每行给出 `[p25, p75]` 作为该档的正常区间，并附 p50 及其按论文聚类的 bootstrap CI；`band` 表示两侧都算异常，`low` 表示越低越好。

| 档 | 指标 | 正常区间 | p50 | CI(p50) | direction |
|---|---|---|---|---|---|
| cvpr|body | density.coverage_text | [0.623, 0.842] | 0.753 | [0.72, 0.777] | band |
| cvpr|body | whitespace.total_ratio | [0.074, 0.231] | 0.157 | [0.143, 0.179] | band |
| cvpr|body | readability.chars_per_line_mean | [37, 46.4] | 43.25 | [41.7, 44.2] | band |
| cvpr|body | readability.leading_ratio | [1.196, 1.196] | 1.196 | [1.196, 1.196] | band |
| cvpr|body | alignment.left_var | [2.277, 19.945] | 10.229 | [5.645, 13.146] | low |
| cvpr|body | balance.left_right | [0.493, 0.558] | 0.515 | [0.509, 0.52] | band |
| acl|body | density.coverage_text | [0.704, 0.883] | 0.814 | [0.796, 0.828] | band |
| acl|body | whitespace.total_ratio | [0.076, 0.187] | 0.129 | [0.116, 0.138] | band |
| acl|body | readability.chars_per_line_mean | [35.6, 40.4] | 39.1 | [38.6, 39.55] | band |
| acl|body | readability.leading_ratio | [1.232, 1.232] | 1.232 | [1.232, 1.232] | band |
| acl|body | alignment.left_var | [1.115, 7.536] | 2.417 | [2.09, 2.899] | low |
| acl|body | balance.left_right | [0.493, 0.533] | 0.509 | [0.504, 0.512] | band |
| cvpr|references | density.coverage_text | [0.688, 0.854] | 0.837 | [0.83, 0.843] | band |
| cvpr|references | whitespace.total_ratio | [0.146, 0.312] | 0.163 | [0.157, 0.17] | band |
| cvpr|references | readability.chars_per_line_mean | [40.2, 42.325] | 41.4 | [40.9, 41.8] | band |
| cvpr|references | readability.leading_ratio | [1.096, 1.096] | 1.096 | [1.096, 1.096] | band |
| cvpr|references | alignment.left_var | [18.751, 36.135] | 28.791 | [23.428, 31.94] | low |
| cvpr|references | balance.left_right | [0.495, 0.618] | 0.502 | [0.5, 0.505] | band |
| acl|appendix | density.coverage_text | [0.43, 0.819] | 0.687 | [0.636, 0.735] | band |
| acl|appendix | whitespace.total_ratio | [0.148, 0.497] | 0.238 | [0.209, 0.269] | band |
| acl|appendix | readability.chars_per_line_mean | [29.225, 40.2] | 38.4 | [37.6, 38.95] | band |
| acl|appendix | readability.leading_ratio | [1.079, 1.232] | 1.232 | [1.231, 1.232] | band |
| acl|appendix | alignment.left_var | [1.275, 6.053] | 3.128 | [2.478, 3.959] | low |
| acl|appendix | balance.left_right | [0.494, 0.591] | 0.519 | [0.51, 0.529] | band |
| cvpr|figure-page | density.coverage_text | [0.124, 0.265] | 0.164 | [0.091, 0.27] | band |
| cvpr|figure-page | whitespace.total_ratio | [0.348, 0.433] | 0.381 | [0.315, 0.437] | band |
| cvpr|figure-page | readability.chars_per_line_mean | [47.975, 85.4] | 72.85 | [44.9, 87.5] | band |
| cvpr|figure-page | readability.leading_ratio | [1.096, 1.196] | 1.171 | [1.096, 1.196] | band |
| cvpr|figure-page | alignment.left_var | [0, 0.751] | 0.032 | — | low |
| cvpr|figure-page | balance.left_right | [0.786, 0.902] | 0.849 | [0.778, 0.916] | band |
| eccv|body | density.coverage_text | [0.665, 0.848] | 0.775 | [0.746, 0.802] | band |
| eccv|body | whitespace.total_ratio | [0.101, 0.221] | 0.155 | [0.14, 0.169] | band |
| eccv|body | readability.chars_per_line_mean | [52.15, 62.9] | 60.1 | [58.8, 61.1] | band |
| eccv|body | readability.leading_ratio | [1.196, 1.196] | 1.196 | [1.196, 1.196] | band |
| eccv|body | alignment.left_var | [0.005, 6.91] | 3.85 | [3.378, 4.295] | low |
| eccv|body | balance.left_right | [0.509, 0.523] | 0.515 | [0.514, 0.516] | band |

## 7. 已知局限

| # | 局限 | 影响 | 计划 |
|---|---|---|---|
| P1 | 会议 × 角色 的细档样本量差异大（如 KDD n=6 的 `body`） | 低可信度档的区间不稳 | 已按可信度分档标注；阶段 4 对 low 档回退到 `role` 层 |
| P2 | 未按届次（year）分层 | 同一会议不同年份的风格漂移被平均掉 | 样本够了以后加 `venue|year|role` 档（当前按 venue 合并以免档太碎） |
| P3 | `math-heavy` 阈值仍无分布依据 | 可能偏松/偏紧 | 阶段 4 用数学字形占比的实际分布定 |
| P4 | 档案不含"内容语义"（如公式/表格的数量） | 只是版面几何档 | 属方案范围之外，由缺陷层与 LLM 判断覆盖 |

## 8. 复现命令

```bash
cd datasets/conf-specs
python3 tools/extract_metrics.py              # ① 全库提取（可续跑）
python3 tools/build_profile.py                # ② 建档案 + 去冗余 + 摘要 + 回填本文档 §6
python3 tools/build_profile.py --no-ci         # 跳过 bootstrap（快，无 CI）
python3 tools/build_profile.py --no-doc        # 只重建档案，不改本文档
cd ../.. && python3 tests/run_tests.py         # 含 18 项阶段 2 回归
```
