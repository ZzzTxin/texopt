# examples/ —— 靶稿（fixtures）

这批 `.tex` 是 texopt 的**固定靶子**，只读，供 `tests/run_tests.py` 的集成检查与
README 快速开始使用。

> 教训：这批靶稿曾经整批丢失（工作区、git 历史、归档 zip 里都没有），导致套件里
> 5 项集成检查长期只能 SKIP（见 `docs/stage0_visual_inventory.md` 第 8 节）。
> 现在**靶稿 + 生成脚本一起进 git**；再丢的话：

```bash
python3 examples/gen_fixtures.py    # 重建全部靶稿（纯标准库，纯 ASCII）
```

## 靶稿清单与预期出口状态

| 文件 | 内容 | 默认要求下的出口状态 |
|---|---|---|
| `demo.tex` | 干净稿：单栏 10pt/a4/25.4mm，自然 **6 页** | `DONE`（只注入质量宏，L=0，无 high 视觉缺陷） |
| `issues.tex` | 只埋 4 类**规则可修**问题：`\vspace{2cm}` / 正文 `\newpage` / 裸 `$$` / `[H]` 浮动体（外加一处 `\underline` 仅报告） | `DONE`（5 个动作被接受） |
| `chaos.tex` | 12 类常见混乱（手动分页/间距/字号、`[h]`/`[H]`、超宽图、`\hline`+booktabs 混用、长词…） | `DONE`（`--full`） |
| `nightmare.tex` | 27 类排版灾难（`fleqn`、`\linespread{1.7}`、负 `\vspace`、巨型图、多栏、页眉过长…） | `NEEDS_REVIEW`（`--full`；确定性修复做完后仍留 high 视觉缺陷，如实上报） |
| `aidtest.tex` | 阅读辅助内容 + 2 处 WARNING 告示块 + 超宽图 | `DONE`（删辅助/告示 + 图归一） |
| `fig_violation.tex` | `aidtest.tex` 的**图形保真反例**：把那张图重绘成 TikZ | `verify()` 必须报「图形内容被改动」的 L 违规 |
| `propose_target.tex` | 模型在环靶稿：40mm 边距（版心 130mm）+ 图宽 140mm（低于 150mm 超宽阈值，规则闭环不动它） | `DONE`；供 `apply_proposals` 的接受/回滚/BLOCKED 三态验证 |

状态由 `tests/run_tests.py` 的 `fixtures` 列表锁定（2026-09-30 按实测值写入）。
改靶稿内容就必须重跑并同步这里的预期值 —— 否则回归会红，这是刻意的。

## 其它

- `test0911/`、`test0913/`、`NeurlPS examples/`：更早的整篇实验稿（会议模板/范围/真实论文），
  不是脚本生成，内容较大，保持原样。
- `gen_fixtures.py` 生成的正文段落是英文的：避免 CJK 字体依赖，xelatex + Latin Modern
  即可编译；图形统一用 mwe 包的 `example-image`（TeX Live 自带）。
