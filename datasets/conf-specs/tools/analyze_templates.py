#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
analyze_templates.py —— 为“模板设计”任务做数据侧统计。

只读数据（conferences/ years/ samples/ patterns/ summary/），输出：
  analysis/template-inputs.json   每会议的稳健统计（median/P25/P75）+ 异常清单
  analysis/anomalies.md           异常与冲突的可读清单

设计原则（对应任务要求）：
  - 只用稳健统计（median / P25 / P75 / min / max / n），不输出 mean 作为结论值；
  - 样本量 < 8 时降级 confidence（n<=6 → low，7<=n<=9 → medium, n>=10 → 视一致性定 high/medium）
  - 不修改任何原始数据；发现冲突只记录。
"""
import json
import os
import re
import statistics as st
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # datasets/conf-specs
OUT = os.path.join(ROOT, "analysis")

CONFS = ["neurips", "icml", "iclr", "acl", "emnlp", "cvpr", "iccv", "eccv",
         "aaai", "ijcai", "siggraph", "kdd", "www", "osdi", "sosp", "nsdi"]


def jload(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def quantile(xs, q):
    """线性插值分位数；xs 无需预排序。"""
    if not xs:
        return None
    s = sorted(xs)
    if len(s) == 1:
        return s[0]
    pos = (len(s) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(s) - 1)
    frac = pos - lo
    return round(s[lo] * (1 - frac) + s[hi] * frac, 3)


def robust(xs):
    xs = [x for x in xs if isinstance(x, (int, float))]
    if not xs:
        return None
    return {
        "n": len(xs),
        "min": round(min(xs), 3),
        "p25": quantile(xs, 0.25),
        "median": quantile(xs, 0.5),
        "p75": quantile(xs, 0.75),
        "max": round(max(xs), 3),
        "iqr": round((quantile(xs, 0.75) or 0) - (quantile(xs, 0.25) or 0), 3),
    }


def mode(xs):
    xs = [x for x in xs if x is not None]
    if not xs:
        return None
    c = Counter(xs)
    top = c.most_common()
    best = top[0][1]
    vals = sorted([k for k, v in top if v == best], key=lambda z: str(z))
    return {"value": vals[0], "count": best, "n": len(xs),
            "consistent": len(vals) == 1}


def hc(conf, key):
    """取 hard_constraints 里的原始值（含 confidence），不存在返回 None。"""
    return conf.get("hard_constraints", {}).get(key)


def rec(conf, key):
    return conf.get("recommended", {}).get(key)


def main():
    os.makedirs(OUT, exist_ok=True)
    result = {"schema_version": "1.0",
              "generated_by": "tools/analyze_templates.py",
              "note": "稳健统计直接由 samples/_measurements/*.json 重算；"
                      "patterns/*.json 给的是均值，本文件一律不用均值作结论。",
              "conferences": {}}
    anomalies = []
    coverage = []
    mentioned_in_patterns = []

    for conf_id in CONFS:
        cpath = os.path.join(ROOT, "conferences", f"{conf_id}.json")
        conf = jload(cpath)
        # ---- 样本归属：以 samples/<conf>.samples.list.json 为准 ----
        slist = jload(os.path.join(ROOT, "samples", f"{conf_id}.samples.list.json"))
        sample_ids = [p["sample_id"] for p in slist["papers"]]
        meas = {}
        for sid in sample_ids:
            mp = os.path.join(ROOT, "samples", "_measurements", f"{sid}.json")
            if not os.path.exists(mp):
                anomalies.append({"conference": conf_id, "type": "missing_measurement",
                                  "sample_id": sid, "detail": "measurements 文件缺失"})
                continue
            mrec = jload(mp)
            # 测量缓存里除了成功记录，还有 build_dataset.py 写的失败占位
            # （{"sample_id","pdf_url","error"}，没有 measured）。这些不能当成功样本用，
            # 但也绝不能把整个脚本掀翻——记成异常，下次 build_dataset.py 会自动重试测量。
            if not mrec.get("measured"):
                anomalies.append({
                    "conference": conf_id, "type": "measurement_failed", "sample_id": sid,
                    "detail": re.sub(r"\s+", " ", str(mrec.get("error") or "缓存里没有 measured 字段"))[:200]})
                continue
            meas[sid] = mrec["measured"]
        if len(meas) != len(sample_ids):
            print(f"  ! {conf_id}: {len(sample_ids) - len(meas)}/{len(sample_ids)} 篇样本无可用测量"
                  f"（已记入 anomalies.md）", flush=True)

        ids = list(meas.keys())
        g = lambda fn: [fn(meas[s]) for s in ids]

        def mg(sid, path, default=None):
            cur = meas[sid]
            for k in path.split("."):
                if not isinstance(cur, dict) or k not in cur:
                    return default
                cur = cur[k]
            return cur

        def vals(path, default=None):
            return [mg(s, path, default) for s in ids]

        stats = {
            "pdf_pages": robust(g(lambda m: m.get("pdf_pages"))),
            "content_pages": robust(g(lambda m: m.get("content_pages"))),
            "body_font_pt": robust(g(lambda m: m.get("body_font_pt_snap") or m.get("body_font_pt"))),
            "caption_font_pt": robust(g(lambda m: m.get("caption_font_pt"))),
            "text_width_pt": robust(g(lambda m: m.get("text_width_pt"))),
            "text_height_pt": robust(g(lambda m: m.get("text_height_pt"))),
            "column_gap_pt": robust(g(lambda m: m.get("column_gap_pt"))),
            "margins_left_mm": robust(vals("margins_mm.left")),
            "margins_right_mm": robust(vals("margins_mm.right")),
            "margins_top_mm": robust(vals("margins_mm.top")),
            "margins_bottom_mm": robust(vals("margins_mm.bottom")),
            "figures": robust(g(lambda m: m.get("figures"))),
            "tables": robust(g(lambda m: m.get("tables"))),
            "equations": robust(g(lambda m: m.get("equations"))),
            "algorithms": robust(g(lambda m: m.get("algorithms"))),
            "listings": robust(g(lambda m: m.get("listings"))),
            "refs": robust(g(lambda m: m.get("refs"))),
            "footnotes_est": robust(g(lambda m: m.get("footnotes_est"))),
            "lines_per_page": robust(g(lambda m: m.get("lines_per_page"))),
            "fig_width_frac": robust(vals("figure_geometry.fig_width_frac_median")),
            "fig_width_frac_p90": robust(vals("figure_geometry.fig_width_frac_p90")),
            "fig_height_frac": robust(vals("figure_geometry.fig_height_frac_median")),
            "full_width_fig_frac": robust(vals("figure_geometry.full_width_fig_frac")),
            "full_width_floats": robust(g(lambda m: m.get("full_width_floats"))),
        }
        # 密度（每页），只用 content_pages>0 的样本
        dens = defaultdict(list)
        for s in ids:
            cp = meas[s].get("content_pages") or 0
            if cp <= 0:
                continue
            for name, key in (("figures_per_page", "figures"), ("tables_per_page", "tables"),
                              ("equations_per_page", "equations"), ("algorithms_per_page", "algorithms"),
                              ("refs_per_page", "refs")):
                v = meas[s].get(key)
                if isinstance(v, (int, float)):
                    dens[name].append(v / cp)
        density = {k: robust(v) for k, v in dens.items()}

        # 类别型
        cat = {
            "paper_size": mode(g(lambda m: m.get("paper_size"))),
            "columns": mode(g(lambda m: m.get("columns"))),
            "ref_style": mode(g(lambda m: m.get("ref_style"))),
            "caption_align": (lambda c: {"left": c.get("left", 0), "center": c.get("center", 0),
                                          "left_ratio": round(c.get("left", 0) / max(1, sum(c.values())), 3)})(
                {k: sum((m.get("caption_align") or {}).get(k, 0) for m in meas.values())
                 for k in ("left", "center")}),
            "font_size_hist_top": mode(g(lambda m: max(m.get("font_size_hist", {"0": 0}).items(),
                                                       key=lambda kv: kv[1])[0]
                                         if m.get("font_size_hist") else None)),
        }
        # 全宽浮动体位置（把每篇的 dict 汇总）
        fwpos = Counter()
        for s in ids:
            for k, v in (mg(s, "full_width_float_pos", {}) or {}).items():
                fwpos[k] += v
        fw_tot = sum(fwpos.values()) or 1
        cat["full_width_float_pos_ratio"] = {k: round(v / fw_tot, 3) for k, v in fwpos.items()}

        # 图像几何位置（fig_pos）
        figpos = Counter()
        for s in ids:
            for k, v in (mg(s, "figure_geometry.fig_pos", {}) or {}).items():
                figpos[k] += v
        fig_tot = sum(figpos.values()) or 1
        cat["figure_pos_ratio"] = {k: round(v / fig_tot, 3) for k, v in figpos.items()}

        # ---- 异常检测 ----
        conf_anom = []
        for s in ids:
            m = meas[s]
            cp = m.get("content_pages")
            pl = (hc(conf, "page_limit_content") or {}).get("value")
            if m.get("refs") == 0:
                conf_anom.append({"sample_id": s, "type": "refs_zero",
                                  "detail": "refs=0 → 参考文献区未被识别（多为 PDF 缺 bookmarks/线条），非论文真的没有参考文献"})
            if cp is not None and cp < 4:
                conf_anom.append({"sample_id": s, "type": "content_pages_implausible",
                                  "detail": f"content_pages={cp} 明显偏小，疑为正文页定位失败"})
            elif cp is not None and isinstance(pl, (int, float)) and cp > pl + 6:
                conf_anom.append({"sample_id": s, "type": "content_pages_over_limit",
                                  "detail": f"content_pages={cp} > 官方上限 {pl} + 6：可能是 camera-ready/附录并入，也可能定位偏差；按冲突保留不修改"})
            fw = mg(s, "figure_geometry.fig_width_frac_median")
            if isinstance(fw, (int, float)) and fw > 1.001:
                conf_anom.append({"sample_id": s, "type": "fig_width_frac_gt_1",
                                  "detail": f"fig_width_frac_median={fw:.3f} > 1：该类图片几何宽超过单栏/版心基准，实际多为跨栏或整版图，不能当“超宽违规”处理"})
            off_cols = (hc(conf, "columns") or {}).get("value")
            if off_cols is not None and m.get("columns") is not None and m["columns"] != off_cols:
                conf_anom.append({"sample_id": s, "type": "columns_mismatch",
                                  "detail": f"实测 columns={m['columns']} ≠ 官方/模板 columns={off_cols}（可能为整版跨栏图导致行首聚类偏移）"})
            off_ps = (hc(conf, "paper_size") or {}).get("value")
            if off_ps and m.get("paper_size") and m["paper_size"] != off_ps:
                conf_anom.append({"sample_id": s, "type": "paper_size_mismatch",
                                  "detail": f"实测 paper_size={m['paper_size']} ≠ 官方 {off_ps}"})
            off_fs = (hc(conf, "body_font_size_pt") or {}).get("value")
            ms = m.get("body_font_pt_snap")
            if off_fs and ms and abs(ms - off_fs) > 1.0:
                conf_anom.append({"sample_id": s, "type": "body_font_mismatch",
                                  "detail": f"实测正文 {ms}pt ≠ 官方/模板 {off_fs}pt"})
        for a in conf_anom:
            a["conference"] = conf_id
        anomalies.extend(conf_anom)

        # ---- confidence 分级 ----
        n = len(ids)
        if n <= 6:
            lvl = "low"
        elif n <= 9:
            lvl = "medium"
        else:
            lvl = "high"
        result["conferences"][conf_id] = {
            "name": conf.get("name"),
            "current_edition": conf.get("current_edition"),
            "family": conf.get("family"),
            "n_samples": n,
            "n_measurements": len(ids),
            "sample_confidence": lvl,
            "official": {
                "page_limit_content": hc(conf, "page_limit_content"),
                "page_limit_total": hc(conf, "page_limit_total"),
                "references_counted": hc(conf, "references_counted"),
                "appendix_allowed": hc(conf, "appendix_allowed"),
                "appendix_counted": hc(conf, "appendix_counted"),
                "camera_ready_extra_pages": hc(conf, "camera_ready_extra_pages"),
                "anonymity": hc(conf, "anonymity"),
                "paper_size": hc(conf, "paper_size"),
                "columns": hc(conf, "columns"),
                "body_font_size_pt": hc(conf, "body_font_size_pt"),
                "body_font_family": hc(conf, "body_font_family"),
                "margins_mm": hc(conf, "margins_mm"),
                "text_width_mm": hc(conf, "text_width_mm"),
                "text_height_mm": hc(conf, "text_height_mm"),
                "column_gap_mm": hc(conf, "column_gap_mm"),
                "line_spacing": hc(conf, "line_spacing"),
                "bib_style": hc(conf, "bib_style"),
                "page_numbering": hc(conf, "page_numbering"),
                "title_format": hc(conf, "title_format"),
                "abstract_max_words": hc(conf, "abstract_max_words"),
                "checklist_required": hc(conf, "checklist_required"),
                "float_placement_rules": hc(conf, "float_placement_rules"),
                "figure_caption_position": hc(conf, "figure_caption_position"),
                "table_caption_position": hc(conf, "table_caption_position"),
            },
            "recommended": {k: rec(conf, k) for k in conf.get("recommended", {})},
            "template_basis": conf.get("template_basis"),
            "texopt_requirement_map": conf.get("texopt_requirement_map"),
            "history": conf.get("history", []),
            "open_questions": conf.get("open_questions", []),
            "measured": stats,
            "density": density,
            "categorical": cat,
            "anomalies": conf_anom,
        }
        coverage.append((conf_id, n, len(conf_anom)))

    # ---- 通用规则清单（原样带走，供模板 optimization_policy 引用） ----
    result["generalizable_rules"] = jload(
        os.path.join(ROOT, "summary", "texopt-generalizable-rules.json"))["rules"]

    with open(os.path.join(OUT, "template-inputs.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)

    # ---- 可读异常清单 ----
    lines = ["# 数据异常与冲突清单（自动生成，勿手改）", "",
             "来源：`tools/analyze_templates.py`，扫描 `samples/_measurements/*.json` 与各会议官方条目。",
             "规则：只记录，不修改原始数据。", "",
             "| 会议 | 样本 | 类型 | 说明 |", "|---|---|---|---|"]
    for a in anomalies:
        lines.append(f"| {a['conference']} | {a.get('sample_id','-')} | {a['type']} | {a['detail']} |")
    lines += ["", "## 每会议异常计数", "", "| 会议 | 样本数 | 异常数 |", "|---|---|---|"]
    for cid, n, na in coverage:
        lines.append(f"| {cid} | {n} | {na} |")
    with open(os.path.join(OUT, "anomalies.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print("wrote", os.path.join(OUT, "template-inputs.json"))
    print("wrote", os.path.join(OUT, "anomalies.md"))
    for cid, n, na in coverage:
        print(f"  {cid:9s} n={n:2d} anomalies={na}")


if __name__ == "__main__":
    main()
