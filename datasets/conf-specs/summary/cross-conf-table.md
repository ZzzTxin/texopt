# 跨会议硬性要求速查表（自动生成，勿手改）

数值均取自 `conferences/*.json` 的 `hard_constraints`（每条可回溯到官方来源）。
`—` = 未在该会议官方材料中找到明文/未收录。

| 会议 | page_limit_content | page_limit_total | references_counted | appendix_counted | paper_size | columns | body_font_size_pt | bib_style | anonymity | figure_caption_position | table_caption_position | page_numbering |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| AAAI | 7 | — | False | — | letter | 2 | 10 | author-year | double-blind | below | below | none (no page numbers, headers or footers) |
| ACL | 8 | — | False | False | a4 | 2 | 11 | acl_natbib | double-blind | — | — | review-numbered; final unnumbered |
| CVPR | 8 | — | False | — | letter | 2 | 10 | — | double-blind | — | — | review version numbered, camera-ready no page numbers |
| ECCV | 14 | — | False | — | — | 1 | 10 | splncs04 | double-blind | — | — | — |
| EMNLP | 8 | — | False | False | a4 | 2 | 11 | acl_natbib | double-blind | — | — | review-numbered; final unnumbered |
| ICCV | 8 | — | False | — | letter | 2 | 10 | — | double-blind | — | — | review version numbered, camera-ready no page numbers |
| ICLR | 10 | — | False | False | letter | 1 | 10 | author-year | double-blind | — | — | no page numbers; submission carries a running header and line-numbered ruler |
| ICML | 8 | — | False | False | letter | 2 | 10 | author-year | double-blind | — | — | — |
| IJCAI | 7 | 9 | True | — | letter | 2 | 10 | named (author-year) | double-blind | — | — | none (line numbers required for review) |
| KDD | 8 | 12 | False | False | letter | 2 | 9 | ACMReferenceFormat | double-blind | — | — | — |
| NeurIPS | 9 | — | False | False | letter | 1 | 10 | natbib | double-blind | — | — | — |
| NSDI | 12 | — | False | False | letter | 2 | 10 | — | double-blind | — | — | numbered |
| OSDI | 12 | — | False | — | letter | 2 | 10 | — | double-blind | — | — | numbered |
| SIGGRAPH | 7 | 10 | False | False | letter | 2 | 9 | ACMReferenceFormat | double-blind | — | — | numbered with paper ID (submission) |
| SOSP | 12 | — | False | — | a4 or letter | 2 | 10 | — | double-blind | — | — | numbered |
| WWW | 8 | 12 | False | True | letter | 2 | 9 | ACMReferenceFormat | double-blind | — | — | — |

## 实测统计（真实论文样本，自动生成）

| 会议 | 样本数 | 栏数 | 版心宽(pt) | 正文字号(pt) | 左边距(mm) | 图/篇 | 表/篇 | 公式/篇 | 参考文献/篇 |
|---|---|---|---|---|---|---|---|---|---|
| AAAI | 6 | 2 | 504.0 | 10.0 | 19.0 | 6.167 | 3.333 | 9.0 | 20.667 |
| ACL | 7 | 2 | 454.9 | 11.0 | 24.7 | 8.286 | 10.0 | 9.571 | 9.714 |
| CVPR | 8 | 2 | 495.0 | 10.0 | 20.6 | 5.75 | 4.0 | 4.875 | 52.625 |
| ECCV | 6 | 1 | 345.8 | 10.0 | 47.6 | 5.5 | 5.167 | 8.0 | 1.0 |
| EMNLP | 7 | 2 | 455.7 | 11.0 | 24.7 | 5.714 | 12.714 | 4.714 | 14.429 |
| ICCV | 8 | 2 | 495.0 | 10.0 | 20.6 | 6.0 | 4.125 | 11.5 | 69.875 |
| ICLR | 6 | 1 | 396.0 | 10.0 | 38.1 | 9.667 | 6.333 | 20.333 | 4.0 |
| ICML | 6 | 2 | 487.15 | 10.0 | 19.2 | 11.833 | 6.667 | 56.833 | 2.667 |
| IJCAI | 7 | 2 | 504.0 | 10.0 | 19.0 | 2.714 | 3.286 | 6.571 | 2.143 |
| KDD | 6 | 2 | 505.1 | 9.0 | 18.75 | 5.333 | 6.0 | 12.667 | 52.333 |
| NeurIPS | 6 | 1 | 396.95 | 10.0 | 37.8 | 9.167 | 6.833 | 8.0 | 44.333 |
| NSDI | 7 | 2 | 505.4 | 10.0 | 18.6 | 16.571 | 1.286 | 3.429 | 66.857 |
| OSDI | 6 | 2 | 504.95 | 10.0 | 18.75 | 13.333 | 2.333 | 0.0 | 88.333 |
| SIGGRAPH | 7 | 2 | 508.9 | 9.0 | 18.1 | 11.714 | 1.571 | 10.857 | 3.429 |
| SOSP | 7 | 1/2 | 504.8 | 10.0 | 18.8 | 14.571 | 4.571 | 1.714 | 73.429 |
| WWW | 7 | 1/2 | 504.9 | 9.0 | 18.8 | 7.286 | 7.429 | 20.857 | 43.571 |
