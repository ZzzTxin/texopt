---
name: latex-opt
description: 用 texopt 对 LaTeX 论文做整体排版优化（期刊模板/自定义要求/页数限制），确定性闭环 + LLM 模型在环提案，正文语义零改动。
---

# texopt 整体排版优化（确定性闭环 + 模型在环）

定位：论文**整体排版**优化（Page Limit 只是要求规格之一）。三层职责：
Layer 1 硬约束→规则；Layer 2 可量化质量→程序搜索；Layer 3 整体布局/审美→LLM。

原则：**规则负责底线，算法负责搜索，模型负责复杂判断，编译器负责现实验证。**
Model-in-the-loop = LLM 真正进入「感知→判断→修改→编译→验证→再判断」循环，
**不是**让 LLM 一次性改论文。

## 标准流程

1. 读目标 `.tex`（只读），选要求来源：
   `--template <id>` / `--require my-reqs.json` / `--target N`（可叠加）。
   结构/版面规范另行指定（也可用 `--template report` 一键）：
   ```bash
   python3 optimize.py paper.tex --toc --header --heading-color 0,62,120
   python3 optimize.py paper.tex --template report
   ```
2. 跑确定性闭环 **并输出请求包**：
   ```bash
   python3 optimize.py <paper.tex> --template X [--require Y] [--target N] --emit-request
   ```
   产出 `workbench/`：`paper.tex`、`report.md`、`state.json`、`advisory.json`、
   `llm_request.json`、`pages/page-*.png`、`visual.md`。
   闭环自动处理：断行质量宏、fleqn、浮动体参数（含 `[H]` 解绑）、超宽图
   （含相对超宽 `1.18\linewidth`）、裸 `$$`、字号/边距硬性规范、
   目录页/页眉（要求开启时属 L）、标题着色、阅读辅助内容与 WARNING 告示块
   定点删除，以及**正文排版卫生**（对应动作）：
   - `remove_manual_pagebreak`：删正文 `\newpage`/`\clearpage`
   - `remove_excessive_vspace`：删过大的 `\vspace{...}`
   - `normalize_local_font_size`：删正文行内字号乱标
   - `normalize_heading_size`：标题字号压回层级上限
   - `reduce_list_spacing`：收紧列表 `itemsep/topsep/parsep`
   - `add_hyphenation_points`：超长不可断词插 `\-` 断点
   - `break_long_urls`：长 URL 注入 `xurl`（允许任意位置断行）
   - `fix_table_width`：超宽表格改 tabularx（自适应列宽）
   - `balance_pages`：注入 `\raggedbottom` 改善页面平衡
   每条都整篇重编译后全局重评，变差即回滚。
3. 读 `llm_request.json`（状态 + 残余问题 + 可用动作 + 页面图）与
   `advisory.json`。对**难以用规则决定**的问题（留白/视觉重心/图该浮到哪或多大/
   图文关系）写成 `proposals.json`：
   ```json
   {"schema": "texopt.proposals/v1", "round": 1,
    "assessment": "整体判断…",
    "proposals": [{"id": "p1", "issue": "page_balance", "location": "page 5",
      "severity": "moderate", "reason": "下半页空白过大",
      "proposal": {"action": "set_float_spec", "target": "figure#2",
                   "params": {"spec": "tbp"}}}]}
   ```
   动作只能用 `--list-actions` 的白名单（否则 BLOCKED）；不改正文/不编内容/不跑 shell。
4. 执行提案（程序逐条：白名单校验→应用→编译→全局验收→变差回滚，再出下轮请求）：
   ```bash
   python3 optimize.py paper.tex --proposals proposals.json --emit-request
   ```
5. 多轮往返直到 `DONE` / `CONVERGED` / `NO_IMPROVEMENT` / `EXHAUSTED` / `BLOCKED`；
最多 5 轮失败后停下来汇报。出口状态含义：`DONE`= 应用了被接受的动作；
`CONVERGED`= 无可动候选；`NO_IMPROVEMENT`= 有候选但全都没改善（未改任何内容，
不伪造“优化成功”）；`EXHAUSTED`= 仍缺 L。
   只想核对某次手工编辑时用：
   ```bash
   python3 optimize.py workbench/paper.tex --verify --original <原稿.tex>
   ```
   通过标准：`语义内容保留：通过`（正文文字/词序/标点/公式/引用零变化，
   排版命令与空白差异不计——这是**归一化文本保持检查**，不声称语义等价证明）
   且 L=0。

## 结构 / 版面规范（可配置）

| 能力 | 要求字段（默认） | 归属 |
|---|---|---|
| 目录页 | `toc`(False) / `toc_min_sections`(3) | L（要求开启时） |
| 页眉 | `running_header`(False) / `header_left`/`header_right` | L（要求开启时） |
| 标题着色 | `heading_color`(None，如 `0,62,120`) | A |
| 阅读辅助清理 | `strip_reading_aids`(**True**) | 元信息清理 |
| 告示块清理 | `remove_warning_boxes`(**True**) | 元信息清理 |
| 图形保真 | `preserve_figures`(**True**) | L |

## 图形保真（重要）

图**不得重绘或改写**：禁止用 TikZ 重画、禁止换算坐标轴/量纲、禁止改数据点。
需要重建/嵌图时，从**原稿 PDF 裁切原图原样嵌入**：

```bash
python3 optimize.py --extract-fig 原稿.pdf --page 3 \
    --box 308,112,432,258 --out figs/fig1.png --dpi 400
# 输出可直接落地的：\includegraphics[width=124.0bp]{figs/fig1.png}
```

闭环把每个 figure/table 的内容指纹（宽度/位置参数归一）与 `--original`
对照，不一致即 L 违规「图形/表格内容被改动」，并给 `figure_unpreserved`
建议。裁切框单位为 pt，原点在页面左上角。

## 红线
- 正文语义零改动：可删/改**排版命令**（手动分页/过大 `\vspace`/行内字号/
  断词点 `\-`/列表间距选项/表格列格式）与浮动体参数/图宽，不可删改**正文
  文字、词序、标点、公式、引用、图表内容**——除非用户明确批准（语义抛光
  属第三期，需用户在场）。这是**归一化文本保持检查**，不声称证明语义等价。
- **LLM 不能随意改论文**：提案只能命中白名单动作；未知动作 → BLOCKED；
  不跑任意 shell、不改任意文件。
- **元信息清理只认已知模式**：`START READING HERE`、
  `document order was not finalized`、行首 `WARNING:/CAUTION:/ATTENTION:`
  告示。它们不是论文正文，属可删项；除此之外任何文字删除都算内容改动。
- 原件（输入 .tex）只读，永远只编辑 workbench/ 副本。
- 不编造：不知道图表内容就不补题注；不虚构引用/数据/结论。
- 表格超宽等结构性问题：给建议，等作者决策。
- 页数：默认不动全局版心（--tune-geometry 才授权）；超页给建议不硬压。
- 诚实标注：A 是**排版质量/审美代理**（非人类审美评分）；视觉代理指标
  为**实验性且未并入 A**；不声称全局最优。
