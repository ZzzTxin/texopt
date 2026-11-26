# texopt 逐文件功能索引（2026-11-16）

以当前工作区为快照。源码逻辑、配置结构、说明文档与资产用途分别核对；外部论文正文不冒充精读。
2026-11-19 已清理两个内嵌 HTML 副本和三张 DOCX 回读图，本索引保留其历史条目并改指向保留版本；详见 [清理结果](CLEANUP_RESULT_20261119.md)。
核心理解和已复现差异见 [理解报告](REPO_UNDERSTANDING_20261116.md)。
全库 13795 个文件的路径/大小清单在 `workbench/repo_understanding/file_index.md`；
机器可读信息在 `inventory.json`；76 个 Python 文件的函数/类与原行号见 `source_index.md`。

本索引逐项列出项目文件及原有工作区文件，共 377 项。

| 文件 | 行数/字节 | 内容与功能 |
|---|---:|---|
| [.gitignore](../.gitignore) | 77 行 | 版本控制排除规则：区分源码、原始语料、编译缓存与实验生成物。 |
| [AGENTS.md](../AGENTS.md) | 101 行 | AGENTS.md —— texopt 排版优化 Agent；正文结构见下方文档目录。 |
| [README.md](../README.md) | 465 行 | texopt —— 论文整体排版优化 Agent；正文结构见下方文档目录。 |
| [SOUL.md](../SOUL.md) | 13 行 | SOUL.md —— texopt；正文结构见下方文档目录。 |
| [optimize.py](../optimize.py) | 495 行 | 命令行入口：加载要求，分发优化、验证、提案、影子评估和裁图工具，打印结果。 |
| [settings.json](../settings.json) | 13 行 | 显式 --settings 加载的运行配置；CLI 并不自动加载仓库根同名文件。 |
| [datasets/conf-specs/.gitignore](../datasets/conf-specs/.gitignore) | 3 行 | 版本控制排除规则：区分源码、原始语料、编译缓存与实验生成物。 |
| [datasets/conf-specs/BRIEF_research.md](../datasets/conf-specs/BRIEF_research.md) | 126 行 | BRIEF_research.md —— 会议排版规范调研作业书（子代理用）；正文结构见下方文档目录。 |
| [datasets/conf-specs/README.md](../datasets/conf-specs/README.md) | 139 行 | 计算机顶会论文排版规范数据集（texopt dataset）；正文结构见下方文档目录。 |
| [datasets/conf-specs/SUBAGENT_TASK.md](../datasets/conf-specs/SUBAGENT_TASK.md) | 118 行 | SUBAGENT_TASK.md —— 子代理作业单（会议排版规范数据集）；正文结构见下方文档目录。 |
| [datasets/conf-specs/analysis/anomalies.md](../datasets/conf-specs/analysis/anomalies.md) | 489 行 | 数据异常与冲突清单（自动生成，勿手改）；正文结构见下方文档目录。 |
| [datasets/conf-specs/analysis/template-inputs.json](../datasets/conf-specs/analysis/template-inputs.json) | 14822 行 | analyze_templates.py 汇总的官方值、实测稳健统计、密度和冲突；build_templates.py 的输入。 |
| [datasets/conf-specs/candidates/aaai.jsonl](../datasets/conf-specs/candidates/aaai.jsonl) | 60 行 | 官方索引抓取的候选论文池（60 行），尚须经 add_samples.py 入库。 |
| [datasets/conf-specs/candidates/acl.jsonl](../datasets/conf-specs/candidates/acl.jsonl) | 60 行 | 官方索引抓取的候选论文池（60 行），尚须经 add_samples.py 入库。 |
| [datasets/conf-specs/candidates/cvpr.jsonl](../datasets/conf-specs/candidates/cvpr.jsonl) | 60 行 | 官方索引抓取的候选论文池（60 行），尚须经 add_samples.py 入库。 |
| [datasets/conf-specs/candidates/eccv.jsonl](../datasets/conf-specs/candidates/eccv.jsonl) | 60 行 | 官方索引抓取的候选论文池（60 行），尚须经 add_samples.py 入库。 |
| [datasets/conf-specs/candidates/emnlp.jsonl](../datasets/conf-specs/candidates/emnlp.jsonl) | 60 行 | 官方索引抓取的候选论文池（60 行），尚须经 add_samples.py 入库。 |
| [datasets/conf-specs/candidates/iccv.jsonl](../datasets/conf-specs/candidates/iccv.jsonl) | 60 行 | 官方索引抓取的候选论文池（60 行），尚须经 add_samples.py 入库。 |
| [datasets/conf-specs/candidates/icml.jsonl](../datasets/conf-specs/candidates/icml.jsonl) | 57 行 | 官方索引抓取的候选论文池（57 行），尚须经 add_samples.py 入库。 |
| [datasets/conf-specs/candidates/ijcai.jsonl](../datasets/conf-specs/candidates/ijcai.jsonl) | 60 行 | 官方索引抓取的候选论文池（60 行），尚须经 add_samples.py 入库。 |
| [datasets/conf-specs/candidates/naacl.jsonl](../datasets/conf-specs/candidates/naacl.jsonl) | 60 行 | 官方索引抓取的候选论文池（60 行），尚须经 add_samples.py 入库。 |
| [datasets/conf-specs/candidates/neurips.jsonl](../datasets/conf-specs/candidates/neurips.jsonl) | 30 行 | 官方索引抓取的候选论文池（30 行），尚须经 add_samples.py 入库。 |
| [datasets/conf-specs/candidates/nsdi.jsonl](../datasets/conf-specs/candidates/nsdi.jsonl) | 40 行 | 官方索引抓取的候选论文池（40 行），尚须经 add_samples.py 入库。 |
| [datasets/conf-specs/candidates/osdi.jsonl](../datasets/conf-specs/candidates/osdi.jsonl) | 20 行 | 官方索引抓取的候选论文池（20 行），尚须经 add_samples.py 入库。 |
| [datasets/conf-specs/candidates/wacv.jsonl](../datasets/conf-specs/candidates/wacv.jsonl) | 60 行 | 官方索引抓取的候选论文池（60 行），尚须经 add_samples.py 入库。 |
| [datasets/conf-specs/conferences/aaai.json](../datasets/conf-specs/conferences/aaai.json) | 2224 行 | AAAI-25 会议规范源数据；官方硬要求 21 项、推荐 4 项、溯源 43 条；供校验和模板生成。 |
| [datasets/conf-specs/conferences/acl.json](../datasets/conf-specs/conferences/acl.json) | 3464 行 | ACL 2025 会议规范源数据；官方硬要求 21 项、推荐 6 项、溯源 75 条；供校验和模板生成。 |
| [datasets/conf-specs/conferences/cvpr.json](../datasets/conf-specs/conferences/cvpr.json) | 3389 行 | CVPR 2025 会议规范源数据；官方硬要求 18 项、推荐 6 项、溯源 76 条；供校验和模板生成。 |
| [datasets/conf-specs/conferences/eccv.json](../datasets/conf-specs/conferences/eccv.json) | 1634 行 | ECCV 2026 会议规范源数据；官方硬要求 16 项、推荐 6 项、溯源 10 条；供校验和模板生成。 |
| [datasets/conf-specs/conferences/emnlp.json](../datasets/conf-specs/conferences/emnlp.json) | 3359 行 | EMNLP 2025 会议规范源数据；官方硬要求 19 项、推荐 6 项、溯源 73 条；供校验和模板生成。 |
| [datasets/conf-specs/conferences/iccv.json](../datasets/conf-specs/conferences/iccv.json) | 3381 行 | ICCV 2025 会议规范源数据；官方硬要求 18 项、推荐 5 项、溯源 76 条；供校验和模板生成。 |
| [datasets/conf-specs/conferences/iclr.json](../datasets/conf-specs/conferences/iclr.json) | 1158 行 | ICLR 2025 会议规范源数据；官方硬要求 18 项、推荐 2 项、溯源 21 条；供校验和模板生成。 |
| [datasets/conf-specs/conferences/icml.json](../datasets/conf-specs/conferences/icml.json) | 3130 行 | ICML 2025 会议规范源数据；官方硬要求 17 项、推荐 3 项、溯源 71 条；供校验和模板生成。 |
| [datasets/conf-specs/conferences/ijcai.json](../datasets/conf-specs/conferences/ijcai.json) | 3302 行 | IJCAI 2025 会议规范源数据；官方硬要求 18 项、推荐 7 项、溯源 73 条；供校验和模板生成。 |
| [datasets/conf-specs/conferences/kdd.json](../datasets/conf-specs/conferences/kdd.json) | 1068 行 | KDD 2025 会议规范源数据；官方硬要求 17 项、推荐 2 项、溯源 12 条；供校验和模板生成。 |
| [datasets/conf-specs/conferences/neurips.json](../datasets/conf-specs/conferences/neurips.json) | 2202 行 | NeurIPS 2025 会议规范源数据；官方硬要求 16 项、推荐 5 项、溯源 46 条；供校验和模板生成。 |
| [datasets/conf-specs/conferences/nsdi.json](../datasets/conf-specs/conferences/nsdi.json) | 2425 行 | NSDI '25 会议规范源数据；官方硬要求 17 项、推荐 1 项、溯源 51 条；供校验和模板生成。 |
| [datasets/conf-specs/conferences/osdi.json](../datasets/conf-specs/conferences/osdi.json) | 1725 行 | OSDI '25 会议规范源数据；官方硬要求 18 项、推荐 4 项、溯源 30 条；供校验和模板生成。 |
| [datasets/conf-specs/conferences/siggraph.json](../datasets/conf-specs/conferences/siggraph.json) | 1082 行 | SIGGRAPH 2025 会议规范源数据；官方硬要求 19 项、推荐 2 项、溯源 12 条；供校验和模板生成。 |
| [datasets/conf-specs/conferences/sosp.json](../datasets/conf-specs/conferences/sosp.json) | 984 行 | SOSP 2025 会议规范源数据；官方硬要求 14 项、推荐 1 项、溯源 11 条；供校验和模板生成。 |
| [datasets/conf-specs/conferences/www.json](../datasets/conf-specs/conferences/www.json) | 1076 行 | WWW 2026 会议规范源数据；官方硬要求 16 项、推荐 2 项、溯源 13 条；供校验和模板生成。 |
| [datasets/conf-specs/human/README.md](../datasets/conf-specs/human/README.md) | 69 行 | 人类成对比较数据（阶段 7 步骤三）；正文结构见下方文档目录。 |
| [datasets/conf-specs/human/pairs.example.json](../datasets/conf-specs/human/pairs.example.json) | 14 行 | 档案权重的历史成对比较数据。pairs.example.json 仅为示例；现有 pairs.json 为已采集记录，阶段 17 后不新增问卷。 |
| [datasets/conf-specs/human/pairs.json](../datasets/conf-specs/human/pairs.json) | 194 行 | 档案权重的历史成对比较数据。pairs.example.json 仅为示例；现有 pairs.json 为已采集记录，阶段 17 后不新增问卷。 |
| [datasets/conf-specs/metrics/index.json](../datasets/conf-specs/metrics/index.json) | 9861 行 | 608 篇 / 10538 页的页面测量索引，含状态、栏数、角色分布和耗时。 |
| [datasets/conf-specs/metrics/profiles/aesthetic_profile.json](../datasets/conf-specs/metrics/profiles/aesthetic_profile.json) | 88657 行 | 在线影子评估读取的 v2 档案，含分层分位、马氏判定块和已应用的历史权重。 |
| [datasets/conf-specs/metrics/profiles/aesthetic_weights.json](../datasets/conf-specs/metrics/profiles/aesthetic_weights.json) | 122 行 | 档案权重标定结果，供挂载 profile；与当前 A_soft 权重是两套参数。 |
| [datasets/conf-specs/metrics/profiles/aesthetic_weights_report.md](../datasets/conf-specs/metrics/profiles/aesthetic_weights_report.md) | 33 行 | 阶段 7 权重校准报告（方案 10.3 步骤二/三）；正文结构见下方文档目录。 |
| [datasets/conf-specs/metrics/profiles/eval_external.json](../datasets/conf-specs/metrics/profiles/eval_external.json) | 3266 行 | E1–E4 外部验证完整结果。 |
| [datasets/conf-specs/metrics/profiles/eval_external.md](../datasets/conf-specs/metrics/profiles/eval_external.md) | 102 行 | 阶段 8：外部验证（方案 13）；正文结构见下方文档目录。 |
| [datasets/conf-specs/metrics/profiles/eval_gate.json](../datasets/conf-specs/metrics/profiles/eval_gate.json) | 65 行 | 12.6 逐维资格门；shadow 加载后剔除未过维度。 |
| [datasets/conf-specs/metrics/profiles/eval_protocol.json](../datasets/conf-specs/metrics/profiles/eval_protocol.json) | 5834 行 | 12.1–12.6 内部评测完整结果。 |
| [datasets/conf-specs/metrics/profiles/eval_report.md](../datasets/conf-specs/metrics/profiles/eval_report.md) | 109 行 | 阶段 5 评测与验收协议报告（方案 12.1-12.6）；正文结构见下方文档目录。 |
| [datasets/conf-specs/metrics/profiles/profile_sensitivity.json](../datasets/conf-specs/metrics/profiles/profile_sensitivity.json) | 75 行 | E4 真编译退化响应与 λ>0 前置资格门。 |
| [datasets/conf-specs/metrics/profiles/redundancy.json](../datasets/conf-specs/metrics/profiles/redundancy.json) | 1082 行 | 指标相关簇、强相关对与 PCA 结果，供选维和报告。 |
| [datasets/conf-specs/metrics/profiles/shadow_report.json](../datasets/conf-specs/metrics/profiles/shadow_report.json) | 21351 行 | 全库 in-sample 档案评估、疑似合订本标记与逐篇结果。 |
| [datasets/conf-specs/metrics/profiles/shadow_summary.md](../datasets/conf-specs/metrics/profiles/shadow_summary.md) | 76 行 | 阶段 4 影子评估摘要（全库，in-sample）；正文结构见下方文档目录。 |
| [datasets/conf-specs/metrics/profiles/summary.md](../datasets/conf-specs/metrics/profiles/summary.md) | 156 行 | 审美档案摘要（阶段 2 自动生成）；正文结构见下方文档目录。 |
| [datasets/conf-specs/patterns/float_patterns.json](../datasets/conf-specs/patterns/float_patterns.json) | 79 行 | 跨会议浮动体或版面元素的实测统计汇总；用于分析与合理性参考。 |
| [datasets/conf-specs/patterns/layout_patterns.json](../datasets/conf-specs/patterns/layout_patterns.json) | 51 行 | 跨会议浮动体或版面元素的实测统计汇总；用于分析与合理性参考。 |
| [datasets/conf-specs/samples/aaai.samples.jsonl](../datasets/conf-specs/samples/aaai.samples.jsonl) | 36 行 | 样本与 PDF 几何测量合并的逐篇记录（36 行），供聚合和模板统计。 |
| [datasets/conf-specs/samples/aaai.samples.list.json](../datasets/conf-specs/samples/aaai.samples.list.json) | 402 行 | aaai 的 36 篇样本清单，含官方落地页、PDF 及证据 source_id。 |
| [datasets/conf-specs/samples/acl.samples.jsonl](../datasets/conf-specs/samples/acl.samples.jsonl) | 67 行 | 样本与 PDF 几何测量合并的逐篇记录（67 行），供聚合和模板统计。 |
| [datasets/conf-specs/samples/acl.samples.list.json](../datasets/conf-specs/samples/acl.samples.list.json) | 743 行 | acl 的 67 篇样本清单，含官方落地页、PDF 及证据 source_id。 |
| [datasets/conf-specs/samples/cvpr.samples.jsonl](../datasets/conf-specs/samples/cvpr.samples.jsonl) | 68 行 | 样本与 PDF 几何测量合并的逐篇记录（68 行），供聚合和模板统计。 |
| [datasets/conf-specs/samples/cvpr.samples.list.json](../datasets/conf-specs/samples/cvpr.samples.list.json) | 754 行 | cvpr 的 68 篇样本清单，含官方落地页、PDF 及证据 source_id。 |
| [datasets/conf-specs/samples/eccv.samples.jsonl](../datasets/conf-specs/samples/eccv.samples.jsonl) | 36 行 | 样本与 PDF 几何测量合并的逐篇记录（36 行），供聚合和模板统计。 |
| [datasets/conf-specs/samples/eccv.samples.list.json](../datasets/conf-specs/samples/eccv.samples.list.json) | 402 行 | eccv 的 36 篇样本清单，含官方落地页、PDF 及证据 source_id。 |
| [datasets/conf-specs/samples/emnlp.samples.jsonl](../datasets/conf-specs/samples/emnlp.samples.jsonl) | 66 行 | 样本与 PDF 几何测量合并的逐篇记录（66 行），供聚合和模板统计。 |
| [datasets/conf-specs/samples/emnlp.samples.list.json](../datasets/conf-specs/samples/emnlp.samples.list.json) | 732 行 | emnlp 的 66 篇样本清单，含官方落地页、PDF 及证据 source_id。 |
| [datasets/conf-specs/samples/iccv.samples.jsonl](../datasets/conf-specs/samples/iccv.samples.jsonl) | 68 行 | 样本与 PDF 几何测量合并的逐篇记录（68 行），供聚合和模板统计。 |
| [datasets/conf-specs/samples/iccv.samples.list.json](../datasets/conf-specs/samples/iccv.samples.list.json) | 754 行 | iccv 的 68 篇样本清单，含官方落地页、PDF 及证据 source_id。 |
| [datasets/conf-specs/samples/iclr.samples.jsonl](../datasets/conf-specs/samples/iclr.samples.jsonl) | 6 行 | 样本与 PDF 几何测量合并的逐篇记录（6 行），供聚合和模板统计。 |
| [datasets/conf-specs/samples/iclr.samples.list.json](../datasets/conf-specs/samples/iclr.samples.list.json) | 78 行 | iclr 的 6 篇样本清单，含官方落地页、PDF 及证据 source_id。 |
| [datasets/conf-specs/samples/icml.samples.jsonl](../datasets/conf-specs/samples/icml.samples.jsonl) | 62 行 | 样本与 PDF 几何测量合并的逐篇记录（62 行），供聚合和模板统计。 |
| [datasets/conf-specs/samples/icml.samples.list.json](../datasets/conf-specs/samples/icml.samples.list.json) | 688 行 | icml 的 62 篇样本清单，含官方落地页、PDF 及证据 source_id。 |
| [datasets/conf-specs/samples/ijcai.samples.jsonl](../datasets/conf-specs/samples/ijcai.samples.jsonl) | 66 行 | 样本与 PDF 几何测量合并的逐篇记录（66 行），供聚合和模板统计。 |
| [datasets/conf-specs/samples/ijcai.samples.list.json](../datasets/conf-specs/samples/ijcai.samples.list.json) | 732 行 | ijcai 的 66 篇样本清单，含官方落地页、PDF 及证据 source_id。 |
| [datasets/conf-specs/samples/kdd.samples.jsonl](../datasets/conf-specs/samples/kdd.samples.jsonl) | 6 行 | 样本与 PDF 几何测量合并的逐篇记录（6 行），供聚合和模板统计。 |
| [datasets/conf-specs/samples/kdd.samples.list.json](../datasets/conf-specs/samples/kdd.samples.list.json) | 72 行 | kdd 的 6 篇样本清单，含官方落地页、PDF 及证据 source_id。 |
| [datasets/conf-specs/samples/neurips.samples.jsonl](../datasets/conf-specs/samples/neurips.samples.jsonl) | 37 行 | 样本与 PDF 几何测量合并的逐篇记录（37 行），供聚合和模板统计。 |
| [datasets/conf-specs/samples/neurips.samples.list.json](../datasets/conf-specs/samples/neurips.samples.list.json) | 413 行 | neurips 的 37 篇样本清单，含官方落地页、PDF 及证据 source_id。 |
| [datasets/conf-specs/samples/nsdi.samples.jsonl](../datasets/conf-specs/samples/nsdi.samples.jsonl) | 45 行 | 样本与 PDF 几何测量合并的逐篇记录（45 行），供聚合和模板统计。 |
| [datasets/conf-specs/samples/nsdi.samples.list.json](../datasets/conf-specs/samples/nsdi.samples.list.json) | 501 行 | nsdi 的 45 篇样本清单，含官方落地页、PDF 及证据 source_id。 |
| [datasets/conf-specs/samples/osdi.samples.jsonl](../datasets/conf-specs/samples/osdi.samples.jsonl) | 24 行 | 样本与 PDF 几何测量合并的逐篇记录（24 行），供聚合和模板统计。 |
| [datasets/conf-specs/samples/osdi.samples.list.json](../datasets/conf-specs/samples/osdi.samples.list.json) | 270 行 | osdi 的 24 篇样本清单，含官方落地页、PDF 及证据 source_id。 |
| [datasets/conf-specs/samples/siggraph.samples.jsonl](../datasets/conf-specs/samples/siggraph.samples.jsonl) | 7 行 | 样本与 PDF 几何测量合并的逐篇记录（7 行），供聚合和模板统计。 |
| [datasets/conf-specs/samples/siggraph.samples.list.json](../datasets/conf-specs/samples/siggraph.samples.list.json) | 83 行 | siggraph 的 7 篇样本清单，含官方落地页、PDF 及证据 source_id。 |
| [datasets/conf-specs/samples/sosp.samples.jsonl](../datasets/conf-specs/samples/sosp.samples.jsonl) | 7 行 | 样本与 PDF 几何测量合并的逐篇记录（7 行），供聚合和模板统计。 |
| [datasets/conf-specs/samples/sosp.samples.list.json](../datasets/conf-specs/samples/sosp.samples.list.json) | 83 行 | sosp 的 7 篇样本清单，含官方落地页、PDF 及证据 source_id。 |
| [datasets/conf-specs/samples/www.samples.jsonl](../datasets/conf-specs/samples/www.samples.jsonl) | 7 行 | 样本与 PDF 几何测量合并的逐篇记录（7 行），供聚合和模板统计。 |
| [datasets/conf-specs/samples/www.samples.list.json](../datasets/conf-specs/samples/www.samples.list.json) | 83 行 | www 的 7 篇样本清单，含官方落地页、PDF 及证据 source_id。 |
| [datasets/conf-specs/schema/EXAMPLE_conference.json](../datasets/conf-specs/schema/EXAMPLE_conference.json) | 98 行 | 会议规范/模板的受控字段、结构契约或示例；由 validate.py / validate_templates.py 消费。 |
| [datasets/conf-specs/schema/KEY_VOCAB.md](../datasets/conf-specs/schema/KEY_VOCAB.md) | 146 行 | 会议规范/模板的受控字段、结构契约或示例；由 validate.py / validate_templates.py 消费。 |
| [datasets/conf-specs/schema/conference.schema.json](../datasets/conf-specs/schema/conference.schema.json) | 117 行 | 会议规范/模板的受控字段、结构契约或示例；由 validate.py / validate_templates.py 消费。 |
| [datasets/conf-specs/schema/template.schema.json](../datasets/conf-specs/schema/template.schema.json) | 324 行 | 会议规范/模板的受控字段、结构契约或示例；由 validate.py / validate_templates.py 消费。 |
| [datasets/conf-specs/sources/fetch_log.jsonl](../datasets/conf-specs/sources/fetch_log.jsonl) | 773 行 | 来源抓取追加日志（773 行），含 URL、状态、时间与 SHA-256，供 mk_source.py 建立证据条目。 |
| [datasets/conf-specs/summary/cross-conf-summary.md](../datasets/conf-specs/summary/cross-conf-summary.md) | 102 行 | 跨会议排版规范总结（人工汇总）；正文结构见下方文档目录。 |
| [datasets/conf-specs/summary/cross-conf-table.md](../datasets/conf-specs/summary/cross-conf-table.md) | 18 行 | 跨会议硬性要求速查表（自动生成，勿手改）；正文结构见下方文档目录。 |
| [datasets/conf-specs/summary/link-repair-report.md](../datasets/conf-specs/summary/link-repair-report.md) | 9 行 | 样本链接修复报告；正文结构见下方文档目录。 |
| [datasets/conf-specs/summary/sample-link-check.md](../datasets/conf-specs/summary/sample-link-check.md) | 76 行 | 样本 PDF 链接可用性检查（自动生成）；正文结构见下方文档目录。 |
| [datasets/conf-specs/summary/template-design-report.md](../datasets/conf-specs/summary/template-design-report.md) | 321 行 | 会议排版模板设计报告（16 会议 · 数据驱动）；正文结构见下方文档目录。 |
| [datasets/conf-specs/summary/template-matrix.md](../datasets/conf-specs/summary/template-matrix.md) | 23 行 | 16 会议模板速查表（自动生成，勿手改）；正文结构见下方文档目录。 |
| [datasets/conf-specs/summary/texopt-generalizable-rules.json](../datasets/conf-specs/summary/texopt-generalizable-rules.json) | 206 行 | 16 条跨会议通用规则与接入缺口（L/A/R 三层），带证据指针，供 analyze_templates/build_templates 选择适用规则；部分 R 项是历史缺口。 |
| [datasets/conf-specs/summary/texopt-integration-report.md](../datasets/conf-specs/summary/texopt-integration-report.md) | 381 行 | 会议模板 → texopt 接入现状（自动生成，勿手改）；正文结构见下方文档目录。 |
| [datasets/conf-specs/templates-v2/aaai.json](../datasets/conf-specs/templates-v2/aaai.json) | 1714 行 | --conference 完整档案：官方要求、实测区间、basis 与未接入政策；扁平投影 {"page_limit":7,"font_pt":10,"margin_mm":19.05,"float_spec":"tbp","overwide_fig_threshold_mm":177.8,"eq_fleqn_allowed":false,"enable_quality_macros":true} |
| [datasets/conf-specs/templates-v2/acl.json](../datasets/conf-specs/templates-v2/acl.json) | 2310 行 | --conference 完整档案：官方要求、实测区间、basis 与未接入政策；扁平投影 {"page_limit":8,"font_pt":11,"margin_mm":25.0,"float_spec":"tbp","overwide_fig_threshold_mm":160.0,"eq_fleqn_allowed":false,"enable_quality_macros":true} |
| [datasets/conf-specs/templates-v2/cvpr.json](../datasets/conf-specs/templates-v2/cvpr.json) | 2257 行 | --conference 完整档案：官方要求、实测区间、basis 与未接入政策；扁平投影 {"page_limit":8,"font_pt":10,"margin_mm":20.6,"float_spec":"tbp","overwide_fig_threshold_mm":174.6,"eq_fleqn_allowed":false,"enable_quality_macros":true} |
| [datasets/conf-specs/templates-v2/eccv.json](../datasets/conf-specs/templates-v2/eccv.json) | 1364 行 | --conference 完整档案：官方要求、实测区间、basis 与未接入政策；扁平投影 {"page_limit":14,"font_pt":10,"margin_mm":12,"float_spec":"tbp","overwide_fig_threshold_mm":122,"eq_fleqn_allowed":false,"enable_quality_macros":true} |
| [datasets/conf-specs/templates-v2/emnlp.json](../datasets/conf-specs/templates-v2/emnlp.json) | 2283 行 | --conference 完整档案：官方要求、实测区间、basis 与未接入政策；扁平投影 {"page_limit":8,"font_pt":11,"margin_mm":25.0,"float_spec":"tbp","overwide_fig_threshold_mm":160.0,"eq_fleqn_allowed":false,"enable_quality_macros":true} |
| [datasets/conf-specs/templates-v2/iccv.json](../datasets/conf-specs/templates-v2/iccv.json) | 2257 行 | --conference 完整档案：官方要求、实测区间、basis 与未接入政策；扁平投影 {"page_limit":8,"font_pt":10,"margin_mm":20.6,"float_spec":"tbp","overwide_fig_threshold_mm":174.6,"eq_fleqn_allowed":false,"enable_quality_macros":true} |
| [datasets/conf-specs/templates-v2/iclr.json](../datasets/conf-specs/templates-v2/iclr.json) | 1080 行 | --conference 完整档案：官方要求、实测区间、basis 与未接入政策；扁平投影 {"page_limit":10,"font_pt":10,"margin_mm":25.4,"float_spec":"tbp","overwide_fig_threshold_mm":139.7,"eq_fleqn_allowed":false,"enable_quality_macros":true} |
| [datasets/conf-specs/templates-v2/icml.json](../datasets/conf-specs/templates-v2/icml.json) | 1790 行 | --conference 完整档案：官方要求、实测区间、basis 与未接入政策；扁平投影 {"page_limit":8,"font_pt":10,"margin_mm":22.225,"float_spec":"tbp","overwide_fig_threshold_mm":171.45,"eq_fleqn_allowed":false,"enable_quality_macros":true} |
| [datasets/conf-specs/templates-v2/ijcai.json](../datasets/conf-specs/templates-v2/ijcai.json) | 2272 行 | --conference 完整档案：官方要求、实测区间、basis 与未接入政策；扁平投影 {"page_limit":7,"font_pt":10,"margin_mm":19.05,"float_spec":"tbp","overwide_fig_threshold_mm":177.8,"eq_fleqn_allowed":false,"enable_quality_macros":true} |
| [datasets/conf-specs/templates-v2/kdd.json](../datasets/conf-specs/templates-v2/kdd.json) | 1054 行 | --conference 完整档案：官方要求、实测区间、basis 与未接入政策；扁平投影 {"page_limit":8,"font_pt":9,"margin_mm":19.05,"float_spec":"tbp","overwide_fig_threshold_mm":177.8,"eq_fleqn_allowed":false,"enable_quality_macros":true} |
| [datasets/conf-specs/templates-v2/neurips.json](../datasets/conf-specs/templates-v2/neurips.json) | 1488 行 | --conference 完整档案：官方要求、实测区间、basis 与未接入政策；扁平投影 {"page_limit":9,"font_pt":10,"margin_mm":25.4,"float_spec":"tbp","overwide_fig_threshold_mm":139.7,"eq_fleqn_allowed":false,"enable_quality_macros":true} |
| [datasets/conf-specs/templates-v2/nsdi.json](../datasets/conf-specs/templates-v2/nsdi.json) | 1529 行 | --conference 完整档案：官方要求、实测区间、basis 与未接入政策；扁平投影 {"page_limit":12,"font_pt":10,"margin_mm":19.05,"float_spec":"tbp","overwide_fig_threshold_mm":177.8,"eq_fleqn_allowed":false,"enable_quality_macros":true} |
| [datasets/conf-specs/templates-v2/osdi.json](../datasets/conf-specs/templates-v2/osdi.json) | 1273 行 | --conference 完整档案：官方要求、实测区间、basis 与未接入政策；扁平投影 {"page_limit":12,"font_pt":10,"margin_mm":19.05,"float_spec":"tbp","overwide_fig_threshold_mm":177.8,"eq_fleqn_allowed":false,"enable_quality_macros":true} |
| [datasets/conf-specs/templates-v2/siggraph.json](../datasets/conf-specs/templates-v2/siggraph.json) | 1078 行 | --conference 完整档案：官方要求、实测区间、basis 与未接入政策；扁平投影 {"page_limit":7,"font_pt":9,"margin_mm":18.34,"float_spec":"tbp","overwide_fig_threshold_mm":179.2,"eq_fleqn_allowed":false,"enable_quality_macros":true} |
| [datasets/conf-specs/templates-v2/sosp.json](../datasets/conf-specs/templates-v2/sosp.json) | 1123 行 | --conference 完整档案：官方要求、实测区间、basis 与未接入政策；扁平投影 {"page_limit":12,"font_pt":10,"margin_mm":18.8,"float_spec":"tbp","overwide_fig_threshold_mm":178,"eq_fleqn_allowed":false,"enable_quality_macros":true} |
| [datasets/conf-specs/templates-v2/www.json](../datasets/conf-specs/templates-v2/www.json) | 1053 行 | --conference 完整档案：官方要求、实测区间、basis 与未接入政策；扁平投影 {"page_limit":8,"font_pt":9,"margin_mm":19.05,"float_spec":"tbp","overwide_fig_threshold_mm":177.8,"eq_fleqn_allowed":false,"enable_quality_macros":true} |
| [datasets/conf-specs/texopt-templates/aaai.json](../datasets/conf-specs/texopt-templates/aaai.json) | 9 行 | build_dataset.py 生成的轻量要求包；install_templates.sh 可安装到根 templates/。 |
| [datasets/conf-specs/texopt-templates/acl.json](../datasets/conf-specs/texopt-templates/acl.json) | 9 行 | build_dataset.py 生成的轻量要求包；install_templates.sh 可安装到根 templates/。 |
| [datasets/conf-specs/texopt-templates/cvpr.json](../datasets/conf-specs/texopt-templates/cvpr.json) | 10 行 | build_dataset.py 生成的轻量要求包；install_templates.sh 可安装到根 templates/。 |
| [datasets/conf-specs/texopt-templates/eccv.json](../datasets/conf-specs/texopt-templates/eccv.json) | 10 行 | build_dataset.py 生成的轻量要求包；install_templates.sh 可安装到根 templates/。 |
| [datasets/conf-specs/texopt-templates/emnlp.json](../datasets/conf-specs/texopt-templates/emnlp.json) | 9 行 | build_dataset.py 生成的轻量要求包；install_templates.sh 可安装到根 templates/。 |
| [datasets/conf-specs/texopt-templates/iccv.json](../datasets/conf-specs/texopt-templates/iccv.json) | 10 行 | build_dataset.py 生成的轻量要求包；install_templates.sh 可安装到根 templates/。 |
| [datasets/conf-specs/texopt-templates/iclr.json](../datasets/conf-specs/texopt-templates/iclr.json) | 9 行 | build_dataset.py 生成的轻量要求包；install_templates.sh 可安装到根 templates/。 |
| [datasets/conf-specs/texopt-templates/icml.json](../datasets/conf-specs/texopt-templates/icml.json) | 9 行 | build_dataset.py 生成的轻量要求包；install_templates.sh 可安装到根 templates/。 |
| [datasets/conf-specs/texopt-templates/ijcai.json](../datasets/conf-specs/texopt-templates/ijcai.json) | 9 行 | build_dataset.py 生成的轻量要求包；install_templates.sh 可安装到根 templates/。 |
| [datasets/conf-specs/texopt-templates/kdd.json](../datasets/conf-specs/texopt-templates/kdd.json) | 12 行 | build_dataset.py 生成的轻量要求包；install_templates.sh 可安装到根 templates/。 |
| [datasets/conf-specs/texopt-templates/neurips.json](../datasets/conf-specs/texopt-templates/neurips.json) | 9 行 | build_dataset.py 生成的轻量要求包；install_templates.sh 可安装到根 templates/。 |
| [datasets/conf-specs/texopt-templates/nsdi.json](../datasets/conf-specs/texopt-templates/nsdi.json) | 9 行 | build_dataset.py 生成的轻量要求包；install_templates.sh 可安装到根 templates/。 |
| [datasets/conf-specs/texopt-templates/osdi.json](../datasets/conf-specs/texopt-templates/osdi.json) | 9 行 | build_dataset.py 生成的轻量要求包；install_templates.sh 可安装到根 templates/。 |
| [datasets/conf-specs/texopt-templates/siggraph.json](../datasets/conf-specs/texopt-templates/siggraph.json) | 12 行 | build_dataset.py 生成的轻量要求包；install_templates.sh 可安装到根 templates/。 |
| [datasets/conf-specs/texopt-templates/sosp.json](../datasets/conf-specs/texopt-templates/sosp.json) | 8 行 | build_dataset.py 生成的轻量要求包；install_templates.sh 可安装到根 templates/。 |
| [datasets/conf-specs/texopt-templates/www.json](../datasets/conf-specs/texopt-templates/www.json) | 12 行 | build_dataset.py 生成的轻量要求包；install_templates.sh 可安装到根 templates/。 |
| [datasets/conf-specs/tools/analyze_templates.py](../datasets/conf-specs/tools/analyze_templates.py) | 320 行 | analyze_templates.py —— 为“模板设计”任务做数据侧统计。 |
| [datasets/conf-specs/tools/bootstrap_py.sh](../datasets/conf-specs/tools/bootstrap_py.sh) | 87 行 | 为数据测量安装独立 pdfminer/pypdf 依赖；旧环境还生成 cryptography shim；不属于优化入口。 |
| [datasets/conf-specs/tools/build_dataset.py](../datasets/conf-specs/tools/build_dataset.py) | 365 行 | build_dataset.py —— 数据集的“汇总编译”步骤。 |
| [datasets/conf-specs/tools/build_profile.py](../datasets/conf-specs/tools/build_profile.py) | 299 行 | build_profile.py —— 阶段 2：把全库 page_metrics.v1 汇总成「审美档案」。 |
| [datasets/conf-specs/tools/build_templates.py](../datasets/conf-specs/tools/build_templates.py) | 732 行 | build_templates.py —— 用数据生成 16 个会议的 texopt 排版模板（templates-v2/）。 |
| [datasets/conf-specs/tools/calibrate_weights.py](../datasets/conf-specs/tools/calibrate_weights.py) | 160 行 | calibrate_weights.py —— 阶段 7：审美权重校准（方案 10.3 步骤二/三）。 |
| [datasets/conf-specs/tools/check_conference_integration.py](../datasets/conf-specs/tools/check_conference_integration.py) | 123 行 | check_conference_integration.py —— 记录「会议模板 → texopt」的接入现状。 |
| [datasets/conf-specs/tools/check_sample_links.py](../datasets/conf-specs/tools/check_sample_links.py) | 116 行 | check_sample_links.py —— 逐个校验 samples/*.samples.list.json 里的 pdf_url 是否可下载。 |
| [datasets/conf-specs/tools/eval_external.py](../datasets/conf-specs/tools/eval_external.py) | 338 行 | eval_external.py —— 阶段 8：外部验证（方案 13）。 |
| [datasets/conf-specs/tools/eval_protocol.py](../datasets/conf-specs/tools/eval_protocol.py) | 474 行 | eval_protocol.py —— 阶段 5：评测与验收协议（方案 12.1-12.6）全流程。 |
| [datasets/conf-specs/tools/extract_metrics.py](../datasets/conf-specs/tools/extract_metrics.py) | 155 行 | extract_metrics.py —— 阶段 1：全库逐篇提取 page_metrics.v1 并缓存。 |
| [datasets/conf-specs/tools/fetch_source.sh](../datasets/conf-specs/tools/fetch_source.sh) | 93 行 | 下载或复制来源归档，提取文本并追加 SHA-256/HTTP 状态抓取日志。 |
| [datasets/conf-specs/tools/install_templates.sh](../datasets/conf-specs/tools/install_templates.sh) | 54 行 | 将 texopt-templates 安装至根 templates；默认预览，覆盖冲突需 --force。 |
| [datasets/conf-specs/tools/make_pairs.py](../datasets/conf-specs/tools/make_pairs.py) | 388 行 | make_pairs.py —— 阶段 7 步骤三：生成「人类成对比较」采集包（方案 10.3）。 |
| [datasets/conf-specs/tools/measure_pdf.py](../datasets/conf-specs/tools/measure_pdf.py) | 604 行 | measure_pdf.py —— 从真实论文 PDF 量取排版特征（可复现、可追溯）。 |
| [datasets/conf-specs/tools/mk_source.py](../datasets/conf-specs/tools/mk_source.py) | 99 行 | mk_source.py —— 从 sources/fetch_log.jsonl 生成 conferences/*.json 里的 Source 条目。 |
| [datasets/conf-specs/tools/oa.py](../datasets/conf-specs/tools/oa.py) | 45 行 | oa.py —— 通过 OpenAlex 按标题查论文元数据（找 arXiv id / 落地页）。 |
| [datasets/conf-specs/tools/profile_attr.py](../datasets/conf-specs/tools/profile_attr.py) | 84 行 | 阶段 8 · E1 归因：A_profile 对源码级退化为什么不敏感？（只编译一次，不跑闭环） |
| [datasets/conf-specs/tools/shadow_report.py](../datasets/conf-specs/tools/shadow_report.py) | 184 行 | shadow_report.py —— 阶段 4：全库影子评估（离线，用已提取的 page_metrics）。 |
| [datasets/conf-specs/tools/totext.py](../datasets/conf-specs/tools/totext.py) | 49 行 | totext.py —— 把 html/pdf/sty 归档文件抽取为纯文本（用于引用校验/人工核对）。 |
| [datasets/conf-specs/tools/validate.py](../datasets/conf-specs/tools/validate.py) | 233 行 | validate.py —— 数据集溯源与结构校验（“每条结论必须可追溯”的强制闸门）。 |
| [datasets/conf-specs/tools/validate_templates.py](../datasets/conf-specs/tools/validate_templates.py) | 104 行 | validate_templates.py —— 用 schema/template.schema.json 校验 templates-v2/*.json。 |
| [datasets/conf-specs/tools/crawl/README.md](../datasets/conf-specs/tools/crawl/README.md) | 153 行 | tools/crawl —— 论文样本爬取（与既有 107 篇同一格式）；正文结构见下方文档目录。 |
| [datasets/conf-specs/tools/crawl/add_samples.py](../datasets/conf-specs/tools/crawl/add_samples.py) | 186 行 | add_samples.py —— 把候选论文「入库」：补溯源来源 + 追加样本清单。 |
| [datasets/conf-specs/tools/crawl/common.py](../datasets/conf-specs/tools/crawl/common.py) | 240 行 | crawl/common.py —— 论文爬取公共层（只用标准库，无需 pip）。 |
| [datasets/conf-specs/tools/crawl/fix_links.py](../datasets/conf-specs/tools/crawl/fix_links.py) | 187 行 | fix_links.py —— 已入库样本 pdf_url 的体检 / 自动修复 / 丢弃。 |
| [datasets/conf-specs/tools/crawl/styles.py](../datasets/conf-specs/tools/crawl/styles.py) | 102 行 | crawl/styles.py —— 新增样本的「命名与归属样式」单一来源。 |
| [datasets/conf-specs/tools/crawl/venues.py](../datasets/conf-specs/tools/crawl/venues.py) | 440 行 | venues.py —— 从官方索引页抓「候选论文清单」（每个会议一个 adapter，只出链接不出 PDF）。 |
| [datasets/conf-specs/years/aaai.history.json](../datasets/conf-specs/years/aaai.history.json) | 121 行 | 从 conferences 的 history 按键整理的历年要求变化与过时提示；不直接参与优化。 |
| [datasets/conf-specs/years/acl.history.json](../datasets/conf-specs/years/acl.history.json) | 188 行 | 从 conferences 的 history 按键整理的历年要求变化与过时提示；不直接参与优化。 |
| [datasets/conf-specs/years/cvpr.history.json](../datasets/conf-specs/years/cvpr.history.json) | 104 行 | 从 conferences 的 history 按键整理的历年要求变化与过时提示；不直接参与优化。 |
| [datasets/conf-specs/years/eccv.history.json](../datasets/conf-specs/years/eccv.history.json) | 121 行 | 从 conferences 的 history 按键整理的历年要求变化与过时提示；不直接参与优化。 |
| [datasets/conf-specs/years/emnlp.history.json](../datasets/conf-specs/years/emnlp.history.json) | 144 行 | 从 conferences 的 history 按键整理的历年要求变化与过时提示；不直接参与优化。 |
| [datasets/conf-specs/years/iccv.history.json](../datasets/conf-specs/years/iccv.history.json) | 127 行 | 从 conferences 的 history 按键整理的历年要求变化与过时提示；不直接参与优化。 |
| [datasets/conf-specs/years/iclr.history.json](../datasets/conf-specs/years/iclr.history.json) | 198 行 | 从 conferences 的 history 按键整理的历年要求变化与过时提示；不直接参与优化。 |
| [datasets/conf-specs/years/icml.history.json](../datasets/conf-specs/years/icml.history.json) | 168 行 | 从 conferences 的 history 按键整理的历年要求变化与过时提示；不直接参与优化。 |
| [datasets/conf-specs/years/ijcai.history.json](../datasets/conf-specs/years/ijcai.history.json) | 127 行 | 从 conferences 的 history 按键整理的历年要求变化与过时提示；不直接参与优化。 |
| [datasets/conf-specs/years/kdd.history.json](../datasets/conf-specs/years/kdd.history.json) | 230 行 | 从 conferences 的 history 按键整理的历年要求变化与过时提示；不直接参与优化。 |
| [datasets/conf-specs/years/neurips.history.json](../datasets/conf-specs/years/neurips.history.json) | 215 行 | 从 conferences 的 history 按键整理的历年要求变化与过时提示；不直接参与优化。 |
| [datasets/conf-specs/years/nsdi.history.json](../datasets/conf-specs/years/nsdi.history.json) | 138 行 | 从 conferences 的 history 按键整理的历年要求变化与过时提示；不直接参与优化。 |
| [datasets/conf-specs/years/osdi.history.json](../datasets/conf-specs/years/osdi.history.json) | 153 行 | 从 conferences 的 history 按键整理的历年要求变化与过时提示；不直接参与优化。 |
| [datasets/conf-specs/years/siggraph.history.json](../datasets/conf-specs/years/siggraph.history.json) | 196 行 | 从 conferences 的 history 按键整理的历年要求变化与过时提示；不直接参与优化。 |
| [datasets/conf-specs/years/sosp.history.json](../datasets/conf-specs/years/sosp.history.json) | 205 行 | 从 conferences 的 history 按键整理的历年要求变化与过时提示；不直接参与优化。 |
| [datasets/conf-specs/years/www.history.json](../datasets/conf-specs/years/www.history.json) | 228 行 | 从 conferences 的 history 按键整理的历年要求变化与过时提示；不直接参与优化。 |
| [docs/PROJECT_MAP.md](../docs/PROJECT_MAP.md) | 250 行 | texopt 项目地图（PROJECT_MAP）；正文结构见下方文档目录。 |
| [docs/README.md](../docs/README.md) | 65 行 | docs 索引；正文结构见下方文档目录。 |
| [docs/corpus_fields_plain_20261026.md](../docs/corpus_fields_plain_20261026.md) | 257 行 | 语料层 Step 1：每一项数据到底是什么意思（大白话版）；正文结构见下方文档目录。 |
| [docs/corpus_inventory_20261026.md](../docs/corpus_inventory_20261026.md) | 50 行 | 语料层 Step 1：数据清单与已做分析（2026-10-26）；正文结构见下方文档目录。 |
| [docs/make_formula_doc.py](../docs/make_formula_doc.py) | 235 行 | 构建《texopt 评分模型 v2 讲解版》HTML 文档。 |
| [docs/model_v3_design_20261014.html](../docs/model_v3_design_20261014.html) | 240 行 | texopt 模型 v3 结构设计说明（2026-10-14）；引用外置 SVG 公式的展示版，由 docs/make_formula_doc.py 生成。 |
| [docs/model_v3_design_20261014.template.html](../docs/model_v3_design_20261014.template.html) | 240 行 | texopt 模型 v3 结构设计说明（2026-10-14）；占位公式源模板，由 docs/make_formula_doc.py 生成。 |
| `docs/model_v3_design_20261014_single.html`（已清理） | 240 行 | 重复内嵌展示版，2026-11-19 已清理；使用 [普通 HTML](model_v3_design_20261014.html)，需要时可由生成器再生成。 |
| [docs/page_metrics_v1.md](../docs/page_metrics_v1.md) | 136 行 | page_metrics.v1 —— 页面级指标数据结构规范；正文结构见下方文档目录。 |
| [docs/scoring_report_20261102.html](../docs/scoring_report_20261102.html) | 342 行 | texopt 打分评价体系 · 现状总结（2026-11-02 阶段汇报）；引用外置 SVG 公式的展示版，由 docs/make_formula_doc.py 生成。 |
| [docs/scoring_report_20261102.pdf](../docs/scoring_report_20261102.pdf) | 888362 B | 评分说明导出的 PDF。 |
| [docs/scoring_report_20261102.template.html](../docs/scoring_report_20261102.template.html) | 342 行 | texopt 打分评价体系 · 现状总结（2026-11-02 阶段汇报）；占位公式源模板，由 docs/make_formula_doc.py 生成。 |
| `docs/scoring_report_20261102_single.html`（已清理） | 342 行 | 重复内嵌展示版，2026-11-19 已清理；使用 [普通 HTML](scoring_report_20261102.html) 或现有 PDF。 |
| [docs/stage0_visual_inventory.md](../docs/stage0_visual_inventory.md) | 234 行 | 阶段 0 交付：visual.py 盘点 + 指标—现状—缺口表；正文结构见下方文档目录。 |
| [docs/stage10_a_soft_smooth_form_20261028.md](../docs/stage10_a_soft_smooth_form_20261028.md) | 99 行 | Step 2-b：A_soft 软指标改成「平滑目标」形式（2026-10-28）；正文结构见下方文档目录。 |
| [docs/stage10b_pair_sheet_20261028.md](../docs/stage10b_pair_sheet_20261028.md) | 135 行 | Step 2-c：成对比较验收表（2026-10-28）；正文结构见下方文档目录。 |
| [docs/stage11_severity_sheet_20261028.md](../docs/stage11_severity_sheet_20261028.md) | 168 行 | Step 5-a：缺陷严重度标定（2026-10-28）；正文结构见下方文档目录。 |
| [docs/stage12_gate_exit_two_lines_20261030.md](../docs/stage12_gate_exit_two_lines_20261030.md) | 137 行 | 阶段 12：gate 一票否决 + 两线分离 + P 权重回填 + ρ 等边际收益（2026-10-30）；正文结构见下方文档目录。 |
| [docs/stage13_rho_tradeoff_20261031.md](../docs/stage13_rho_tradeoff_20261031.md) | 97 行 | 阶段 13：ρ 的无差异点重标定（0.341 → 15，2026-10-31）；正文结构见下方文档目录。 |
| [docs/stage14_pweight_unified_20261102.md](../docs/stage14_pweight_unified_20261102.md) | 110 行 | 阶段 14：P 权重的「同一把尺子」标定（2026-11-02）；正文结构见下方文档目录。 |
| [docs/stage15_local_global_20261102.md](../docs/stage15_local_global_20261102.md) | 123 行 | 阶段 15：单页打分 / 整篇打分（局部 vs 整体，2026-11-02）；正文结构见下方文档目录。 |
| [docs/stage16_model2_metrics_20261102.md](../docs/stage16_model2_metrics_20261102.md) | 128 行 | 阶段 16：model2 指标重选（可辨识性 + 敏感性双体检，2026-11-02）；正文结构见下方文档目录。 |
| [docs/stage17_no_human_calibration_20261111.md](../docs/stage17_no_human_calibration_20261111.md) | 83 行 | 阶段 17 前置决定：不再新增人工打分类标定（2026-11-11）；正文结构见下方文档目录。 |
| [docs/stage1_role_and_extraction.md](../docs/stage1_role_and_extraction.md) | 185 行 | 阶段 1 交付：页面角色标注 + 页面级指标提取；正文结构见下方文档目录。 |
| [docs/stage2_profile.md](../docs/stage2_profile.md) | 323 行 | 阶段 2 交付：审美档案（正常范围）+ 去冗余；正文结构见下方文档目录。 |
| [docs/stage3_whitespace.md](../docs/stage3_whitespace.md) | 128 行 | 阶段 3 交付：留白结构化识别（五类 + region 列表）；正文结构见下方文档目录。 |
| [docs/stage4_aesthetic_profile.md](../docs/stage4_aesthetic_profile.md) | 162 行 | 阶段 4 交付：多维异常检测（马氏距离）+ 非单调带外损失 A_profile（影子模式）；正文结构见下方文档目录。 |
| [docs/stage5_eval_protocol.md](../docs/stage5_eval_protocol.md) | 133 行 | 阶段 5 交付：评测与验收协议（方案 12.1-12.6）；正文结构见下方文档目录。 |
| [docs/stage6_shadow_integration.md](../docs/stage6_shadow_integration.md) | 122 行 | 阶段 6 交付：影子模式接入 texopt（λ = 0，仅报告）；正文结构见下方文档目录。 |
| [docs/stage7_weight_calibration.md](../docs/stage7_weight_calibration.md) | 153 行 | 阶段 7 交付：审美权重校准（方案 10.3 步骤二/三）；正文结构见下方文档目录。 |
| [docs/stage8_eval_external.md](../docs/stage8_eval_external.md) | 400 行 | 阶段 8：外部验证（方案 13）；正文结构见下方文档目录。 |
| [docs/stage9_detector_check_20261027.md](../docs/stage9_detector_check_20261027.md) | 184 行 | Step 2：检测器体检（2026-10-27）；正文结构见下方文档目录。 |
| [docs/aesthetic/README.md](../docs/aesthetic/README.md) | 289 行 | 审美量化模型（model2：A_soft + A_profile）；正文结构见下方文档目录。 |
| [docs/formula_doc_assets/eq_A.svg](../docs/formula_doc_assets/eq_A.svg) | 78 行 | 公式 SVG：eq_A；对应 docs/make_formula_doc.py 的 EQS 字典，供两套 HTML 文档引用。历史公式可能不代表现行评分。 |
| [docs/formula_doc_assets/eq_Adefect.svg](../docs/formula_doc_assets/eq_Adefect.svg) | 332 行 | 公式 SVG：eq_Adefect；对应 docs/make_formula_doc.py 的 EQS 字典，供两套 HTML 文档引用。历史公式可能不代表现行评分。 |
| [docs/formula_doc_assets/eq_I.svg](../docs/formula_doc_assets/eq_I.svg) | 60 行 | 公式 SVG：eq_I；对应 docs/make_formula_doc.py 的 EQS 字典，供两套 HTML 文档引用。历史公式可能不代表现行评分。 |
| [docs/formula_doc_assets/eq_Istruct.svg](../docs/formula_doc_assets/eq_Istruct.svg) | 79 行 | 公式 SVG：eq_Istruct；对应 docs/make_formula_doc.py 的 EQS 字典，供两套 HTML 文档引用。历史公式可能不代表现行评分。 |
| [docs/formula_doc_assets/eq_J1.svg](../docs/formula_doc_assets/eq_J1.svg) | 81 行 | 公式 SVG：eq_J1；对应 docs/make_formula_doc.py 的 EQS 字典，供两套 HTML 文档引用。历史公式可能不代表现行评分。 |
| [docs/formula_doc_assets/eq_L.svg](../docs/formula_doc_assets/eq_L.svg) | 83 行 | 公式 SVG：eq_L；对应 docs/make_formula_doc.py 的 EQS 字典，供两套 HTML 文档引用。历史公式可能不代表现行评分。 |
| [docs/formula_doc_assets/eq_M1.svg](../docs/formula_doc_assets/eq_M1.svg) | 44 行 | 公式 SVG：eq_M1；对应 docs/make_formula_doc.py 的 EQS 字典，供两套 HTML 文档引用。历史公式可能不代表现行评分。 |
| [docs/formula_doc_assets/eq_M2.svg](../docs/formula_doc_assets/eq_M2.svg) | 58 行 | 公式 SVG：eq_M2；对应 docs/make_formula_doc.py 的 EQS 字典，供两套 HTML 文档引用。历史公式可能不代表现行评分。 |
| [docs/formula_doc_assets/eq_P.svg](../docs/formula_doc_assets/eq_P.svg) | 119 行 | 公式 SVG：eq_P；对应 docs/make_formula_doc.py 的 EQS 字典，供两套 HTML 文档引用。历史公式可能不代表现行评分。 |
| [docs/formula_doc_assets/eq_dcontent.svg](../docs/formula_doc_assets/eq_dcontent.svg) | 43 行 | 公式 SVG：eq_dcontent；对应 docs/make_formula_doc.py 的 EQS 字典，供两套 HTML 文档引用。历史公式可能不代表现行评分。 |
| [docs/formula_doc_assets/eq_gate.svg](../docs/formula_doc_assets/eq_gate.svg) | 116 行 | 公式 SVG：eq_gate；对应 docs/make_formula_doc.py 的 EQS 字典，供两套 HTML 文档引用。历史公式可能不代表现行评分。 |
| [docs/formula_doc_assets/eq_keep.svg](../docs/formula_doc_assets/eq_keep.svg) | 74 行 | 公式 SVG：eq_keep；对应 docs/make_formula_doc.py 的 EQS 字典，供两套 HTML 文档引用。历史公式可能不代表现行评分。 |
| [docs/formula_doc_assets/eq_lcompile.svg](../docs/formula_doc_assets/eq_lcompile.svg) | 77 行 | 公式 SVG：eq_lcompile；对应 docs/make_formula_doc.py 的 EQS 字典，供两套 HTML 文档引用。历史公式可能不代表现行评分。 |
| [docs/formula_doc_assets/eq_lfig.svg](../docs/formula_doc_assets/eq_lfig.svg) | 69 行 | 公式 SVG：eq_lfig；对应 docs/make_formula_doc.py 的 EQS 字典，供两套 HTML 文档引用。历史公式可能不代表现行评分。 |
| [docs/formula_doc_assets/eq_lpage.svg](../docs/formula_doc_assets/eq_lpage.svg) | 91 行 | 公式 SVG：eq_lpage；对应 docs/make_formula_doc.py 的 EQS 字典，供两套 HTML 文档引用。历史公式可能不代表现行评分。 |
| [docs/formula_doc_assets/eq_lspec.svg](../docs/formula_doc_assets/eq_lspec.svg) | 62 行 | 公式 SVG：eq_lspec；对应 docs/make_formula_doc.py 的 EQS 字典，供两套 HTML 文档引用。历史公式可能不代表现行评分。 |
| [docs/formula_doc_assets/eq_order.svg](../docs/formula_doc_assets/eq_order.svg) | 120 行 | 公式 SVG：eq_order；对应 docs/make_formula_doc.py 的 EQS 字典，供两套 HTML 文档引用。历史公式可能不代表现行评分。 |
| [docs/formula_doc_assets/eq_rep_accept.svg](../docs/formula_doc_assets/eq_rep_accept.svg) | 73 行 | 公式 SVG：eq_rep_accept；对应 docs/make_formula_doc.py 的 EQS 字典，供两套 HTML 文档引用。历史公式可能不代表现行评分。 |
| [docs/formula_doc_assets/eq_rep_loss.svg](../docs/formula_doc_assets/eq_rep_loss.svg) | 128 行 | 公式 SVG：eq_rep_loss；对应 docs/make_formula_doc.py 的 EQS 字典，供两套 HTML 文档引用。历史公式可能不代表现行评分。 |
| [docs/formula_doc_assets/eq_rep_m1.svg](../docs/formula_doc_assets/eq_rep_m1.svg) | 85 行 | 公式 SVG：eq_rep_m1；对应 docs/make_formula_doc.py 的 EQS 字典，供两套 HTML 文档引用。历史公式可能不代表现行评分。 |
| [docs/formula_doc_assets/eq_rep_order.svg](../docs/formula_doc_assets/eq_rep_order.svg) | 95 行 | 公式 SVG：eq_rep_order；对应 docs/make_formula_doc.py 的 EQS 字典，供两套 HTML 文档引用。历史公式可能不代表现行评分。 |
| [docs/formula_doc_assets/eq_rep_page.svg](../docs/formula_doc_assets/eq_rep_page.svg) | 82 行 | 公式 SVG：eq_rep_page；对应 docs/make_formula_doc.py 的 EQS 字典，供两套 HTML 文档引用。历史公式可能不代表现行评分。 |
| [docs/formula_doc_assets/eq_rep_pool.svg](../docs/formula_doc_assets/eq_rep_pool.svg) | 114 行 | 公式 SVG：eq_rep_pool；对应 docs/make_formula_doc.py 的 EQS 字典，供两套 HTML 文档引用。历史公式可能不代表现行评分。 |
| [docs/formula_doc_assets/eq_rep_scale.svg](../docs/formula_doc_assets/eq_rep_scale.svg) | 60 行 | 公式 SVG：eq_rep_scale；对应 docs/make_formula_doc.py 的 EQS 字典，供两套 HTML 文档引用。历史公式可能不代表现行评分。 |
| [docs/formula_doc_assets/eq_rep_w.svg](../docs/formula_doc_assets/eq_rep_w.svg) | 110 行 | 公式 SVG：eq_rep_w；对应 docs/make_formula_doc.py 的 EQS 字典，供两套 HTML 文档引用。历史公式可能不代表现行评分。 |
| [docs/formula_doc_assets/eq_s1.svg](../docs/formula_doc_assets/eq_s1.svg) | 28 行 | 公式 SVG：eq_s1；对应 docs/make_formula_doc.py 的 EQS 字典，供两套 HTML 文档引用。历史公式可能不代表现行评分。 |
| [docs/formula_doc_assets/eq_s2.svg](../docs/formula_doc_assets/eq_s2.svg) | 45 行 | 公式 SVG：eq_s2；对应 docs/make_formula_doc.py 的 EQS 字典，供两套 HTML 文档引用。历史公式可能不代表现行评分。 |
| [docs/formula_doc_assets/eq_s3.svg](../docs/formula_doc_assets/eq_s3.svg) | 103 行 | 公式 SVG：eq_s3；对应 docs/make_formula_doc.py 的 EQS 字典，供两套 HTML 文档引用。历史公式可能不代表现行评分。 |
| [docs/formula_doc_assets/eq_s4.svg](../docs/formula_doc_assets/eq_s4.svg) | 46 行 | 公式 SVG：eq_s4；对应 docs/make_formula_doc.py 的 EQS 字典，供两套 HTML 文档引用。历史公式可能不代表现行评分。 |
| [docs/formula_doc_assets/eq_s5.svg](../docs/formula_doc_assets/eq_s5.svg) | 62 行 | 公式 SVG：eq_s5；对应 docs/make_formula_doc.py 的 EQS 字典，供两套 HTML 文档引用。历史公式可能不代表现行评分。 |
| [docs/formula_doc_assets/eq_s6.svg](../docs/formula_doc_assets/eq_s6.svg) | 95 行 | 公式 SVG：eq_s6；对应 docs/make_formula_doc.py 的 EQS 字典，供两套 HTML 文档引用。历史公式可能不代表现行评分。 |
| [docs/formula_doc_assets/eq_s7.svg](../docs/formula_doc_assets/eq_s7.svg) | 71 行 | 公式 SVG：eq_s7；对应 docs/make_formula_doc.py 的 EQS 字典，供两套 HTML 文档引用。历史公式可能不代表现行评分。 |
| [docs/formula_doc_assets/eq_softloss.svg](../docs/formula_doc_assets/eq_softloss.svg) | 100 行 | 公式 SVG：eq_softloss；对应 docs/make_formula_doc.py 的 EQS 字典，供两套 HTML 文档引用。历史公式可能不代表现行评分。 |
| [docs/formula_doc_assets/eq_softpool.svg](../docs/formula_doc_assets/eq_softpool.svg) | 121 行 | 公式 SVG：eq_softpool；对应 docs/make_formula_doc.py 的 EQS 字典，供两套 HTML 文档引用。历史公式可能不代表现行评分。 |
| [docs/formula_doc_assets/eq_total_now.svg](../docs/formula_doc_assets/eq_total_now.svg) | 43 行 | 公式 SVG：eq_total_now；对应 docs/make_formula_doc.py 的 EQS 字典，供两套 HTML 文档引用。历史公式可能不代表现行评分。 |
| [docs/formula_doc_assets/eq_vis.svg](../docs/formula_doc_assets/eq_vis.svg) | 53 行 | 公式 SVG：eq_vis；对应 docs/make_formula_doc.py 的 EQS 字典，供两套 HTML 文档引用。历史公式可能不代表现行评分。 |
| [docs/notes/frequency_weighting_idea_20261016.md](../docs/notes/frequency_weighting_idea_20261016.md) | 1 行 | 文本说明；正文结构见下方文档目录。 |
| [docs/scoring/README.md](../docs/scoring/README.md) | 290 行 | 打分模型（gate + model1 + model2）；正文结构见下方文档目录。 |
| [examples/README.md](../examples/README.md) | 34 行 | examples/ —— 靶稿（fixtures）；正文结构见下方文档目录。 |
| [examples/aidtest.tex](../examples/aidtest.tex) | 71 行 | 只读 LaTeX 靶稿或真实论文输入；结构与依赖已解析，实际用途见主理解报告的样例表。 |
| [examples/chaos.tex](../examples/chaos.tex) | 92 行 | 只读 LaTeX 靶稿或真实论文输入；结构与依赖已解析，实际用途见主理解报告的样例表。 |
| [examples/demo.tex](../examples/demo.tex) | 187 行 | 只读 LaTeX 靶稿或真实论文输入；结构与依赖已解析，实际用途见主理解报告的样例表。 |
| [examples/fig_violation.tex](../examples/fig_violation.tex) | 76 行 | 只读 LaTeX 靶稿或真实论文输入；结构与依赖已解析，实际用途见主理解报告的样例表。 |
| [examples/gen_fixtures.py](../examples/gen_fixtures.py) | 548 行 | 生成 examples/ 里的靶稿（demo / issues / chaos / nightmare / aidtest / |
| [examples/issues.tex](../examples/issues.tex) | 56 行 | 只读 LaTeX 靶稿或真实论文输入；结构与依赖已解析，实际用途见主理解报告的样例表。 |
| [examples/nightmare.tex](../examples/nightmare.tex) | 144 行 | 只读 LaTeX 靶稿或真实论文输入；结构与依赖已解析，实际用途见主理解报告的样例表。 |
| [examples/propose_target.tex](../examples/propose_target.tex) | 37 行 | 只读 LaTeX 靶稿或真实论文输入；结构与依赖已解析，实际用途见主理解报告的样例表。 |
| [examples/NeurlPS examples/00README.json](../examples/NeurlPS%20examples/00README.json) | 13 行 | arXiv/TeX Live 工程的主文件、版本和构建流程元数据。 |
| [examples/NeurlPS examples/main.bbl](../examples/NeurlPS%20examples/main.bbl) | 419 行 | 真实论文工程的参考文献源或展开文件；随工作副本复制，保持内容。 |
| [examples/NeurlPS examples/main.tex](../examples/NeurlPS%20examples/main.tex) | 390 行 | 只读 LaTeX 靶稿或真实论文输入；结构与依赖已解析，实际用途见主理解报告的样例表。 |
| [examples/NeurlPS examples/neurips_2026.sty](../examples/NeurlPS%20examples/neurips_2026.sty) | 443 行 | NeurIPS 2026 官方排版样式，供该真实样例主文档加载；属于输入工程。 |
| [examples/NeurlPS examples/data/adjudication_stats.tex](../examples/NeurlPS%20examples/data/adjudication_stats.tex) | 14 行 | Silent Revision 论文的表格/附录/统计片段，由同工程 main.tex 的 input 引入。 |
| [examples/NeurlPS examples/data/appendixA_pairs.tex](../examples/NeurlPS%20examples/data/appendixA_pairs.tex) | 20 行 | Silent Revision 论文的表格/附录/统计片段，由同工程 main.tex 的 input 引入。 |
| [examples/NeurlPS examples/data/appendixB_variants.tex](../examples/NeurlPS%20examples/data/appendixB_variants.tex) | 17 行 | Silent Revision 论文的表格/附录/统计片段，由同工程 main.tex 的 input 引入。 |
| [examples/NeurlPS examples/data/appendixC_manifest.tex](../examples/NeurlPS%20examples/data/appendixC_manifest.tex) | 53 行 | Silent Revision 论文的表格/附录/统计片段，由同工程 main.tex 的 input 引入。 |
| [examples/NeurlPS examples/data/appendixM1_pairs.tex](../examples/NeurlPS%20examples/data/appendixM1_pairs.tex) | 14 行 | Silent Revision 论文的表格/附录/统计片段，由同工程 main.tex 的 input 引入。 |
| [examples/NeurlPS examples/data/appendixM2_loo.tex](../examples/NeurlPS%20examples/data/appendixM2_loo.tex) | 9 行 | Silent Revision 论文的表格/附录/统计片段，由同工程 main.tex 的 input 引入。 |
| [examples/NeurlPS examples/data/appendix_examples.tex](../examples/NeurlPS%20examples/data/appendix_examples.tex) | 107 行 | Silent Revision 论文的表格/附录/统计片段，由同工程 main.tex 的 input 引入。 |
| [examples/NeurlPS examples/data/table1_rows.tex](../examples/NeurlPS%20examples/data/table1_rows.tex) | 13 行 | Silent Revision 论文的表格/附录/统计片段，由同工程 main.tex 的 input 引入。 |
| [examples/NeurlPS examples/data/table2_category.tex](../examples/NeurlPS%20examples/data/table2_category.tex) | 11 行 | Silent Revision 论文的表格/附录/统计片段，由同工程 main.tex 的 input 引入。 |
| [examples/NeurlPS examples/figures/fig0_pipeline.pdf](../examples/NeurlPS%20examples/figures/fig0_pipeline.pdf) | 103037 B | 真实论文工程的原始图/补充材料 PDF，供 includegraphics 或人工参考。 |
| [examples/NeurlPS examples/figures/fig1_srr_by_pair.pdf](../examples/NeurlPS%20examples/figures/fig1_srr_by_pair.pdf) | 30365 B | 真实论文工程的原始图/补充材料 PDF，供 includegraphics 或人工参考。 |
| [examples/NeurlPS examples/figures/fig2_direction_by_pair.pdf](../examples/NeurlPS%20examples/figures/fig2_direction_by_pair.pdf) | 28423 B | 真实论文工程的原始图/补充材料 PDF，供 includegraphics 或人工参考。 |
| [examples/test0911/chaotic_layout_test.tex](../examples/test0911/chaotic_layout_test.tex) | 94 行 | 只读 LaTeX 靶稿或真实论文输入；结构与依赖已解析，实际用途见主理解报告的样例表。 |
| [examples/test0911/scope_test.tex](../examples/test0911/scope_test.tex) | 356 行 | 只读 LaTeX 靶稿或真实论文输入；结构与依赖已解析，实际用途见主理解报告的样例表。 |
| [examples/test0911/tiny_conf_test.tex](../examples/test0911/tiny_conf_test.tex) | 12 行 | 只读 LaTeX 靶稿或真实论文输入；结构与依赖已解析，实际用途见主理解报告的样例表。 |
| [examples/test0913/00README.json](../examples/test0913/00README.json) | 17 行 | arXiv/TeX Live 工程的主文件、版本和构建流程元数据。 |
| [examples/test0913/integration.pdf](../examples/test0913/integration.pdf) | 35652 B | 真实论文工程的原始图/补充材料 PDF，供 includegraphics 或人工参考。 |
| [examples/test0913/main.bbl](../examples/test0913/main.bbl) | 361 行 | 真实论文工程的参考文献源或展开文件；随工作副本复制，保持内容。 |
| [examples/test0913/main.tex](../examples/test0913/main.tex) | 309 行 | 只读 LaTeX 靶稿或真实论文输入；结构与依赖已解析，实际用途见主理解报告的样例表。 |
| [examples/test0913/mainNotes.bib](../examples/test0913/mainNotes.bib) | 0 行 | 真实论文工程的参考文献源或展开文件；随工作副本复制，保持内容。 |
| [examples/test0913/microgear_laser_results.pdf](../examples/test0913/microgear_laser_results.pdf) | 218234 B | 真实论文工程的原始图/补充材料 PDF，供 includegraphics 或人工参考。 |
| [examples/test0913/vernier_tuning_combined.pdf](../examples/test0913/vernier_tuning_combined.pdf) | 266031 B | 真实论文工程的原始图/补充材料 PDF，供 includegraphics 或人工参考。 |
| [examples/test0913/anc/supplementary.pdf](../examples/test0913/anc/supplementary.pdf) | 217510 B | 真实论文工程的原始图/补充材料 PDF，供 includegraphics 或人工参考。 |
| [metrics/p_weight_tradeoff_20261102.json](../metrics/p_weight_tradeoff_20261102.json) | 314 行 | 两轮作答合并成一条 b(c) 曲线；c* = 翻转区间中点（见 tools/pweight_combine.py）；w = c* / ρ |
| [metrics/p_weight_tradeoff_round1_20261102.json](../metrics/p_weight_tradeoff_round1_20261102.json) | 168 行 | 同一把尺子：c* = 人判无差异点（边距 mm），w = c* / ρ（等边际收益自洽） |
| [metrics/p_weight_tradeoff_round2_20261102.json](../metrics/p_weight_tradeoff_round2_20261102.json) | 191 行 | 同一把尺子：c* = 人判无差异点（边距 mm），w = c* / ρ（等边际收益自洽） |
| [metrics/pweight_applied_20261102.json](../metrics/pweight_applied_20261102.json) | 28 行 | w = c*/ρ（两轮无差异点合并），口径 A：整体缩放使 7 项权重和与旧值相等，ρ=15 不动 |
| [metrics/rho_exchange_rate.json](../metrics/rho_exchange_rate.json) | 400 行 | 等边际收益：ρ = ΔI / (−ΔP) |
| [metrics/rho_tradeoff_20261031.json](../metrics/rho_tradeoff_20261031.json) | 74 行 | 生成「缺陷保留(A) vs 缺陷修掉+代价(B)」版本对，人工三选一（左/右/无差异），取偏好转折点 |
| [metrics/severity_weights_applied.json](../metrics/severity_weights_applied.json) | 124 行 | w = severity(BT, human 15 题) / freq(corpus per_page)；sqrt 阻尼；缩放到现行权重同量纲（见 docs/stage11_*.md） |
| [metrics/soft_identifiability_20261102.json](../metrics/soft_identifiability_20261102.json) | 185 行 | 标定/指标体检的冻结结果；工具按需读取。 |
| [metrics/soft_identifiability_20261102.md](../metrics/soft_identifiability_20261102.md) | 47 行 | A_soft 指标可辨识性体检（2026-11-02）；正文结构见下方文档目录。 |
| [metrics/soft_sensitivity_20261102.json](../metrics/soft_sensitivity_20261102.json) | 304 行 | 标定/指标体检的冻结结果；工具按需读取。 |
| [metrics/soft_v2_weights_20261111.json](../metrics/soft_v2_weights_20261111.json) | 83 行 | objective-response |
| [skills/latex-opt/SKILL.md](../skills/latex-opt/SKILL.md) | 121 行 | texopt 整体排版优化（确定性闭环 + 模型在环）；正文结构见下方文档目录。 |
| [templates/README.md](../templates/README.md) | 68 行 | templates/ —— 期刊/会议排版要求预设；正文结构见下方文档目录。 |
| [templates/aaai.json](../templates/aaai.json) | 9 行 | --template 轻量要求预设；{"page_limit":7,"font_pt":10,"margin_mm":19.05,"float_spec":"tb","overwide_fig_threshold_mm":177.8} |
| [templates/acl.json](../templates/acl.json) | 9 行 | --template 轻量要求预设；{"page_limit":8,"font_pt":11,"margin_mm":25.0,"float_spec":"tbp","overwide_fig_threshold_mm":160.0} |
| [templates/acm-full.json](../templates/acm-full.json) | 8 行 | --template 轻量要求预设；{"font_pt":10,"float_spec":"tbp","overwide_fig_threshold_mm":110.0,"enable_quality_macros":true} |
| [templates/cvpr.json](../templates/cvpr.json) | 10 行 | --template 轻量要求预设；{"page_limit":8,"font_pt":10,"margin_mm":20.64,"float_spec":"tbp","overwide_fig_threshold_mm":174.6,"margin_min_mm":20.6} |
| [templates/eccv.json](../templates/eccv.json) | 10 行 | --template 轻量要求预设；{"page_limit":14,"font_pt":10,"margin_mm":12,"float_spec":"tbp","overwide_fig_threshold_mm":122.0,"margin_min_mm":12} |
| [templates/emnlp.json](../templates/emnlp.json) | 9 行 | --template 轻量要求预设；{"page_limit":8,"font_pt":11,"margin_mm":25.0,"float_spec":"tbp","overwide_fig_threshold_mm":160.0} |
| [templates/iccv.json](../templates/iccv.json) | 10 行 | --template 轻量要求预设；{"page_limit":8,"font_pt":10,"margin_mm":20.64,"float_spec":"tbp","overwide_fig_threshold_mm":174.6,"margin_min_mm":20.6} |
| [templates/iclr.json](../templates/iclr.json) | 9 行 | --template 轻量要求预设；{"page_limit":10,"font_pt":10,"margin_mm":38.1,"float_spec":"tbp","overwide_fig_threshold_mm":139.7} |
| [templates/icml.json](../templates/icml.json) | 9 行 | --template 轻量要求预设；{"page_limit":9,"font_pt":10,"margin_mm":22.225,"float_spec":"tbp","overwide_fig_threshold_mm":171.45} |
| [templates/ijcai.json](../templates/ijcai.json) | 9 行 | --template 轻量要求预设；{"page_limit":9,"font_pt":10,"margin_mm":19.05,"float_spec":"tbp","overwide_fig_threshold_mm":177.8} |
| [templates/kdd.json](../templates/kdd.json) | 12 行 | --template 轻量要求预设；{"page_limit":8,"font_pt":9,"margin_mm":19.05,"eq_fleqn_allowed":true,"float_spec":"tbp","microtype":true,"overwide_fig_threshold_mm":177.8,"verbose":false} |
| [templates/neurips.json](../templates/neurips.json) | 9 行 | --template 轻量要求预设；{"page_limit":9,"font_pt":10,"margin_mm":25.4,"float_spec":"tbp","overwide_fig_threshold_mm":139.7} |
| [templates/nsdi.json](../templates/nsdi.json) | 9 行 | --template 轻量要求预设；{"page_limit":12,"font_pt":10,"margin_mm":19.05,"float_spec":"tbp","overwide_fig_threshold_mm":177.8} |
| [templates/osdi.json](../templates/osdi.json) | 9 行 | --template 轻量要求预设；{"page_limit":12,"font_pt":10,"margin_mm":19.05,"float_spec":"tbp","overwide_fig_threshold_mm":177.8} |
| [templates/siggraph.json](../templates/siggraph.json) | 12 行 | --template 轻量要求预设；{"page_limit":7,"font_pt":9,"margin_mm":18.34,"eq_fleqn_allowed":true,"float_spec":"tbp","microtype":true,"overwide_fig_threshold_mm":179.2,"verbose":false} |
| [templates/sosp.json](../templates/sosp.json) | 8 行 | --template 轻量要求预设；{"page_limit":12,"font_pt":10,"margin_mm":19.05,"overwide_fig_threshold_mm":178.0} |
| [templates/www.json](../templates/www.json) | 12 行 | --template 轻量要求预设；{"page_limit":8,"font_pt":9,"margin_mm":19.05,"eq_fleqn_allowed":true,"float_spec":"tbp","microtype":true,"overwide_fig_threshold_mm":177.8,"verbose":false} |
| [tests/run_tests.py](../tests/run_tests.py) | 2411 行 | texopt 回归测试：单元检查 + 端到端闭环 + 模型在环往返。 |
| [texopt/__init__.py](../texopt/__init__.py) | 12 行 | 包说明与版本 0.2.0；这里的三态出口说明已落后于当前实现。 |
| [texopt/actions.py](../texopt/actions.py) | 1324 行 | 纯字符串排版变换及 TeX 注入块；动作返回新源码、是否改动、说明，由 core 决定是否保留。 |
| [texopt/advise.py](../texopt/advise.py) | 247 行 | 将源码/日志/硬约束残余问题转换成分级建议及建议动作，供模型或作者处理。 |
| [texopt/aesthetic.py](../texopt/aesthetic.py) | 790 行 | 分层稳健异常检测：IQR 标准化、收缩相关矩阵、马氏距离、带外损失及 A_profile。 |
| [texopt/conference.py](../texopt/conference.py) | 406 行 | 16 个 templates-v2 会议档案的来源门控和字段投影；统计值只作合理性参考，未接入项单独登记。 |
| [texopt/core.py](../texopt/core.py) | 1495 行 | 闭环中枢：工程副本、候选顺序、gate 定向修复与暂存链、整篇编译验收、回滚、提案执行及报告落盘。 |
| [texopt/engine.py](../texopt/engine.py) | 391 行 | XeLaTeX/Poppler/SyncTeX 工具探测、超时重试、进程树清理、PDF 总页和正文页区间、原 PDF 裁图。路径守卫目前按 WSL 编写。 |
| [texopt/evalexternal.py](../texopt/evalexternal.py) | 670 行 | E1 源码退化真编译、E2 像素/矢量路径对照、E3 论文聚合、E4 缺陷敏感性与 λ 资格。 |
| [texopt/evalproto.py](../texopt/evalproto.py) | 882 行 | 12.1–12.6 内部评测：指标注入、论文级交叉切分、误报、可分性、稳定性及维度门槛。 |
| [texopt/extract.py](../texopt/extract.py) | 986 行 | pdfminer 字形/文本行/图形提取、4pt 网格版心覆盖、浮动体题注锚定、页面指标和角色输入。 |
| [texopt/page_metrics.py](../texopt/page_metrics.py) | 395 行 | page_metrics.v1 容器、状态、校验、聚合、缺失字段、旧视觉格式适配及 JSON 读写。 |
| [texopt/page_score.py](../texopt/page_score.py) | 246 行 | 用 SyncTeX 将缺陷归属到页，提供 mean/topk/peak 与无法归属项；仅诊断，不参与验收。 |
| [texopt/perceive.py](../texopt/perceive.py) | 903 行 | 源码正则与环境栈解析、日志缺陷解析、卫生扫描、PDF 页数交叉核对及灰度视觉测量，形成 Perception。 |
| [texopt/profile.py](../texopt/profile.py) | 373 行 | 缓存页面指标的分层分位、按论文聚类 bootstrap、可信度、Spearman、相关簇与纯 Python PCA。 |
| [texopt/proposal.py](../texopt/proposal.py) | 166 行 | LLM 请求包输出与嵌套/扁平提案 JSON 规范化；不内置模型 API。 |
| [texopt/requirements.py](../texopt/requirements.py) | 233 行 | Requirement 数据类、5 个内置模板、外置轻量模板、要求文件与运行配置合并。 |
| [texopt/roles.py](../texopt/roles.py) | 173 行 | 跨页规则状态机，识别标题、正文、图页、表页、公式密集、参考文献和附录等角色，并保留结构 flags。 |
| [texopt/score.py](../texopt/score.py) | 695 行 | gate 明细、P 缺陷、I 干预、M1/M2、内容归一化、软指标平滑损失及逐指标跨页聚合。 |
| [texopt/shadow.py](../texopt/shadow.py) | 334 行 | 加载档案、评测门槛和敏感性门，观测 A_profile，生成版本化快照与影子报告；不改变主判定。 |
| [texopt/visual.py](../texopt/visual.py) | 483 行 | PDF 渲染 PNG/PGM、灰度墨迹与空白带指标、像素角色代理、视觉缺陷与报告。 |
| [texopt/weights.py](../texopt/weights.py) | 439 行 | 档案评分权重的消融信噪比、聚类 bootstrap、历史 Bradley–Terry 拟合与权重验收。 |
| [texopt/whitelist.py](../texopt/whitelist.py) | 510 行 | 28 个模型提案动作的注册、参数校验、包装和执行隔离；不负责最终验收。 |
| [texopt/whitespace.py](../texopt/whitespace.py) | 455 行 | 4pt 空白网格、四邻域连通分量、邻接证据和五类留白分类。 |
| [tools/_ink_profile.py](../tools/_ink_profile.py) | 39 行 | 墨迹行剖面：直接看某页 ink 覆盖到页面纵向哪个位置（判断是否压进下边距）。 |
| [tools/_pweight_probe.py](../tools/_pweight_probe.py) | 53 行 | 快速迭代 harness：编译单个构造的 A/B 两版，打印每页字数与告警，不渲染图。 |
| [tools/apply_severity_weights.py](../tools/apply_severity_weights.py) | 164 行 | 回填 P（页面缺陷）比重：把 workbench-severity/result.json 的标定结果落到 score.py。 |
| [tools/calibrate_rho.py](../tools/calibrate_rho.py) | 243 行 | ρ 标定（等边际收益口径）：用闭环实际数据定 W_PAGE_DEFECT。 |
| [tools/corpus_analyze.py](../tools/corpus_analyze.py) | 240 行 | 语料层 Step 1 的分析：从缓存日志+rows 汇总各类指标分布。 |
| [tools/corpus_build.py](../tools/corpus_build.py) | 285 行 | 语料层 Step 1：编译 paperfit-bench-originals 的 200 篇原件，抽缺陷与页面指标。 |
| [tools/detector_check.py](../tools/detector_check.py) | 492 行 | Step 2：检测器体检（注入 → 感知 → 响应方向）。 |
| [tools/make_detector_sheet.py](../tools/make_detector_sheet.py) | 249 行 | Step 2 验收：20 页人工排序表 + 排序一致性（Spearman）。 |
| [tools/make_pair_sheet.py](../tools/make_pair_sheet.py) | 365 行 | Step 2-c：**成对比较**验收表（12 对，每对只点一次），替代整页排序。 |
| [tools/make_pweight_sheet.py](../tools/make_pweight_sheet.py) | 489 行 | P 权重统一标定表：把「人眼可判的缺陷」全部换成同一把尺子（边距 mm）。 |
| [tools/make_severity_sheet.py](../tools/make_severity_sheet.py) | 455 行 | Step 5-a：缺陷**严重度**成对比较表（15 题）——只问「哪个更影响阅读」。 |
| [tools/make_tradeoff_check.py](../tools/make_tradeoff_check.py) | 213 行 | 一致性复核（6 题）：回答两个问题—— |
| [tools/make_tradeoff_sheet.py](../tools/make_tradeoff_sheet.py) | 557 行 | 等边际收益标定表（ρ）—— 生成「缺陷 vs 干预代价」的 15 道二选一题。 |
| [tools/make_tradeoff_v2.py](../tools/make_tradeoff_v2.py) | 372 行 | ρ 第二轮（强化版）：把无差异点钉准，并校准 I 的内部系数。 |
| [tools/pweight_ab_compare.py](../tools/pweight_ab_compare.py) | 82 行 | P 权重回填 A/B：同一批靶稿分别在旧权重（stage 11 human×corpus）与现行权重 |
| [tools/pweight_ab_run.py](../tools/pweight_ab_run.py) | 32 行 | P 权重回填 A/B：同一批靶稿分别在**旧权重**与**现行权重**下跑完整闭环。 |
| [tools/pweight_combine.py](../tools/pweight_combine.py) | 239 行 | P 权重：把多轮标定表的作答合并成一条曲线，估每类缺陷的无差异点 c*。 |
| [tools/rho_ab_compare.py](../tools/rho_ab_compare.py) | 83 行 | ρ A/B：同一份靶稿在 ρ=0.341（旧口径）与 ρ=15（无差异点）下各跑一遍， |
| [tools/rho_ab_run.py](../tools/rho_ab_run.py) | 16 行 | 以指定 ρ 跑 optimize.py（不改源码）：供 tools/rho_ab_compare.py 调用。 |
| [tools/soft_identifiability.py](../tools/soft_identifiability.py) | 333 行 | A_soft 指标**可辨识性体检**（阶段 16，2026-11-02）。 |
| [tools/soft_sensitivity.py](../tools/soft_sensitivity.py) | 180 行 | A_soft 指标**敏感性体检**（阶段 16，2026-11-02）。 |
| [tools/soft_v2_weights.py](../tools/soft_v2_weights.py) | 166 行 | SOFT_SPEC v2 权重：**从客观响应导出**（不再使用人工成对比较 / BT 标定）。 |
| [workbench/patent_draft/build_claims.py](../workbench/patent_draft/build_claims.py) | 195 行 | 生成 14 项权利要求的 DOCX，并检查压缩包、XML、正文回读和页码字段。 |
| [workbench/patent_draft/build_specification.py](../workbench/patent_draft/build_specification.py) | 313 行 | 生成说明书 DOCX、可编辑公式与三张流程/结构图。 |
| [workbench/patent_draft/build_specification_compact.py](../workbench/patent_draft/build_specification_compact.py) | 94 行 | 替换说明书为压缩正文、保留旧稿备份并输出字数统计。 |
| [workbench/patent_draft/compact_word_count.json](../workbench/patent_draft/compact_word_count.json) | 6 行 | 压缩版专利说明书的字数统计，不含图中文字。 |
| [workbench/patent_draft/spec_figure_1.png](../workbench/patent_draft/spec_figure_1.png) | 125871 B | 专利说明书的原理流程/候选验收/系统结构图；review_latest 为 DOCX 嵌图回读副本。 |
| [workbench/patent_draft/spec_figure_2.png](../workbench/patent_draft/spec_figure_2.png) | 97172 B | 专利说明书的原理流程/候选验收/系统结构图；review_latest 为 DOCX 嵌图回读副本。 |
| [workbench/patent_draft/spec_figure_3.png](../workbench/patent_draft/spec_figure_3.png) | 131656 B | 专利说明书的原理流程/候选验收/系统结构图；review_latest 为 DOCX 嵌图回读副本。 |
| [workbench/patent_draft/texopt权利要求书.docx](../workbench/patent_draft/texopt权利要求书.docx) | 42004 B | texopt 专利材料；已核对 ZIP/XML 正文结构及嵌入图片，不属于优化器运行产物。 |
| [workbench/patent_draft/texopt说明书.docx](../workbench/patent_draft/texopt说明书.docx) | 332384 B | texopt 专利材料；已核对 ZIP/XML 正文结构及嵌入图片，不属于优化器运行产物。 |
| [workbench/patent_draft/texopt说明书_压缩前备份.docx](../workbench/patent_draft/texopt说明书_压缩前备份.docx) | 410692 B | texopt 专利材料；已核对 ZIP/XML 正文结构及嵌入图片，不属于优化器运行产物。 |
| `workbench/patent_draft/review_latest/image1.png`（已清理） | 125871 B | 2026-11-19 已清理完全重复的回读副本；保留 [源图 1](../workbench/patent_draft/spec_figure_1.png)。 |
| `workbench/patent_draft/review_latest/image2.png`（已清理） | 97172 B | 2026-11-19 已清理完全重复的回读副本；保留 [源图 2](../workbench/patent_draft/spec_figure_2.png)。 |
| `workbench/patent_draft/review_latest/image3.png`（已清理） | 131656 B | 2026-11-19 已清理完全重复的回读副本；保留 [源图 3](../workbench/patent_draft/spec_figure_3.png)。 |

## 文档内容目录

以下为每份 Markdown 的章节主题；阶段文档是当时记录，最新阶段决定与代码须一并核对。

### AGENTS.md

# AGENTS.md —— texopt 排版优化 Agent；## 定位；## 三层职责（不把所有问题交给 LLM）；## 两级架构；## 标准工作流（对每一份论文）；## 硬约束（与代码同源）；## 白名单动作（可供提案选择，`--list-actions`）；## 出口状态（不要“L=0 就报 CONVERGED”，也不要“没有可接受动作就 DONE”）；## 边界（本版不做）

### README.md

# texopt —— 论文整体排版优化 Agent；## 目录；## 1 当前状态（2026-11-11，阶段 16）；## 2 定位与边界；## 3 设计原则：规则 / 算法 / 模型 / 编译器；## 4 打分：gate + 两条线；### 4.1 gate（一票否决）；### 4.2 `M1 = ρ·P + I`；### 4.3 `M2 = A_soft + λ·A_profile`；### 4.4 标定链：每个数字从哪来；## 5 闭环与验收；## 6 动作体系（28 个白名单动作）；## 7 要求对接：模板 / 会议 / 自定义；## 8 感知层；## 9 模型在环（Model-in-the-loop）；# ① 跑确定性闭环，并输出请求包；#    -> workbench/{paper.tex, report.md, state.json, advisory.json,；#                 llm_request.json, pages/page-*.png, visual.md}；# ② LLM 读 llm_request.json，产出 proposals.json（结构化提案）；# ③ 程序逐条执行：白名单校验 → 应用 → 编译 → 全局验收 → 变差回滚 → 下一轮；## 10 单页诊断：局部 vs 整体；## 11 输出状态；## 12 标定链与实验资产；## 13 仓库结构与数据策略；## 14 测试与回归；## 15 已知局限；## 16 下一步；## 17 文档索引

### SOUL.md

# SOUL.md —— texopt

### datasets/conf-specs/BRIEF_research.md

# BRIEF_research.md —— 会议排版规范调研作业书（子代理用）；## 0. 背景（为什么做）；## 1. 你的产出（只写这些文件，不要碰别人的）；## 2. 每个会议要做的事；### 2.1 找并归档来源（至少覆盖）；### 2.2 写 `conferences/<id>.json`；### 2.3 写 `samples/<id>.samples.list.json`；### 2.4 自查（必须做，直到 0 error）；## 3. 质量要求

### datasets/conf-specs/README.md

# 计算机顶会论文排版规范数据集（texopt dataset）；## 目录结构；## 三级证据强度（对应任务要求的「硬性 / 推荐 / 统计规律」）；## 溯源机制（“不许凭经验臆测”是机器强制的）；## 工具用法；## 与 texopt 模块的对接；### 模板设计与接入（2026-09-12）；## 维护；## 已知局限（诚实声明）；## 工程注意（踩过的坑）

### datasets/conf-specs/SUBAGENT_TASK.md

# SUBAGENT_TASK.md —— 子代理作业单（会议排版规范数据集）；## 你要交付什么；## 硬性规则（会被自动闸门检查）；## 工具；## 已有的归档来源（优先复用，别重复抓）；## 样本论文怎么找、怎么证明（重点，别凭记忆）；## 写 JSON 的要点；## 完成标准

### datasets/conf-specs/analysis/anomalies.md

# 数据异常与冲突清单（自动生成，勿手改）；## 每会议异常计数

### datasets/conf-specs/human/README.md

# 人类成对比较数据（阶段 7 步骤三）；## 文件；## 格式；## 采集工具（阶段 8 新增，2026-10-01）；# 浏览器打开 workbench-eval/pairs_sheet/sheet.html，逐对选择，；# 把页面底部文本框里的 JSON 复制存成 answers.json；## 采集建议（避免权重只学到极端对比）；## 用法

### datasets/conf-specs/metrics/profiles/aesthetic_weights_report.md

# 阶段 7 权重校准报告（方案 10.3 步骤二/三）；## 验收（不劣化才启用）；## 逐维权重（信号 / 噪声 / 信噪比 / 95% CI）；## 步骤三：人类成对比较（Bradley–Terry）

### datasets/conf-specs/metrics/profiles/eval_external.md

# 阶段 8：外部验证（方案 13）；## E1 端到端退化（真实文档 + 真实优化器，真编译）；### neurips-real；### paper-real；### demo-fixture；### issues-fixture；## E2 第二套工具链复测（矢量/文本层 vs 像素层）；## E3 论文级报告；## E4 缺陷敏感性（A_profile 的 λ 前置门）

### datasets/conf-specs/metrics/profiles/eval_report.md

# 阶段 5 评测与验收协议报告（方案 12.1-12.6）；## 12.1 负样本注入（构造性验证）；## 12.2 假阳率（特异性，目标 ≤ 0.05）；## 12.3 会议可分性（有效性 sanity check）；## 12.4 稳定性与可复现性；## 12.5 与人类判断的相关性（探索性）；## 12.6 验收门槛（逐指标）

### datasets/conf-specs/metrics/profiles/shadow_summary.md

# 阶段 4 影子评估摘要（全库，in-sample）；## A_profile 最高的 15 篇（归因自查：应为真的版面异常篇）；## 疑似合订本/结构异常篇（26 篇，已排除出统计）；## 人工核对队列（阶段 6；档内相对 A_profile 前 10）

### datasets/conf-specs/metrics/profiles/summary.md

# 审美档案摘要（阶段 2 自动生成）；## 各会议 × 页面角色（样本量与可信度）；## 高相关指标组（同一现象，需去冗余）；## 相关性最强的前 15 对；## PCA 主成分（标准化后）；## 马氏判定块（阶段 4）

### datasets/conf-specs/schema/KEY_VOCAB.md

# KEY_VOCAB —— 受控字段表（数据集契约）；## 0. 顶层结构；## 1. Entry（约束条目）；## 2. hard_constraints / recommended 允许的键；## 3. Stat（统计量，来自真实论文样本测量）；## 4. Change（逐年变化）；## 5. Source（来源）；## 6. texopt_requirement_map

### datasets/conf-specs/summary/cross-conf-summary.md

# 跨会议排版规范总结（人工汇总）；## 0. 覆盖范围与证据分级；## 1. 硬性要求的跨会议对比（结论）；## 2. 真实论文的统计规律（实测，非规则）；## 3. 哪些规则可以抽象为 texopt 的通用规则；## 4. 已知局限（诚实声明）

### datasets/conf-specs/summary/cross-conf-table.md

# 跨会议硬性要求速查表（自动生成，勿手改）；## 实测统计（真实论文样本，自动生成）

### datasets/conf-specs/summary/link-repair-report.md

# 样本链接修复报告

### datasets/conf-specs/summary/sample-link-check.md

# 样本 PDF 链接可用性检查（自动生成）

### datasets/conf-specs/summary/template-design-report.md

# 会议排版模板设计报告（16 会议 · 数据驱动）；## 0. 交付物与复现；## 1. 统一模板 Schema；## 2. 从数据到字段：生成规则；## 3. 16 个会议模板设计；### 3.1 NeurIPS（NeurIPS 2025，ml）；### 3.2 ICML（ICML 2025，ml）；### 3.3 ICLR（ICLR 2025，ml）；### 3.4 ACL（ACL 2025，nlp）；### 3.5 EMNLP（EMNLP 2025，nlp）；### 3.6 CVPR（CVPR 2025，cv）；### 3.7 ICCV（ICCV 2025，cv）；### 3.8 ECCV（ECCV 2026，cv）；### 3.9 AAAI（AAAI-25，ai）；### 3.10 IJCAI（IJCAI 2025，ai）；### 3.11 SIGGRAPH（SIGGRAPH 2025，graphics）；### 3.12 KDD（KDD 2025，data）；### 3.13 WWW（WWW 2026，data）；### 3.14 OSDI（OSDI '25，systems）；### 3.15 SOSP（SOSP 2025，systems）；### 3.16 NSDI（NSDI '25，systems）；## 4. 跨会议横向结论；## 5. 数据异常与可信度说明；### 5.1 任务点名的三项检查；### 5.2 其他异常（逐样本，全部保留在 `analysis/anomalies.md`）；### 5.3 系统性不可靠字段（已在每个模板 `confidence.unreliable_fields` 列出）；### 5.4 可信度分级；### 5.5 已知数据缺口（未做，不假装做了）；## 6. 与 texopt 的对接；## 7. 后续建议（按性价比排序）

### datasets/conf-specs/summary/template-matrix.md

# 16 会议模板速查表（自动生成，勿手改）

### datasets/conf-specs/summary/texopt-integration-report.md

# 会议模板 → texopt 接入现状（自动生成，勿手改）；## 1. 已接入的字段（会议 json → texopt Requirement）；### 字段来源与依据（每会议）；## 3. 模板是怎么进入优化过程的（代码路径）；## 4. 暂时没有用上的内容汇总；## 2. 暂未接入的内容（明确记录，不强行加入）；### 匿名要求：texopt 没有匿名检查/清理动作（不在白名单）（16）；### 已用于 typography.body_font_pt 投影（不重复接入）（16）；### 栏数：需改 documentclass（texopt 明确不改文档类）（16）；### 题注字号/位置等细节：本版无对应动作（不改 caption 样式），仅作参考（16）；### 几何观测值与版心尺寸：仅作参考（texopt 只消费 margin_floor_mm）（16）；### 浮动体统计与位置先验：仅作参考（texopt 只消费 float_spec 与超宽阈值）（16）；### 样本统计量：只用于『排版是否合理』的参考核对，不作硬约束（16）；### 设计期优化建议（priority/actions/avoid/unsupported）：供人工与后续自动化消费（16）；### 可信度元信息（样本量/可靠字段/冲突）：供报告展示（16）；### 来源清单：溯源信息（16）；### 字段级 basis 登记：溯源信息（16）；### 统计口径：溯源信息（16）；### 生成器信息：溯源信息（16）；### 题注字号与位置：本版无对应动作（只比对，不改）（16）；### 四边边距明细：已折算为 margin_floor_mm（不对称边距需后续字段支持）（15）；### 纸张尺寸：需改文档类/geometry 选项（后续阶段）（15）；### 版心宽：仅作参考（set_margin 只改边距，不改版心）（15）；### 附录政策：texopt 不改内容，仅记录（13）；### 栏间距：需改文档类/宏包（后续阶段）（13）；### 参考文献风格：需换 .bst/宏包，属跨文档类迁移（后续阶段）（11）；### 页码策略：需改模板页脚/样式（后续阶段）（11）；### 录用后加页规则：本次按投稿版口径，不加页（11）；### 附录计页：仅用于口径说明（9）；### 标题格式：需改文档类/模板（后续阶段）（8）；### 字体族：需换文档类/宏包（跨类迁移，后续阶段）（8）；### 版心高：仅作参考（6）；### checklist：texopt 不生成也不检查（内容层，不在白名单）（5）；### 行距：当前无对应白名单动作（属版心参数）（5）；### 浮动体规则描述：已部分体现为 float_spec，其余为文字说明（2）；### 摘要字数限制：属内容层，texopt 不改内容（2）；### 图题位置：无对应动作（不改 caption 样式）（1）；### 表题位置：无对应动作（1）；### 四边最小边距：texopt 压页下限，不得低于此值：basis=sample-stat 不是官方来源（仅 ('official', 'template-implied', 'inferred')），按任务要求不作硬约束（1）

### datasets/conf-specs/tools/crawl/README.md

# tools/crawl —— 论文样本爬取（与既有 107 篇同一格式）；## 一条命令链条；# 0) 一次性：准备 PDF 依赖（本机无 pip，走纯 wheel 解包）；# 1) 抓候选清单（每会一条；索引页自动归档为 src-<conf>-<year>-proceedings）；# 2) 入库（归档落地页 + 生成 sample-paper 来源 + 追加样本；可中断，重跑续跑）；# …其余会议同上，逐个替换 --conference；# 3) 闸门（不通过就别继续）；# 若仍有不可用：先体检再修；# 4) 测量 + 统计 + 生成 texopt 模板（先按会议跑，最后可全量重跑）；# python3 tools/build_dataset.py          # 全量 16 会一起重算；# 5) 模板链 + 安装进 texopt；## 支持的会议（Tier A：官方索引页一页拿全量直链）；## 关键约定；## 常用参数；## 坏链怎么办（`fix_links.py`）；## 防呆（默认开启）；## 耗时参考（单机串行）

### docs/PROJECT_MAP.md

# texopt 项目地图（PROJECT_MAP）；## 1. 五层结构（先建立心智模型）；## 2. L1 可执行核心；### 2.0 入口；### 2.1 闭环主干（修改→编译→验收）；### 2.2 量化与打分（"模型"的数学部分）；### 2.3 要求 / 模板；### 2.4 视觉 / 页面感知（审美量化的证据层）；### 2.5 审美模型（model2 的后半段）；### 2.6 评测协议（证明"模型有效"的部分）；## 3. L2 配置与预设；## 4. 测试与靶稿；## 5. L3 数据资产；### 5.1 `datasets/conf-specs/` —— 会议排版规范数据集（5698 文件）；### 5.2 `paperfit-bench-originals/` —— 真实论文原件（7895 文件）；## 6. L4 标定产物：`metrics/*.json`（10 个）；## 7. L4 标定工具：`tools/*.py`（21 个）；## 8. L5 文档：`docs/`（69 文件）；## 9. L5 实验/工作台产物（**这些都是可再生的，不是资产**）；## 10. 一次运行的调用链（谁在什么时候被用）；## 11. 关于"太庞大"：哪些是模型，哪些不是

### docs/README.md

# docs 索引；## 现行规范（看这三份就够）；## 阶段记录（历史证据，不是现行口径）；## 其他；## 已删除（2026-10-31 清理，可从 git 历史取回）

### docs/corpus_fields_plain_20261026.md

# 语料层 Step 1：每一项数据到底是什么意思（大白话版）；## 0　先懂三件事，后面全通；## 1　表 1 逐项说明（采集了什么）；### 1.1　标识与元数据（这部分只是"这行数据是谁"）；### 1.2　编译结果（4 项）；### 1.3　规模（1 项）；### 1.4　缺陷计数（9 项，这一节最重要）；#### ① `overfull`（行溢出 / 内容戳出版心）；#### ② `underfull`（行欠满 / 字间距被拉稀）；#### ③ `vbox_over`（页盒溢出 / 一页塞不下）；#### ④ `vbox_under`（页盒欠满 / 一页没填满）；#### ⑤ `floatwarn`（浮动体警告）；#### ⑥ `warn`（其它警告）；#### ⑦ `errors`（真错误）；#### ⑧ `macros_missing`（质量宏缺失）；#### ⑨ `float_H`（强制就地放置 `[H]`）；### 1.5　缺陷幅度（比"有没有"更关键的一层）；### 1.6　页面像素指标（11 项，model2 的原料）；### 1.7　日志样本（`warn_samples`）；## 2　表 2 六个分析项逐个说明；### 2.1　论文规模；### 2.2　缺陷频率；### 2.3　缺陷幅度；### 2.4　软指标分位；### 2.5　现有带命中率；### 2.6　卫生与工程；## 3　表 3 那些"没分析"的，为什么没分析；## 4　几个统计说法的大白话解释；## 5　这一步确认的三个 bug（都要在 Step 2 修）；## 6　术语速查

### docs/corpus_inventory_20261026.md

# 语料层 Step 1：数据清单与已做分析（2026-10-26）；## 表 1　采集了什么（每篇 1 行，每页 1 条）；## 表 2　分析了什么（6 组）；## 表 3　采集了但这一步**没有**分析（明确留白）；## 三个已确认的口径 bug（Step 2 待修）

### docs/page_metrics_v1.md

# page_metrics.v1 —— 页面级指标数据结构规范；## 1. 目的与边界；## 2. 顶层结构；### 2.1 `doc`；### 2.2 `pages[]`；### 2.3 `whitespace.regions[]`（空白区域）；### 2.4 `paper`；## 3. status 取值；## 4. 校验与工具函数；## 5. 阶段 0 的实际填充情况；## 6. 版本演进约定

### docs/stage0_visual_inventory.md

# 阶段 0 交付：visual.py 盘点 + 指标—现状—缺口表；## 1. 盘点范围与口径；## 2. 指标—现状—缺口表；### 2.1 Density 页面密度；### 2.2 Ratio 图文关系；### 2.3 Balance 页面平衡；### 2.4 Whitespace 留白；### 2.5 Alignment 对齐；### 2.6 Consistency 一致性；### 2.7 Page Rhythm 页面节奏；### 2.8 Readability 可读性；### 2.9 Micro-typography 微观排版；### 2.10 Figure Quality 图件质量；### 2.11 分层、统计与模型（方案第五、九、十、十一章）；### 2.12 数据与基础设施；## 3. 汇总；## 4. 实测验证（阶段 0 跑通）；## 5. 阶段 0 发现的问题与修复；### 5.1 工作副本命名三处不同步（真 bug，影响「模型在环」）；### 5.2 脏工作区污染 → 基线被误判「无法编译」；### 5.3 测试遇到 FAILED 直接崩（KeyError 'l'）；### 5.4 像素量去重；### 5.5 回归结果；### 5.6 两个待你决定的问题（未动）；## 6. 阶段 0 结论与阶段 1 建议顺序

### docs/stage10_a_soft_smooth_form_20261028.md

# Step 2-b：A_soft 软指标改成「平滑目标」形式（2026-10-28）；## 1　改了什么；### 1.1 旧形式（2026-09 ~ 10-27）；### 1.2 新形式（`texopt/score.py` `SOFT_SPEC` + `soft_metric_loss()`）；## 2　改完的复测（同一批 20 页、同一份人排序）；## 3　诚实的边界；## 4　下一步；## 5　复现

### docs/stage10b_pair_sheet_20261028.md

# Step 2-c：成对比较验收表（2026-10-28）；## 1　怎么用；## 2　题目是怎么挑的（`tools/make_pair_sheet.py`）；## 3　判分口径（`--import answers.json`）；## 4　为什么成对比较比排序更省事也更可信；## 5　复现；## 6　第一轮实测（2026-10-28 10:43）与改进；### 6.1 三条可读出的信息；### 6.2 第二轮配对（已按以下规则重建，2026-10-28 10:52）；## 7　第二轮实测（2026-10-28 11:38）：**通过**；### 7.1 两处仍需注意；### 7.2 验收口径建议（写进后续文档）

### docs/stage11_severity_sheet_20261028.md

# Step 5-a：缺陷严重度标定（2026-10-28）；## 1　只问「人眼能看见」的 10 类；## 2　题目设计（`tools/make_severity_sheet.py`）；## 3　估计方法：Bradley-Terry + Jeffreys 先验；## 4　频率项（语料，200 篇 / 3898 页）；## 5　权重公式（带阻尼）；## 6　边界与后续；## 7　复现；## 8　实测结果（2026-10-28 13:34，`answers (3).json`）；### 8.1 尺度问题（重要）；### 8.2 回填前必须做的验证

### docs/stage12_gate_exit_two_lines_20261030.md

# 阶段 12：gate 一票否决 + 两线分离 + P 权重回填 + ρ 等边际收益（2026-10-30）；## 1　任务1：gate 一票否决（入口门，不是分数项）；## 2　任务2：两线分离（model1 / model2 并行，不相加）；## 3　任务3：P 权重回填（数据来源）；## 4　ρ：等边际收益（用闭环实测数据定）；## 5　实测；### 5.1 ρ 实测（2026-10-30，4 篇真编译闭环）；### 5.2 gate 退出实测（`python3 optimize.py … --target N`）；### 5.3 全量回归（2026-10-30 19:05）；### 5.4 已知边界

### docs/stage13_rho_tradeoff_20261031.md

# 阶段 13：ρ 的无差异点重标定（0.341 → 15，2026-10-31）；## 1　为什么旧口径不行；## 2　新方法：无差异点（等边际收益）；## 3　口径含义；## 4　重标定后的影响（A/B 实测，2026-11-01）；## 5　待办（下一步）；## 6　复现

### docs/stage14_pweight_unified_20261102.md

# 阶段 14：P 权重的「同一把尺子」标定（2026-11-02）；## 1　问题：P 的内部结构是两张皮；## 2　方法：两轮阶梯 + 翻转区间；## 3　结果；## 4　口径 A：为什么缩放；## 6　回填后的行为 A/B（2026-11-02，`tools/pweight_ab_compare.py`）；## 7　局限（必须写进论文）；## 8　复现

### docs/stage15_local_global_20261102.md

# 阶段 15：单页打分 / 整篇打分（局部 vs 整体，2026-11-02）；## 1　连档压页：机制 bug；### 1.1 现象；### 1.2 修法：暂存链（provisional chain）；### 1.3 验证（`s14/plateau-*`，9 项）；## 2　单页打分：为什么需要，怎么加；### 2.1 问题；### 2.2 归因：日志缺陷怎么落到页上；### 2.3 三种读法（同一份数据，不替人做选择）；### 2.4 边界：这一层**不改判定**；## 3　还没定的三件事（需要拍口径，才敢动公式）

### docs/stage16_model2_metrics_20261102.md

# 阶段 16：model2 指标重选（可辨识性 + 敏感性双体检，2026-11-02）；## 1　两个体检的分工；## 2　可辨识性：篇内损失极差（不是原始值）；## 3　敏感性：坏版面下谁有反应；## 4　SOFT_SPEC v2 草案；## 5　角色代理（已实现）；## 6　下一步

### docs/stage17_no_human_calibration_20261111.md

# 阶段 17 前置决定：不再新增人工打分类标定（2026-11-11）；## 1 现在有哪些东西是靠人打分的；## 2 替代方案：四类客观信号；## 3 影响分析：为什么这次改动风险不大；## 4 已落地（本阶段）；## 5 修订后的阶段 17 计划（无人工环节）；## 6 诚实边界

### docs/stage1_role_and_extraction.md

# 阶段 1 交付：页面角色标注 + 页面级指标提取；## 1. 交付物；## 2. 关键口径（精确定义，方案第六章的落地）；## 3. 角色标注规则（方案第五章 5.1）；## 4. 提取覆盖矩阵（阶段 1 后）；## 5. 实测；### 5.1 两个典型靶子（抽查）；### 5.2 全库（608 篇 / 10538 页）；## 6. 阶段 1 修掉的 5 个真 bug（都是实测暴露的）；## 7. 已知局限与阶段 2 校准清单；## 8. 复现命令

### docs/stage2_profile.md

# 阶段 2 交付：审美档案（正常范围）+ 去冗余；## 1. 档案做了什么（一句话）；## 2. 档案结构；## 3. 统计口径（必须说清，否则不可复现）；## 4. 去冗余（`redundancy.json`）；## 5. 用分布做的 3 项校准（阶段 1 遗留清单的落地）；### 5.1 角色阈值改为由分布定；### 5.2 角色优先级调整：整页图/表提到参考文献、附录之前；### 5.3 对齐指标按行类型拆分；## 6. 实测（608 篇 / 10538 页）；### 6.1 语料与角色分布（校准后）；### 6.2 各会议 × 页面角色：样本量与可信度；### 6.3 去冗余（|ρ| ≥ 0.8）；### 6.4 代表档的正常区间（抽检）；## 7. 已知局限；## 8. 复现命令

### docs/stage3_whitespace.md

# 阶段 3 交付：留白结构化识别（五类 + region 列表）；## 1. 一句话；## 2. 五类留白（口径）；## 3. 算法（方案 7.2 的落地）；## 4. 阈值（都可复算，全部是几何量）；## 5. 输出示例；## 6. 页眉/页脚识别（阶段 1 遗留 L5，本次一并做掉）；## 7. 阶段 3 修掉的真 bug（都由实测暴露，非猜测）；## 8. 实测；## 9. 已知局限与后续；## 10. 复现命令

### docs/stage4_aesthetic_profile.md

# 阶段 4 交付：多维异常检测（马氏距离）+ 非单调带外损失 A_profile（影子模式）；## 1. 一句话；## 2. 三个量；## 3. 分层与回退链（方案 5.2 / 5.3）；## 4. 稳健化（本机无 numpy/scipy，全部手写）；## 5. 构建期 vs 在线；## 6. 影子模式接入（13.1 / 13.2 / 13.4 / 13.5）；## 7. 被实测纠正的口径（都是真问题，不是设想）；## 8. 全库影子评估（in-sample，口径须谨慎引用）；## 9. 测试（22 项，全部纯逻辑）；## 10. 复现命令；# 关闭影子：TEXOPT_NO_SHADOW=1；## 11. 已知局限与后续（对应方案第十二、十四章）

### docs/stage5_eval_protocol.md

# 阶段 5 交付：评测与验收协议（方案 12.1-12.6）；## 1. 一句话；## 2. 协议实现（`texopt/evalproto.py`）；## 3. 结果；### 12.1 负样本注入；### 12.2 假阳率（目标 ≤ 5%）；### 12.3 会议可分性；### 12.4 稳定性与可复现性；### 12.5 与人类判断的相关性；### 12.6 验收门槛结论；## 4. 阶段 5 修掉的真问题（都是协议跑出来的，不是设想）；## 5. 测试（22 项，纯逻辑）；## 6. 复现命令；## 7. 已知局限与后续

### docs/stage6_shadow_integration.md

# 阶段 6 交付：影子模式接入 texopt（λ = 0，仅报告）；## 1. 一句话；## 2. 口径（13.1）；## 3. 接入点（唯一的、顺序上安全的）；## 4. 产物；## 5. 开关与用法；# 只看影子报告，不优化（基线编译一次，四处不改文档）；# 正常优化（默认带影子观测）；# 关闭影子（离线/受限环境或纯确定性回归）；# 用别的档案（例如消融实验的档案）；## 6. 逐维门槛（阶段 5 的联动）；## 7. 人工核对清单（阶段 6 的正式产出动作）；## 8. 实测片段（回归靶稿，`_regress/s6_run_on`）；## 9. 已知局限

### docs/stage7_weight_calibration.md

# 阶段 7 交付：审美权重校准（方案 10.3 步骤二/三）；## 1. 一句话；## 2. 步骤二：消融校准怎么算的；## 3. 结果（80 组试验，bootstrap 200 次）；## 4. 验收（不劣化才启用）；## 5. 步骤三：人类成对比较（Bradley–Terry）；# 人填完后：把答案 JSON 导入 -> human/pairs.json；# 最后一步才会把 aesthetic_weights.json 变成 ablation+human；## 6. λ 的状态（重要，别误读）；## 7. 本阶段修掉的真问题（都是实测暴露）；## 8. 测试（11 项）；## 9. 复现命令；## 10. 已知局限（不包装）

### docs/stage8_eval_external.md

# 阶段 8：外部验证（方案 13）；## 1. E1 端到端退化（真实文档 + 真实优化器，真编译）；### 1.1 设计；### 1.2 关键修正：必须记录「修复前」的一组量；### 1.3 结果（2026-10-01 终态：干净工作区 + 修正 (a) + 人类权重已挂回档案；2470.4s）；### 1.4 三条结论（含两条负面结果）；### 1.5 归因（2026-10-01 补做，两个负面结果都说清楚了）；#### A. 为什么 `paper-real` 不单调且修复不完全；#### B. 为什么 A_profile 对退化不敏感；# 产出 workbench-eval/profile_attr/attr_profile.json；### 1.6 诚实边界；## 2. E2 第二套工具链复测（矢量/文本层 vs 像素层）；### 2.1 口径；### 2.2 结果（12 篇真实论文 × 每篇前 8 页，dpi 50）；### 2.3 两个真结论（都不是「两套工具链分歧」）；### 2.4 局限；## 3. E3 论文级报告（回应阶段 7 局限 L4：池化稀释）；### 3.1 方法；### 3.2 结果（60 篇真实论文，复用缓存页指标，λ=0）；### 3.3 局限；## 4. 一句话总结（按实际测量值）；## 5. 依据归因做的两处修复（2026-10-01）；### 5.1 （a）验收口径：A 优先，I 只做 tie-break；### 5.2 （b）λ 前置门：把“缺陷敏感”与“常态偏离”拆开；### 5.3 测量可复现性：残留 `.aux` 会改变 A（2026-10-01 补修）；### 5.4 两个修复的联带效果；## 6. 复现命令；# E1 端到端退化（真编译；每篇 干净 + 4 档，约 30-60 分钟）；# E2 第二套工具链（12 篇 × 8 页，dpi 50，约 2-3 分钟）；# E3 论文级报告（离线，秒级）；# E1 归因：A_profile 逐维分解（每个退化档只编译一次，不分档跑闭环；约 5-8 分钟）；# 三段结果合并写入 metrics/profiles/eval_external.{json,md}

### docs/stage9_detector_check_20261027.md

# Step 2：检测器体检（2026-10-27）；## 0　这一步在干什么（大白话）；## 1　合成图注入：量得准不准；## 2　日志注入：缺陷认得全不全；## 3　真实语料：正常范围写得对不对；## 4　`band` 的判决：暂缓；## 5　结论表；## 6　本步改动清单；## 7　人工排序验收（唯一还需要人的一步）；## 8　还没做的；## 9　边界（诚实说明）

### docs/aesthetic/README.md

# 审美量化模型（model2：A_soft + A_profile）；## 1. 它是什么，在系统里的位置；## 2. 诚实边界（先看这段，再看数字）；## 3. 快速开始；# ① 只跑影子评估（λ=0，只出报告，不改文档）；#    -> workbench/aesthetic_shadow.md / aesthetic_shadow.json；# ② 正常优化（默认带影子观测，可用 --no-aesthetic-shadow 关掉）；# ③ 结构化审美体检（指标精度 / 日志覆盖率 / 语料区间）；# ④ 回归（含 s6 开关影子判定一致性、s12 权重 artifact 漂移检查）；## 4. 数据模型：`page_metrics.v1`；## 5. `A_soft`：绝对软指标（平滑目标形式）；### 5.1 公式；### 5.2 现行参数（`SOFT_SPEC`）；### 5.3 为什么不是"带内一律 0"；## 6. 页面视觉缺陷（像素层，单独检测）；## 7. 分层：页面角色与留白分类；## 8. `A_profile`：档案 + 马氏距离 + 带外损失（λ=0）；## 9. 标定与验证：每一层都问过"凭什么是这个数"；### 阶段 5 协议结果（自洽性，不等于"与人类审美一致"）；### 外部验证里两条负面结果（必须保留）；## 10. 复现命令；# 全库指标提取（矢量/文本层；--pixels 追加像素层，慢很多）；# 重算档案（分位 + 聚类 bootstrap；--no-ci 跳过）；# 协议评测 12.1-12.6（--render 额外做渲染层注入 + 重编译稳定性）；# 权重校准（消融 80 组 + bootstrap 200）；# 人工数据：成对比较 / 严重度；# 外部验证与归因；## 11. 文件与产物索引；## 12. 已知局限与下一步

### docs/notes/frequency_weighting_idea_20261016.md

短篇想法/约定，无分节标题。

### docs/scoring/README.md

# 打分模型（gate + model1 + model2）；## 1. 一句话；## 2. 为什么不是单一总分（三次修正的教训）；## 3. gate：底层逻辑门；### 3.1 检查项；### 3.2 页数口径（避免误伤合法论文）；### 3.3 gate 定向修复（可修项的一次机会）；## 4. model1：`M1 = ρ·P + I`；### 4.1 P：页面缺陷（半硬性）；### 4.2 ρ：缺陷 ↔ 代价的汇率；### 4.3 I：干预代价；### 4.4 参考终态（阶段 12，真编译）；## 5. model2：`M2 = A_soft + λ·A_profile`；### 5.5　单页打分 / 整篇打分（阶段 15，2026-11-02）；## 6. 验收规则（`core.py: _accept`）；## 7. 字段与产物；## 8. 复现与自检；# 回归（含 s12：gate 结构化完整性 / gate 修复动作面 / 无 total 字段 /；#            验收无补偿 / 权重 artifact 对齐 / ρ 中位与裁剪）；# 权重 artifact 漂移检查；# ρ 的人工无差异标定（生成 15 题 → 人填 → 解 ρ）；# ρ 的历史口径（闭环平均代价，仅作交叉参考）；# gate 行为验证：不可达页数 → BLOCKED_GATE（0 个动作可试 + 建议）；## 9. 已知局限

### examples/README.md

# examples/ —— 靶稿（fixtures）；## 靶稿清单与预期出口状态；## 其它

### metrics/soft_identifiability_20261102.md

# A_soft 指标可辨识性体检（2026-11-02）；## 1　判定表；## 2　冗余（body 页，Spearman |ρ| ≥ 0.8）；## 3　全页秩相关矩阵（含页类型混杂）；## 4　读法

### skills/latex-opt/SKILL.md

# texopt 整体排版优化（确定性闭环 + 模型在环）；## 标准流程；## 结构 / 版面规范（可配置）；## 图形保真（重要）；# 输出可直接落地的：\includegraphics[width=124.0bp]{figs/fig1.png}；## 红线

### templates/README.md

# templates/ —— 期刊/会议排版要求预设；## 字段说明（全部可选，缺省 = 不约束/不干预）；## 边界说明（当前版）；## 自定义要求文件；## 结构 / 版面规范字段（2026-09-10 新增）

