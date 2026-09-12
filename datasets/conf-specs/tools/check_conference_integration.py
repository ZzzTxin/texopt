#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_conference_integration.py —— 记录「会议模板 → texopt」的接入现状。

只读：用 texopt.conference 逐个加载 templates-v2/*.json，输出
  summary/texopt-integration-report.md
   - 每会议：投影进 Requirement 的字段（含来源路径与 basis）
   - 未接入的字段：按原因分组（接不上的内容一律明确记录，不强行接入）

用法: python3 tools/check_conference_integration.py
"""
import json
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                 # datasets/conf-specs
REPO = os.path.dirname(os.path.dirname(ROOT))  # texopt 仓库根
sys.path.insert(0, REPO)

from texopt import conference as C           # noqa: E402

OUT = os.path.join(ROOT, "summary", "texopt-integration-report.md")


def main() -> int:
    rows = C.list_conferences()
    lines = ["# 会议模板 → texopt 接入现状（自动生成，勿手改）", "",
             f"- 模板目录：`{C.templates_dir()}`（共 {len(rows)} 个会议）",
             "- 接入方式：`python3 optimize.py paper.tex --conference <id>`",
             "- 原则：**官方硬约束 → 违规判定（L）；真实论文统计 → 合理性参考（不入 L、不影响评分）；"
             "接不上的字段逐条记录**。",
             "- 生成：`python3 tools/check_conference_integration.py`", ""]

    # ---- 投影总表 ----
    lines += ["## 1. 已接入的字段（会议 json → texopt Requirement）", "",
              "| 会议 | 页数上限 | 页数口径 | 字号 | 边距下限 | 浮动体 | 超宽图阈值 | 公式居中 | 质量宏 |",
              "|---|---|---|---|---|---|---|---|---|"]
    deferred_all = defaultdict(list)
    for r in rows:
        p = C.load(r["id"])
        f = p.requirement_fields
        lines.append("| {} | {} | {} | {} | {} | {} | {} | {} | {} |".format(
            p.id, f.get("page_limit"), p.page_limit_scope, f.get("font_pt"),
            f.get("margin_mm", "—（未接入）") if f.get("margin_mm") is not None else "—（未接入）",
            f.get("float_spec"),
            f.get("overwide_fig_threshold_mm"), f.get("eq_fleqn_allowed"),
            f.get("enable_quality_macros")))
        for d in p.deferred:
            deferred_all[d["reason"]].append(f"{p.id}:{d['path']}")
    lines.append("")
    lines += ["### 字段来源与依据（每会议）", "",
              "| 会议 | 字段 | 模板路径 | basis |", "|---|---|---|---|"]
    for r in rows:
        p = C.load(r["id"])
        for fld, src in p.field_sources.items():
            lines.append(f"| {p.id} | `{fld}` | `{src['path']}` | {src['basis']} |")
    lines.append("")

    # ---- 未接入 ----
    lines += ["", "## 3. 模板是怎么进入优化过程的（代码路径）", "",
              "```",
              "python3 optimize.py paper.tex --conference aaai",
              "  │",
              "  ├─ texopt.conference.load('aaai')        # 读 templates-v2/aaai.json",
              "  │    PROJECTIONS 表：json 路径 → Requirement 字段（带 basis 门控）",
              "  │      L 字段只接受 basis ∈ {official, template-implied, inferred}",
              "  │      其余（density_targets/*_observed/position_prior）→ soft，仅参考",
              "  ├─ Requirement.load(base=<投影字段>)     # 会议优先级最低",
              "  ├─ conference.apply_to(req, profile)     # 写字段 + 页数口径 + 附 soft/deferred",
              "  ├─ core.Optimizer.run()                  # 与不指定会议同一条代码路径",
              "  │    score.l_violations()：官方硬约束 → 违规（L）",
              "  │    score.page_status()：页数按正文页/总页口径（pdftotext 定位参考文献首页）",
              "  └─ finalize()：报告 + state.json 附 conference 块（合理性核对、未接入项）",
              "```",
              "",
              "语义约定：",
              "",
              "| 模板内容 | 用途 | 说明 |",
              "|---|---|---|",
              "| hard_constraints（official/template-implied/inferred） | **违规判定（L）** | 不满足即不计入验收达标 |",
              "| 页数上限 | L | 默认按「正文页」口径：pdftotext 找参考文献首页 k，"
              "下界 k−1 超限才判违规（避免把恰好写到参考文献首页的合法论文误判） |",
              "| 官方最小边距 margin_floor_mm | L（下限语义） | 低于才判违规；高于不干预，"
              "**不得把合法的宽/不对称边距改小** |",
              "| typography.caption_* / density_targets / observed / position_prior | **合理性参考** | "
              "只写进报告（reasonableness），不进 L、不参与 A 打分 |",
              "| 无对应字段/动作的项 | **明确记录** | 见下方第 2 节，不强行接入 |",
              "",
              "优先级（从低到高）：会议模板 < --require 文件 < --settings < CLI 参数。"
              "不指定 --conference 时 `base=None`，代码路径与行为与以前完全一致。",
              ""]
    lines += ["## 4. 暂时没有用上的内容汇总", "",
              "共 %d 类原因（合计 %d 条记录）：" % (len(deferred_all),
                                                 sum(len(v) for v in deferred_all.values())),
              ""]
    for reason, items in sorted(deferred_all.items(), key=lambda kv: -len(kv[1])):
        lines.append(f"- {reason}（{len(items)} 条）")
    lines.append("")
    lines += ["## 2. 暂未接入的内容（明确记录，不强行加入）", "",
              f"共 {sum(len(v) for v in deferred_all.values())} 条记录，按原因分组：", ""]
    for reason, items in sorted(deferred_all.items(),
                                key=lambda kv: -len(kv[1])):
        lines.append(f"### {reason}（{len(items)}）")
        lines.append("")
        uniq = sorted(set(i.split(":", 1)[1] for i in items))
        confs = sorted(set(i.split(":", 1)[0] for i in items))
        lines.append(f"- 涉及字段：" + "，".join(f"`{u}`" for u in uniq[:20])
                     + (" 等" if len(uniq) > 20 else ""))
        lines.append(f"- 涉及会议：{len(confs)} 个（{', '.join(confs[:16])}）")
        lines.append("")
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"wrote {OUT}")
    print(f"会议 {len(rows)} 个；未接入记录 {sum(len(v) for v in deferred_all.values())} 条"
          f"（{len(deferred_all)} 类原因）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
