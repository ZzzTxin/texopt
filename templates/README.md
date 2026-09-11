# templates/ —— 期刊/会议排版要求预设

每个 `.json` 对应一个模板 id，用法：

```bash
python3 optimize.py paper.tex --template my-journal
```

## 字段说明（全部可选，缺省 = 不约束/不干预）

| 字段 | 含义 | 示例 |
|---|---|---|
| `name` / `desc` | 展示用，不参与优化 | — |
| `font_pt` | 硬性要求字号档（10/11/12），不符会作为 L 违规修复 | `10` |
| `page_limit` | 页数上限（L 硬约束），排版手段优先，穷尽才语义抛光 | `8` |
| `margin_mm` | 硬性要求等效单边页边距（mm） | `20.0` |
| `float_spec` | 浮动体位置参数规范，`[h]`/`[h!]` 等不稳定写法会被规范化 | `"tbp"` |
| `eq_fleqn_allowed` | `false` = 公式必须居中（移除 fleqn 选项） | `false` |
| `enable_quality_macros` | 注入断行质量宏（孤行寡行/连字符/溢出缓解） | `true` |
| `overwide_fig_threshold_mm` | 插图数值宽度超过此值自动归一 `\linewidth` | `120.0` |
| `overwide_table_report` | 超宽表格检测并写入报告（不自动改） | `true` |
| `margin_min_mm` / `margin_step_mm` | 压页时页边距下限/步长 | `20.0` / `2.0` |
| `allow_fontsize_step` | 压页时允许字号降到要求档以下（下限 10pt） | `true` |

## 边界说明（当前版）

- 只做排版面优化，**不改任何正文内容**（文字/公式/图表内容，机器 diff 校验）；
- 跨文档类模板迁移（如 article → IEEEtran/cvpr 类）与版式级重排
  （双栏、页眉页脚、参考文献格式）属后续阶段；
- 孤行寡行的像素级检测、留白审美需页面图像视觉层（advanced 多源判断阶段），
  当前以编译日志 vbox 信号 + 断行质量宏作为代理。

## 自定义要求文件

`--require` 指向任意 JSON，字段同上，比模板优先级高，可与模板叠加：

```bash
python3 optimize.py paper.tex --template ieee --require my-reqs.json
```

`my-reqs.json` 示例：

```json
{
  "name": "我的投稿要求",
  "page_limit": 6,
  "font_pt": 11,
  "margin_mm": 21.0,
  "float_spec": "tb",
  "overwide_fig_threshold_mm": 110.0
}
```

## 结构 / 版面规范字段（2026-09-10 新增）

| 字段 | 默认 | 含义 | 归属 |
|---|---|---|---|
| `toc` / `toc_min_sections` | False / 3 | 目录页（要求开启时属 L） | L |
| `running_header` / `header_left` / `header_right` | False | 页眉 | L |
| `heading_color` | None | 标题强调色（如 `"0,62,120"`） | A |
| `strip_reading_aids` | True | 删阅读辅助内容 | 元信息 |
| `remove_warning_boxes` | True | 删 WARNING 告示块 | 元信息 |
| `preserve_figures` | True | 图形保真（不得重绘/改写） | L |

内置 `report` 模板 = 目录+页眉+彩色标题+元信息清理一键组合。

> 模型在环：无论来自哪个模板，LLM 只能通过 `--list-actions` 里的白名单动作
> 提出修改；具体见 README「模型在环」一节。
