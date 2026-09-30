# 阶段 4 影子评估摘要（全库，in-sample）

- 论文：582/608 篇可判定；档案 v2；用时 16s
- 阶段 5 门槛（12.6）：剔除维度 readability.leading_ratio、density.coverage_table
- ⚠ in-sample：语料页即档案构建数据，D² 偏小、异常率偏低，**不能**当假阳率结论（阶段 5 做正式协议）

| 会议 | 篇 | 页 | A_profile 中位 | A_profile P90 | 异常页率 | 疑似合订本 |
|---|---|---|---|---|---|---|
| aaai | 36 | 321 | 0.7286410000000001 | 1.0848505 | 0.07477 | 0 |
| acl | 67 | 1245 | 0.835398 | 1.5921110000000005 | 0.12289 | 3 |
| cvpr | 68 | 726 | 0.764094 | 1.242045 | 0.08953 | 0 |
| eccv | 36 | 635 | 1.2859615 | 2.5106535 | 0.06457 | 0 |
| emnlp | 66 | 1109 | 1.033555 | 1.6407238000000004 | 0.1587 | 7 |
| iccv | 68 | 747 | 0.890251 | 1.4235190000000002 | 0.09103 | 0 |
| iclr | 6 | 151 | 0.937432 | 1.32776 | 0.09272 | 0 |
| icml | 62 | 1333 | 0.97094 | 1.4795338 | 0.10578 | 7 |
| ijcai | 66 | 577 | 0.777122 | 1.141751 | 0.08319 | 0 |
| kdd | 6 | 80 | 0.865621 | 1.21852 | 0.1 | 0 |
| neurips | 37 | 982 | 1.1811585 | 1.5720796 | 0.12322 | 9 |
| nsdi | 45 | 895 | 1.085196 | 2.0878408 | 0.12961 | 0 |
| osdi | 24 | 469 | 1.089181 | 1.7555265999999998 | 0.17058 | 0 |
| siggraph | 7 | 81 | 0.606202 | 1.4297114 | 0.07407 | 0 |
| sosp | 7 | 165 | 0.990028 | 1.3467462000000001 | 0.05455 | 0 |
| www | 7 | 105 | 1.168952 | 1.5320132000000002 | 0.15238 | 0 |

## A_profile 最高的 15 篇（归因自查：应为真的版面异常篇）

| 论文 | 会议 | 页 | A_profile | 档内相对 | D² P90 | 异常页 |
|---|---|---|---|---|---|---|
| s-nsdi-2024-025 | nsdi | 21 | 6.36145 | 5.862 | 85.142652 | 10 |
| s-cvpr-2024-002 | cvpr | 10 | 5.974963 | 7.8197 | 52.26158029999999 | 5 |
| s-icml-2024-016 | icml | 24 | 3.485911 | 3.5902 | 19.914692399999993 | 4 |
| s-eccv-2022-013 | eccv | 16 | 3.166282 | 2.4622 | 12.4275485 | 3 |
| s-nsdi-2025-004 | nsdi | 18 | 2.87212 | 2.6466 | 27.07401090000002 | 3 |
| s-eccv-2022-016 | eccv | 18 | 2.670293 | 2.0765 | 7.371714900000001 | 1 |
| s-nsdi-2024-013 | nsdi | 19 | 2.606466 | 2.4018 | 43.469460999999995 | 5 |
| s-eccv-2022-012 | eccv | 17 | 2.55557 | 1.9873 | 7.6370818 | 1 |
| s-emnlp-2025-031 | emnlp | 22 | 2.517635 | 2.4359 | 27.185507200000032 | 4 |
| s-eccv-2022-007 | eccv | 17 | 2.510724 | 1.9524 | 8.622106000000002 | 2 |
| s-eccv-2022-014 | eccv | 17 | 2.510583 | 1.9523 | 9.4401098 | 1 |
| s-eccv-2022-027 | eccv | 19 | 2.500811 | 1.9447 | 4.47562 | 1 |
| s-iccv-2025-014 | iccv | 10 | 2.476103 | 2.7814 | 31.413611199999956 | 3 |
| s-eccv-2022-004 | eccv | 16 | 2.472239 | 1.9225 | 5.3706055 | 1 |
| s-eccv-2022-029 | eccv | 20 | 2.377262 | 1.8486 | 3.7687969 | 1 |

## 疑似合订本/结构异常篇（26 篇，已排除出统计）

| 论文 | 会议 | 页 | A_profile |
|---|---|---|---|
| s-acl-2025-012 | acl | 46 | 7.985903 |
| s-icml-2025-031 | icml | 29 | 2.113264 |
| s-neurips-2024-010 | neurips | 30 | 1.954866 |
| s-neurips-2024-018 | neurips | 42 | 1.717264 |
| s-icml-2025-017 | icml | 25 | 1.654891 |
| s-neurips-2024-019 | neurips | 43 | 1.414271 |
| s-emnlp-2025-010 | emnlp | 31 | 1.235106 |
| s-emnlp-2024-027 | emnlp | 36 | 1.200148 |
| s-icml-2025-014 | icml | 57 | 1.197448 |
| s-neurips-2024-021 | neurips | 43 | 1.170751 |

## 人工核对队列（阶段 6；档内相对 A_profile 前 10）

逐条核对：①最偏离维度是否有可见问题（无可见问题 → 疑假阳，记台账）②最异常页是否真实异常（而非数据/合订本问题）

| 论文 | 会议 | 档内相对 | A_profile | 最偏离维度（倍率） | 最异常页（角色/主因） |
|---|---|---|---|---|---|
| s-cvpr-2024-002 | cvpr | 7.8197 | 5.974963 | balance.visual_centroid_y=14.819763；whitespace.total_ratio=7.997402；balance.d_mid=6.953749 | p1 title/balance.visual_centroid_y |
| s-nsdi-2024-025 | nsdi | 5.862 | 6.36145 | balance.visual_centroid_y=13.349608；whitespace.total_ratio=11.972863；balance.d_mid=8.364487 | p3 body/balance.visual_centroid_y |
| s-icml-2024-016 | icml | 3.5902 | 3.485911 | balance.visual_centroid_y=8.602913；density.coverage_text=5.393188；whitespace.total_ratio=4.061209 | p3 body/balance.visual_centroid_y |
| s-iccv-2025-014 | iccv | 2.7814 | 2.476103 | density.coverage_text=3.569653；balance.d_mid=3.191167；balance.visual_centroid_y=2.991236 | p1 title/density.coverage_text |
| s-ijcai-2024-006 | ijcai | 2.7423 | 2.131087 | balance.visual_centroid_y=3.723774；ratio.fig_text=3.472891；balance.d_mid=2.08795 | p1 title/density.coverage_text |
| s-nsdi-2025-004 | nsdi | 2.6466 | 2.87212 | balance.d_mid=4.939584；balance.visual_centroid_y=4.117198；whitespace.total_ratio=3.81387 | p1 title/balance.d_mid |
| s-siggraph-2025-002 | siggraph | 2.4871 | 1.507655 | ratio.fig_text=2.976375；alignment.center_var=2.011923；density.coverage_text=1.832304 | p1 title/whitespace.total_ratio |
| s-acl-2025-023 | acl | 2.4736 | 2.066469 | balance.visual_centroid_y=4.662126；balance.d_mid=2.515678；density.coverage_text=1.974199 | p4 body/balance.visual_centroid_y |
| s-eccv-2022-013 | eccv | 2.4622 | 3.166282 | balance.visual_centroid_y=10.795019；balance.d_mid=2.20896；alignment.center_var=2.020558 | p1 title/balance.d_mid |
| s-emnlp-2025-031 | emnlp | 2.4359 | 2.517635 | alignment.center_var=6.576907；balance.visual_centroid_y=3.631752；balance.d_mid=2.15123 | p5 body/balance.d_mid |
