# -*- coding: utf-8 -*-
"""回填 P（页面缺陷）比重：把 workbench-severity/result.json 的标定结果落到 score.py。

背景：`PAGE_DEFECT_WEIGHT` 那 11 个比重原本是 9 月手拍的；2026-10-28 用
「人的严重度（15 题成对比较，Bradley-Terry） ÷ 语料频率（200 篇/3898 页）」
算出有来源的候选值（见 docs/stage11_severity_sheet_20261028.md）。

本工具做三件事：
  1. `--write`  生成 `metrics/severity_weights_applied.json`（Applied artifact，
     含 provenance：来源文件、题数、每项 old/new/basis）；
  2. `--check`  校验 score.py 的 PAGE_DEFECT_WEIGHT / VISUAL_DEFECT_M1 与 artifact
     是否一致（防「改了代码没回填 / 回填了没记录」）；
  3. `--print`  打印新旧对照表。

口径：只替换 `basis == "human×corpus"` 的项；`prior_kept` 的项保留现行值
（语料里计数为 0 或无该字段，作不了分母——不伪造）。
"""
from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULT = os.path.join(ROOT, "workbench-severity", "result.json")
ARTIFACT = os.path.join(ROOT, "metrics", "severity_weights_applied.json")
SCORE = os.path.join(ROOT, "texopt", "score.py")

# 现行代码里的先验（回填时"保留项"的取值基线；改先验请同步这里）
PRIOR_PAGE_DEFECT = {
    "overfull": 1.0, "underfull": 0.6, "vbox_over": 1.0, "vbox_under": 1.4,
    "floatwarn": 1.6, "tab_overwide": 1.2, "fig_overwide": 1.0, "warn": 0.3,
    "macros_missing": 2.0, "unstable_spec": 0.8, "spec_H": 0.5,
}
PRIOR_VISUAL_M1 = {"stranded_block": 1.2, "near_empty": 0.6}


def load_result(path: str = RESULT) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build(result: dict) -> dict:
    """由标定结果生成 applied 权重（只改 human×corpus 项）。"""
    page = dict(PRIOR_PAGE_DEFECT)
    visual = dict(PRIOR_VISUAL_M1)
    items = {}
    for key, row in (result.get("proposed") or {}).items():
        final = row.get("final")
        basis = row.get("basis") or "prior_kept"
        old = PRIOR_PAGE_DEFECT.get(key, PRIOR_VISUAL_M1.get(key))
        if final is not None and basis == "human×corpus":
            if key in page:
                page[key] = final
            elif key in visual:
                visual[key] = final
            items[key] = {"old": old, "new": final, "basis": basis,
                          "severity_rel": row.get("severity_rel"),
                          "freq_rel": row.get("freq_rel"),
                          "w_damped": row.get("w_damped")}
        else:
            items[key] = {"old": old, "new": old, "basis": "prior_kept",
                          "severity_rel": row.get("severity_rel"),
                          "freq_rel": row.get("freq_rel"),
                          "w_damped": None}
    return {
        "schema": "texopt.severity_weights.v1",
        "source": os.path.relpath(RESULT, ROOT),
        "n_questions": result.get("n_questions"),
        "n_decided": result.get("n_decided"),
        "method": "w = severity(BT, human 15 题) / freq(corpus per_page)；"
                  "sqrt 阻尼；缩放到现行权重同量纲（见 docs/stage11_*.md）",
        "scale_note": "ρ 是总尺度锚点，这里只改 P 内部相对结构",
        "page_defect_weight": page,
        "visual_defect_m1": visual,
        "items": items,
        "untested_tech_items": ["warn", "macros_missing", "unstable_spec"],
        "caveat": "严重度为单人判断（n=1 人，15 题），只够定大致顺序；"
                  "17 个 P 项里 5 项仍是先验（语料无分母）。",
    }


def write(applied: dict, path: str = ARTIFACT) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(applied, f, ensure_ascii=False, indent=2)
    return path


def code_weights(path: str = SCORE):
    """从 score.py 里读出现行常量（不 import，避免副作用）。"""
    sys.path.insert(0, ROOT)
    from texopt import score as S          # noqa: E402
    return dict(S.PAGE_DEFECT_WEIGHT), dict(S.VISUAL_DEFECT_M1)


def check(applied: dict, tol: float = 1e-6) -> list[str]:
    page, visual = code_weights()
    bad = []
    for k, v in applied["page_defect_weight"].items():
        cur = page.get(k)
        if cur is None or abs(cur - v) > tol:
            bad.append(f"PAGE_DEFECT_WEIGHT[{k}] 代码={cur} artifact={v}")
    for k, v in applied["visual_defect_m1"].items():
        cur = visual.get(k)
        if cur is None or abs(cur - v) > tol:
            bad.append(f"VISUAL_DEFECT_M1[{k}] 代码={cur} artifact={v}")
    return bad


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="写 artifact")
    ap.add_argument("--check", action="store_true", help="校验代码与 artifact 一致")
    ap.add_argument("--print", dest="show", action="store_true", help="打印对照表")
    ap.add_argument("--result", default=RESULT)
    args = ap.parse_args()
    if not os.path.isfile(args.result):
        print(f"缺少标定结果：{args.result}")
        return 2
    applied = build(load_result(args.result))
    if args.write:
        p = write(applied)
        print(f"[写] {p}")
    if args.show or not (args.write or args.check):
        print(f"{'项':<16}{'旧':>8}{'新':>8}  来源")
        for k, v in applied["items"].items():
            print(f"{k:<16}{str(v['old']):>8}{str(v['new']):>8}  {v['basis']}")
    if args.check:
        bad = check(applied)
        if bad:
            print(f"[不一致] {len(bad)} 处：")
            for b in bad:
                print("  -", b)
            return 1
        print("[一致] score.py 与 artifact 完全对齐")
    return 0


if __name__ == "__main__":
    sys.exit(main())
