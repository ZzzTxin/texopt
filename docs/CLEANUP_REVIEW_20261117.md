# texopt 冗余清理判断（2026-11-17）

> 后续执行：2026-11-19 已按首轮名单清理 1,740 个文件、69,772,793 字节。本文保留评估时的历史语境；实际结果与验证见 [清理记录](CLEANUP_RESULT_20261119.md)。

本轮只做判断与清单，没有删除、移动原有文件，没有修改优化源码、权重或论文。未收到清理范围的进一步偏好时，按“保留优化器开发、测试与研究复现能力”评估。

结论：先清历史评测中的重复工作副本、重复展示版本和少量可重算缓存。可列入首轮清理的共有 **1,740 个文件、69,772,793 字节（69.77 MB，66.54 MiB）**。大体积语料需要另行归档或明确放弃某项复现用途，不能把它们统一称为无用文件。

## 1. 首轮建议清理范围

以下空间按十进制 MB 计算。具体文件、保留副本与 SHA-256 见 [recommended_manifest.json](../workbench/redundancy_audit/recommended_manifest.json)。这份清单是审阅结果，不是删除授权或已删除记录。

| 路径/范围 | 文件数 | 大小 | 判断与条件 |
|---|---:|---:|---|
| `datasets/conf-specs/workbench-eval/e1/` 内已核对的输入副本 | 729 | 30.628 MB | 与保留的 `examples/` 等输入内容完全相同；只清名单中条目，保留报告和不同内容的实验稿 |
| `datasets/conf-specs/workbench-eval/e4/` 内已核对的输入副本 | 733 | 30.772 MB | 同上；有些目录还套了一层 `e4/e4/`，进一步增加重复 |
| `datasets/conf-specs/workbench-eval/profile_attr/` 内已核对的输入副本 | 156 | 6.121 MB | 与保留输入 SHA-256 一致，删除不影响当前入口、固定靶稿与最终结论 |
| `workbench/patent_draft/review_latest/image1.png`、`image2.png`、`image3.png` | 3 | 0.355 MB | 与同级上方保留的 `spec_figure_1/2/3.png` 逐张哈希一致；DOCX 回读校验副本 |
| `datasets/conf-specs/workbench-soft/cache/*.json` | 117 | 0.427 MB | 像素可辨识性分析的中间缓存；最终结果在根 `metrics/`；删除后体检会重新渲染，耗时增加 |
| `docs/model_v3_design_20261014_single.html` | 1 | 0.928 MB | 与普通 `.html` 文本和结构一致，只有图片 src 为内嵌数据；保留普通版、模板与 SVG |
| `docs/scoring_report_20261102_single.html` | 1 | 0.542 MB | 同上；保留普通版、模板、SVG 和现有 PDF |
| 合计 | **1,740** | **69.773 MB** | 不包含原始语料、最终指标文件、人工作答或专利正文 |

前三行共 **1,618 个文件、67,521,159 字节**。一张原图在工作区中被复制了约 60 份，例如 `vernier_tuning_combined.pdf`、`microgear_laser_results.pdf` 和 supplementary.pdf；这里的重复经过内容哈希核对，不是按文件名猜测。

清除旧实验输入后，旧实验目录不再是一套可直接重新编译的独立工程；重跑时需由脚本从固定输入重新生成。现存 `report.md`、`state.json`、不同内容的实验源稿、人工作答及最终指标仍保留。后续若希望每个历史实验都能原地重编译，应把整个实验目录归档，而不是执行这部分清理。

117 个 soft 缓存和 2 个单文件 HTML **已经被 Git 跟踪**，实际清理时会产生 119 项受控删除；其余 1,621 项为未跟踪的重复副本。执行时还应同步更新文档中对删除文件的链接。`docs/make_formula_doc.py` 当前还会重新生成 `_single.html`，若希望永久只留普通版，需要同时调整生成策略。

## 2. 可从日常工作区移出的旧工具

这类文件节省不了多少空间，整理的价值主要在减少入口混淆。建议先移入历史工具归档，再决定是否永久删除；此处没有执行移动。

| 文件 | 当前用途与判断 |
|---|---|
| `tools/_pweight_probe.py`（2,067 B） | 一次性 P 权重构造编译探针，未发现其他 Python 代码导入；可退出活跃工具区 |
| `tools/_ink_profile.py`（1,519 B） | 特定页墨迹剖面调试器，未发现其他 Python 代码导入；历史文档仍引用，可归档 |
| `tools/make_detector_sheet.py`（10,371 B） | 早期 20 页人工排序表；现已停止新增人工问卷，当前没有代码导入它；保留历史复现价值，可归档 |
| `tools/make_tradeoff_check.py`（9,532 B） | 旧版 ρ 人工一致性复核题；日常优化不调用，可归档 |
| `tools/make_tradeoff_v2.py`（16,547 B） | 旧版第二轮无差异点问卷；被 make_tradeoff_check 导入，需成组归档和改相对入口 |
| `tools/rho_ab_compare.py` + `rho_ab_run.py` | 历史 ρ 行为对照成套入口，可作为归档实验组保留 |
| `tools/pweight_ab_compare.py` + `pweight_ab_run.py` | 历史 P 权重 A/B 成套入口，可作为归档实验组保留 |

不能因为“停止发问卷”就删掉所有 `make_*`：

- `make_pair_sheet.py` 和 `make_severity_sheet.py` 仍被测试导入。
- `make_tradeoff_sheet.py` 被 `make_pweight_sheet.py`、`make_tradeoff_v2.py`、`make_tradeoff_check.py` 共用编译/定位/渲染/HTML 能力。
- `apply_severity_weights.py`、`calibrate_rho.py`、`pweight_combine.py` 在测试和已落地参数核对中有用途。
- `soft_identifiability.py`、`soft_sensitivity.py`、`soft_v2_weights.py` 属最新指标工作流，应该保留。

根 `tools/` 的全部 22 个脚本合计只有 236,712 字节。清代码应以职责和维护成本为依据，不能用它代替大体积产物整理。

## 3. 大体积目录：建议外部归档，而不是当垃圾删除

| 范围 | 体积 | 日常优化是否直接读取 | 删除/移出后失去什么 |
|---|---:|---|---|
| `paperfit-bench-originals/paperfit-bench/raw/` | 2.694 GB / 200 包 | 不直接读取 | 扰动后的 benchmark 考题输入；与干净 arXiv 原稿不同 |
| `paperfit-bench-originals/paperfit-bench-originals/` | 3.299 GB | 不直接读取 | 200 篇干净 TeX 工程、原包，`tools/corpus_build.py` 的输入 |
| `paperfit-bench-originals/paperfit-originals/` | 112.03 MB | 不直接读取 | 10 篇代表工程、编译结果和部分不同的 bbl；不能整目录判为完全重复 |
| 上述整个 `paperfit-bench-originals/` | **6.106 GB** | 不直接读取 | 三类语料与 metadata；若整体迁移，要保留 manifests/metadata 并调整语料工具路径 |
| `datasets/conf-specs/sources/raw/pdfs/` | **2.753 GB / 611 PDF** | 当前影子模式评估用户论文时不依赖这批语料 PDF | PDF 测量、角色核对、图像体检和历史配对图的重建证据；部分测试也会抽用 |
| `datasets/conf-specs/sources/raw/` 除 pdfs 外 | **167.10 MB** | 主优化入口不读取 | 官方指南、模板和样本落地页 HTML/TXT 等来源证据；validate.py 要靠它核验引文 |

整套 PaperFit 语料和 pdfs 两项合计 **8.859 GB**，占工作区绝大部分。如果主要目标是释放数 GB，应把它们迁往另一个已确定的存储位置并登记路径，而不是删掉小工具。移动到同一磁盘的另一个目录只会让项目目录变小，不会释放该盘空间；独立磁盘归档才会释放原盘空间。

`source.eprint` 的 200 个下载原包合计 **1.571 GB**，已包含在上表的 3.299 GB 内，不能重复计算。它们可能与已解压工程形成可去重层，但本轮没有验证每个归档成员都完整解出，也没有逐个校验包内内容；因此不放入首轮删除名单。扰动考题的 `.tar.gz` 和干净原件的 `.eprint` 也不能按论文 ID 相同就互删。

10 篇代表工程的进一步核对：213 个文件、38,763,512 字节在 200 篇目录里存在相同内容；**4 份 `main.bbl` 不同**，还有编译 PDF/日志/压缩包等不同路径条目。没有任何一个代表工程通过“全部文件都在另一处相同保留”的检查。若后续去重，应先分离编译结果、差异 bbl 与原包，再按文件合并，不能直接删整个代表目录。详情见 [representatives.json](../workbench/redundancy_audit/representatives.json)。

## 4. 看起来像缓存，当前应保留

| 范围 | 大小 | 保留原因 |
|---|---:|---|
| `datasets/conf-specs/metrics/pages/` | 65.73 MB / 608 JSON | 测试 stage7/stage8、档案重建与评测均读取。删除后部分测试跳过或因目录不存在失败，不能算保留回归能力 |
| `datasets/conf-specs/samples/_measurements/` | 1.26 MB / 608 JSON | 模板统计重建的缓存输入；体积小，删除可能触发重新下载/测量 |
| `datasets/conf-specs/metrics/profiles/aesthetic_profile.json` | 1.61 MB | 默认在线影子档案，不是废弃模型 |
| `metrics/profiles/eval_gate.json`、`profile_sensitivity.json` | 数 KB | 控制剔除哪些档案维度、是否允许 λ>0；缺失会改变保护或可用性 |
| 根 `metrics/` | 约 46 KB | 权重来源、冻结先验、最新客观响应证据；测试和核对工具仍读 |
| `datasets/conf-specs/human/pairs.json` | 很小 | 历史真实标注；停止新增标注不等于删除旧证据 |
| `datasets/conf-specs/workbench-eval/pairs_sheet/` | 12.27 MB | 包含 answers.json、sheet.json 和与标注配对的页图；目前保留原始核对包 |
| `workbench/patent_draft/` 除 review_latest 外 | 约 1.21 MB | 权利要求、说明书、压缩前版本、生成脚本和源图；属于用户材料，不是优化器缓存 |

特别注意旧 `workbench-eval/eval_gate.json`、`eval_protocol.json`、`eval_report.md` 与当前 `metrics/profiles/` 同名文件**内容不同**。当前运行已使用 profiles 版本，但旧文件仍是阶段快照；可单独归档，不能声称它们是逐字重复后直接覆盖。

## 5. 源码和模板中没有理由直接删的部分

`optimize.py` 的静态包内依赖可达 19 个 texopt 模块；另外的 `evalproto.py`、`evalexternal.py`、`weights.py` 由测试与评测工具使用，`__init__.py` 是包入口。**texopt/ 的 23 个模块都保留。** 未被 optimize.py 直接导入并不等于无用。

根 `templates/` 与 `datasets/conf-specs/texopt-templates/` 有 16 对 JSON 完全相同，源副本合计只有 **4,669 字节**；它们分别是生成结果和安装位置。移除一套会影响 build/install 流程，收益很低。`templates-v2/` 则是带来源和统计的完整档案，服务 `--conference`，与轻量模板不等价。

`examples/*.tex`、gen_fixtures.py、真实论文的 sty/bbl/PDF/data 片段均保留；这些是固定测试输入及恢复工具。不能把所有 PDF 都当编译产物，也不能把所有 bbl 都当可以重建的缓存：某些真实工程依靠随附 bbl 编译。

## 6. 文档和本次/上次盘点文件的整理

- `docs/stage*.md` 建议整理进历史文档区，保留每阶段为何改公式、参数和验收规则的依据；移目录需要更新 README 与文档相互链接。
- `docs/PROJECT_MAP.md` 与 11-16 的逐文件索引有重叠。建议以后选一份作为主索引，另一份保留历史快照，避免继续维护三份相似地图。
- 11-16 阅读工作区约 **7.08 MB**，其中 `inventory.json` + `file_index.md` 两个索引约 **6.80 MB**。日常运行不需要它们；若不再需要逐文件审计，可只保留较小的理解报告/函数索引/行为探针与验证结果，再删重建型大清单。当前理解报告引用它们，实际删除前需更新相关链接，首轮清单暂未包含。
- 本轮也只保留紧凑的评估摘要和具体候选清单，没有保留另一套完整 13k 文件盘点，以免清理评估继续堆积同类大索引。审阅结束后本轮工作区也可归档。
- 没有发现项目侧现成 `__pycache__` 或可直接清理的实验 `.aux/.log/.pgm`；本轮主要收益来自重复输入副本，不能把不存在的缓存算入释放空间。

## 7. 实施顺序与验证边界

建议第一轮按 recommended_manifest 精确清理 **69.77 MB**，并同时更新指向被删除单文件 HTML 的文档链接；原始论文、固定样例、人工作答、专利正文、最终指标和源码均保留。

第二轮再整理历史工具与文档目录，成组调整导入/生成路径，完成相应回归。第三轮若仍需要数 GB 空间，明确归档存储位置，迁移大语料并修正其消费者路径。

本轮执行的是依赖检查、SHA-256/大小比对、HTML 结构比对与候选路径验证，没有运行清理，也没有重跑耗时的 TeX 集成测试。清单已验证：候选路径均在工作区内；每个保留副本均不在候选名单中；已有哈希/大小匹配；保护输入与人工作答未混入。执行前仍须重新确认文件和保留副本未发生变化。

机器可读证据：

- [首轮建议逐文件清单](../workbench/redundancy_audit/recommended_manifest.json)
- [依赖、体积与重复摘要](../workbench/redundancy_audit/assessment.json)
- [HTML 内容比对](../workbench/redundancy_audit/html_equivalence.json)
- [10 篇代表工程差异比对](../workbench/redundancy_audit/representatives.json)
