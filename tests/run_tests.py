#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""texopt 回归测试：单元检查 + 端到端闭环 + 模型在环往返。

用法：
    python3 tests/run_tests.py            # 常用集（较快）
    python3 tests/run_tests.py --full     # 含 chaos/nightmare 大靶子
    python3 tests/run_tests.py --list     # 只列测试名

设计原则：
  * 单元测试自带内联靶稿（不依赖 examples/，缺失靶子也不会误报失败）；
  * 集成测试依赖 examples/ 靶稿，靶稿不存在时标 SKIP 并提示（缺靶稿 ≠ 代码错）；
  * 测试只写 `_regress/` 目录（Windows 盘符下，编译产物可落盘），跑完即清理；
    绝不触碰 examples/ 里的固定靶子（原件只读）。
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from texopt import actions, proposal, score as S, visual, whitelist  # noqa: E402
from texopt import perceive as P                                      # noqa: E402
from texopt.core import Optimizer, verify                             # noqa: E402
from texopt.requirements import Requirement                           # noqa: E402

OUT = os.path.join(ROOT, "_regress")
EX = os.path.join(ROOT, "examples")

PASS, FAIL, SKIP = [], [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}"
          + (f" — {detail}" if detail and not cond else ""))


def skip(name, why):
    SKIP.append(name)
    print(f"  [SKIP] {name} — {why}")


def _req(**kw):
    base = dict(verbose=False)
    base.update(kw)
    return Requirement(**base)


def _have(*names):
    return all(os.path.isfile(os.path.join(EX, n)) for n in names)


# ---------------------------------------------------------------- 内联单元靶稿
# 故意埋入各类排版问题（手动分页/过大 vspace/行内字号/标题字号/列表间距/
# 超宽相对图宽/长词），用于验证「检测 -> 动作」链路，不依赖 examples/。
UNIT_SRC = r"""\documentclass[10pt,a4paper]{article}
\usepackage[margin=0.55in]{geometry}
\usepackage{graphicx,float,titlesec,enumitem}
\titleformat{\section}{\Huge\bfseries}{\thesection}{0.2em}{}
\titleformat{\subsection}{\Large\bfseries}{\thesubsection}{0.1em}{}
\begin{document}
\section{Introduction}
This paragraph mentions a pseudopseudohypoparathyroidismcounterrevolutionarieselectroencephalographicallyincomprehensibilities word.
\begin{itemize}[leftmargin=1pt,itemsep=18pt,topsep=15pt]
\item first item
\end{itemize}
\begin{figure}[H]\centering\includegraphics[width=1.18\linewidth]{example-image}\caption{A wide figure.}\end{figure}
\begin{table}[h]\centering\begin{tabular}{ll}a&b\\c&d\\\end{tabular}\end{table}
{\Large This paragraph is oversized compared with the body text.}
\newpage
\vspace{3cm}
\section{Conclusion}
Done.
\end{document}
"""


# ---------------------------------------------------------------- 单元测试

def unit_tests():
    print("\n== 单元测试 ==")
    src = UNIT_SRC

    # 1) 白名单闸门
    check("white/unknown-action-blocked",
          whitelist.validate("rewrite_text", {})["ok"] is False)
    check("white/bad-param-blocked",
          whitelist.validate("set_fontsize", {"pt": 9})["ok"] is False)
    check("white/header-injection-blocked",
          whitelist.validate("add_header", {"left": r"\input{/etc/passwd}"})["ok"]
          is False)
    check("white/width-injection-blocked",
          whitelist.validate("set_fig_width", {"width": r"\write18{x}"})["ok"]
          is False)
    check("white/good-action-ok",
          whitelist.validate("set_fig_width",
                             {"width": r"0.8\linewidth", "target": "fig#1"})["ok"])
    # 新增动作均在白名单内（模型在环可请求）
    new_actions = ["remove_manual_pagebreak", "remove_excessive_vspace",
                   "normalize_local_font_size", "normalize_heading_size",
                   "reduce_list_spacing", "add_hyphenation_points",
                   "fix_table_width", "balance_pages"]
    check("white/new-actions-registered",
          all(whitelist.validate(a, {})["ok"] for a in new_actions),
          str([a for a in new_actions
               if not whitelist.validate(a, {})["ok"]]))

    # 2) 定点动作按正序编号
    tg = actions.list_float_targets(src)
    check("action/target-index-order",
          [t["kind"] for t in tg] == ["figure", "table"], str(tg))
    new, ok, note, n = actions.set_float_spec(src, "tbp", "figure#1")
    check("action/set_float_spec-single",
          ok and r"\begin{figure}[tbp]" in new
          and r"\begin{table}[h]" in new, note)
    new2, ok2, _, _ = actions.set_fig_width(src, r"0.9\linewidth", 1)
    check("action/set_fig_width-single",
          ok2 and r"width=0.9\linewidth" in new2)

    # 3) 内容保护：排版命令级变化不算改内容；删正文词算改内容
    a = S.semantic_diff(src, src.replace(r"\noindent", ""), _req())
    check("content/layout-cmd-ignored", a["preserved"])
    b = S.semantic_diff(src, src.replace("Introduction", "Intro", 1), _req())
    check("content/word-deletion-detected", not b["preserved"])
    # L（引擎级归一）也允许「排版命令可动面」的删除
    c = S.body_unchanged(src, src.replace("\\newpage", "", 1), _req())
    check("content/L-allows-pagebreak-removal", c)
    d = S.body_unchanged(src, src.replace(
        "pseudopseudohypoparathyroidismcounterrevolutionarieselectroencephalographicallyincomprehensibilities",
        ""), _req())
    check("content/L-detects-text-deletion", not d)

    # 4) 提案解析（嵌套 / 扁平两种写法）
    items = proposal.parse_proposals({
        "proposals": [
            {"id": "x", "proposal": {"action": "set_float_spec",
                                     "target": "figure#1", "params": {"spec": "tbp"}}},
            {"id": "y", "action": "set_fig_width",
             "params": {"width": r"\linewidth", "target": "fig#1"}},
        ]})["items"]
    check("proposal/parse-nested-and-flat",
          items[0]["action"] == "set_float_spec" and items[1]["action"] == "set_fig_width"
          and items[1]["params"]["width"] == r"\linewidth")

    # 5) 视觉层 PGM 解析（若有样例）
    pgm = os.path.join(OUT, "unit-probe.pgm")
    os.makedirs(OUT, exist_ok=True)
    with open(pgm, "wb") as f:                       # 造 8x8 全黑 PGM
        f.write(b"P5\n8 8\n255\n" + bytes([0] * 64))
    m = visual.page_proxy(pgm)
    check("visual/pgm-proxy", m["ink_ratio"] == 1.0, str(m))
    os.remove(pgm)

    # 6) 检测层：卫生/标题字号/列表间距都能被检出
    kinds = {h["kind"] for h in P.scan_hygiene(src)}
    check("hygiene/detects-new-kinds",
          {"manual_pagebreak", "manual_vspace", "size_switch", "heading_size",
           "list_spacing", "unbreakable"} <= kinds, str(sorted(kinds)))
    # preamble 的 \titleformat 字号算 heading_size（不再误报为行内 size_switch）
    hl = [(h["kind"], h["line"]) for h in P.scan_hygiene(src)]
    check("hygiene/preamble-size-not-inline",
          all(k != "size_switch" for k, ln in hl if ln <= 6), str(hl))

    # 7) 新增动作：生效 + 幂等 + 内容归一后不变（L 级）
    cases = [
        ("remove_manual_pagebreak", lambda s: actions.remove_manual_pagebreak(s)),
        ("remove_excessive_vspace", lambda s: actions.remove_excessive_vspace(s)),
        ("normalize_local_font_size", lambda s: actions.normalize_local_font_size(s)),
        ("normalize_heading_size", lambda s: actions.normalize_heading_size(s)),
        ("reduce_list_spacing", lambda s: actions.reduce_list_spacing(s)),
        ("add_hyphenation_points", lambda s: actions.add_hyphenation_points(s)),
        ("normalize_fig_width", lambda s: actions.normalize_fig_width(s)),
        ("sanitize_float_specs(H)", lambda s: actions.sanitize_float_specs(s, "tbp", True)),
        ("balance_pages", lambda s: actions.balance_pages(s)),
    ]
    cur = src
    for name, fn in cases:
        out = fn(cur)
        ok = out[1] and out[0] is not None
        keep = S.body_unchanged(src, out[0], _req()) if ok else False
        again = fn(out[0])[1] if ok else True          # 幂等：第二次应为 False
        check(f"action/{name}-applies+idempotent+content-safe",
              ok and keep and (again is False),
              f"ok={ok} content_safe={keep} idempotent={again}")
        if ok:
            cur = out[0]
    # 具体语义检查
    check("action/fig-width-relative-clamped",
          r"width=\linewidth" in actions.normalize_fig_width(src)[0]
          and "1.18" not in actions.normalize_fig_width(src)[0])
    check("action/float-H-released",
          "figure}[tbp]" in actions.sanitize_float_specs(src, "tbp", True)[0])
    check("action/float-H-kept-by-default",
          actions.sanitize_float_specs(r"\begin{figure}[H]x\end{figure}",
                                       "tbp")[1] is False)
    check("action/heading-size-capped",
          r"\Large\bfseries" in actions.normalize_heading_size(src)[0]
          and r"\Huge" not in actions.normalize_heading_size(src)[0])
    check("action/list-spacing-dropped",
          "itemsep" not in actions.reduce_list_spacing(src)[0]
          and r"\begin{itemize}" in actions.reduce_list_spacing(src)[0])
    check("action/vspace-large-only",
          actions.remove_excessive_vspace(
              "\\begin{document}x\\vspace{2pt}y\\end{document}")[1] is False
          and actions.remove_excessive_vspace(
              "\\begin{document}x\\vspace{3cm}y\\end{document}")[1] is True)
    check("action/hyphenation-keeps-word",
          "pseudopseudohypoparathyroidismcounterrevolutionarieselectroencephalographicallyincomprehensibilities"
          in actions.add_hyphenation_points(src)[0].replace("\\-", ""))

    # 8) 表格：超宽 tabular -> tabularx（自适应，不压缩）
    tabsrc = ("\\documentclass{article}\\begin{document}\n"
              "\\begin{tabular}{lrrr}a&b&c&d\\\\\\end{tabular}\n"
              "\\end{document}\n")
    tnew, tok, tnote = actions.fix_table_width(tabsrc)
    check("action/table-to-tabularx",
          tok and "tabularx}{\\linewidth}{Xrrr}" in tnew
          and "\\end{tabularx}" in tnew and "\\usepackage{tabularx}" in tnew,
          tnote)
    check("action/table-no-resizebox", "resizebox" not in tnew)

    # 9) 评分：相对超宽图 / 编译 warning / [H] 都要计入 A
    class _FakePer:
        src = "\\begin{document}x\\end{document}"
        issues = {"overfull": [], "underfull": [], "vbox": [], "floats": [],
                  "tables_overwide": [], "warnings": ["LaTeX Warning: x"],
                  "hygiene": [{"kind": "manual_pagebreak", "line": 1,
                               "detail": "d"}]}
        source = {"graphics_width_expr": ["1.18\\linewidth", "0.9\\linewidth"],
                  "float_envs": [{"spec": "H"}]}
    a_src = "texopt: 排版质量宏"
    class _FakePer2(_FakePer):
        src = "texopt: 排版质量宏"
    A1 = S.aesthetic_score(_FakePer(), _req())
    check("score/relative-overwide+warning+H-counted",
          A1 > 0.3 + 1.0 + 0.5, f"A={A1}")
    check("score/overwide-figs-rule",
          S._overwide_figs(_FakePer(), _req()) == ["1.18\\linewidth"],
          str(S._overwide_figs(_FakePer(), _req())))

    # 10) 出口状态：不再"L=0 就 CONVERGED"
    opt = Optimizer(os.path.join(EX, "nonexistent.tex"), _req(), OUT)
    opt.attempts, opt.accepted = 0, 0
    check("exit/no-candidate->CONVERGED", opt.exit_status({"l": []}) == "CONVERGED")
    opt.attempts, opt.accepted = 3, 0
    check("exit/attempted-but-no-gain->NO_IMPROVEMENT",
          opt.exit_status({"l": []}) == "NO_IMPROVEMENT")
    opt.attempts, opt.accepted = 3, 2
    check("exit/applied->DONE", opt.exit_status({"l": []}) == "DONE")
    check("exit/L-violation->EXHAUSTED",
          opt.exit_status({"l": ["页数 9 超出限制 8"]}) == "EXHAUSTED")


# ---------------------------------------------------------------- 集成测试

def integration_case(name, tex, expect_status, expect_l0=True, **kw):
    outdir = os.path.join(OUT, name)
    shutil.rmtree(outdir, ignore_errors=True)
    opt = Optimizer(os.path.join(EX, tex), _req(**kw), outdir)
    res = opt.run()
    expect = expect_status if isinstance(expect_status, tuple) else (expect_status,)
    check(f"closure/{name}:status in {expect}",
          res["status"] in expect, res["status"])
    if expect_l0:
        check(f"closure/{name}:L=0", not res["l"], str(res["l"]))


def integration_mitl():
    """模型在环往返：接受 / 回滚 / BLOCKED 三态都验证。

    靶稿缺失时用内联靶稿 + 直接构造提案（不依赖 examples/ 里的 json）。
    """
    name = "mitl"
    outdir = os.path.join(OUT, name)
    shutil.rmtree(outdir, ignore_errors=True)
    fixture = os.path.join(EX, "propose_target.tex")
    if os.path.isfile(fixture):
        src_path = fixture
    else:
        src_path = os.path.join(OUT, "mitl_target.tex")
        os.makedirs(OUT, exist_ok=True)
        with open(src_path, "w", encoding="utf-8") as f:
            f.write(UNIT_SRC)
    opt = Optimizer(src_path, _req(), outdir)
    base = opt.run()
    check("mitl/closure-baseline",
          base["status"] in ("CONVERGED", "DONE", "NO_IMPROVEMENT"),
          base.get("status") or base.get("reason"))
    check("mitl/baseline-has-A", base.get("a", -1) >= 0, str(base)[:200])

    items = proposal.parse_proposals({"proposals": [
        # p1：合法但会让全局分变差（[tbp] -> [h] 属不稳定浮动参数）-> 应回滚
        {"id": "p1", "issue": "bad_spec", "proposal": {
            "action": "set_float_spec",
            "params": {"spec": "h", "target": "figure#1"}}},
        # p2：非白名单动作 -> BLOCKED
        {"id": "p2", "issue": "unknown", "proposal": {
            "action": "rewrite_text", "params": {}}},
    ]})["items"]
    res = opt.apply_proposals(items)
    check("mitl/one-rolled-back", len(res.get("rejected", [])) == 1,
          json.dumps(res, ensure_ascii=False)[:300])
    check("mitl/one-blocked", len(res.get("blocked", [])) == 1)
    fin = opt.finalize()
    check("mitl/final-L0", not fin["l"], str(fin["l"]))
    v = verify(os.path.join(outdir, "paper.tex"), src_path, _req())
    check("mitl/content-preserved",
          v["content_preserved"] and v["semantic"]["preserved"], str(v["l"]))
    req = opt.emit_request(2, with_visual=False)
    check("mitl/request-emitted",
          req["schema"] == proposal.REQUEST_SCHEMA and req["round"] == 2)
    check("mitl/request-has-whitelist", len(req["allowed_actions"]) >= 15)


def integration_figure_violation():
    """图形保真反例：重绘的图应被 L 判违规。"""
    if not _have("fig_violation.tex", "aidtest.tex"):
        skip("figviolation/flagged", "缺少 examples/fig_violation.tex 或 aidtest.tex")
        return
    v = verify(os.path.join(EX, "fig_violation.tex"),
               os.path.join(EX, "aidtest.tex"), _req())
    check("figviolation/flagged",
          any("图形" in x for x in v["l"]), str(v["l"]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", action="store_true", help="含 chaos/nightmare 大靶子")
    ap.add_argument("--keep", action="store_true", help="保留 _regress/ 产物（默认清理）")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()
    if args.list:
        print("unit_tests, closure:{demo,issues,aidtest,propose_target,"
              "test0911/chaotic_layout_test}, mitl, figure_violation"
              + (", closure:{chaos,nightmare}" if args.full else ""))
        return 0

    os.makedirs(OUT, exist_ok=True)
    unit_tests()
    fixtures = [("demo", "demo.tex", "CONVERGED"),
                ("issues", "issues.tex", "CONVERGED"),
                ("aidtest", "aidtest.tex", "CONVERGED"),
                ("propose_target", "propose_target.tex", "CONVERGED"),
                ("chaotic_layout", os.path.join("test0911", "chaotic_layout_test.tex"),
                 ("DONE", "CONVERGED", "NO_IMPROVEMENT"))]
    if args.full:
        fixtures += [("chaos", "chaos.tex", "CONVERGED"),
                     ("nightmare", "nightmare.tex", "CONVERGED")]
    for name, tex, expect in fixtures:
        if not _have(tex):
            skip(f"closure/{name}", f"缺少 examples/{tex}（靶稿未随项目提供）")
            continue
        integration_case(name, tex, expect)
    integration_mitl()
    integration_figure_violation()

    print(f"\n== 结果：{len(PASS)} 通过 / {len(FAIL)} 失败 / {len(SKIP)} 跳过 ==")
    for f in FAIL:
        print(f"  FAIL: {f}")
    if SKIP:
        print(f"  （{len(SKIP)} 项跳过：examples/ 靶稿缺失，非代码问题）")
    if not args.keep:
        shutil.rmtree(OUT, ignore_errors=True)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
