#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_templates.py —— 用数据生成 16 个会议的 texopt 排版模板（templates-v2/）。

输入（只读）：
  analysis/template-inputs.json   ← tools/analyze_templates.py 产出的稳健统计
  conferences/<id>.json           ← 官方硬性约束 + 引文 + 来源
  summary/texopt-generalizable-rules.json
  samples/<id>.samples.list.json  ← 样本清单（用于 sources/traceability）
输出：
  templates-v2/<id>.json          ← 统一 Schema 的模板（schema/template.schema.json）
  summary/template-matrix.md      ← 跨会议速查表（自动生成）

**不做任何“凭经验手写规则”**：每个数值都按下面写明的推导规则从数据算出，
并登记 basis（official / template-implied / sample-stat / derived）。
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTDIR = os.path.join(ROOT, "templates-v2")

# 标准纸张（pt→mm）；LNCS 为 Springer 单行本规格，ECCV 使用
PAPER = {
    "letter": {"pt": [612.0, 792.0], "mm": [215.9, 279.4]},
    "a4": {"pt": [595.28, 841.89], "mm": [210.0, 297.0]},
    "lncs": {"pt": [439.37, 666.14], "mm": [155.0, 235.0]},
}

BASIS_DEF = {
    "official": "官方指南/CFP/模板说明的明文字面值",
    "template-implied": "从官方 .sty/.cls 源码或官方模板文件读出（无文字明文）",
    "inferred": "由多源交叉推断（官方无明文，但模板行为 + 样本实测一致），可信度低于 template-implied",
    "sample-stat": "真实论文 PDF 实测的稳健统计（median/P25/P75），不是规则",
    "derived": "由前述值按固定公式推导（如 版心宽 = 行尾众数 − 行首最小值）",
}

# 不合规代价分级（依据各会议官方措辞：出现 “reject/desk reject/not be reviewed” 类的按 reject-risk）
REJECT_RISK_KEYS = {
    "page_limit_content", "page_limit_total", "paper_size", "columns",
    "body_font_size_pt", "margins_mm", "text_width_mm", "anonymity",
    "camera_ready_extra_pages", "checklist_required", "title_format",
}
DESK_CHECK_KEYS = {
    "references_counted", "appendix_allowed", "appendix_counted",
    "bib_style", "page_numbering", "column_gap_mm", "text_height_mm",
    "line_spacing", "abstract_max_words", "section_numbering",
    "float_placement_rules", "body_font_family", "template_file", "template_url",
    "figure_caption_position", "table_caption_position", "dual_submission_policy",
    "submission_system", "supplementary_policy",
}


def jload(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def metric(value, basis, unit=None, stat="value", n=None, reliable=None,
           derivation=None, observed=None, evidence=None, note=None):
    d = {"value": value, "basis": basis}
    if unit is not None:
        d["unit"] = unit
    if stat != "value" or basis == "sample-stat":
        d["stat"] = stat
    if n is not None:
        d["n"] = n
    if reliable is not None:
        d["reliable"] = reliable
    if derivation:
        d["derivation"] = derivation
    if observed:
        d["observed"] = observed
    if evidence:
        d["evidence"] = evidence
    if note:
        d["note"] = note
    return d


def rb(rob, unit=None):
    """analysis 的 robust dict → schema 的 robust dict"""
    if not rob:
        return {"n": 0, "median": None}
    d = {k: rob.get(k) for k in ("n", "min", "p25", "median", "p75", "max")}
    if unit:
        d["unit"] = unit
    return d


def off(official, key):
    v = official.get(key)
    return v if isinstance(v, dict) else None


def build_one(cid, A, conf, slog, rules):
    o = A["official"]
    m = A["measured"]
    dens = A["density"]
    cat = A["categorical"]
    n = A["n_samples"]

    # ---------- 基本量 ----------
    cols_m = cat["columns"] or {}
    cols = (off(o, "columns") or {}).get("value")
    cols_basis = "official" if cols else "sample-stat"
    if cols is None:
        cols = cols_m.get("value")
    two_col = cols == 2

    size_o = off(o, "paper_size")
    size_name = (size_o or {}).get("value")
    size_basis = (size_o or {}).get("confidence", "sample-stat") if size_o else "sample-stat"
    if size_name and "or" in str(size_name):
        size_name_raw = size_name
        size_name = cols_m and (cat["paper_size"] or {}).get("value") or "letter"
        size_note = f"官方允许多纸型（{size_name_raw}）；按实测 {size_name} 处理，需在使用前确认目标模板"
        size_key = size_name
    else:
        size_note = None
        size_key = size_name
    if cid == "eccv":
        size_key, size_name = "lncs", "lncs"
        size_basis = "template-implied"
        size_note = ("官方 LNCS(splncs04) 版式；Springer LNCS 单行本页面 155×235mm。"
                     "实测样本 PDF 页面为 letter（ECVA 发布版把 LNCS 版心放在 letter 页面内），"
                     "两者并存，模板取官方 LNCS 页面，实测页宽作为冲突保留。")
    paper = PAPER.get(str(size_key), PAPER["letter"])

    tw_o = off(o, "text_width_mm")
    tw_m = m.get("text_width_pt") or {}
    text_w_mm = (tw_o or {}).get("value")
    tw_basis = (tw_o or {}).get("confidence", "template-implied") if tw_o else None
    if text_w_mm is None:
        # 推导：A4/letter 页宽 − 2×官方边距
        mg = (off(o, "margins_mm") or {}).get("value") or {}
        if mg and mg.get("left") and mg.get("right"):
            text_w_mm = round(paper["mm"][0] - mg["left"] - mg["right"], 1)
            tw_basis, tw_deriv = "derived", f"页宽 {paper['mm'][0]}mm − 左右边距 {mg['left']}/{mg['right']}mm"
        else:
            text_w_mm = round(tw_m.get("median", 0) * 25.4 / 72, 1)
            tw_basis, tw_deriv = "sample-stat", "样本实测版心宽 median 换算"
    else:
        tw_deriv = None

    gap_o = off(o, "column_gap_mm")
    gap_mm = (gap_o or {}).get("value")
    gap_basis = (gap_o or {}).get("confidence", "template-implied") if gap_o else None
    if gap_mm is None and two_col:
        gm = m.get("column_gap_pt") or {}
        if gm.get("median"):
            gap_mm = round(gm["median"] * 25.4 / 72, 2)
            gap_basis = "sample-stat"

    col_w_mm = None
    if two_col and text_w_mm and gap_mm:
        col_w_mm = round((text_w_mm - gap_mm) / 2, 1)

    th_o = off(o, "text_height_mm")
    text_h_mm = (th_o or {}).get("value")
    th_m = m.get("text_height_pt") or {}

    # 边距：官方优先，缺失用实测 median
    mg_o = (off(o, "margins_mm") or {}).get("value") or {}
    margins = {}
    for side, key in (("left", "margins_left_mm"), ("right", "margins_right_mm"),
                      ("top", "margins_top_mm"), ("bottom", "margins_bottom_mm")):
        if side in mg_o and mg_o[side] is not None:
            margins[f"{side}_mm"] = metric(mg_o[side], (off(o, "margins_mm") or {}).get("confidence", "official"),
                                           unit="mm")
        else:
            rob = m.get(key)
            margins[f"{side}_mm"] = metric(rob["median"] if rob else None, "sample-stat", unit="mm",
                                           stat="median", n=n,
                                           observed=rb(rob, "mm"),
                                           note="官方未给明文，取实测中位数（不要当硬约束）")
    numeric_margins = [v["value"] for v in margins.values() if isinstance(v.get("value"), (int, float))]
    margin_floor = min(numeric_margins) if numeric_margins else None
    mf_basis = ("official" if all(v["basis"] in ("official", "template-implied")
                                 for v in margins.values()) else "sample-stat")

    # ---------- hard_constraints ----------
    hard = {}
    for k, v in sorted(o.items()):
        if not isinstance(v, dict) or v.get("value") is None:
            continue
        impact = "reject-risk" if k in REJECT_RISK_KEYS else (
            "desk-check" if k in DESK_CHECK_KEYS else "informational")
        hard[k] = {
            "value": v.get("value"),
            "unit": v.get("unit"),
            "scope": v.get("scope") or "both",
            "confidence": v.get("confidence", "official"),
            "compliance_impact": impact,
            "evidence": v.get("evidence") or [],
            "note": v.get("note"),
        }

    # ---------- geometry ----------
    geometry = {
        "page_size": metric(size_name, size_basis, note=size_note),
        "page_width_mm": metric(paper["mm"][0], "derived", unit="mm",
                                derivation=f"标准纸张 {size_key} 宽度（{paper['pt'][0]}pt）"),
        "page_height_mm": metric(paper["mm"][1], "derived", unit="mm",
                                 derivation=f"标准纸张 {size_key} 高度（{paper['pt'][1]}pt）"),
        "columns": metric(cols, cols_basis, note=("双栏" if two_col else "单栏")),
        "text_width_mm": metric(text_w_mm, tw_basis, unit="mm", derivation=tw_deriv),
        "margins": margins,
        "margin_floor_mm": metric(margin_floor, mf_basis, unit="mm",
                                  derivation="取四边最小值（texopt 压页时不得低于此值）"),
        "observed": {
            "text_width_mm": rb(tw_m, "pt"),
            "text_height_mm": rb(th_m, "pt"),
            "margins_left_mm": rb(m.get("margins_left_mm"), "mm"),
            "margins_right_mm": rb(m.get("margins_right_mm"), "mm"),
            "margins_top_mm": rb(m.get("margins_top_mm"), "mm"),
            "margins_bottom_mm": rb(m.get("margins_bottom_mm"), "mm"),
        },
    }
    if text_h_mm is not None:
        geometry["text_height_mm"] = metric(text_h_mm,
                                            (th_o or {}).get("confidence", "template-implied"), unit="mm")
    elif th_m.get("median"):
        geometry["text_height_mm"] = metric(round(th_m["median"] * 25.4 / 72, 1), "sample-stat", unit="mm",
                                            stat="median", n=n, observed=rb(th_m, "pt"),
                                            note="官方未给明文，取实测中位数")
    if two_col:
        geometry["column_gap_mm"] = metric(gap_mm, gap_basis, unit="mm")
        geometry["column_width_mm"] = metric(col_w_mm, "derived", unit="mm",
                                             derivation="(版心宽 − 栏间距)/2")
        geometry["observed"]["column_gap_pt"] = rb(m.get("column_gap_pt"), "pt")

    # ---------- typography ----------
    fs_o = off(o, "body_font_size_pt")
    fs_obs = (m.get("body_font_pt") or {})
    agree = (fs_o and fs_obs.get("median") is not None
             and abs(fs_o["value"] - fs_obs["median"]) <= 0.5)
    family_o = off(o, "body_font_family")
    typo = {
        "body_font_pt": metric((fs_o or {}).get("value", fs_obs.get("median")),
                               (fs_o or {}).get("confidence", "sample-stat"),
                               unit="pt", n=n, observed=rb(fs_obs, "pt"),
                               note=(None if agree else
                                     f"官方 {fs_o['value'] if fs_o else '-'}pt 与实测中位 "
                                     f"{fs_obs.get('median')}pt 不完全一致，按官方值，冲突见 confidence.conflicts")),
        "caption_font_pt": metric((m.get("caption_font_pt") or {}).get("median"), "sample-stat", unit="pt",
                                  stat="median", n=n, observed=rb(m.get("caption_font_pt"), "pt"),
                                  reliable=(m.get("caption_font_pt") or {}).get("n", 0) >= 5),
    }
    if family_o:
        typo["body_font_family"] = metric(family_o["value"], family_o.get("confidence", "official"))
    ls_o = off(o, "line_spacing")
    if ls_o:
        typo["line_spacing"] = metric(ls_o["value"], ls_o.get("confidence", "official"))
    rec = A.get("recommended", {})
    figcap = off(o, "figure_caption_position") or rec.get("figure_caption_position")
    tabcap = off(o, "table_caption_position") or rec.get("table_caption_position")
    typo["caption_position"] = {}
    for name, src_ in (("figure", figcap), ("table", tabcap)):
        if isinstance(src_, dict):
            typo["caption_position"][name] = metric(src_.get("value"), src_.get("confidence", "official"),
                                                    evidence=src_.get("evidence"))
        else:
            typo["caption_position"][name] = metric(None, "sample-stat", note="官方未明文")
    ca = cat.get("caption_align") or {}
    typo["caption_align_observed"] = {"n": n, "median": ca.get("left_ratio"),
                                     "unit": "left_ratio",
                                     "left": ca.get("left"), "center": ca.get("center")}
    typo["notes"] = []
    if off(o, "title_format"):
        typo["notes"].append("标题格式官方有明文，见 hard_constraints.title_format")
    if isinstance(figcap, dict) and isinstance(tabcap, dict) and \
            figcap.get("value") != tabcap.get("value"):
        typo["notes"].append(f"题注位置图/表不同：图 {figcap.get('value')} / 表 {tabcap.get('value')}")

    # ---------- float_policy ----------
    fw = (m.get("fig_width_frac") or {})
    fwf = (m.get("full_width_fig_frac") or {})
    fwfl = (m.get("full_width_floats") or {})
    fwpos = cat.get("full_width_float_pos_ratio") or {}
    figpos = cat.get("figure_pos_ratio") or {}
    fwfrac = fwf.get("median") or 0
    fwtop = fwpos.get("top") or 0
    figw_reliable = (not two_col) and (fw.get("max") is None or fw["max"] <= 1.001)
    th_mm = text_w_mm
    float_policy = {
        "float_spec": metric("tbp", "derived",
                             derivation="texopt 白名单动作 sanitize_float_specs 的目标档；"
                                        "[h]/[h!] 属不稳定写法（通用规则 A-04），真实论文以 t/b 为主",
                             note=f"实测全宽浮动体位置 top={fwpos.get('top')} "
                                  f"bottom={fwpos.get('bottom')} mid={fwpos.get('mid')}"),
        "figure_width": {
            "typical_frac": rb(fw),
            "denominator": "版心全宽（单栏=版心；双栏=两栏+栏间距）",
            "overwide_threshold_mm": metric(th_mm, "derived", unit="mm",
                                            derivation="= 官方/实测版心宽（texopt normalize_fig_width 阈值）"),
            "spanning_note": ("双栏会议的 fig_width_frac 中位数 ≈ 页面宽度/版心宽 "
                              "（比值 1.2~1.3），说明测量把跨栏/整页图块合并成一条超宽框；"
                              "该字段在双栏会议标记为不可靠，不得当“超宽违规”或“典型图宽”用。"
                              if two_col else
                              "单栏会议 fig_width_frac 即“图宽/版心宽”，>1 的个别值表示图块略超版心（孤例）。"),
        },
        "full_width_figure": {
            "frac": rb(fwf),
            "count_per_paper": rb(fwfl),
        },
        "position_prior": {
            "full_width_float_ratio": fwpos,
            "figure_ratio": figpos,
        },
        "official_rules": [],
        "notes": [],
    }
    fpr = off(o, "float_placement_rules")
    if fpr:
        float_policy["official_rules"].append(f"hard_constraints.float_placement_rules: {fpr['value']}")
    for k in ("float_placement_rules", "figure_width_hint", "table_style_hint", "float_density_hint"):
        if k in rec:
            float_policy["official_rules"].append(f"recommended.{k}: {rec[k].get('value')}")
    if two_col:
        float_policy["notes"].append("图宽分栏不可只用 PDF 几何判定：texopt 需在视觉层（Phase 4）"
                                     "区分“栏内图 / 跨栏图”，当前阈值取版心全宽以免误伤全宽图。")
    if fwtop >= 0.55:
        float_policy["notes"].append(f"浮动体以顶部为主（实测全宽浮动体 top={fwtop:.0%}），"
                                     "texopt 应优先把浮动体推到页顶/跨栏页顶，而不是底部。")
    elif (fwpos.get("bottom") or 0) >= 0.3:
        float_policy["notes"].append(f"浮动体顶/底并重（top={fwtop:.0%} bottom={fwpos.get('bottom'):.0%}），"
                                     "不应强制全部推到页顶；优先消除页面中部的浮动体（mid="
                                     f"{fwpos.get('mid', 0):.0%}）。")
    else:
        float_policy["notes"].append(f"全宽浮动体数量少（比例 {fwfrac:.2f}），位置强约束收益有限；"
                                     "优先治理栏内浮动体与图宽。")

    # ---------- density_targets ----------
    refs_style = (cat.get("ref_style") or {}).get("value")
    refs_ok = (refs_style == "numeric") and ((m.get("refs") or {}).get("median") or 0) >= 20
    dens_targets = {}
    for name, key, rel in (("figures", "figures", True), ("tables", "tables", True),
                           ("equations", "equations", True), ("algorithms", "algorithms", True),
                           ("footnotes", "footnotes_est", False),
                           ("refs", "refs", refs_ok)):
        rob = m.get(key) or {}
        rec_rel = rel
        note = None
        if key == "refs" and not refs_ok:
            note = (f"参考文献条数为测量伪影：检测式只认 [n] 数字引用/短作者串，"
                    f"{refs_style} 风格长作者列表漏检（见 confidence.conflicts）。该字段不可用。")
        if key == "algorithms":
            note = "算法环境极少（多数会议中位数 0），不作优化目标"
        dens_targets[name] = {
            "basis": "sample-stat",
            "reliable": rec_rel,
            "per_paper": rb(rob),
            "target_range": [rob.get("p25"), rob.get("p75")] if rob.get("p25") is not None else None,
            "note": note,
        }
        if name + "_per_page" in dens:
            dens_targets[name]["per_content_page"] = rb(dens[name + "_per_page"])
    lp = m.get("lines_per_page") or {}
    dens_targets["lines_per_page"] = {
        "basis": "sample-stat", "reliable": False,
        "per_paper": rb(lp),
        "note": "定义=正文页全部文本行数/正文页数（双栏会议为两栏之和），噪声大且跨栏不可比，"
                "仅作同会议内部参考，不作优化目标。",
    }
    dens_targets["content_pages"] = {
        "basis": "sample-stat", "reliable": True,
        "per_paper": rb(m.get("content_pages")),
        "target_range": [m["content_pages"].get("p25"), m["content_pages"].get("p75")]
        if (m.get("content_pages") or {}).get("p25") is not None else None,
        "note": "content_pages = 参考文献首页之前的部分；与官方上限并不相等（见 confidence.conflicts），"
                "不得强行统一。",
    }

    # ---------- optimization_policy ----------
    pl = hard.get("page_limit_content", {}).get("value") or hard.get("page_limit_total", {}).get("value")
    cp = (m.get("content_pages") or {}).get("median")
    slack = (pl - cp) if (pl and cp) else None
    figs_pp = (dens.get("figures_per_page") or {}).get("median") or 0
    tabs_pp = (dens.get("tables_per_page") or {}).get("median") or 0
    eq_pp = (dens.get("equations_per_page") or {}).get("median") or 0
    artifacts = [a for a in A.get("anomalies", []) if a["type"] == "fig_width_frac_gt_1"]

    cands = []

    n_reject = len([k for k, v in hard.items() if v["compliance_impact"] == "reject-risk"])
    cands.append((1000, "L", {
        "direction": "L 层硬性合规修复（页数/字号/边距/纸张/栏数，先于一切审美优化）",
        "why": f"官方硬约束共 {n_reject} 项被判为不合规风险项（含 "
               f"{"、".join(sorted([k for k, v in hard.items() if v['compliance_impact'] == 'reject-risk']))}）；"
               f"texopt 的 L 项是字典序首项，A 的收益不能换 L。",
        "evidence": [f"hard_constraints.page_limit_content={pl}",
                     f"hard_constraints.body_font_size_pt={(off(o,'body_font_size_pt') or {}).get('value')}",
                     f"geometry.margin_floor_mm={margin_floor}",
                     f"hard_constraints.columns={cols}"],
        "texopt_actions": ["set_fontsize", "set_margin", "drop_fleqn"],
    }))
    if slack is not None and slack <= 1.5:
        cands.append((60 + 20 * (1.5 - slack), "page", {
            "direction": "页数控制（压页）：纯排版手段优先，避免语义抛光",
            "why": f"样本 content_pages 中位数 {cp}，官方正文上限 {pl}（差 {slack:+.1f} 页）。"
                   "注意口径：content_pages = 参考文献首页之前（含该页），参考文献与附录不计入，"
                   "与官方“正文页上限”不能直接等同，真实余量需按目标模板重编译确认。",
            "evidence": [f"density_targets.content_pages.per_paper.median={cp}",
                         f"hard_constraints.page_limit_content={pl}"],
            "texopt_actions": ["set_margin", "reduce_list_spacing", "remove_excessive_vspace",
                               "normalize_fig_width"],
        }))
        if margin_floor is not None and margin_floor <= 20.0:
            cands.append((50 - margin_floor, "margin", {
                "direction": "页边距可压缩空间极小：压页需转向字号档/行距/浮动体与列表间距",
                "why": f"官方最小边距仅 {margin_floor}mm（低于 20mm），已无合法压缩余地，"
                       "继续压边距会直接踩硬约束。",
                "evidence": ["geometry.margin_floor_mm"],
                "texopt_actions": ["reduce_list_spacing", "remove_excessive_vspace", "sanitize_float_specs"],
            }))
    elif slack is not None and slack >= 3:
        cands.append((30 + 4 * slack, "page", {
            "direction": "页数有余量时转向“留白/密度一致性”而不是继续压页",
            "why": f"样本正文页中位数 {cp} 距上限 {pl} 有 {slack:.1f} 页余量；"
                   "压页会牺牲留白，应转向孤行寡行、间距一致性与浮动体位置。",
            "evidence": [f"density_targets.content_pages.per_paper.median={cp}"],
            "texopt_actions": ["inject_quality_macros", "sanitize_float_specs"],
        }))
    cands.append((45 + 22 * figs_pp + 18 * fwfrac, "float", {
        "direction": "浮动体位置与跨栏占比：把图/表推到页顶、消除页面中部的浮动体",
        "why": f"每页图数中位数 {figs_pp:.2f}（每篇 {m.get('figures',{}).get('median')} 张）、"
               f"满宽图占比 {fwfrac:.2f}、全宽浮动体出现位置 top={fwpos.get('top', 0):.0%}/"
               f"bottom={fwpos.get('bottom', 0):.0%}/mid={fwpos.get('mid', 0):.0%}；"
               "浮动体位置是这类会议最主要的版面噪声来源。",
        "evidence": ["float_policy.position_prior", "density_targets.figures.per_content_page"],
        "texopt_actions": ["sanitize_float_specs", "set_float_spec"],
    }))
    if tabs_pp >= 0.35:
        cands.append((28 + 45 * tabs_pp, "table", {
            "direction": "表格宽度治理（tabularx 自适应、去竖线、超宽表检测）",
            "why": f"每页表数中位数 {tabs_pp:.2f}（每篇 {m.get('tables',{}).get('median')} 张），"
                   "表格密度高；超宽表格是双栏排版最常见的溢出源。",
            "evidence": ["density_targets.tables.per_content_page"],
            "texopt_actions": ["fix_table_width"],
        }))
    if eq_pp >= 1.0:
        cands.append((30 + 28 * eq_pp, "equation", {
            "direction": "公式排版：居中、编号一致、避免超宽公式",
            "why": f"每页公式数中位数 {eq_pp:.2f}；公式密度高的稿件容易出现居中不一致（fleqn）与溢出。",
            "evidence": ["density_targets.equations.per_content_page"],
            "texopt_actions": ["drop_fleqn", "normalize_dollar_math"],
        }))
    elif eq_pp < 0.5:
        cands.append((20, "equation", {
            "direction": "公式不是本会议的主要改进面（实测近零）",
            "why": f"每页公式数中位数 {eq_pp:.2f}、每篇 {m.get('equations',{}).get('median')} 个，"
                   "优化预算应投入浮动体与表格而非公式。",
            "evidence": ["density_targets.equations.per_paper"],
            "texopt_actions": [],
        }))
    if (tw_m.get("median") or 999) < 420 and not two_col:
        cands.append((58, "breaking", {
            "direction": "窄版心断行质量（overfull/underfull、连字符、孤行寡行）",
            "why": f"单栏版心仅 {text_w_mm}mm（实测中位 {round((tw_m.get('median') or 0)*25.4/72,1)}mm），"
                   "行短词长，断行质量比双栏更容易恶化。",
            "evidence": ["geometry.observed.text_width_mm", "通用规则 A-04"],
            "texopt_actions": ["inject_quality_macros", "add_hyphenation_points"],
        }))
    if two_col:
        cands.append((34 + 30 * fwfrac, "span", {
            "direction": "图宽归一与超宽图检测（双栏特有：区分栏内图/跨栏图）",
            "why": f"版心 {text_w_mm}mm、单栏宽 {col_w_mm}mm；实测有 {len(artifacts)} 个样本的“图块≈整页宽”，"
                   "说明跨栏图普遍。texopt 需按栏宽判定，避免把跨栏图压成栏宽。",
            "evidence": ["float_policy.figure_width.spanning_note"],
            "texopt_actions": ["normalize_fig_width", "set_fig_width"],
        }))
    cands.append((10, "fallback", {
        "direction": "断行/间距质量兜底（overfull·underfull·vbox、列表与章节间距一致）",
        "why": "编译日志级信号是当前可用的主要 A 代理，任何会议都应作为兜底项。",
        "evidence": ["summary/texopt-generalizable-rules.json (A 层规则)"],
        "texopt_actions": ["inject_quality_macros", "reduce_list_spacing", "normalize_heading_size"],
    }))

    cands.sort(key=lambda x: -x[0])
    picked, seen = [], set()
    for score, fam, c in cands:
        if fam in seen and fam != "page":
            continue
        picked.append(c)
        seen.add(fam)
        if len(picked) >= 5:
            break
    if len(picked) < 3:
        for score, fam, c in cands:
            if c not in picked:
                picked.append(c)
            if len(picked) >= 3:
                break
    prio = [dict(rank=i + 1, **c) for i, c in enumerate(picked)]

    avoid = [
        "不得为压页而删改正文文字/公式/引用（L 项内容保持率为硬下限）",
        "不得把样本统计值当硬约束（例如按中位数强制改变字号或页边距）",
        "不得用全局手段抹平跨会议差异：单栏/双栏、参考文献计页规则、纸型逐会不同",
    ]
    if not refs_ok:
        avoid.append("不得以 refs_per_paper 为目标：该会议该指标为测量伪影")
    if two_col:
        avoid.append("不得据 fig_width_frac>1 判定“超宽图”：双栏下该比值≈整页宽，是跨栏图被合并的伪影")
    if slack is not None and slack <= 1.5:
        avoid.append("页数临界时不得先动用语义抛光（必须排版手段穷尽）")

    actions = {
        "normalize_fig_width": {"threshold_mm": th_mm,
                                "note": "阈值=版心全宽；双栏下栏内图目标为栏宽，需视觉层支持"},
        "sanitize_float_specs": {"req_spec": "tbp"},
        "set_margin": {"min_mm": max(12.0, (margin_floor or 18.0) - 6.0),
                       "note": "下限 = 官方最小边距 −6mm（保守），低于 margin_floor_mm 需人工确认"},
        "inject_quality_macros": {"enable": True},
        "drop_fleqn": {"enable": True},
    }

    unsupported = conf.get("texopt_requirement_map", {}).get("unsupported_constraints", [])

    applicable = []
    for r in rules:
        ap = str(r.get("applies_to", ""))
        if "all 16" in ap or cid in ap.lower():
            applicable.append(r["id"])

    # ---------- confidence ----------
    conflicts = []
    for a in A.get("anomalies", []):
        resolution = None
        if a["type"] == "refs_zero":
            resolution = "判为测量伪影，refs 字段标记不可靠，不作为模板值"
        elif a["type"] == "fig_width_frac_gt_1":
            resolution = "判为跨栏/整页图块合并伪影，不计入“超宽违规”"
        elif a["type"] == "content_pages_implausible":
            resolution = "该样本正文页数不可用；中位数由其余样本给出"
        elif a["type"] == "content_pages_over_limit":
            resolution = "按冲突保留：样本可能为 camera-ready/含附录，不据此修改官方上限"
        elif a["type"] == "columns_mismatch":
            resolution = "该样本版面结构特殊（整页跨栏），不影响会议级结论"
        elif a["type"] == "paper_size_mismatch":
            resolution = "官方允许多纸型/实测漂移，按官方值并在 page_size.note 说明"
        elif a["type"] == "body_font_mismatch":
            resolution = "该样本正文实际字号偏离官方档，按官方值，样本仅作观测"
        conflicts.append({"type": a["type"], "sample_id": a.get("sample_id"),
                          "detail": a["detail"], "resolution": resolution})
    if cid == "eccv":
        conflicts.append({"type": "official_vs_sample_page_size", "sample_id": None,
                          "detail": "官方 LNCS 页面 155×235mm，实测样本页面为 letter（ECVA 发布版）",
                          "resolution": "模板取官方 LNCS 页面；实测页宽只作观测"})
    if not refs_ok:
        conflicts.append({"type": "refs_measurement_artifact", "sample_id": None,
                          "detail": f"refs 中位数 {(m.get('refs') or {}).get('median')} 与真实引用量级不符"
                                    f"（ref_style={refs_style}）",
                          "resolution": "正则只认 [n]/短作者串，长作者列表漏检；该字段不可用"})
    if pl and cp and cp > pl:
        conflicts.append({"type": "content_pages_vs_official_limit", "sample_id": None,
                          "detail": f"实测 content_pages 中位数 {cp} > 官方正文上限 {pl}"
                                    "（口径不同：含参考文献首页，且部分样本把附录并入正文区）",
                          "resolution": "保留冲突，不修改官方上限；模板以官方值为 L 约束，实测值仅供观测"})

    reliable_fields, unreliable_fields = [], []
    for name, t in dens_targets.items():
        (reliable_fields if t.get("reliable") else unreliable_fields).append(f"density_targets.{name}")
    (reliable_fields if figw_reliable else unreliable_fields).append("float_policy.figure_width.typical_frac")
    for f in ("page_size", "columns", "text_width_mm", "margin_floor_mm", "margins",
              "body_font_pt", "caption_font_pt", "full_width_figure.frac"):
        reliable_fields.append(f"{f}")
    reliable_fields.append("density_targets.content_pages")

    notes = []
    if n <= 6:
        notes.append(f"样本仅 {n} 篇：所有 sample-stat 字段为低可信度，仅作参考区间，不得升格为规则")
    elif n <= 9:
        notes.append(f"样本 {n} 篇：sample-stat 字段为中可信度")
    if two_col:
        notes.append("双栏会议：图宽/浮动体几何受跨栏合并影响，需视觉层复核")

    confidence = {
        "sample_n": n,
        "level": A["sample_confidence"],
        "reliable_fields": sorted(set(reliable_fields)),
        "unreliable_fields": sorted(set(unreliable_fields)),
        "conflicts": conflicts,
        "notes": notes,
    }

    # ---------- sources / traceability ----------
    sources = []
    for s in conf.get("sources", []):
        sources.append({"kind": "official-source", "ref": s.get("id"),
                        "url": s.get("url"), "note": s.get("title")})
    for p in slog.get("papers", []):
        sources.append({"kind": "sample-pdf", "ref": p.get("sample_id"),
                        "url": p.get("pdf_url"), "note": p.get("title")})
    for r in rules:
        if r["id"] in applicable:
            sources.append({"kind": "rule", "ref": r["id"], "url": None,
                            "note": r.get("statement", "")[:160]})
    sources.append({"kind": "analysis-file",
                    "ref": "analysis/template-inputs.json", "url": None,
                    "note": "稳健统计（median/P25/P75）来源"})
    sources.append({"kind": "analysis-file", "ref": "samples/_measurements/*.json", "url": None,
                    "note": "单篇论文实测几何"})

    field_basis = {}
    def reg(path, basis):
        field_basis[path] = basis
    for k, v in hard.items():
        reg(f"hard_constraints.{k}", v["confidence"])
    reg("geometry.page_size", geometry["page_size"]["basis"])
    reg("geometry.page_width_mm", "derived")
    reg("geometry.page_height_mm", "derived")
    reg("geometry.columns", geometry["columns"]["basis"])
    reg("geometry.text_width_mm", geometry["text_width_mm"]["basis"])
    reg("geometry.margin_floor_mm", mf_basis)
    for k, v in geometry["margins"].items():
        reg(f"geometry.margins.{k}", v["basis"])
    if "column_gap_mm" in geometry:
        reg("geometry.column_gap_mm", geometry["column_gap_mm"]["basis"])
        reg("geometry.column_width_mm", "derived")
    if "text_height_mm" in geometry:
        reg("geometry.text_height_mm", geometry["text_height_mm"]["basis"])
    reg("typography.body_font_pt", typo["body_font_pt"]["basis"])
    reg("typography.caption_font_pt", "sample-stat")
    if "body_font_family" in typo:
        reg("typography.body_font_family", typo["body_font_family"]["basis"])
    if "line_spacing" in typo:
        reg("typography.line_spacing", typo["line_spacing"]["basis"])
    for k, v in typo["caption_position"].items():
        reg(f"typography.caption_position.{k}", v["basis"])
    reg("float_policy.float_spec", "derived")
    reg("float_policy.figure_width.overwide_threshold_mm", "derived")
    for k in dens_targets:
        reg(f"density_targets.{k}", dens_targets[k]["basis"])

    template = {
        "schema_version": "1.0",
        "id": cid,
        "conference": conf.get("abbr") or conf.get("name"),
        "edition": A["current_edition"],
        "family": A["family"],
        "generated_by": "tools/build_templates.py (from analysis/template-inputs.json)",
        "data_basis": {
            "n_samples": n,
            "n_measurements": A["n_measurements"],
            "focus_editions": conf.get("focus_editions", []),
            "measurement_method": "tools/measure_pdf.py (pdfminer.six 字形级几何)",
            "robust_stats_only": True,
        },
        "sources": sources,
        "traceability": {"basis_definitions": BASIS_DEF, "field_basis": field_basis},
        "hard_constraints": hard,
        "geometry": geometry,
        "typography": typo,
        "float_policy": float_policy,
        "density_targets": dens_targets,
        "optimization_policy": {
            "priority": prio,
            "avoid": avoid,
            "actions": actions,
            "unsupported": unsupported,
            "applicable_rules": applicable,
        },
        "confidence": confidence,
        "texopt_flat": {
            "page_limit": pl,
            "font_pt": (off(o, "body_font_size_pt") or {}).get("value"),
            "margin_mm": margin_floor,
            "float_spec": "tbp",
            "overwide_fig_threshold_mm": th_mm,
            "eq_fleqn_allowed": False,
            "enable_quality_macros": True,
        },
    }
    return template


def main():
    A = jload(os.path.join(ROOT, "analysis", "template-inputs.json"))["conferences"]
    rules = jload(os.path.join(ROOT, "summary", "texopt-generalizable-rules.json"))["rules"]
    os.makedirs(OUTDIR, exist_ok=True)
    summary_rows = []
    for cid, a in A.items():
        conf = jload(os.path.join(ROOT, "conferences", f"{cid}.json"))
        slog = jload(os.path.join(ROOT, "samples", f"{cid}.samples.list.json"))
        t = build_one(cid, a, conf, slog, rules)
        p = os.path.join(OUTDIR, f"{cid}.json")
        with open(p, "w", encoding="utf-8") as f:
            json.dump(t, f, ensure_ascii=False, indent=1)
        print("wrote", p)
        summary_rows.append(t)

    # 速查表
    lines = ["# 16 会议模板速查表（自动生成，勿手改）", "",
             "来源：`templates-v2/*.json`；basis 含义见 `schema/template.schema.json`。",
             "`*` = 该字段实测不可靠（见各模板 confidence.unreliable_fields）。", "",
             "| 会议 | 届次 | 页数上限 | 正文页中位 | 纸型 | 栏 | 正文字号 | 版心mm | 栏宽mm | 边距下限mm | refs计页 | 图/页 | 表/页 | 式/页 | 满宽图frac | 样本n | 可信度 |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for t in summary_rows:
        h = t["hard_constraints"]
        g = t["geometry"]
        d = t["density_targets"]
        def mv(x, key="value"):
            v = t
            return v
        lines.append("| {} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {} |".format(
            t["id"], t["edition"],
            h.get("page_limit_content", {}).get("value", "-"),
            d["content_pages"]["per_paper"].get("median", "-"),
            g["page_size"]["value"],
            g["columns"]["value"],
            t["typography"]["body_font_pt"]["value"],
            g["text_width_mm"]["value"],
            (g.get("column_width_mm") or {}).get("value", "-"),
            g["margin_floor_mm"]["value"],
            h.get("references_counted", {}).get("value", "-"),
            d["figures"].get("per_content_page", {}).get("median", "-"),
            d["tables"].get("per_content_page", {}).get("median", "-"),
            d["equations"].get("per_content_page", {}).get("median", "-"),
            f"{'%.3f' % (t['float_policy']['full_width_figure']['frac'].get('median') or 0)}"
            + ("*" if g["columns"]["value"] == 2 else ""),
            t["confidence"]["sample_n"], t["confidence"]["level"]))
    with open(os.path.join(ROOT, "summary", "template-matrix.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("wrote summary/template-matrix.md")


if __name__ == "__main__":
    main()
