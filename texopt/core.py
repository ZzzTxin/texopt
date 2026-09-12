# -*- coding: utf-8 -*-
"""决策 + 主循环（整体排版优化闭环核心）。

主线（2026-09-09 用户重对齐）：texopt 优化的是整篇论文的排版质量，
不是『压进 N 页』。目标函数为全局量化：
    total = L_fail * 1e6 + A + I
  * L（基础逻辑）：编译通过/渲染 PDF/正文零改动/页数限制（若要求）
                 + 硬性规范（要求指定的字号、页边距、公式居中）
  * A（审美量化）：正文溢出、页面垂直质量(vbox，孤行寡行代理)、
                 浮动体警告、超宽图/表 —— 全部为整篇重编译后的统计量
  * I（干预代价）：改动离原稿越远代价越高（最小干预）

全局性（局部最优≠全局最优）：每个候选动作都要『整篇重编译 → 全局重评
分』；验收判据是全局目标改善。修一处却让别处恶化的动作会被判负回滚；
达标后评分会自动把参数拉回『最宽松且最优』的临界点（松弛天然发生）。

主循环：每轮从候选池（L 修复 > 压缩 > 质量/松弛）按序取第一个有全局
正收益的动作执行；无候选可改善即收敛。所有动作幂等、备份、可回滚。

出口三态：
  CONVERGED  L 全达标，质量分收敛（残余 cosmetic 问题在报告中列出）
  EXHAUSTED  L 仍有违规（通常为超页）且排版手段穷尽 -> 语义抛光建议
  FAILED     基线无法编译 / 环境缺失
"""
from __future__ import annotations

import json
import os
import shutil

from . import (actions, advise, conference as confmod, engine, perceive as P,
               proposal, score as S, visual, whitelist)
from .requirements import Requirement

# L 类硬约束修复动作：文档状态（L 数/页数）变化后允许重试。
# 原因：会议模式下「页数」与「边距/字号」互相牵制——页数降下来后，
# 之前被回滚的边距修复才能成立；审美/质量类动作保持一次性语义。
RETRYABLE_KEYS = {"margin_spec", "font_spec", "fleqn"}


class Optimizer:
    def __init__(self, original_tex: str, req: Requirement, outdir: str,
                 resume: bool = False):
        self.original = os.path.abspath(original_tex)
        self.req = req
        self.outdir = outdir
        self.work_tex = os.path.join(outdir, "paper.tex")
        self.resume = resume            # True：沿用已有工作副本（模型在环续跑）
        self.iter = 0
        self.records = []
        self.orig_body = None            # 内容完整性机器校验基准
        self.orig_per = None             # 原稿 Perception（干预代价基准）
        self._blocked: set[str] = set()  # 失败动作指纹（L 类带状态签名可重试），防重复试错
        self._llm_failed: set[str] = set()  # 已失败的 LLM 提案指纹（跨轮阻止）
        self.attempts = 0                # 本轮实际编译验证过的候选动作数
        self.accepted = 0                # 本轮被接受的动作数
        self.baseline = None             # 基线评分快照（报告「A: old -> new」用）
        self._defects: list = []         # 当前视觉缺陷（出口状态判定用）
        self._state = None               # 上一次接受后的 (Perception, 评分)

    # ------------------------------------------------------------- 工具
    def _log(self, msg):
        if self.req.verbose:
            print(msg)

    def _ensure_orig(self):
        """保证内容基准与 I 基准就位（resume 路径不经过 run() 时用）。"""
        if self.orig_per is None:
            self.orig_per = _static_perception(self.original)
        if self.orig_body is None:
            with open(self.original, encoding="utf-8", errors="replace") as f:
                self.orig_body = S.content_body(f.read())

    def _read(self) -> str:
        with open(self.work_tex, encoding="utf-8") as f:
            return f.read()

    def _write(self, text: str):
        with open(self.work_tex, "w", encoding="utf-8") as f:
            f.write(text)

    def _record(self, note: str, per, cur, accepted: bool, compile_ok: bool,
                source: str = "rule", detail: str = ""):
        self.records.append({
            "iteration": self.iter, "action": note, "source": source,
            "l": list(cur["l"]) if cur else [], "a": cur["a"] if cur else None,
            "i": cur["i"] if cur else None,
            "total": cur["total"] if cur else None,
            "pages": per.pages if per else None,
            "accepted": bool(accepted), "compile_ok": bool(compile_ok),
            "detail": detail,
        })

    # ------------------------------------------------------------- 候选池
    def _candidates(self, per: P.Perception, cur_lv: list[str]):
        """基于当前感知生成候选动作（按优先级排序，返回 (key, apply_fn, note)）。

        每轮推进一档；失败动作记入 _blocked，避免同状态重复试错。
        """
        req, src = self.req, per.source
        sig = f"{len(cur_lv)}|{per.pages}"   # 状态签名（防重复试错的粒度）
        cands = []
        cur_margin = src.get("geometry_margin_mm")
        orig_margin = self.orig_per.source.get("geometry_margin_mm")
        cur_font = src["font_pt"]
        orig_font = self.orig_per.source["font_pt"]
        has_page_lv = any("页数" in x for x in cur_lv)
        pages = S.judge_pages(per, req) or 0

        def add(key, fn, note):
            # 指纹含状态签名：文档状态（L 数/页数）变了以后，之前失败的动作可以重试
            # —— 会议模式下边距与页数互相牵制（页数降下来后，边距才能合法提高），
            # 否则会出现「页数降下来了但边距还是没修」。
            # 只有 L 类硬约束修复动作享有重试（审美/质量动作保持原有一次性语义，
            # 避免改动默认模式下的收敛行为）。
            stamp = f"{key}@{sig}" if key in RETRYABLE_KEYS else key
            if stamp not in self._blocked \
                    and all(k != key for k, _, _ in cands):
                cands.append((key, fn, note))

        # 0) 断行质量宏（无损，一次）
        if req.enable_quality_macros and "texopt: 排版质量宏" not in per.src:
            add("quality", lambda s: actions.inject_quality_macros(s),
                "注入断行质量宏（防孤行寡行/连字符堆叠/溢出）")

        # 1) L：硬性规范修复（要求明确指定才动）
        if src["fleqn"] and not req.eq_fleqn_allowed:
            add("fleqn", actions.drop_fleqn, "移除 fleqn，公式恢复居中")
        if req.font_pt and cur_font != req.font_pt:
            add("font_spec",
                lambda s, n=req.font_pt: actions.set_fontsize(s, n),
                f"字号对齐要求 {cur_font}pt -> {req.font_pt}pt")
        margin_floor_mode = bool(getattr(req, "margin_is_floor", False))
        if req.margin_mm and cur_margin is not None \
                and ((cur_margin < req.margin_mm - 0.5) if margin_floor_mode
                     else abs(cur_margin - req.margin_mm) > 0.5):
            add("margin_spec",
                lambda s, n=req.margin_mm, c=cur_margin:
                    actions.set_margin(s, n, cur_mm=c),
                (f"页边距低于官方下限，提到 {req.margin_mm:g}mm"
                 if margin_floor_mode else
                 f"页边距对齐要求 {cur_margin:g}mm -> {req.margin_mm:g}mm")
                + f"（当前 {cur_margin:g}mm）")

        # 1.5) 结构规范：目录页 / 页眉（属『前置结构』，L 项）
        if req.toc and not src.get("has_toc") \
                and src.get("sections", 0) >= req.toc_min_sections:
            add("toc", actions.insert_toc,
                "插入目录页 \\tableofcontents")
        if req.running_header and not src.get("has_header"):
            add("header",
                lambda s: actions.add_header(s, req.header_left,
                                             req.header_right),
                "注入页眉（fancyhdr：左标题/右页码）")
        # 1.6) 标题着色（审美项，要求指定才做）
        if req.heading_color and not src.get("has_heading_color"):
            add("heading_color",
                lambda s, c=req.heading_color: actions.color_headings(s, c),
                f"标题着色（section/subsection -> {req.heading_color}）")
        # 1.7) 元信息清理：阅读辅助内容 / WARNING 告示（要求开启才做）
        hyg = {h["kind"] for h in per.issues.get("hygiene", [])}
        if req.strip_reading_aids and "reading_aid" in hyg:
            add("strip_aids", actions.strip_reading_aids,
                "删除阅读辅助内容（START READING HERE 等）")
        if req.remove_warning_boxes and "warning_box" in hyg:
            add("strip_warn", actions.remove_warning_boxes,
                "删除 WARNING 类告示块")

        # 2) L：页数限制压缩（仅当超页；默认不动全局版心）
        #    —— 调页边距/字号会让图表与正文重新分布、版面错位，属破坏性
        #    手段，仅当用户显式开启 allow_geometry_tune 才作为候选。
        if has_page_lv:
            # 超宽图归一（图本身超出版心，归一属于修复且能省行，始终允许）
            if S._overwide_figs(per, req):
                add("fig_norm", actions.normalize_fig_width,
                    "压页：超宽图归一化到 \\linewidth")
            if req.allow_geometry_tune:
                # margin 压缩下限：不得低于要求 margin（若有）或安全下限
                floor = max(req.margin_mm or 0, req.margin_min_mm)
                if cur_margin is not None and cur_margin > floor + 1e-6:
                    nxt = max(cur_margin - req.margin_step_mm, floor)
                    add("margin_cut",
                        lambda s, n=nxt, c=cur_margin:
                            actions.set_margin(s, n, cur_mm=c),
                        f"压页：页边距 {cur_margin:g}mm -> {nxt:g}mm"
                        f"（用户已授权版心调整）")
                if req.allow_fontsize_step and req.font_pt is None \
                        and cur_font > 10:
                    add("font_cut",
                        lambda s, n=cur_font - 1: actions.set_fontsize(s, n),
                        f"压页：字号 {cur_font}pt -> {cur_font - 1}pt"
                        f"（用户已授权版心调整）")

        # 3) 质量 / 松弛（L 已全清时：最小干预回拉 + 审美改善）
        if not cur_lv and req.allow_geometry_tune:
            if req.font_pt is None and cur_font < orig_font:
                add("font_back",
                    lambda s, n=cur_font + 1: actions.set_fontsize(s, n),
                    f"松弛：字号 {cur_font}pt -> {cur_font + 1}pt（回近原稿）")
            if cur_margin is not None and orig_margin is not None \
                    and cur_margin < orig_margin - 1e-6 \
                    and (not req.page_limit or S.within_limit(per, req)):
                nxt = min(cur_margin + req.margin_step_mm, orig_margin)
                if margin_floor_mode and req.margin_mm:
                    nxt = max(nxt, req.margin_mm)   # 松弛不得低于官方下限
                add("margin_back",
                    lambda s, n=nxt, c=cur_margin:
                        actions.set_margin(s, n, cur_mm=c),
                    f"松弛：页边距 {cur_margin:g}mm -> {nxt:g}mm（回近原稿）")
        # 浮动体参数规范化（无论 L，改善放置稳定性；[H] 强排会把图钉死在
        # 本行，是页面失衡/大块留白的常见来源，由全局评分仲裁是否保留）
        specs = [(fe.get("spec") or "").strip()
                 for fe in src.get("float_envs", [])]
        unstable = any(actions._unstable_spec(sp) for sp in specs if sp)
        has_H = any(sp == "H" for sp in specs)
        if unstable or (has_H and req.free_floating_H):
            add("float_spec",
                lambda s, n=req.float_spec, h=req.free_floating_H:
                    actions.sanitize_float_specs(s, n, include_H=h),
                f"浮动体位置参数规范化（目标 [{req.float_spec}]"
                + ("，含 [H] 强排解绑" if has_H and req.free_floating_H else "")
                + "）")
        # 裸 $$ 数学归一（源码卫生，可安全自动）
        if any(h["kind"] == "dollar_math"
               for h in per.issues.get("hygiene", [])):
            add("math_cleanup", actions.normalize_dollar_math,
                "裸 $$..$$ 数学归一为 \\[..\\]")
        # 超宽图归一（纯审美路径；阈值内自然跳过）
        if S._overwide_figs(per, req):
            add("fig_norm", actions.normalize_fig_width,
                "超宽图归一化到 \\linewidth")

        # 2.5) 确定性排版卫生修复（2026-09-11 新增）
        #      —— 「感知层检测到了，但以前没有任何动作能修」的那批问题。
        #      每条仍走 应用→整篇重编译→全局评分→接受/回滚，任何一条
        #      若让全局分不降，就被回滚并记 blocked（不会贸然破坏版面）。
        hyg_kinds = {h["kind"] for h in per.issues.get("hygiene", [])}
        if req.tidy_manual_pagebreaks and "manual_pagebreak" in hyg_kinds:
            add("pagebreak_rm", actions.remove_manual_pagebreak,
                "删除正文手动分页（\\newpage/\\clearpage），交回 LaTeX 全局断页")
        if req.tidy_manual_vspace and "manual_vspace" in hyg_kinds:
            add("vspace_rm",
                lambda s, m=req.vspace_min_mm: actions.remove_excessive_vspace(
                    s, m * 72.27 / 25.4),
                f"删除过大的手动垂直间距（≥ {req.vspace_min_mm:g}mm）")
        if req.normalize_heading_size and "heading_size" in hyg_kinds:
            add("heading_size", actions.normalize_heading_size,
                "标题字号压回层级上限（section ≤ \\Large 等）")
        if req.normalize_local_font_size and "size_switch" in hyg_kinds:
            add("local_font", actions.normalize_local_font_size,
                "删除正文行内字号乱标（\\Large/\\tiny…）")
        if req.reduce_list_spacing and "list_spacing" in hyg_kinds:
            add("list_spacing",
                lambda s, m=req.list_spacing_max_pt:
                    actions.reduce_list_spacing(s, m),
                f"收紧列表间距（> {req.list_spacing_max_pt:g}pt 的 itemsep/topsep…）")
        if req.break_long_urls and "long_url" in hyg_kinds:
            add("url_break", actions.break_long_urls,
                "注入 \\usepackage{xurl}（超长 URL 断行）")
        if req.break_long_words and "unbreakable" in hyg_kinds:
            add("hyphenate", actions.add_hyphenation_points,
                "为超长不可断词插入 \\- 断词点（TeX 合法断行机制）")
        if req.fix_overwide_tables and per.issues.get("tables_overwide"):
            _tlines = [t["line"] for t in per.issues["tables_overwide"]
                       if t.get("line")]
            add("table_width",
                lambda s, ln=_tlines: actions.fix_table_width(s, ln),
                "超宽表格改用 tabularx（\\linewidth 自适应列宽）")
        # 2.6) Phase 2：版面/页面级缺陷 -> 动作（阈值与检测同源）
        if req.normalize_title and "title_size" in hyg_kinds:
            add("title_size",
                lambda s, c=req.title_size_cap: actions.normalize_title(s, c),
                f"文档标题字号压回上限（≤ \\{req.title_size_cap}）")
        if req.normalize_parskip and "parskip" in hyg_kinds:
            add("parskip",
                lambda s, m=req.parskip_max_pt: actions.normalize_parskip(s, m),
                f"收敛过大的 \\parskip（≤ {req.parskip_max_pt:g}pt）")
        if req.normalize_header and "header_abnormal" in hyg_kinds:
            add("header_norm",
                lambda s, m=req.header_max_chars: actions.normalize_header(s, m),
                f"清空过长页眉（> {req.header_max_chars} 字符）")
        if req.remove_mid_multicols and "multicols_mid" in hyg_kinds:
            add("multicols", actions.remove_mid_multicols,
                "移除正文中途的局部双栏（内容保留）")
        if req.reduce_oversized_figures and \
                ({"fig_oversized", "subfig_overfull"} & hyg_kinds):
            add("fig_size",
                lambda s, h=req.max_fig_height_frac, t=req.subfig_max_sum:
                    actions.reduce_oversized_figures(s, h, t),
                "收敛过大图片（height/子图并排超版心）")
        # 表格列宽：超宽（overfull 落在 tabular）或明显窄于版心
        _tlines = [t["line"] for t in per.issues.get("tables_overwide", [])
                   if t.get("line")]
        _tlines += [h["line"] for h in per.issues.get("hygiene", [])
                    if h["kind"] == "table_narrow"]
        if req.fix_overwide_tables and _tlines:
            add("table_width",
                lambda s, ln=_tlines: actions.fix_table_width(s, ln),
                "表格改用 tabularx（超宽/窄表 -> \\linewidth 自适应列宽）")
        # 视觉信号驱动：明显「巨大内容块 / 内容孤立」-> 缩小满宽大图
        _vdef = S.visual_defects(per)
        if req.shrink_oversized_figures and any(
                d["kind"] in ("giant_content", "stranded_block") for d in _vdef):
            add("fig_shrink",
                lambda s, f=req.fig_shrink_factor:
                    actions.shrink_oversized_figures(s, f),
                f"按视觉信号缩小满宽大图（x{req.fig_shrink_factor:g}）")
        # 页面平衡 / 浮动体放置：有视觉缺陷或页面垂直质量问题时尝试
        if req.balance_pages and req.tune_float_placement \
                and (per.issues.get("vbox") or _vdef):
            add("page_balance", actions.balance_pages,
                "浮动体放置/页面平衡调优（raggedbottom + float fraction）")
        return cands

    # ------------------------------------------------------------- 单步执行
    def _step(self, per: P.Perception, cur: dict) -> bool:
        """执行一个正收益候选；返回是否接受。

        接受时把该状态的 (Perception, 评分) 存进 self._state，供主循环复用
        —— 免去“接受后再感知一次”的重复整篇编译。
        """
        self._state = None
        src = self._read()
        cur_lv = cur["l"]
        cur_pages = per.pages
        for key, apply_fn, note in self._candidates(per, cur_lv):
            sig = f"{len(cur_lv)}|{per.pages}"
            stamp = f"{key}@{sig}" if key in RETRYABLE_KEYS else key
            out = apply_fn(src)
            if out is None or not out[1]:
                self._blocked.add(stamp)
                continue
            new_src, note_ok = out[0], out[2]
            self.iter += 1
            self.attempts += 1
            self._write(new_src)
            nper = P.perceive(self.work_tex, self.req)
            ncur = S.total_score(nper, self.req, self.orig_per)
            accepted = nper.ok and self._accept(ncur, cur, nper.pages,
                                                cur_pages, cur_lv)
            if accepted:
                self.accepted += 1
                self._log(f"  [接受] {note_ok}")
                self._log(f"         L={len(ncur['l'])} A={ncur['a']} "
                          f"I={ncur['i']} 总分 {cur['total']} -> {ncur['total']}"
                          + (f" | {nper.pages} 页" if nper.pages else ""))
                self._record(note_ok, nper, ncur, True, True, "rule")
                self._state = (nper, ncur)
                return True
            # 回滚
            self._write(src)
            self._blocked.add(stamp)
            why = "" if nper.ok else \
                f"编译失败：{nper.compile.first_error}"
            self._log(f"  [回滚] {note_ok}（{why or '全局评分无改善'}）")
            self._record(note_ok, nper, ncur, False, nper.ok, "rule",
                         why or "全局评分无改善")
        return False

    def _accept(self, ncur: dict, cur: dict, n_pages, c_pages, cur_lv) -> bool:
        """验收：全局目标是否改善（lexicographic：L 优先，页数压缩组合放宽）。"""
        n_lv, c_lv = ncur["l"], cur["l"]
        if len(n_lv) < len(c_lv):
            return True
        if len(n_lv) > len(c_lv):
            return False
        # L 违规数相同：若仍在压页（双方都有页数违规），页数不增即保留
        # （省页可能需连续多档才兑现，避免丢失组合收益 —— 旧版『组合性』保证）
        if n_lv and any("页数" in x for x in n_lv) \
                and any("页数" in x for x in c_lv):
            return n_pages is not None and n_pages <= (c_pages or 1 << 30)
        # L 全清：严格模式 —— 全局评分必须改善（含松弛回拉的 I 收益）
        return ncur["total"] < cur["total"] - 1e-9

    # ------------------------------------------------------------- 主入口
    def run(self) -> dict:
        """确定性闭环：感知→评分→候选动作→编译→验收/回滚。

        resume=True 时沿用已有工作副本（模型在环续跑，不重拷原稿）。
        """
        issues = engine.check_environment() + engine.check_output_dir(self.outdir)
        if issues:
            return {"status": "FAILED", "reason": "；".join(issues)}
        os.makedirs(self.outdir, exist_ok=True)
        with open(self.original, encoding="utf-8", errors="replace") as f:
            self.orig_body = S.content_body(f.read())
        if self.resume:
            if not os.path.isfile(self.work_tex):
                return {"status": "FAILED",
                        "reason": f"没有可续跑的工作副本 {self.work_tex}；"
                                  "请先跑一次确定性闭环"}
        else:
            shutil.copyfile(self.original, self.work_tex)   # 原件只读，工作副本

        per = P.perceive(self.work_tex, self.req)
        if not per.ok:
            self._save_state("FAILED")
            return {"status": "FAILED", "reason": "基线文档无法编译",
                    "first_error": per.compile.first_error}
        self.orig_per = _static_perception(self.original)  # I 基准（静态解析，不编译）
        cur = S.total_score(per, self.req, self.orig_per)
        self.baseline = {"a": cur["a"], "i": cur["i"], "pages": per.pages,
                         "total": cur["total"], "l": len(cur["l"])}

        self._log(f"基线：{os.path.basename(self.original)} "
                  f"{per.pages} 页 | 字号 {per.source['font_pt']}pt | "
                  f"边距 {per.source['geometry_margin_mm']:g}mm"
                  + ("（续跑已有工作副本）" if self.resume else ""))
        self._log(f"要求：模板/规格 -> {self._req_summary()}")
        self._log(f"初始全局评分：L={len(cur['l'])} A={cur['a']} I={cur['i']} "
                  f"(总分 {cur['total']})")
        for v in cur["l"]:
            self._log(f"  [L 违规] {v}")
        if not cur["l"]:
            self._log("  L 达标（编译 ✓ 渲染 ✓ 内容零改动 ✓ 页数 ✓ 硬性规范 ✓）")

        # 连续无改善轮数达标才停（避免“一轮没吃到就收敛”）
        stall = 0
        while self.iter < self.req.max_iterations:
            if not self._step(per, cur):
                stall += 1
                if stall >= max(1, int(self.req.min_stall_rounds)):
                    break
                continue
            stall = 0
            if self._state is not None:               # 复用接受态（免重复编译）
                per, cur = self._state
            else:
                per = P.perceive(self.work_tex, self.req)
                cur = S.total_score(per, self.req, self.orig_per)
        else:
            self._log(f"[!] 达到迭代上限 {self.req.max_iterations}")
        return self.finalize()

    # ------------------------------------------------------------- 模型在环
    def _proposal_key(self, item: dict) -> str:
        return json.dumps([item.get("action"), item.get("params")],
                          ensure_ascii=False, sort_keys=True)

    def apply_proposals(self, items: list[dict]) -> dict:
        """模型在环：逐条执行 LLM 提案，每步完整走 编译→全局评分→验收/回滚。

        与规则闭环共用同一套验收函数 _accept（L 优先、严格改善才保留），
        因此「LLM 觉得更好」不构成接受理由——必须过现实验证。
        未知动作/非法参数/已失败过的提案 → BLOCKED（不落地、不编译）。
        """
        result = {"applied": [], "rejected": [], "blocked": [], "skipped": []}
        self._ensure_orig()
        per = P.perceive(self.work_tex, self.req)
        if not per.ok:
            return {"error": "工作副本无法编译，无法执行提案"}
        cur = S.total_score(per, self.req, self.orig_per)

        for item in items:
            action = item.get("action")
            params = dict(item.get("params") or {})
            label = f"[LLM] {item.get('id','?')} {action} {params}"
            # 1) 白名单闸门
            v = whitelist.validate(action, params)
            if not v["ok"]:
                rec = {"id": item.get("id"), "action": action,
                       "params": params, "reason": "; ".join(v["errors"])}
                result["blocked"].append(rec)
                self._log(f"  [BLOCKED] {label}（{rec['reason']}）")
                self._record(label, per, cur, False, True, "llm",
                             "BLOCKED: " + rec["reason"])
                continue
            key = self._proposal_key(item)
            if key in self._llm_failed:
                result["skipped"].append({"id": item.get("id"),
                                          "reason": "同一提案此前已失败"})
                self._log(f"  [跳过] {label}（同一提案此前已失败）")
                continue
            # 2) 应用 → 编译 → 全局评分 → 验收
            src = self._read()
            res = whitelist.apply(action, src, v["params"])
            if not res["ok"] or not res["applied"]:
                note = res["note"] or "; ".join(res["errors"]) or "无改动"
                result["skipped"].append({"id": item.get("id"), "reason": note})
                self._log(f"  [跳过] {label}（{note}）")
                continue
            self.iter += 1
            self.attempts += 1
            self._write(res["new_src"])
            nper = P.perceive(self.work_tex, self.req)
            ncur = S.total_score(nper, self.req, self.orig_per)
            accepted = nper.ok and self._accept(ncur, cur, nper.pages,
                                                per.pages, cur["l"])
            tag = f"{item.get('issue','?')}/{item.get('location','')}".strip("/")
            if accepted:
                self.accepted += 1
                self._log(f"  [接受·LLM] {label}  ->  L={len(ncur['l'])} "
                          f"A={ncur['a']} I={ncur['i']} "
                          f"({cur['total']} -> {ncur['total']})"
                          + (f" | {nper.pages} 页" if nper.pages else ""))
                self._record(f"{label} | {tag}", nper, ncur, True, True,
                             "llm", res["note"])
                result["applied"].append({"id": item.get("id"),
                                          "note": res["note"],
                                          "l": ncur["l"], "a": ncur["a"],
                                          "i": ncur["i"],
                                          "total": ncur["total"]})
                per, cur = nper, ncur
            else:
                self._write(src)
                self._llm_failed.add(key)
                why = "" if nper.ok else f"编译失败：{nper.compile.first_error}"
                why = why or "全局评分无改善（L 优先 / 严格改善才保留）"
                self._log(f"  [回滚·LLM] {label}（{why}）")
                self._record(f"{label} | {tag}", nper, ncur, False, nper.ok,
                             "llm", why)
                result["rejected"].append({"id": item.get("id"),
                                           "reason": why})
        return result

    def emit_request(self, round_no: int = 1, with_visual: bool = True,
                     visual_dpi: int = 110) -> dict:
        """把当前状态 + 残余问题 + 白名单 + 页面图像 打包给 LLM。"""
        self._ensure_orig()
        per = P.perceive(self.work_tex, self.req)
        cur = S.total_score(per, self.req, self.orig_per)
        with open(self.original, encoding="utf-8", errors="replace") as f:
            orig_src = f.read()
        adv = advise.build_advisory(orig_src, per, self.req)
        images, verr = [], None
        if with_visual and per.ok and per.compile.pdf_path:
            vres = visual.visual_report(per.compile.pdf_path, self.outdir,
                                        dpi=visual_dpi)
            images = vres.get("images", [])
            verr = vres.get("error")
        req = proposal.build_request(
            per, self.req, cur, round_no, images, adv,
            doc_paths={"original_tex": self.original, "work_tex": self.work_tex,
                       "pdf": per.compile.pdf_path if per.ok else None,
                       "outdir": self.outdir})
        path = os.path.join(self.outdir, "llm_request.json")
        proposal.write_json(path, req)
        self._log(f"\n[模型在环] 已生成请求包：{path}"
                  f"（round {round_no}，{len(adv)} 条残余问题，"
                  f"{len(req['allowed_actions'])} 个可用动作，"
                  f"{len(images)} 张页面图）")
        return req

    # ------------------------------------------------------------- 收尾
    def finalize(self, status: str | None = None, per=None, cur=None) -> dict:
        """写 state.json / report.md / advisory.json，返回结果 dict。

        出口状态（2026-09-11 细分化）：
          DONE             L 达标且本轮应用了 ≥1 个被接受的动作（真改动了）
          NO_IMPROVEMENT   L 达标、有可动候选，但没有任何一个能改善版面
                           —— 不伪造“优化成功”（未修改任何内容）
          CONVERGED        L 达标且根本没有可动候选（文档本就没问题）
          EXHAUSTED        L 仍有违规（通常超页）且排版手段穷尽
          FAILED           基线无法编译 / 环境缺失
        关键：不再“L=0 就 CONVERGED”——L 与 A 分开看，A 还有可修项
        却无候选可动时，会如实报 NO_IMPROVEMENT 而不是 CONVERGED。
        """
        self._ensure_orig()
        if per is None:
            per = P.perceive(self.work_tex, self.req)
        if cur is None:
            cur = S.total_score(per, self.req, self.orig_per)
        self._defects = S.visual_defects(per)          # 供 exit_status 复用
        if status is None:
            status = self.exit_status(cur, self._defects)
        self._save_state(status, per, cur)
        self._write_report(status, per, cur)
        with open(self.original, encoding="utf-8", errors="replace") as f:
            orig_src = f.read()
        adv = advise.build_advisory(orig_src, per, self.req)
        with open(os.path.join(self.outdir, "advisory.json"), "w",
                  encoding="utf-8") as f:
            json.dump({"status": status, "count": len(adv),
                       "allowed_actions": [a["action"]
                                           for a in whitelist.describe()],
                       "items": adv}, f, ensure_ascii=False, indent=2)
        if adv:
            self._log(f"\n[模型在环] {len(adv)} 条残余问题待人工/LLM 决策"
                      f"（见 advisory.json，按 severity 排序）：")
            for it in adv[:8]:
                loc = f" 第{it['line']}行" if it["line"] else ""
                self._log(f"  [{it['severity']}] {it['kind']}{loc}: "
                          f"{it['issue'][:60]}")
            if len(adv) > 8:
                self._log(f"  …另 {len(adv) - 8} 条见 advisory.json")
        base = self.baseline or {"a": None, "pages": None}
        # 会议要求（会议模板）：只报告不伪造，供上层 Agent/报告消费
        conf = None
        if getattr(self.req, "conference", None):
            st = S.page_status(per, self.req) if per else {}
            conf = {
                "id": self.req.conference,
                "page_scope": st.get("scope"),
                "page_limit": self.req.page_limit,
                "pages_total": st.get("total"),
                "content_pages_lower": st.get("content_lower"),
                "content_pages_upper": st.get("content_upper"),
                "page_advisory": S.page_advisory(per, self.req) if per else None,
                "official": self.req.official_constraints,
                "reasonableness": confmod.reasonableness(per, self.req) if per
                else {"enabled": False},
                "unused": getattr(self.req, "unused_template_parts", None) or [],
            }
        return {"status": status, "l": cur["l"], "a": cur["a"], "i": cur["i"],
                "pages": per.pages, "tex": self.work_tex,
                "pdf": per.compile.pdf_path if per and per.ok else None,
                "advisory_count": len(adv),
                "accepted": self.accepted, "attempts": self.attempts,
                "visual_defects": list(self._defects),
                "ink_mean": (per.visual or {}).get("ink_mean") if per else None,
                "a_before": base["a"], "pages_before": base["pages"],
                "total": cur["total"], "total_before": base.get("total"),
                "conference": conf,
                "blocked": sorted({k.split("@")[0] for k in self._blocked})}

    def exit_status(self, cur: dict, defects: list | None = None) -> str:
        """出口状态判定（Phase 2：不只看 L，也不只看 A 数字）。

        DONE / CONVERGED 需要：L 达标 + 无 high 级视觉缺陷（+ 可选 A 上限）。
        仍有明显视觉缺陷时，如实报 NEEDS_REVIEW，而不是 DONE。
        """
        if cur["l"]:
            return "EXHAUSTED"
        defects = self._defects if defects is None else defects
        if any(d.get("severity") == "high" for d in (defects or [])):
            return "NEEDS_REVIEW"       # 仍存在明显视觉缺陷（已尽力/或需人工）
        if self.req.done_max_a is not None and cur["a"] > self.req.done_max_a:
            return "NEEDS_REVIEW"       # A 高于配置阈值
        if self.attempts == 0:
            return "CONVERGED"          # 无可动候选：文档本就达标
        if self.accepted == 0:
            return "NO_IMPROVEMENT"     # 有候选但全部没改善（已回滚/阻止）
        return "DONE"                   # 确实应用了被接受的动作

    def _req_summary(self) -> str:
        r = self.req
        parts = []
        conf = getattr(r, "conference", None)
        if conf:
            scope = "正文页" if getattr(r, "page_limit_scope", "total") == "content" \
                else "总页数"
            parts.append(f"会议模板 {conf}（页数按{scope}口径）")
        if r.page_limit:
            parts.append(f"页数 ≤ {r.page_limit}")
        if r.font_pt:
            parts.append(f"字号 {r.font_pt}pt")
        if r.margin_mm:
            parts.append(f"边距 {'≥ ' if getattr(r, 'margin_is_floor', False) else ''}"
                         f"{r.margin_mm:g}mm")
        parts.append(f"浮动体 [{r.float_spec}]")
        if not r.eq_fleqn_allowed:
            parts.append("公式居中")
        if r.enable_quality_macros:
            parts.append("禁孤行寡行")
        if r.toc:
            parts.append("目录页")
        if r.running_header:
            parts.append("页眉")
        if r.heading_color:
            parts.append(f"标题着色 {r.heading_color}")
        if r.strip_reading_aids:
            parts.append("清理阅读辅助")
        if r.remove_warning_boxes:
            parts.append("清理告示块")
        if r.preserve_figures:
            parts.append("图形保真")
        return "，".join(parts) if parts else "无额外要求（纯质量模式）"

    def _conference_section(self, per) -> list:
        """报告中的「会议要求」段：官方硬约束 → 违规判定；统计 → 合理性核对；
        模板里本版接不上的字段 → 逐条登记（任务要求 5/7）。"""
        r = self.req
        cid = getattr(r, "conference", None)
        if not cid:
            return []
        oc = getattr(r, "official_constraints", None) or {}

        def v(x):
            if x is None:
                return "—"
            return json.dumps(x, ensure_ascii=False) if isinstance(x, (dict, list)) else str(x)

        out = ["## 会议要求（会议模板 templates-v2）\n",
               f"- 会议模板：**{cid}**（官方要求仅作 L 判定；真实论文统计仅作合理性参考）",
               f"- 页数口径：**{oc.get('page_limit_scope')}**"
               f"（官方 references_counted={v(oc.get('references_counted'))}）；"
               f"本次 page_limit={r.page_limit}，实测正文页上界="
               f"{getattr(per, 'content_pages_upper', None)}"
               if per else "- 页数口径：—",
               "", "### 官方规定 → 违规判定（L 项）\n",
               "| 官方硬约束 | 值 | texopt 用法（对应字段） |",
               "|---|---|---|",
               f"| 正文页上限 | {v(oc.get('page_limit_content'))} | L `page_limit`={r.page_limit}",
               f"| 总页上限 | {v(oc.get('page_limit_total'))} | 参考（部分会议用）",
               f"| 参考文献计页 | {v(oc.get('references_counted'))} | 决定页数口径 = {oc.get('page_limit_scope')}",
               f"| 纸张尺寸 | {v(oc.get('paper_size'))} | 参考（本版不改 documentclass）",
               f"| 栏数 | {v(oc.get('columns'))} | 参考（本版不改 documentclass）",
               f"| 正文字号 | {v(oc.get('body_font_size_pt'))} | L `font_pt`={r.font_pt}",
               f"| 页边距（四边） | {v(oc.get('margins_mm'))} | L `margin_mm`={r.margin_mm}（取最小边）",
               f"| 双盲匿名 | {v(oc.get('anonymity'))} | 仅记录（无对应动作）",
               f"| paper checklist | {v(oc.get('checklist_required'))} | 仅记录（内容层）",
               f"| 录用加页 | {v(oc.get('camera_ready_extra_pages'))} | 本次按投稿版，不加页",
               ""]
        pa = S.page_advisory(per, r) if per else None
        if pa:
            out += [f"> 页数提示：{pa}", ""]

        rr = confmod.reasonableness(per, r) if per else {"enabled": False}
        if rr.get("enabled"):
            out += ["### 真实论文统计 → 合理性核对（仅参考，不参与判定）\n",
                    f"（样本 n={rr.get('sample_n')}，可信度 {rr.get('level')}；"
                    "下列偏差只说明『与常见论文不同』，**不判违规、不影响评分**）\n",
                    "| 指标 | 本文档 | 真实论文区间(P25–P75) | 状态 |",
                    "|---|---|---|---|"]
            for c in rr.get("checks", []):
                ref = c.get("reference") or {}
                if "p25" in ref:
                    ref_s = f"{ref.get('p25')}–{ref.get('p75')}"
                else:
                    ref_s = json.dumps(ref, ensure_ascii=False)
                obs = (json.dumps(c["observed"], ensure_ascii=False)
                       if isinstance(c["observed"], dict) else c["observed"])
                out.append(f"| {c['name']} | {obs}{c.get('unit', '')} "
                           f"| {ref_s} | {c['status']} |")
            for d in rr.get("deviations", []):
                out.append(f"\n> 参考：{d}")
            out.append("")
        elif getattr(r, "soft_targets", None):
            out += ["### 真实论文统计 → 合理性核对\n",
                    "未能量取可比指标（数据不足），不臆测。", ""]

        unused = getattr(r, "unused_template_parts", None) or []
        if unused:
            out += [f"### 模板中暂未接入的内容（{len(unused)} 项，已记录不强行接入）\n",
                    "详见 `datasets/conf-specs/summary/texopt-integration-report.md`。"
                    "（主要为：栏数/纸张/字体族等需换文档类的项、匿名与 checklist 等无动作的项、"
                    "样本统计类项。）", ""]
        return out

    # ------------------------------------------------------------- 落盘
    def _save_state(self, status: str, per=None, cur=None):
        state = {
            "status": status,
            "pages": per.pages if per else None,
            "scores": {
                "l_violations": cur["l"] if cur else [],
                "a": cur["a"] if cur else None,
                "i": cur["i"] if cur else None,
                "total": cur["total"] if cur else None,
            },
            "blocked_actions": sorted({k.split("@")[0] for k in self._blocked}),
            "llm_failed_proposals": sorted(self._llm_failed),
            "visual": (per.visual if per and per.visual else None),
            "visual_defects": (per.visual.get("defects") if per and per.visual
                               else None),
            "steps": self.records,
            "note": "steps 中 source=rule 为确定性闭环，source=llm 为模型在环提案；"
                    "全部经整篇重编译后全局重评，accepted=false 即已回滚。",
        }
        with open(os.path.join(self.outdir, "state.json"), "w",
                  encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)

    def _write_report(self, status: str, per, cur):
        r = self.req
        base = self.baseline or {}
        a0, p0 = base.get("a"), base.get("pages")
        if status == "DONE":
            headline = (f"✅ DONE：应用了 {self.accepted} 个被接受的动作"
                        f"（尝试 {self.attempts} 个候选）。"
                        f"A: {a0} -> {cur['a']}；页数: {p0} -> "
                        f"{per.pages if per else '—'}")
        elif status == "NO_IMPROVEMENT":
            headline = ("⚠ NO_IMPROVEMENT：试过 "
                        f"{self.attempts} 个候选，没有任何一个能改善全局评分"
                        "，已全部回滚 —— 未修改任何内容（不伪造“优化成功”）")
        elif status == "CONVERGED":
            headline = ("✅ CONVERGED：L 全部达标，且没有可动的候选“动作”"
                        "（文档本身已无可自动修的排版问题）")
        elif status == "NEEDS_REVIEW":
            ds = self._defects
            hi = [d for d in ds if d.get("severity") == "high"]
            headline = (f"⚠ NEEDS_REVIEW：排版已尽量优化，但仍有 {len(ds)} 项视觉缺陷"
                        f"（其中 {len(hi)} 项 high）未消除 —— 未判定为 DONE，"
                        "请人工/后续阶段复核（见下「视觉版面质量」与"
                        "「仍需人工处理的问题」）")
        elif status == "EXHAUSTED":
            headline = ("⚠ EXHAUSTED：纯排版手段已穷尽，仍缺 L 硬约束"
                        f"（L 违规 {len(cur['l'])} 项）")
        else:
            headline = f"{status}"
        L = ["# texopt 论文排版优化报告\n",
             f"- 输入文档：`{self.original}`",
             f"- 排版要求：{self._req_summary()}",
             (f"- 最终页数：{per.pages}（正文页数（参考文献之前，含参考文献首页）= "
              f"{getattr(per, 'content_pages_upper', None)}；"
              f"判定口径：{S.page_status(per, r)['label']}）"
              if per and per.ok and getattr(per, "content_pages_upper", None)
              else f"- 最终页数：{per.pages if per and per.ok else '—'}"),
             f"- 全局评分：L 违规 {len(cur['l'])} 项 | A（审美）= {cur['a']} | "
             f"I（干预代价）= {cur['i']}",
             f"- 结果：**{status}**",
             f"- {headline}",
             ""]

        # L 硬约束状态
        L += ["## L 基础逻辑量化（硬约束）\n"]
        l_items = {
            "编译": "编译通过且 PDF 已渲染" if per and per.ok else "编译失败",
            "内容完整": ("正文相对原稿零改动（机器 diff 校验通过）"
                          + ("；已按要求清理阅读辅助/告示块"
                             if (r.strip_reading_aids
                                 or r.remove_warning_boxes) else "")),
            "页数限制": (f"{S.judge_pages(per, r)} 页"
                         f"（{S.page_status(per, r)['label']}；PDF 共 {per.pages} 页）"
                         + (f" ≤ {r.page_limit}" if r.page_limit else "（未要求）"))
                        if per and per.pages else "—",
            "目录页": ("已含 \\tableofcontents" if per and per.source.get("has_toc")
                       else "（未要求）") if r.toc else "（未要求）",
            "页眉": ("已设置" if per and per.source.get("has_header")
                     else "缺失") if r.running_header else "（未要求）",
            "图形保真": "未重绘/改写" if r.preserve_figures else "（未要求）",
        }
        for k, v in l_items.items():
            L.append(f"- {k}：{v}")
        L.append("- 硬性规范（字号/边距/公式居中）："
                 + ("达标" if not any("字号" in x or "页边距" in x
                                      or "fleqn" in x for x in cur["l"])
                    else "未达标"))
        if cur["l"]:
            L.append("\n未达标的 L 项：")
            for v in cur["l"]:
                L.append(f"  - {v}")
        L.append("")

        # ---- 会议要求（会议模板 templates-v2；指定 --conference 时才有） ----
        L += self._conference_section(per)

        # 迭代轨迹
        L += ["## 迭代轨迹（每步 = 整篇重编译后全局重评）\n",
              "（来源 rule = 确定性闭环；llm = 模型在环提案，均过同一验收函数）\n",
              "| # | 来源 | 动作 | L | A | I | 总分 | 结果 |",
              "|---|------|------|---|---|---|------|------|"]
        for rec in self.records:
            mark = "✅接受" if rec["accepted"] else "↩回滚"
            src = rec.get("source", "rule")
            act = rec["action"]
            if not rec["accepted"] and rec.get("detail"):
                act += f"（{rec['detail'][:40]}）"
            L.append(f"| {rec['iteration']} | {src} | {act} | "
                     f"{len(rec['l'])} | {rec['a']} | {rec['i']} | "
                     f"{rec['total']} | {mark} |")
        L.append("")
        if self._blocked or self._llm_failed:
            L += ["### 被阻止/已失败的动作（防重复试错）\n"]
            if self._blocked:
                L.append("- 规则闭环失败动作：" + "，".join(
                    sorted({k.split("@")[0] for k in self._blocked})))
            if self._llm_failed:
                L.append(f"- LLM 失败提案指纹 {len(self._llm_failed)} 条（同提案跨轮跳过）")
            L.append("")

        # 残余问题清单（A 项，未自动修复）
        if per and per.ok:
            iss = per.issues
            resid = []
            for v in iss["vbox"]:
                resid.append(f"页面垂直质量问题（{v['kind']} vbox，"
                             f"badness {v['detail']}）——孤行寡行/断页质量代理信号")
            resid += [f"正文行溢出 Overfull \\hbox（{o['detail']}，"
                      f"第 {o['lines']} 行）" for o in iss["overfull"][:10]]
            resid += [f"浮动体警告：{w}" for w in iss["floats"][:10]]
            resid += [f"表格超宽（overfull 第 {t['line']} 行，"
                      f"{t['detail']}）——只报告不自动改，建议收窄列宽/换 tabularx"
                      for t in iss["tables_overwide"][:10]]
            hygiene_label = {
                "dollar_math": "裸 $$ 数学", "manual_pagebreak": "手动分页",
                "manual_vspace": "手动垂直间距", "underline_abuse": "下划线滥用",
                "noindent": "\\noindent", "size_switch": "字号乱标",
                "hard_linebreak": "硬换行", "center_text": "center 包裹正文",
                "missing_caption": "缺题注", "unbreakable": "超长不可断词",
                "reading_aid": "阅读辅助内容", "warning_box": "WARNING 告示块",
            }
            # 卫生项统一放在「仍需人工/后续处理的问题」一节（避免重复列出）
            if resid:
                L += ["## 残余日志层问题（未能/不自动修复）\n"]
                for x in resid:
                    L.append(f"- {x}")
                L.append("")
                L.append("> 说明：有对应确定性动作的卫生项（手动分页/过大垂直间距/"
                         "行内字号乱标/标题字号/列表间距/超长不可断词/超宽表格）"
                         "已经进入闭环尝试；此处列出的是「全局评分判负已回滚」或"
                         "「需作者意图、程序不擅动」的残留项。孤行寡行的像素级检测"
                         "与留白审美需页面图像视觉层（advanced 阶段，多源判断："
                         "源代码+日志+PDF+图像）；本版以 vbox 信号 + 断行质量宏"
                         "（club/widow penalty）+ \\raggedbottom 作为该维度的代理。")
                L.append("")

        if status == "EXHAUSTED":
            jp = S.judge_pages(per, r) if per else None
            diff = (jp - r.page_limit) if jp and r.page_limit else "?"
            L += ["## 未达标分析与建议\n",
                  "纯排版手段（页边距至下限、字号、浮动体、图片归一）已穷尽，"
                  f"仍差约 **{diff} 页**。下一步属于语义层（Key point 1 的"
                  "兜底路径——纯排版无法解决才允许）：",
                  "1. LLM 语义保意精简（SRTP 后续阶段，受『内容保留率下限』约束）；",
                  "2. 作者人工精简 / 压缩合并图表（需作者决策，Agent 不擅动内容）。"]
            L.append("")

        # ---- 视觉版面质量（Phase 2：来自实际编译后的 PDF） ----
        vis = per.visual if per else None
        if vis and not vis.get("error") and vis.get("pages"):
            L += ["## 视觉版面质量（量自实际编译后的 PDF）\n",
                  f"- 页面数：{vis.get('n')}；墨迹占比 均值 {vis.get('ink_mean')} "
                  f"（最低 {vis.get('ink_min')}，最高 {vis.get('ink_max')}）",
                  f"- 视觉缺陷：{len(self._defects)} 项"
                  + ("" if self._defects else "（无）"),
                  "",
                  "| 页 | 墨迹占比 | 顶部空白 | 底部空白 | 内容高度 | 最大空白带 | "
                  "位置 | 最大内容带 | 上/下半墨迹比 |",
                  "|---|---|---|---|---|---|---|---|---|"]
            for m in vis["pages"]:
                if "error" in m:
                    L.append(f"| {m.get('page')} | — | — | — | — | — | — | — | — |")
                    continue
                L.append(f"| {m['page']} | {m['ink_ratio']} | {m['top_blank']} | "
                         f"{m['bottom_blank']} | {m['content_height']} | "
                         f"{m['max_gap']} | {m['max_gap_at']} | {m['band']} | "
                         f"{m['top_bottom_ratio']} |")
            L.append("")
            if self._defects:
                L.append("视觉缺陷清单（程序判定，已计入 A）：\n")
                for d in self._defects:
                    pag = f"第{d['page']}页 " if d.get("page") else ""
                    L.append(f"- [{d['severity']}] {pag}{d['kind']}：{d['detail']}")
                L.append("")
        elif vis and vis.get("error"):
            L += ["## 视觉版面质量\n",
                  f"- 视觉量化不可用：{vis.get('error')}", ""]

        # ---- 仍需人工处理的问题（不伪造“已完成”） ----
        todo = []
        for d in self._defects:
            pag = f"第{d['page']}页 " if d.get("page") else ""
            todo.append(f"[视觉/{d['severity']}] {pag}{d['kind']}：{d['detail']}")
        hy_label = {
            "dollar_math": "裸 $$ 数学", "manual_pagebreak": "手动分页",
            "manual_vspace": "手动垂直间距", "underline_abuse": "下划线滥用",
            "noindent": "\\noindent", "size_switch": "字号乱标",
            "hard_linebreak": "硬换行", "center_text": "center 包裹正文",
            "missing_caption": "缺题注", "unbreakable": "超长不可断词",
            "reading_aid": "阅读辅助内容", "warning_box": "WARNING 告示块",
            "long_url": "超长 URL", "title_size": "标题字号", "parskip": "段间距",
            "header_abnormal": "页眉异常", "multicols_mid": "中途双栏",
            "fig_oversized": "图片过大", "subfig_overfull": "子图超版心",
            "table_narrow": "表格过窄", "heading_size": "标题字号",
            "list_spacing": "列表间距",
        }
        kind2key = {
            "manual_pagebreak": "pagebreak_rm", "manual_vspace": "vspace_rm",
            "size_switch": "local_font", "heading_size": "heading_size",
            "list_spacing": "list_spacing", "unbreakable": "hyphenate",
            "long_url": "url_break", "title_size": "title_size",
            "parskip": "parskip", "header_abnormal": "header_norm",
            "multicols_mid": "multicols", "fig_oversized": "fig_size",
            "subfig_overfull": "fig_size", "table_narrow": "table_width",
            "dollar_math": "math_cleanup",
        }
        for h in (per.issues.get("hygiene", []) if per and per.ok else []):
            key = kind2key.get(h["kind"])
            note = ("（已进入闭环尝试，被视觉/全局评分判负已回滚 → 说明改它反而更差；"
                    "需作者决策）" if key and any(
                        k.split("@")[0] == key for k in self._blocked) else
                    ("（暂无对应确定性动作，需作者决策）"
                     if key is None else ""))
            todo.append(f"[卫生/{h['kind']}] 第{h['line']}行：{h['detail']}{note}")
        if per and per.ok:
            for o in per.issues.get("overfull", [])[:10]:
                todo.append(f"[日志] 正文行溢出 {o['detail']}（第 {o['lines']} 行）")
            for v in per.issues.get("vbox", [])[:10]:
                todo.append(f"[日志] {v['kind']} vbox（{v['detail']}）")
            for w in per.issues.get("floats", [])[:10]:
                todo.append(f"[日志] 浮动体警告：{w}")
            for w in per.issues.get("warnings", [])[:10]:
                todo.append(f"[日志] 编译警告：{w}")
        if todo:
            L += ["## 仍需人工/后续处理的问题\n",
                  f"共 {len(todo)} 项（含已尝试但被全局/视觉评分判负回滚的项）：\n"]
            for x in todo[:40]:
                L.append(f"- {x}")
            if len(todo) > 40:
                L.append(f"- …另 {len(todo) - 40} 项见 advisory.json / state.json")
            L.append("")
        else:
            L += ["## 仍需人工/后续处理的问题\n",
                  "- 无（视觉缺陷 + 源码卫生 + 编译日志均无残余项）", ""]

        L.append("> 内容完整性：正文内容（文字/公式/引用/图表内容）全程零改动（机器"
                 "diff 校验，白名单排版参数除外）；原文件只读，结果在工作副本 "
                 "`paper.tex`（连同 PDF）。")
        with open(os.path.join(self.outdir, "report.md"), "w",
                  encoding="utf-8") as f:
            f.write("\n".join(L))


def _static_perception(tex_path: str) -> P.Perception:
    """构造一个不触发编译的 Perception（只含源码静态信息）。

    干预代价 I 只依赖源码层指标（字号/边距/浮动体 spec/图宽），
    无需编译原件 —— 模型在环每步 verify 因此只需编译工作副本一次。
    """
    with open(tex_path, encoding="utf-8", errors="replace") as f:
        src = f.read()
    return P.Perception(src=src, source=P.parse_source(src),
                        compile=engine.CompileResult(
                            ok=True, returncode=None),
                        issues={}, pages=None, pdf_pages=None)


def verify(work_tex: str, orig_tex: str, req: Requirement,
           outdir: str | None = None) -> dict:
    """模型在环验证：只读。编译工作副本 -> 全局评分 -> 内容完整性 ->
    建议清单。绝不修改任何文件；每步编辑后用它与原稿对照。
    """
    per = P.perceive(work_tex, req)
    if not per.ok:
        return {"status": "COMPILE_FAIL", "ok": False,
                "pages": None, "first_error": per.compile.first_error,
                "advisory": []}
    orig = _static_perception(orig_tex)
    cur = S.total_score(per, req, orig)
    with open(orig_tex, encoding="utf-8", errors="replace") as f:
        orig_src = f.read()
    # 模型在环标准：L 的正文项 = 语义词元保留（排版命令级变化可接受）。
    # 引擎白名单标准（归一 diff）单独作为 content_preserved 报告。
    sem = S.semantic_diff(orig_src, per.src, req)
    lv = cur["l"]
    if sem["preserved"]:
        lv = [v for v in lv if "正文内容被改动" not in v]
    adv = advise.build_advisory(orig_src, per, req)
    ok = not lv
    out = {
        "status": "OK" if ok else "L_VIOLATION",
        "ok": ok, "pages": per.pages,
        "l": lv, "a": cur["a"], "i": cur["i"],
        "total": round(S.L_PENALTY * len(lv) + cur["a"] + cur["i"], 3),
        "content_preserved": S.body_unchanged(orig_src, per.src, req),
        "semantic": sem,
        "advisory": adv,
        "pdf": per.compile.pdf_path if per.ok else None,
    }
    if outdir:
        os.makedirs(outdir, exist_ok=True)
        with open(os.path.join(outdir, "verify.json"), "w",
                  encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
    return out
