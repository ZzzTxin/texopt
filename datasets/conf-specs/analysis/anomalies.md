# 数据异常与冲突清单（自动生成，勿手改）

来源：`tools/analyze_templates.py`，扫描 `samples/_measurements/*.json` 与各会议官方条目。
规则：只记录，不修改原始数据。

| 会议 | 样本 | 类型 | 说明 |
|---|---|---|---|
| neurips | s-neurips-2024-001 | refs_zero | refs=0 → 参考文献区未被识别（多为 PDF 缺 bookmarks/线条），非论文真的没有参考文献 |
| neurips | s-neurips-2024-004 | content_pages_implausible | content_pages=2 明显偏小，疑为正文页定位失败 |
| neurips | s-neurips-2024-004 | fig_width_frac_gt_1 | fig_width_frac_median=1.021 > 1：该类图片几何宽超过单栏/版心基准，实际多为跨栏或整版图，不能当“超宽违规”处理 |
| iclr | s-iclr-2025-006 | refs_zero | refs=0 → 参考文献区未被识别（多为 PDF 缺 bookmarks/线条），非论文真的没有参考文献 |
| acl | s-acl-2025-001 | fig_width_frac_gt_1 | fig_width_frac_median=1.304 > 1：该类图片几何宽超过单栏/版心基准，实际多为跨栏或整版图，不能当“超宽违规”处理 |
| acl | s-acl-2025-002 | fig_width_frac_gt_1 | fig_width_frac_median=1.308 > 1：该类图片几何宽超过单栏/版心基准，实际多为跨栏或整版图，不能当“超宽违规”处理 |
| acl | s-acl-2025-002 | body_font_mismatch | 实测正文 9.0pt ≠ 官方/模板 11pt |
| acl | s-acl-2025-003 | content_pages_implausible | content_pages=2 明显偏小，疑为正文页定位失败 |
| acl | s-acl-2025-003 | fig_width_frac_gt_1 | fig_width_frac_median=1.309 > 1：该类图片几何宽超过单栏/版心基准，实际多为跨栏或整版图，不能当“超宽违规”处理 |
| acl | s-acl-2025-004 | fig_width_frac_gt_1 | fig_width_frac_median=1.311 > 1：该类图片几何宽超过单栏/版心基准，实际多为跨栏或整版图，不能当“超宽违规”处理 |
| acl | s-acl-2025-005 | fig_width_frac_gt_1 | fig_width_frac_median=1.307 > 1：该类图片几何宽超过单栏/版心基准，实际多为跨栏或整版图，不能当“超宽违规”处理 |
| acl | s-acl-2025-006 | fig_width_frac_gt_1 | fig_width_frac_median=1.310 > 1：该类图片几何宽超过单栏/版心基准，实际多为跨栏或整版图，不能当“超宽违规”处理 |
| acl | s-acl-2025-007 | fig_width_frac_gt_1 | fig_width_frac_median=1.310 > 1：该类图片几何宽超过单栏/版心基准，实际多为跨栏或整版图，不能当“超宽违规”处理 |
| emnlp | s-emnlp-2025-001 | fig_width_frac_gt_1 | fig_width_frac_median=1.313 > 1：该类图片几何宽超过单栏/版心基准，实际多为跨栏或整版图，不能当“超宽违规”处理 |
| emnlp | s-emnlp-2025-002 | fig_width_frac_gt_1 | fig_width_frac_median=1.306 > 1：该类图片几何宽超过单栏/版心基准，实际多为跨栏或整版图，不能当“超宽违规”处理 |
| emnlp | s-emnlp-2025-003 | fig_width_frac_gt_1 | fig_width_frac_median=1.306 > 1：该类图片几何宽超过单栏/版心基准，实际多为跨栏或整版图，不能当“超宽违规”处理 |
| emnlp | s-emnlp-2025-004 | fig_width_frac_gt_1 | fig_width_frac_median=1.306 > 1：该类图片几何宽超过单栏/版心基准，实际多为跨栏或整版图，不能当“超宽违规”处理 |
| emnlp | s-emnlp-2025-005 | fig_width_frac_gt_1 | fig_width_frac_median=1.303 > 1：该类图片几何宽超过单栏/版心基准，实际多为跨栏或整版图，不能当“超宽违规”处理 |
| emnlp | s-emnlp-2025-006 | fig_width_frac_gt_1 | fig_width_frac_median=1.310 > 1：该类图片几何宽超过单栏/版心基准，实际多为跨栏或整版图，不能当“超宽违规”处理 |
| emnlp | s-emnlp-2025-007 | fig_width_frac_gt_1 | fig_width_frac_median=1.308 > 1：该类图片几何宽超过单栏/版心基准，实际多为跨栏或整版图，不能当“超宽违规”处理 |
| cvpr | s-cvpr-2025-001 | fig_width_frac_gt_1 | fig_width_frac_median=1.236 > 1：该类图片几何宽超过单栏/版心基准，实际多为跨栏或整版图，不能当“超宽违规”处理 |
| cvpr | s-cvpr-2025-002 | fig_width_frac_gt_1 | fig_width_frac_median=1.236 > 1：该类图片几何宽超过单栏/版心基准，实际多为跨栏或整版图，不能当“超宽违规”处理 |
| cvpr | s-cvpr-2025-003 | fig_width_frac_gt_1 | fig_width_frac_median=1.234 > 1：该类图片几何宽超过单栏/版心基准，实际多为跨栏或整版图，不能当“超宽违规”处理 |
| cvpr | s-cvpr-2025-004 | fig_width_frac_gt_1 | fig_width_frac_median=1.234 > 1：该类图片几何宽超过单栏/版心基准，实际多为跨栏或整版图，不能当“超宽违规”处理 |
| cvpr | s-cvpr-2025-005 | fig_width_frac_gt_1 | fig_width_frac_median=1.230 > 1：该类图片几何宽超过单栏/版心基准，实际多为跨栏或整版图，不能当“超宽违规”处理 |
| cvpr | s-cvpr-2025-006 | fig_width_frac_gt_1 | fig_width_frac_median=1.236 > 1：该类图片几何宽超过单栏/版心基准，实际多为跨栏或整版图，不能当“超宽违规”处理 |
| cvpr | s-cvpr-2025-007 | fig_width_frac_gt_1 | fig_width_frac_median=1.236 > 1：该类图片几何宽超过单栏/版心基准，实际多为跨栏或整版图，不能当“超宽违规”处理 |
| cvpr | s-cvpr-2025-008 | fig_width_frac_gt_1 | fig_width_frac_median=1.236 > 1：该类图片几何宽超过单栏/版心基准，实际多为跨栏或整版图，不能当“超宽违规”处理 |
| iccv | s-iccv-2025-001 | fig_width_frac_gt_1 | fig_width_frac_median=1.236 > 1：该类图片几何宽超过单栏/版心基准，实际多为跨栏或整版图，不能当“超宽违规”处理 |
| iccv | s-iccv-2025-002 | fig_width_frac_gt_1 | fig_width_frac_median=1.236 > 1：该类图片几何宽超过单栏/版心基准，实际多为跨栏或整版图，不能当“超宽违规”处理 |
| iccv | s-iccv-2025-003 | fig_width_frac_gt_1 | fig_width_frac_median=1.236 > 1：该类图片几何宽超过单栏/版心基准，实际多为跨栏或整版图，不能当“超宽违规”处理 |
| iccv | s-iccv-2025-004 | fig_width_frac_gt_1 | fig_width_frac_median=1.236 > 1：该类图片几何宽超过单栏/版心基准，实际多为跨栏或整版图，不能当“超宽违规”处理 |
| iccv | s-iccv-2025-005 | fig_width_frac_gt_1 | fig_width_frac_median=1.236 > 1：该类图片几何宽超过单栏/版心基准，实际多为跨栏或整版图，不能当“超宽违规”处理 |
| iccv | s-iccv-2025-006 | fig_width_frac_gt_1 | fig_width_frac_median=1.236 > 1：该类图片几何宽超过单栏/版心基准，实际多为跨栏或整版图，不能当“超宽违规”处理 |
| iccv | s-iccv-2025-007 | fig_width_frac_gt_1 | fig_width_frac_median=1.236 > 1：该类图片几何宽超过单栏/版心基准，实际多为跨栏或整版图，不能当“超宽违规”处理 |
| iccv | s-iccv-2025-008 | fig_width_frac_gt_1 | fig_width_frac_median=1.236 > 1：该类图片几何宽超过单栏/版心基准，实际多为跨栏或整版图，不能当“超宽违规”处理 |
| eccv | s-eccv-2024-001 | refs_zero | refs=0 → 参考文献区未被识别（多为 PDF 缺 bookmarks/线条），非论文真的没有参考文献 |
| eccv | s-eccv-2024-002 | refs_zero | refs=0 → 参考文献区未被识别（多为 PDF 缺 bookmarks/线条），非论文真的没有参考文献 |
| aaai | s-aaai-2025-001 | fig_width_frac_gt_1 | fig_width_frac_median=1.214 > 1：该类图片几何宽超过单栏/版心基准，实际多为跨栏或整版图，不能当“超宽违规”处理 |
| aaai | s-aaai-2025-002 | fig_width_frac_gt_1 | fig_width_frac_median=1.214 > 1：该类图片几何宽超过单栏/版心基准，实际多为跨栏或整版图，不能当“超宽违规”处理 |
| aaai | s-aaai-2025-003 | fig_width_frac_gt_1 | fig_width_frac_median=1.214 > 1：该类图片几何宽超过单栏/版心基准，实际多为跨栏或整版图，不能当“超宽违规”处理 |
| aaai | s-aaai-2025-004 | fig_width_frac_gt_1 | fig_width_frac_median=1.214 > 1：该类图片几何宽超过单栏/版心基准，实际多为跨栏或整版图，不能当“超宽违规”处理 |
| aaai | s-aaai-2025-005 | fig_width_frac_gt_1 | fig_width_frac_median=1.214 > 1：该类图片几何宽超过单栏/版心基准，实际多为跨栏或整版图，不能当“超宽违规”处理 |
| aaai | s-aaai-2025-006 | fig_width_frac_gt_1 | fig_width_frac_median=1.214 > 1：该类图片几何宽超过单栏/版心基准，实际多为跨栏或整版图，不能当“超宽违规”处理 |
| ijcai | s-ijcai-2025-001 | fig_width_frac_gt_1 | fig_width_frac_median=1.213 > 1：该类图片几何宽超过单栏/版心基准，实际多为跨栏或整版图，不能当“超宽违规”处理 |
| ijcai | s-ijcai-2025-002 | fig_width_frac_gt_1 | fig_width_frac_median=1.214 > 1：该类图片几何宽超过单栏/版心基准，实际多为跨栏或整版图，不能当“超宽违规”处理 |
| ijcai | s-ijcai-2025-003 | fig_width_frac_gt_1 | fig_width_frac_median=1.214 > 1：该类图片几何宽超过单栏/版心基准，实际多为跨栏或整版图，不能当“超宽违规”处理 |
| ijcai | s-ijcai-2025-004 | fig_width_frac_gt_1 | fig_width_frac_median=1.205 > 1：该类图片几何宽超过单栏/版心基准，实际多为跨栏或整版图，不能当“超宽违规”处理 |
| ijcai | s-ijcai-2025-005 | fig_width_frac_gt_1 | fig_width_frac_median=1.214 > 1：该类图片几何宽超过单栏/版心基准，实际多为跨栏或整版图，不能当“超宽违规”处理 |
| ijcai | s-ijcai-2025-006 | fig_width_frac_gt_1 | fig_width_frac_median=1.214 > 1：该类图片几何宽超过单栏/版心基准，实际多为跨栏或整版图，不能当“超宽违规”处理 |
| ijcai | s-ijcai-2025-007 | fig_width_frac_gt_1 | fig_width_frac_median=1.214 > 1：该类图片几何宽超过单栏/版心基准，实际多为跨栏或整版图，不能当“超宽违规”处理 |
| siggraph | s-siggraph-2024-001 | fig_width_frac_gt_1 | fig_width_frac_median=1.129 > 1：该类图片几何宽超过单栏/版心基准，实际多为跨栏或整版图，不能当“超宽违规”处理 |
| kdd | s-kdd-2024-006 | fig_width_frac_gt_1 | fig_width_frac_median=1.131 > 1：该类图片几何宽超过单栏/版心基准，实际多为跨栏或整版图，不能当“超宽违规”处理 |
| www | s-www-2024-004 | content_pages_over_limit | content_pages=26 > 官方上限 8 + 6：可能是 camera-ready/附录并入，也可能定位偏差；按冲突保留不修改 |
| www | s-www-2024-004 | columns_mismatch | 实测 columns=1 ≠ 官方/模板 columns=2（可能为整版跨栏图导致行首聚类偏移） |
| www | s-www-2024-004 | body_font_mismatch | 实测正文 12.0pt ≠ 官方/模板 9pt |
| sosp | s-sosp-2025-001 | paper_size_mismatch | 实测 paper_size=letter ≠ 官方 a4 or letter |
| sosp | s-sosp-2025-002 | content_pages_over_limit | content_pages=40 > 官方上限 12 + 6：可能是 camera-ready/附录并入，也可能定位偏差；按冲突保留不修改 |
| sosp | s-sosp-2025-002 | columns_mismatch | 实测 columns=1 ≠ 官方/模板 columns=2（可能为整版跨栏图导致行首聚类偏移） |
| sosp | s-sosp-2025-002 | paper_size_mismatch | 实测 paper_size=a4 ≠ 官方 a4 or letter |
| sosp | s-sosp-2025-003 | content_pages_implausible | content_pages=1 明显偏小，疑为正文页定位失败 |
| sosp | s-sosp-2025-003 | paper_size_mismatch | 实测 paper_size=letter ≠ 官方 a4 or letter |
| sosp | s-sosp-2025-004 | paper_size_mismatch | 实测 paper_size=letter ≠ 官方 a4 or letter |
| sosp | s-sosp-2025-005 | paper_size_mismatch | 实测 paper_size=letter ≠ 官方 a4 or letter |
| sosp | s-sosp-2025-006 | paper_size_mismatch | 实测 paper_size=letter ≠ 官方 a4 or letter |
| sosp | s-sosp-2024-001 | paper_size_mismatch | 实测 paper_size=letter ≠ 官方 a4 or letter |

## 每会议异常计数

| 会议 | 样本数 | 异常数 |
|---|---|---|
| neurips | 6 | 3 |
| icml | 6 | 0 |
| iclr | 6 | 1 |
| acl | 7 | 9 |
| emnlp | 7 | 7 |
| cvpr | 8 | 8 |
| iccv | 8 | 8 |
| eccv | 6 | 2 |
| aaai | 6 | 6 |
| ijcai | 7 | 7 |
| siggraph | 7 | 1 |
| kdd | 6 | 1 |
| www | 7 | 3 |
| osdi | 6 | 0 |
| sosp | 7 | 10 |
| nsdi | 7 | 0 |
