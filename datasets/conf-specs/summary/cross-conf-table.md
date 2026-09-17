# 跨会议硬性要求速查表（自动生成，勿手改）

数值均取自 `conferences/*.json` 的 `hard_constraints`（每条可回溯到官方来源）。
`—` = 未在该会议官方材料中找到明文/未收录。

| 会议 | page_limit_content | page_limit_total | references_counted | appendix_counted | paper_size | columns | body_font_size_pt | bib_style | anonymity | figure_caption_position | table_caption_position | page_numbering |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| EMNLP | 8 | — | False | False | a4 | 2 | 11 | acl_natbib | double-blind | — | — | review-numbered; final unnumbered |
| ICML | 8 | — | False | False | letter | 2 | 10 | author-year | double-blind | — | — | — |
| NeurIPS | 9 | — | False | False | letter | 1 | 10 | natbib | double-blind | — | — | — |

## 实测统计（真实论文样本，自动生成）

| 会议 | 样本数 | 栏数 | 版心宽(pt) | 正文字号(pt) | 左边距(mm) | 图/篇 | 表/篇 | 公式/篇 | 参考文献/篇 |
|---|---|---|---|---|---|---|---|---|---|
| EMNLP | 66 | 1/2 | 454.85 | 11.0 | 24.7 | 7.576 | 8.939 | 5.773 | 8.652 |
| ICML | 62 | 2 | 487.2 | 10.0 | 19.2 | 10.548 | 6.855 | 24.323 | 5.484 |
| NeurIPS | 37 | 1 | 397.3 | 10.0 | 37.7 | 8.486 | 5.973 | 20.081 | 51.784 |
