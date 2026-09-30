#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""texopt 命令行入口 —— 论文整体排版优化 Agent（新主线）。

主线（2026-09-09 起）：优化目标是『整篇论文满足要求规格 + 排版质量全局
最优』，由 L（编译/渲染/内容零改动/页数/硬性规范）+ A（审美量化）+ I
（最小干预）三个量化共同决定；Page Limit 只是要求规格里的一个可选字段。

用法示例：
    python3 optimize.py examples/demo.tex                     # 纯质量模式
    python3 optimize.py examples/demo.tex --target 5          # 只要页数限制
    python3 optimize.py examples/demo.tex --template ieee     # 期刊模板
    python3 optimize.py paper.tex --conference aaai           # 会议模板（AAAI）
    python3 optimize.py paper.tex --conference icml           # 会议模板（ICML）
    python3 optimize.py --list-conferences                    # 列出可选会议
    python3 optimize.py my_paper.tex --require my_reqs.json   # 自定义详细要求
    python3 optimize.py my_paper.tex --template acm --require extra.json
    python3 optimize.py --list-templates                      # 列出可用模板

会议模板（--conference，templates-v2/<id>.json）：
    官方硬约束（页数/字号/边距/浮动体规范）→ 转为 L 硬约束，用于判「是否违规」；
    官方页数上限默认按「正文页」口径判定（参考文献不计，pdftotext 定位参考文献首页）；
    真实论文统计（图/表/公式密度、浮动体位置先验）→ 只做「排版是否合理」的参考核对，
    不进 L、不影响评分；模板里本版接不上的字段会列在报告与
    datasets/conf-specs/summary/texopt-integration-report.md 里（不强行接入）。

结构/版面规范（2026-09-10 新增）：
    python3 optimize.py p.tex --toc --header --heading-color 0,62,120
    python3 optimize.py p.tex --template report               # 目录+页眉+彩色标题
    python3 optimize.py p.tex --no-strip-aids                 # 保留阅读辅助内容
    python3 optimize.py --extract-fig orig.pdf --page 3 \
        --box 308,112,432,258 --out figs/fig1.png             # 图形保真裁图

要求优先级：模板预设 < --require 要求文件 < --settings < CLI 参数。
原文件始终只读；优化结果与报告输出到 outdir（默认 <tex所在目录>/workbench）。

模型在环（Model-in-the-loop，Phase 2/3）：LLM 不是一次性改论文，而是进入循环：
    python3 optimize.py paper.tex --emit-request         # 闭环 + 输出请求包给 LLM
    # LLM 读 workbench/llm_request.json（状态+残余问题+白名单+页面图）
    # 写出 proposals.json（结构化提案）
    python3 optimize.py paper.tex --proposals proposals.json --emit-request
    # 程序逐条：白名单校验→应用→编译→全局验收→变差回滚，再出下一轮请求
    python3 optimize.py --list-actions                   # 查看可用白名单动作
视觉感知（Phase 4）：--emit-request 会把每页 PDF 渲染为图（workbench/pages/），
供具备视觉能力的模型判断整体布局（像素代理指标为实验性、未并入 A）。
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from texopt.core import Optimizer, verify, work_tex_path   # noqa: E402
from texopt import proposal as _proposal     # noqa: E402
from texopt import whitelist as _whitelist   # noqa: E402
from texopt import conference as _conference  # noqa: E402
from texopt.requirements import Requirement, list_templates   # noqa: E402

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def _print_status_detail(result: dict) -> None:
    """按出口状态打印人读摘要（不伪造“优化成功”：没改动就直说）。"""
    st = result.get("status")
    if st == "NEEDS_REVIEW":
        ds = result.get("visual_defects") or []
        hi = [d for d in ds if d.get("severity") == "high"]
        print(f"  -> NEEDS_REVIEW：仍有 {len(ds)} 项视觉缺陷（{len(hi)} 项 high）"
              "未消除，未判定 DONE")
        for d in ds[:8]:
            pag = f"第{d['page']}页 " if d.get("page") else ""
            print(f"     [{d['severity']}] {pag}{d['kind']}：{d['detail']}")
        if len(ds) > 8:
            print(f"     …另 {len(ds) - 8} 项见 report.md / state.json")
    elif st == "DONE":
        print(f"  -> DONE：应用了 {result.get('accepted', 0)} 个被接受的动作"
              f"（尝试 {result.get('attempts', 0)} 个候选）")
        print(f"     A: {result.get('a_before')} -> {result.get('a')}；"
              f"Pages: {result.get('pages_before')} -> {result.get('pages')}")
    elif st == "NO_IMPROVEMENT":
        print(f"  -> NO_IMPROVEMENT：试过 {result.get('attempts', 0)} 个候选，"
              "没有任何一个能改善全局评分（均已回滚）")
    elif st == "CONVERGED":
        print("  -> CONVERGED：L 全部达标，且无可自动修复的排版候选")
    elif st == "EXHAUSTED":
        print("  -> EXHAUSTED：仍有 L 硬约束未达标")
    if result.get("blocked"):
        print(f"     被回滚/阻止的动作：{', '.join(result['blocked'])}")


def _print_conference_detail(conf: dict | None) -> None:
    """打印会议要求信息（官方硬约束 / 合理性参考 / 未接入项计数）。"""
    if not conf:
        return
    print(f"  [会议] {conf['id']}：页数上限 {conf.get('page_limit')}"
          f"（口径 {conf.get('page_scope')}；正文页下界/上界 "
          f"{conf.get('content_pages_lower')}/{conf.get('content_pages_upper')}，"
          f"PDF 共 {conf.get('pages_total')} 页）")
    if conf.get("page_advisory"):
        print(f"     {conf['page_advisory']}")
    rr = conf.get("reasonableness") or {}
    if rr.get("enabled"):
        dev = rr.get("deviations") or []
        print(f"  [会议] 合理性核对（仅参考，不影响判定）："
              f"{len(rr.get('checks', []))} 项，偏离参考区间 {len(dev)} 项")
        for d in dev[:4]:
            print(f"     · {d}")
    n_unused = len(conf.get("unused") or [])
    if n_unused:
        print(f"  [会议] 模板中本版未接入的内容：{n_unused} 项已记录"
              "（见 datasets/conf-specs/summary/texopt-integration-report.md）")


def main() -> int:
    ap = argparse.ArgumentParser(
        description="texopt 论文整体排版优化 Agent"
                   "（L 基础逻辑 + A 排版质量代理 + I 最小干预；"
                   "确定性闭环 + 模型在环）")
    ap.add_argument("tex", nargs="?", help="要优化的 .tex 文件（只读）")
    ap.add_argument("--template", "-T", default=None,
                    help="期刊/会议模板预设（ieee/acm/springer-llncs/...，"
                         "或 templates/<id>.json）")
    ap.add_argument("--conference", "-C", default=None,
                    help="会议模板（datasets/conf-specs/templates-v2/<id>.json）："
                         "官方硬约束→违规判定，真实论文统计→合理性参考；"
                         "如 aaai/icml/cvpr/acl/...（--list-conferences 查看）")
    ap.add_argument("--list-conferences", action="store_true",
                    help="列出可选会议模板后退出")
    ap.add_argument("--require", "-r", default=None,
                    help="自定义排版要求 JSON（可给出任意详细要求）")
    ap.add_argument("--list-templates", action="store_true",
                    help="列出可用模板后退出")
    ap.add_argument("--target", "-t", type=int, default=None,
                    help="页数限制（Page Limit，要求规格之一）；"
                         "缺省读 settings/模板")
    ap.add_argument("--outdir", "-o", default=None,
                    help="输出目录（默认 <tex 所在目录>/workbench）")
    ap.add_argument("--settings", "-s", default=None,
                    help="settings.json 配置文件（字段作为默认值）")
    ap.add_argument("--min-margin", type=float, default=None,
                    help="页边距压缩安全下限（mm），覆盖 settings")
    ap.add_argument("--no-fontsize", action="store_true",
                    help="禁止压缩时字号降档，覆盖 settings")
    ap.add_argument("--tune-geometry", action="store_true",
                    help="授权为压页调整全局版心（页边距/字号）——默认禁止，"
                         "因其会改变版面分布，可能造成图表与正文错位")
    ap.add_argument("--quiet", "-q", action="store_true", help="安静模式")
    # ---- 结构规范 / 版面规范（2026-09-10 新增）----
    ap.add_argument("--toc", action=argparse.BooleanOptionalAction,
                    default=None, help="要求目录页（--no-toc 关闭）")
    ap.add_argument("--header", dest="header",
                    action=argparse.BooleanOptionalAction, default=None,
                    help="要求页眉（--no-header 关闭）")
    ap.add_argument("--heading-color", default=None,
                    help="标题强调色，如 0,62,120 或 RGB:... 或颜色名")
    ap.add_argument("--strip-aids", dest="strip_aids",
                    action=argparse.BooleanOptionalAction, default=None,
                    help="删阅读辅助内容（START READING HERE 等），"
                         "--no-strip-aids 保留")
    ap.add_argument("--warning-boxes", dest="warning_boxes",
                    action=argparse.BooleanOptionalAction, default=None,
                    help="删 WARNING/CAUTION 类告示块（--no-warning-boxes 保留）")
    ap.add_argument("--preserve-figures", dest="preserve_figures",
                    action=argparse.BooleanOptionalAction, default=None,
                    help="图形保真：图不得重绘/改写（默认开）")
    ap.add_argument("--extract-fig", metavar="PDF", default=None,
                    help="【工具】从原 PDF 裁切图形区域为图片，输出可落地的 "
                         "\\\\includegraphics 片段（配合 --page/--box/--out）")
    ap.add_argument("--page", type=int, default=None, help="--extract-fig 页码")
    ap.add_argument("--box", default=None,
                    help="--extract-fig 裁切框 x0,y0,x1,y1（pt，页面左上原点）")
    ap.add_argument("--out", default=None, help="--extract-fig 输出图片路径")
    ap.add_argument("--dpi", type=int, default=400, help="--extract-fig 分辨率")
    ap.add_argument("--verify", action="store_true",
                    help="模型在环验证模式（只读）：编译目标 tex、全局评分、"
                         "内容完整性与建议清单，不做任何修改")
    ap.add_argument("--original", default=None,
                    help="原稿 .tex 路径（--verify / --proposals 时用于内容完整性"
                         "对照与干预代价基准）")
    # ---- 模型在环（Model-in-the-loop）闭环 ----
    ap.add_argument("--emit-request", dest="emit_request", action="store_true",
                    help="闭环结束后输出 llm_request.json（状态+残余问题+"
                         "动作白名单+页面图像），交 LLM 判断")
    ap.add_argument("--proposals", default=None,
                    help="模型在环：读取 LLM 产出的 proposals.json，逐条执行"
                         "（白名单校验→编译→全局验收→变差回滚），再输出下一轮 request")
    ap.add_argument("--round", type=int, default=1,
                    help="模型在环轮次号（写入 request/proposals，默认 1）")
    ap.add_argument("--visual", dest="visual",
                    action=argparse.BooleanOptionalAction, default=True,
                    help="--emit-request 时是否渲染页面图（默认开，供视觉模型）")
    ap.add_argument("--visual-dpi", type=int, default=110,
                    help="页面图渲染 DPI（默认 110）")
    ap.add_argument("--visual-metrics", dest="visual_metrics",
                    action=argparse.BooleanOptionalAction, default=None,
                    help="从编译后的 PDF 量取页面级视觉指标并并入 A（默认开）")
    ap.add_argument("--aesthetic-shadow", dest="aesthetic_shadow",
                    action=argparse.BooleanOptionalAction, default=None,
                    help="审美档案影子评估（阶段 6：λ=0，只报告不改判定；默认开）")
    ap.add_argument("--shadow-profile", default=None,
                    help="影子评估用的审美档案路径（默认用随附的 "
                         "datasets/conf-specs/metrics/profiles/aesthetic_profile.json）")
    ap.add_argument("--shadow-only", action="store_true",
                    help="只跑影子评估并输出 aesthetic_shadow.md/.json（不优化）")
    ap.add_argument("--list-actions", action="store_true",
                    help="列出模型在环可用白名单动作后退出")
    ap.add_argument("--json", action="store_true",
                    help="以 JSON 输出结果（便于上层 Agent 消费）")
    args = ap.parse_args()

    if args.list_actions:
        for a in _whitelist.describe():
            ps = "，".join(p["name"] + ("*" if p["required"] else "")
                          for p in a["params"]) or "无参数"
            print(f"- {a['action']} [L{a['level']}/{a['category']}] {a['doc']}"
                  f"  （参数：{ps}）")
        return 0

    if args.list_templates:
        for t in list_templates(SCRIPT_DIR):
            print(f"- {t['id']}: {t['name']} —— {t['desc']}")
        return 0

    if args.list_conferences:
        rows = _conference.list_conferences()
        if not rows:
            print(f"[错误] 没找到会议模板目录："
                  f"{_conference.templates_dir()}")
            return 2
        print(f"会议模板目录：{_conference.templates_dir()}\n")
        for t in rows:
            print(f"- {t['id']:9s} {t.get('conference') or '':22s} "
                  f"{t.get('edition') or '':14s} n={t.get('n_samples')} "
                  f"可信度={t.get('level')}")
        return 0

    # ---------------- 工具：从原 PDF 裁切图形（图形保真） ----------------
    if args.extract_fig:
        from texopt import engine
        if args.page is None or not args.box or not args.out:
            print("[错误] --extract-fig 需要 --page、--box x0,y0,x1,y1、--out")
            return 2
        try:
            box = [float(v) for v in args.box.replace(" ", "").split(",")]
            assert len(box) == 4
        except Exception:
            print("[错误] --box 格式应为 x0,y0,x1,y1")
            return 2
        res = engine.extract_pdf_region(args.extract_fig, args.page, box,
                                       args.out, dpi=args.dpi)
        if res.get("error"):
            print(f"[错误] {res['error']}")
            return 1
        print(f"[图形保真] 已裁切 {args.extract_fig} 第 {args.page} 页 "
              f"({res['width_bp']}x{res['height_bp']}bp) -> {res['out']}")
        print(f"  可嵌入片段：{res['snippet']}")
        return 0

    if not args.tex:
        print("[错误] 需要 .tex 文件（或 --list-templates）")
        return 2
    if not os.path.isfile(args.tex):
        print(f"[错误] 找不到文件：{args.tex}")
        return 2

    settings = {}
    if args.settings and os.path.isfile(args.settings):
        with open(args.settings, encoding="utf-8") as f:
            settings = json.load(f)
    elif args.settings:
        print(f"[警告] settings 文件不存在：{args.settings}")

    # CLI 覆盖：--target/--min-margin/--no-fontsize（最高优先级）
    if args.target is not None:
        settings["page_limit"] = args.target
    if args.min_margin is not None:
        settings["margin_min_mm"] = args.min_margin
    if args.no_fontsize:
        settings["allow_fontsize_step"] = False
    if args.tune_geometry:
        settings["allow_geometry_tune"] = True

    # 模板：CLI > settings.template（缺省 custom）
    tpl = args.template
    if tpl is None and settings.get("template") not in (None, "custom"):
        tpl = settings["template"]

    # 会议模板（templates-v2）：投影为 Requirement 默认值，优先级最低
    prof = None
    if args.conference:
        try:
            prof = _conference.load(args.conference)
        except ValueError as exc:
            print(f"[错误] {exc}")
            return 2

    req = Requirement.load(tex_dir=SCRIPT_DIR, template=tpl,
                           require_file=args.require, settings=settings,
                           base=prof.requirement_fields if prof else None)
    if prof is not None:
        _conference.apply_to(req, prof)
        req._conf_field_sources = prof.field_sources
        if not args.quiet:
            print(f"[会议] {prof.describe()}")
            for w in prof.warnings:
                print(f"[会议][警告] {w}")
            if prof.deferred:
                print(f"[会议] 模板中暂未接入的字段 {len(prof.deferred)} 项"
                      "（已记录，见 summary/texopt-integration-report.md）")
    # 结构/版面规范：CLI 显式给定则覆盖（最高优先级）
    for attr, val in (("toc", args.toc),
                      ("running_header", args.header),
                      ("heading_color", args.heading_color),
                      ("strip_reading_aids", args.strip_aids),
                      ("remove_warning_boxes", args.warning_boxes),
                      ("preserve_figures", args.preserve_figures),
                      ("visual_metrics", args.visual_metrics)):
        if val is not None:
            setattr(req, attr, val)
    # 阶段 6：审美档案影子接入（λ=0，只报告）—— CLI 显式给定则覆盖 settings/模板
    if args.aesthetic_shadow is not None:
        req.aesthetic_shadow = args.aesthetic_shadow
    if args.shadow_profile:
        req.shadow_profile = args.shadow_profile
    outdir = args.outdir or os.path.join(os.path.dirname(
        os.path.abspath(args.tex)), "workbench")
    req.verbose = not args.quiet

    # ---------------- 阶段 6：只跑影子评估（λ=0，仅报告，不改文档） ----------------
    if args.shadow_only:
        if args.aesthetic_shadow is False:
            print("[影子] --shadow-only 与 --no-aesthetic-shadow 冲突")
            return 2
        req.aesthetic_shadow = True
        req.max_iterations = 0            # 不做任何改动：只编译基线 + 影子观测
        opt = Optimizer(args.tex, req, outdir)
        res = opt.run()
        if res.get("status") == "FAILED":
            print(f"[影子] 失败：{res.get('reason')}")
            return 1
        snap = res.get("aesthetic_shadow") or {}
        if not snap or snap.get("status"):
            print("[影子] 未产出（档案缺失或已关闭）："
                  f"{(snap or {}).get('status') or '无'}")
            return 1
        print(f"[影子] λ={snap.get('lambda')}（只报告不改判定）档案={snap.get('profile_version')} "
              f"会议={snap.get('venue') or '（无）'}")
        print(f"[影子] A_defect={snap.get('a_defect')}（现行口径，参与验收）｜"
              f"A_profile={snap.get('a_profile')}｜异常页={snap.get('n_anomalous_pages')}/"
              f"{snap.get('n_pages_scored')}")
        print(f"[影子] 门槛剔除维度：{snap.get('dropped_dims') or '无'}")
        for pth in res.get("aesthetic_shadow_files") or []:
            print(f"[影子] 产出：{pth}")
        return 0

    # ---------------- 模型在环：只读验证模式 ----------------
    if args.verify:
        if not args.original:
            print("[错误] --verify 需要 --original <原稿.tex>（内容完整性对照）")
            return 2
        res = verify(args.tex, args.original, req,
                     outdir=outdir if not args.json else None)
        if res.get("status") == "COMPILE_FAIL":
            print(f"[验证] 编译失败：{res.get('first_error')}")
            return 1
        if args.json:
            import json as _json
            print(_json.dumps(res, ensure_ascii=False, indent=2))
            return 0 if res["ok"] else 1
        print(f"[验证] 状态={res['status']}  页数={res['pages']}  "
              f"L={len(res['l'])} A={res['a']} I={res['i']} "
              f"(总分 {res['total']})")
        print(f"  引擎级正文零改动：{'通过' if res['content_preserved'] else '（有排版级改动——模型在环编辑属预期）'}")
        sem = res["semantic"]
        if sem["preserved"]:
            print("  语义内容保留：通过（正文文字/公式/引用零改动，"
                  "仅排版命令级变化）")
        else:
            print("  语义内容保留：【未通过！正文内容被改动】 "
                  f"({sem['note']})")
        for v in res["l"]:
            print(f"  [L 未达标] {v}")
        if res["advisory"]:
            print(f"\n[建议清单] {len(res['advisory'])} 条残余问题"
                  f"（按 severity 排序，供 LLM/人工决策）：")
            for it in res["advisory"]:
                loc = f" 第{it['line']}行" if it["line"] else ""
                src = f"  | 当前: {it['source_line'][:60]}" \
                    if it["source_line"] else ""
                print(f"  [{it['severity']}] {it['kind']}{loc}")
                print(f"      问题：{it['issue']}")
                print(f"      建议：{it['suggestion']}{src}")
        return 0 if res["ok"] else 1

    # ---------------- 模型在环：逐条执行 LLM 提案 ----------------
    if args.proposals:
        original = args.original or args.tex
        odir = args.outdir or os.path.join(os.path.dirname(
            os.path.abspath(original)), "workbench")
        resume = os.path.isfile(work_tex_path(original, odir))
        opt = Optimizer(original, req, odir, resume=resume)
        if not resume:
            print("[模型在环] 未发现现有工作副本，先跑一次确定性闭环\n")
            base = opt.run()
            if base["status"] == "FAILED":
                print(f"[失败] {base.get('reason')}")
                return 1
        parsed = _proposal.parse_proposals(args.proposals)
        items = parsed["items"]
        print(f"[模型在环] round {args.round}：{len(items)} 条 LLM 提案"
              + (f"（模型整体判断：{parsed['assessment'][:60]}）"
                 if parsed.get("assessment") else ""))
        res = opt.apply_proposals(items)
        if res.get("error"):
            print(f"[失败] {res['error']}")
            return 1
        result = opt.finalize()
        print(f"\n[模型在环] 提案执行结果：接受 {len(res['applied'])} / "
              f"回滚 {len(res['rejected'])} / 阻止 {len(res['blocked'])} / "
              f"跳过 {len(res['skipped'])}")
        if not res["applied"] and (res["blocked"] or res["rejected"]):
            print("  ⚠ 本轮无可接受提案（BLOCKED/回滚）——若无更多可用动作，"
                  "闭环到此为止，未决项留给作者决策")
        for a in res["applied"]:
            print(f"  ✅ {a['id']}: {a['note']}")
        for b in res["blocked"]:
            print(f"  ⛔ {b['id']}: {b['reason']}")
        for c in res["rejected"]:
            print(f"  ↩ {c['id']}: {c['reason']}")
        if args.emit_request:
            opt.emit_request(args.round + 1, with_visual=args.visual,
                             visual_dpi=args.visual_dpi)
        print(f"\n[完成] 状态={result['status']}  L 违规 {len(result['l'])} 项  "
              f"A={result['a']}  I={result['i']}  最终 {result['pages']} 页")
        _print_status_detail(result)
        _print_conference_detail(result.get("conference"))
        print(f"  优化稿：{result['tex']}")
        if args.json:
            import json as _json
            print(_json.dumps({"result": result, "proposals": res},
                              ensure_ascii=False, indent=2))
        return 0 if result["status"] in ("CONVERGED", "DONE") else 1

    opt = Optimizer(args.tex, req, outdir)
    result = opt.run()
    if args.emit_request and result["status"] != "FAILED":
        opt.emit_request(args.round, with_visual=args.visual,
                         visual_dpi=args.visual_dpi)
    print()
    if result["status"] == "FAILED":
        print(f"[失败] {result.get('reason')}")
        if result.get("first_error"):
            print(f"  首个错误：{result['first_error']}")
        return 1
    print(f"[完成] 状态={result['status']}  L 违规 {len(result['l'])} 项  "
          f"A={result['a']}  I={result['i']}  "
          f"最终 {result['pages']} 页")
    _print_status_detail(result)
    _print_conference_detail(result.get("conference"))
    for v in result["l"]:
        print(f"  [L 未达标] {v}")
    if result["status"] == "EXHAUSTED":
        print("  -> 纯排版手段已穷尽，语义抛光（保意精简）为后续阶段兜底路径")
    print(f"  优化稿：{result['tex']}")
    if result.get("pdf"):
        print(f"  PDF：{result['pdf']}")
    print(f"  报告：{os.path.join(outdir, 'report.md')}")
    if args.json:
        import json as _json
        print(_json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] in ("CONVERGED", "DONE") else 1


if __name__ == "__main__":
    sys.exit(main())
