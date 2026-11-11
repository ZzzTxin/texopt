# texopt 项目地图（PROJECT_MAP）

> 目的：一眼看清 texopt 里**每个文件/目录装的是什么、起什么作用、被谁用**。
> 写于 2026-11-07，对应工作区现状（texopt 包 24 个 .py ≈ 1.26 万行，全仓库 ≈ 1.6 万个文件）。
> 读法：先看第 1 节分层，再看第 2 节核心代码（真正的"模型"），第 3 节以后都是**输入数据 / 标定产物 / 文档 / 一次性实验目录**。

---

## 1. 五层结构（先建立心智模型）

| 层 | 内容 | 是否"程序" | 是否可再生产 | 约略体量 |
|---|---|---|---|---|
| L1 可执行核心 | `optimize.py` + `texopt/*.py` | 是 | 否（源码） | 24 文件 / 1.26 万行 |
| L2 配置与预设 | `settings.json`、`templates/*.json`、`datasets/conf-specs/templates-v2/*.json` | 数据 | 部分（模板由脚本生成） | 34 个 json |
| L3 数据资产 | `datasets/conf-specs/`（规范+样本+页指标）、`paperfit-bench-originals/`（真实论文原件） | 数据 | 需要重新抓取/编译才能重建 | ~1.36 万文件 |
| L4 标定与体检 | `metrics/*.json`（标定结论）+ `tools/*.py`（生成这些结论的脚本） | 混合 | 是（脚本在，可复算） | 10 + 21 文件 |
| L5 文档与实验产物 | `docs/`、`workbench-*`、`_probe2`、`examples/` | 否 | 是（除 examples 是宝贵靶稿） | 69 + ~2400 + 44 |

一句话：**真正的"模型"只有 L1 的 24 个文件**；其余 99% 的文件是喂给它的语料、给它定标的问卷结果、证明它有效性的实验记录。

---

## 2. L1 可执行核心

### 2.0 入口

| 文件 | 行数 | 存什么 / 干什么 |
|---|---|---|
| `optimize.py` | 495 | CLI 入口。解析参数（`--template/--conference/--require/--target/--settings/--emit-request/--proposals/--list-actions/--visual/--full/--tune-geometry`）→ 组装 `Requirement` → 调 `core.Optimizer` → 打印状态/报告。**不含算法**，只做参数与输出编排。 |
| `texopt/__init__.py` | 12 | 包声明 + 版本号（0.2.0）+ 设计原则 docstring（感知→决策→执行→验证；规则/算法/模型/编译器分工）。 |

### 2.1 闭环主干（修改→编译→验收）

| 文件 | 行数 | 存什么 | 作用 | 依赖 |
|---|---|---|---|---|
| `core.py` | 1495 | `Optimizer` 类：工作目录准备、候选动作池 `_candidates`、单步执行 `_step`、gate 定向修复 `_gate_repair`、接受判据 `_accept`、主循环 `run`、模型在环执行 `apply_proposals`、请求包发射 `emit_request`、影子评估钩子 `_shadow_*`、收尾 `finalize`/`exit_status`、报告 `_write_report`、`verify()` | **决策中枢**。决定"这一轮试哪个动作、改完算不算数、什么时候停"。验收判据 = 字典序 `(|gate|, M1, M2)`，一切量都在整篇重编译后计算。 | perceive, actions, score, requirements, conference, advise, shadow, proposal, whitelist |
| `engine.py` | 391 | TeX 工具链探测、`compile_tex`（Popen+超时强杀进程树）、`pdf_pages`、`synctex_pages`（源码行→PDF 页）、`content_pages`（pdftotext 定位参考文献首页）、`extract_pdf_region`（从原 PDF 裁原图，保真嵌入） | **唯一碰外部程序的模块**：编译、数页、裁图、分析日志。所有"相信编译器"的部分都在这里。 | 无内部依赖（被 core/perceive/visual/eval* 依赖） |
| `perceive.py` | 903 | L1 源码解析（documentclass/字号/geometry/twocolumn/fleqn/浮动体/图宽/tabular 区间 + 各类卫生检查：标题字号、行距、页眉、multicols、超大图、并列子图、窄表）、L2 日志解析（overfull/underfull/vbox/浮动体警告/错误）、L3 PDF 页数交叉验证、`Perception` 数据类 | **感知层**。把"一篇论文当前长什么样、错在哪"变成一个结构化对象，后续打分全部基于它。 | engine, visual |
| `actions.py` | 1324 | 全部**源码级动作**：`set_margin`/`set_fontsize`/`normalize_fig_width`/`set_fig_width`/`sanitize_float_specs`/`set_float_spec`/`drop_fleqn`/`inject_quality_macros`/`normalize_dollar_math`/`remove_manual_pagebreak`/`remove_excessive_vspace`/`normalize_local_font_size`/`normalize_heading_size`/`reduce_list_spacing`/`add_hyphenation_points`/`balance_pages`/`fix_table_width`/`strip_aids`/`strip_warn`/`insert_toc`/`add_header`/`color_headings` 等 | **执行层**。铁律：只动排版面，正文文字/公式/引用/图内容一律不碰；全部幂等、可回滚。每个函数返回 `(新源码|None, 是否改动, 说明, ...)`。 | perceive（少量常量） |
| `whitelist.py` | 510 | `WHITELIST` 注册表：action 名 → 包装器 + 参数校验器（正则/类型/取值）+ level(L1/L2/L3)+ descriptions | **模型在环的唯一合法修改面**。LLM 提案里出现不在表里的动作 → 直接 BLOCKED。 | actions |
| `proposal.py` | 166 | `build_request`（打包当前状态+残余问题+可用动作+页面图 → `llm_request.json`）、`parse_proposals`（读 `proposals.json` 并规范化） | LLM ↔ texopt 的双向协议（出向请求包 / 入向提案解析）。 | whitelist |
| `advise.py` | 247 | 把闭环修不掉的残余问题转成结构化建议：`id/line/kind/severity(cosmetic|moderate|content)/issue/suggestion/edit_hint` | **建议层**。决定"哪些事程序别硬干，交给人/模型判断"。 | perceive, score |

### 2.2 量化与打分（"模型"的数学部分）

| 文件 | 行数 | 存什么 | 作用 |
|---|---|---|---|
| `score.py` | 695 | `gate_violations/gate_issues`（底层逻辑门）、`page_defect_score`（P，11+ 项加权缺陷计数）、`intervention_cost`（I）、`aesthetic_score`（A_soft，8 个软指标的非单调带外损失）、`content_deviation`（正文改动量）、`total_score`（字典序组装）、`semantic_diff/body_unchanged`（正文零改动的机器校验）、`visual_defects` | **打分主场**。gate + M1=ρ·P+I + M2=A_soft+λ·A_profile 全部定义在这里，配套的权重常量（`PAGE_DEFECT_WEIGHT`、`ρ`、`SOFT_*`）也在这里——**由 tools 标定后回填**。 |
| `page_score.py` | 246 | `page_rows`（把每个缺陷按 SyncTeX 归到具体页）、`summary`（mean/topk/peak 三种读法）、`report_md` | **只做归因**：回答"哪一页最差、差在哪"，不改任何判定口径（用户 2026-11-02 提出的诊断需求）。 |

### 2.3 要求 / 模板

| 文件 | 行数 | 存什么 | 作用 |
|---|---|---|---|
| `requirements.py` | 233 | `Requirement` 数据类（font_pt/page_limit/margin_mm/float_spec/fleqn/质量宏/超宽阈值/结构开关...）+ `list_templates` + 模板/自定义/CLI/settings 三层合并 | **要求规格层**。把"哪里投稿、有什么硬规矩"变成可执行参数。Page limit 只是其中一个可选字段。 |
| `conference.py` | 406 | `ConferenceProfile` + `load`/`apply_to`（读 `datasets/conf-specs/templates-v2/<id>.json`）、`reasonableness`（真实论文统计只做参考核对）、`deferred`（当前消费不了的字段登记） | **会议模板层**。官方硬约束 → gate；真实统计 → 只谈合理性，不进 L、不进 A。16 个会议同一套代码路径。 |

### 2.4 视觉 / 页面感知（审美量化的证据层）

| 文件 | 行数 | 存什么 | 作用 |
|---|---|---|---|
| `visual.py` | 483 | `render_pages/render_gray`（pdftoppm → PNG/PGM）、`page_proxy`、`page_metrics`（像素层：墨迹占比、最大空白带、上下均衡）、`pixel_role`、`find_defects`（stranded_block / near_empty）、`visual_report`、`analyze_pdf` | 给 LLM 一双眼睛 + 可复算的像素代理量。**明确边界：代理量默认不进 A 分**（除 score.py 已并入的那几项软指标）。 |
| `extract.py` | 986 | pdfminer 字形级几何 → 文本行、字号、字体重、图/表框；`measure_frame`（A_usable 版心，双栏去栏缝）、`anchor_floats`（题注锚定浮动区）、`page_metrics_from_items` | 阶段 1：**PDF → page_metrics.v1** 的主提取器。所有几何量量自 PDF 而非源码。 |
| `roles.py` | 173 | 页面角色规则器：title/section-head/body/math-heavy/figure-page/table-page/references/appendix/last-page/unknown + `role_flags` | 阶段 1：分层的前提。统计必须在"同角色"内比对，否则无意义。 |
| `whitespace.py` | 455 | 空白掩码连通域 → 五类留白（structural/float/trailing/boundary/anomalous）+ region 列表 | 阶段 3：**White Space ≠ Bad Space**。只有"超阈且无结构解释"才罚。 |
| `page_metrics.py` | 395 | `page_metrics.v1` schema：blank_page/blank_document、`validate`、`missing_fields`、`summarize_pages`、`finalize`、`from_legacy_visual`、`dump/load`、`coverage_report` | 阶段 0：统一落盘数据结构 + status 字段（extracted/partial/placeholder/unavailable），防止各阶段自造字段。 |

### 2.5 审美模型（model2 的后半段）

| 文件 | 行数 | 存什么 | 作用 |
|---|---|---|---|
| `profile.py` | 373 | `build_profile`（全库 → 分位 p10..p90）、`cluster_bootstrap_ci`（按论文聚类重采样）、`confidence_tier`（high/medium/low）、`spearman`、`pca`、`correlation_and_groups` | 阶段 2：把 608 篇/数千页汇总成"正常范围"档案 `aesthetic_profile.v1`。 |
| `aesthetic.py` | 790 | 手写分位/中位数/IQR、Ledoit-Wolf 收缩、Cholesky/Gauss-Jordan 求逆、chi² 分布、`Detector`（马氏距离 D²）、`build_block`、`pick_detector`、`evaluate_doc`（A_profile = 带外损失 + D² 项）、`select_dims` | 阶段 4：**常态偏离检测**。默认 λ=0 影子模式，只报告不参与验收。 |
| `shadow.py` | 334 | `evaluate_pdf`、`snapshot`（state.json 版本化快照）、`report_md`（aesthetic_shadow.md）、`gate`（审美改善不得让缺陷变差）、`load_gate/load_sensitivity`（剔除未过门槛的维度）、`lambda_eligible` | 阶段 4/6/14：**影子模式接入**。λ 恒为 0，物理上无法影响优化走向；`TEXOPT_NO_SHADOW=1` 可关。 |
| `weights.py` | 439 | `ablation_weights`（信噪比法定权）、`bootstrap_ci`、`fit_bradley_terry`（人类成对比较）、`accept_verdict`、`merge_human`、`apply_to_profile` | 阶段 7：权重标定三步走（等权 → 消融 → 人类偏好），产物落 `metrics/`。 |

### 2.6 评测协议（证明"模型有效"的部分）

| 文件 | 行数 | 存什么 | 作用 |
|---|---|---|---|
| `evalproto.py` | 882 | 12.1 负样本注入（指标层+渲染层）、12.2 假阳率（按 role 分折）、12.3 会议可分性（kNN + 置换检验）、12.4 稳定性（确定性/dpi/重编译）、12.5 与人类相关性（未采集时如实 None）、12.6 验收门槛 `gate_verdicts` | 阶段 5：内部自洽性协议。明确写清"检验的不是与人类审美一致"。 |
| `evalexternal.py` | 670 | E1 端到端退化（真编译，退化档数单调）、E2 双测量路径（矢量 pdfminer ↔ 像素 pdftoppm，Spearman 排序一致性）、E3 论文级报告、`degrade_source`/`sensitivity_sweep`/`paper_level_report` | 阶段 8：外部验证。产物在 `datasets/conf-specs/workbench-eval/`。 |

---

## 3. L2 配置与预设

| 路径 | 存什么 | 谁读 |
|---|---|---|
| `settings.json` | 运行默认值：`template=custom`、`max_iterations=40`、`margin_min_mm=20`、`margin_step_mm=2`、`allow_fontsize_step`、`enable_quality_macros`、`float_spec=tbp`、`aesthetic_shadow`、`shadow_profile` | `optimize.py`（CLI 参数可逐项覆盖） |
| `templates/*.json`（17 个 + README） | 期刊/会议**要求预设**：font_pt / page_limit / margin_mm / float_spec / fleqn / 质量宏 / 超宽阈值 / 压页下限...。用法 `--template <id>`。含 aaai/acl/acm-full/cvpr/eccv/emnlp/iccv/iclr/icml/ijcai/kdd/neurips/nsdi/osdi/siggraph/sosp/www | `requirements.list_templates` |
| `datasets/conf-specs/templates-v2/*.json`（16 个） | **会议模板 v2**：official hard_constraints（带逐字引文证据）+ recommended + density_targets/position_prior（实测统计）+ deferred 清单。用法 `--conference <id>` | `conference.load` |

> 两套模板的分工：`templates/` 是轻量要求包（人工手写、可直接跑）；`templates-v2/` 是带证据链的完整规范库（由 `datasets/conf-specs/tools/build_templates.py` 从 `analysis/template-inputs.json` 生成）。

---

## 4. 测试与靶稿

| 路径 | 存什么 | 作用 |
|---|---|---|
| `tests/run_tests.py` | 单元 + 集成 + 阶段 0-9 + 验收 + 配对表测试（`unit_tests`/`integration_case`/`integration_mitl`/`stage0..9_tests`/`acceptance_tests`） | 回归套件。`--full` 加 chaos/nightmare；只写 `_regress/`，跑完清理。 |
| `examples/*.tex` | 固定靶稿：`demo`（干净 6 页）、`issues`（4 类可修）、`chaos`（12 类混乱）、`nightmare`（27 类灾难）、`aidtest`（辅助内容+告示块+超宽图）、`fig_violation`（图形保真反例）、`propose_target`（Level-3 模型在环靶子）、`test0911`/`test0913`/`NeurlPS examples` | 只读靶子 + 预期出口状态表（见 `examples/README.md`）。 |
| `examples/gen_fixtures.py` | 纯 stdlib 生成器 | 靶稿丢了能一键重建（曾经整批丢失过一次）。 |
| `examples/*.aux|.log|.pdf|.synctex.gz` | 编译残留 | 可再生成，价值低。 |

---

## 5. L3 数据资产

### 5.1 `datasets/conf-specs/` —— 会议排版规范数据集（5698 文件）

| 子目录 | 文件数 | 存什么 | 谁用 |
|---|---|---|---|
| `conferences/<id>.json` | 16 | **规范层**：hard_constraints（official/template-implied/inferred，每条带 evidence.quote 逐字引文）/ recommended / history / statistics | 调研与模板生成 |
| `templates-v2/<id>.json` | 16 | 上面数据的**可执行投影**：hard_constraints → L 字段，统计 → reasonableness | `conference.py` |
| `texopt-templates/<id>.json` | 16 | 供 `--template` 直接用的要求包（安装进 `templates/`） | `requirements.py` |
| `years/<id>.history.json` | 16 | 逐年规范变化 + 过时风险提示 | 维护 |
| `samples/<id>.samples.list.json` + `.jsonl` + `_measurements/` | 640 | **实测层**：每篇论文一行（链接/元数据/PDF 几何测量结果）；单篇测量缓存可复算 | `extract.py`（同一套几何口径） |
| `metrics/index.json` + `metrics/pages/*.json` | 622 | **页指标缓存**：608 篇论文逐页 page_metrics.v1 + 索引（venue/year/pages/layout/roles） | `profile.build_profile`、`evalproto`、`weights` |
| `patterns/*.json` | 2 | 浮动体尺寸/位置/题注统计、公式/算法/参考文献/脚注密度统计 | 模板与合理性参考 |
| `sources/`（raw html/sty/pdf + fetch_log.jsonl） | 2112 | **溯源归档**：官方页面原文、模板 .sty、样本 PDF + sha256/抓取日志 | 引文逐字校验（"不许凭经验臆测"） |
| `schema/` | 4 | 受控字段表 KEY_VOCAB + JSON Schema + 骨架示例 | 校验 |
| `candidates/*.jsonl` | 13 | 候选论文池（未入选样本） | 调研中间产物 |
| `human/pairs.json` | 3 | 人类成对比较数据（Bradley-Terry 输入） | `weights.fit_bradley_terry` |
| `analysis/`、`summary/` | 2 + 8 | 调研异常、跨会议速查表、可抽象为 texopt 通用规则的清单（L/A/R 分层 + 证据指针） | 人读 |
| `tools/` | 29 | 数据集流水线：`fetch_source.sh`/`measure_pdf.py`/`validate.py`/`build_templates.py` 等 | 重建数据集 |
| `workbench-eval/` | 2079（≈83 MB） | 阶段 5/8 评测产物：`eval_gate.json`（维度过门槛结论，被 `shadow.py` 读取）、`eval_protocol.json`、`eval_report.md`、`e1/e4` 运行目录、`render/`（页图）、`profile_attr/` | shadow/evalproto 输出 |
| `workbench-soft/` | 117 | 阶段 16 A_soft 可辨识性/敏感性体检的缓存（逐篇逐页 loss） | `tools/soft_*.py` |

### 5.2 `paperfit-bench-originals/` —— 真实论文原件（7895 文件）

真实投稿论文的 LaTeX 工程（`paperfit-bench/`、`paperfit-originals/` + `metadata` + `raw`）。用途：语料编译（`tools/corpus_build.py` → `/mnt/d/texopt-corpus` 缓存），产出 rows.jsonl（缺陷计数 + 逐页软指标）。**只读，不要在里面跑优化。**

---

## 6. L4 标定产物：`metrics/*.json`（10 个）

这些是**人工作答 → 数学拟合 → 回填源码**的中间结论，每个都能被 `tools/` 里的脚本复算：

| 文件 | 存什么 |
|---|---|
| `rho_exchange_rate.json` | ρ（缺陷↔干预代价的边际替代率）：`rho_raw=0.3408` → `rho_applied=15.0` 的决策记录 |
| `rho_tradeoff_20261031.json` | ρ 第一轮 15 题二选一的作答与转折点估计 |
| `p_weight_tradeoff_round1/round2_20261102.json` | P 内部 7 项权重的两轮"无差异点 c\*"阶梯作答 |
| `p_weight_tradeoff_20261102.json` | 两轮合并成 b(c) 曲线后的 c\*（翻转区间中点）与 w=c\*/ρ |
| `pweight_applied_20261102.json` | 最终回填进 `score.py` 的 P 权重表（口径 A：7 项权重和与原表一致） |
| `severity_weights_applied.json` | 旧口径权重（人的严重度 BT ÷ 语料频率）——已被 pweight 取代，保留作 A/B 对照 |
| `soft_identifiability_20261102.json/.md` | A_soft 8 指标的 loss 取值范围（哪些是常量、哪些只在特定页型动） |
| `soft_sensitivity_20261102.json` | 版面被破坏时各指标的响应幅度 |

---

## 7. L4 标定工具：`tools/*.py`（21 个）

| 分组 | 文件 | 干什么 |
|---|---|---|
| 语料 | `corpus_build.py` / `corpus_analyze.py` | 编译 200 篇原件 → rows.jsonl（缺陷+页指标）；汇总分布 → corpus_stats.json |
| 问卷生成 | `make_severity_sheet.py` / `make_pair_sheet.py` / `make_detector_sheet.py` / `make_tradeoff_sheet.py` / `make_tradeoff_v2.py` / `make_tradeoff_check.py` / `make_pweight_sheet.py` | 生成 HTML 答题表（缺陷严重度、成对比较、ρ 转折点、P 权重阶梯、一致性复核题） |
| 结果合并 | `pweight_combine.py` / `calibrate_rho.py` | 把作答拟合成 c\*/ρ → 写入 `metrics/` |
| 回填 | `apply_severity_weights.py` | 把标定值写进 `score.py` 的常量表（带 diff/备份） |
| A/B 验证 | `pweight_ab_run.py` / `pweight_ab_compare.py` / `rho_ab_run.py` / `rho_ab_compare.py` | 同一靶稿在旧/新权重下各跑一遍闭环，对比 accepted/pages/L/M1/状态，检验重标定是否把行为带偏 |
| 体检 | `detector_check.py` / `soft_identifiability.py` / `soft_sensitivity.py` | 注入→感知→响应方向/幅度；指标可辨识性与敏感性 |
| 小工具 | `_ink_profile.py` / `_pweight_probe.py` | 看某页墨迹纵向落点；单文件快速 A/B 编译探针（不渲染图） |

---

## 8. L5 文档：`docs/`（69 文件）

| 路径 | 内容 |
|---|---|
| `docs/README.md` | 文档总索引 |
| `docs/scoring/README.md` | **打分模型**（gate + M1 + M2 的定义、为什么两条线不相加、为什么 gate 不折成分数） |
| `docs/aesthetic/README.md` | **审美量化**（怎么量、怎么打分、怎么标定、怎么验证、哪里还不靠谱） |
| `stage0_visual_inventory.md` | 阶段 0：现有视觉/量化能力盘点（含靶稿丢失事故记录） |
| `stage1_role_and_extraction.md` | 阶段 1：页面角色 + PDF 指标提取 |
| `stage2_profile.md` | 阶段 2：审美档案（分位/聚类 bootstrap/可信度分档） |
| `stage3_whitespace.md` | 阶段 3：留白五分类 |
| `stage4_aesthetic_profile.md` | 阶段 4：马氏距离 + 带外损失 |
| `stage5_eval_protocol.md` | 阶段 5：评测协议 12.1-12.6 |
| `stage6_shadow_integration.md` | 阶段 6：影子模式接入 |
| `stage7_weight_calibration.md` | 阶段 7：权重校准 |
| `stage8_eval_external.md` | 阶段 8：外部验证 |
| `stage9_detector_check_20261027.md` | 阶段 9：检测器体检 |
| `stage10_a_soft_smooth_form/stage10b_pair_sheet/stage11_severity_sheet` | 阶段 10-11：A_soft 平滑形式、成对表、严重度标定 |
| `stage12_gate_exit_two_lines_20261030.md` | 阶段 12：gate 退出 + 两条评分线分离 |
| `stage13_rho_tradeoff_20261031.md` | 阶段 13：ρ 等边际收益标定 |
| `stage14_pweight_unified_20261102.md` | 阶段 14：P 权重统一到"边距 mm"一把尺子 |
| `stage15_local_global_20261102.md` | 阶段 15：局部/全局聚合（topk vs mean） |
| `stage16_model2_metrics_20261102.md` | 阶段 16：model2 指标可辨识性/敏感性 |
| `page_metrics_v1.md` | page_metrics.v1 字段定义 |
| `model_v3_design_20261014.html`（+ template/single） | 方案 v3 图文稿 |
| `scoring_report_20261102.html/pdf`（+ template/single） | 打分模型图文报告 |
| `formula_doc_assets/*.svg` | 公式插图（eq_gate/eq_M1/eq_A/eq_keep…） |
| `make_formula_doc.py` | 生成上面的公式图 |
| `corpus_inventory_20261026.md` / `corpus_fields_plain_20261026.md` | 语料清点与字段白话说明 |
| `notes/frequency_weighting_idea_20261016.md` | 未采纳的想法备忘 |

---

## 9. L5 实验/工作台产物（**这些都是可再生的，不是资产**）

| 目录 | 是什么 | 建议 |
|---|---|---|
| `workbench-demo/`（43） | demo 靶稿的历史运行产物（run/run2/run3） | 可删 |
| `workbench-detector/`（63） | 检测器体检运行目录（含人工排序 json） | 保留 human_rank.json，其余可删 |
| `workbench-pairs/`（31） | 成对比较问卷与作答（round1/2） | 保留 result*.json |
| `workbench-severity/`（3） | 严重度 15 题作答 + 结果 | `metrics/severity_weights_applied.json` 的来源，可归档 |
| `workbench-tradeoff/`、`-tradeoff2/`、`-tradeoff-check/`（215+233+20） | ρ 第一轮/第二轮/一致性复核的问卷、build 目录、作答 | 保留 answers*/result，build 可删 |
| `workbench-pweight/`、`-pweight2/`（406+244） | P 权重阶梯两轮的问卷与 build | 同上 |
| `workbench-rho-ab/`、`-pweight-ab/`（403+403） | A/B 闭环运行完整产物（每靶稿每口径一份） | 可删（结论已在 metrics + docs） |
| `workbench-pweight_build.log` | 构建日志 | 可删 |
| `_probe2/`（13） | 单篇论文工程的手工探针（含 main.tex/PDF） | 可删 |
| `datasets/conf-specs/workbench-eval/render/`、各 `workbench-*` | 页图与中间 json | 大，可删 |

---

## 10. 一次运行的调用链（谁在什么时候被用）

```
optimize.py
  └─ requirements.Requirement          ← settings.json / templates/*.json / --require
     (+ conference.load → apply_to)    ← templates-v2/*.json
  └─ core.Optimizer(tex, req, outdir)
       ├─ engine.compile_tex → perceive.perceive  (源码+日志+PDF)
       ├─ score.gate_violations / page_defect_score / aesthetic_score
       │     └─ score.visual_defects ← visual.analyze_pdf (PDF→PGM 像素代理)
       ├─ core._candidates → actions.<动作> → engine.compile_tex → 重评
       ├─ _accept：字典序 (|gate|, M1, M2) 严格改善才留下，否则回滚
       ├─ page_score.summary   （归因：哪页最差）
       ├─ advise.build_advisory（修不掉的 → 建议）
       ├─ shadow.evaluate_pdf  （λ=0 影子：A_profile 只报告）
       │     ← profile 档案 + metrics/…（datasets/conf-specs/metrics/）
       └─ finalize → workbench/{paper.tex, report.md, state.json, advisory.json,
                               llm_request.json, pages/page-*.png, visual.md}
       └─ apply_proposals ← proposals.json（LLM）→ whitelist 校验 → 同一套验收
```

数据侧（离线，不参与单次运行）：

```
paperfit-bench-originals ──corpus_build──> /mnt/d/texopt-corpus/rows.jsonl
                                              │
datasets/conf-specs/samples + metrics/pages ──┴─> profile.build_profile ──> aesthetic_profile.v1
                                                    └─ aesthetic.Detector ──> shadow / evalproto / evalexternal
tools/make_*_sheet ──> 人作答 ──> tools/combine ──> metrics/*.json ──> 回填 score.py 常量
```

---

## 11. 关于"太庞大"：哪些是模型，哪些不是

按 1.6 万文件算，**真正的算法代码只占 0.15%**：

- **必须保留**（模型本体）：`texopt/*.py`、`optimize.py`、`settings.json`、`templates/*.json`、`tests/run_tests.py`、`examples/*.tex` + `gen_fixtures.py`、`docs/scoring`、`docs/aesthetic`、`skills/latex-opt/SKILL.md`、`AGENTS.md`/`SOUL.md`、`README.md`、`metrics/*.json`（标定结论，很轻）。
- **数据资产**（大但必要，可外部存储）：`datasets/conf-specs/{conferences,samples,metrics,sources,templates-v2}`、`paperfit-bench-originals/`。重建成本高，建议移到仓库外的数据集目录并用环境变量指向（代码里已有 `TEXOPT_TOOLS` 之类的外部路径习惯）。
- **可再生产物**（可删/可归档）：全部 `workbench-*`、`datasets/conf-specs/workbench-eval/`、`workbench-soft/`、`examples/*.{aux,log,pdf,synctex.gz}`、`_probe2/`、`__pycache__`。
- **建议的单一入口文档**：本文件（`docs/PROJECT_MAP.md`）讲"有什么"，`README.md` 讲"怎么用"，`docs/scoring/README.md` 讲"怎么打分"，`docs/aesthetic/README.md` 讲"审美怎么量"。四份之外的历史 stage 文档按需查，不必通读。
