#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_dataset.py —— 数据集的“汇总编译”步骤。

输入：conferences/*.json（规范层，由调研写入）+ samples/*.samples.list.json（样本清单）
处理：
  1. 逐篇测量真实论文 PDF（tools/measure_pdf.py），结果缓存到 samples/_measurements/
  2. 写 samples/<id>.samples.jsonl（每篇一行：元数据 + measured 几何量）
  3. 聚合统计量写回 conferences/<id>.json["statistics"]（“论文中的统计规律”）
  4. 生成 years/<id>.history.json（逐年规范变化 + 过时风险提示）
  5. 生成 patterns/float_patterns.json、patterns/layout_patterns.json
  6. 生成 summary/measurement-statistics.md、summary/cross-conf-table.md（自动表）
  7. 生成 texopt-templates/<id>.json（可直接给 texopt requirements 模块用）

用法:
    python3 tools/build_dataset.py [--only neurips,icml] [--no-measure] [--pages 25]
"""
from __future__ import annotations

import argparse
import json
import os
import statistics as st
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import measure_pdf as M  # noqa: E402

CACHE = os.path.join(ROOT, "samples", "_measurements")
MAX_MEASURE_S = 180      # 单篇 PDF 量化硬超时（病态大文件在 pdfminer 上可能极慢）

# texopt Requirement 已知字段（生成可用模板时必须局限在这些字段里）
REQ_FIELDS = {
    "page_limit", "font_pt", "margin_mm", "eq_fleqn_allowed", "toc", "running_header",
    "heading_color", "enable_quality_macros", "float_spec", "microtype",
    "overwide_fig_threshold_mm", "overwide_table_report", "allow_geometry_tune",
    "margin_min_mm", "margin_step_mm", "allow_fontsize_step", "max_iterations", "verbose",
}

METRICS = [
    ("pdf_pages", "pages", lambda m, mp: m.get("pdf_pages")),
    ("content_pages", "pages", lambda m, mp: m.get("content_pages")),
    ("body_font_pt", "pt", lambda m, mp: m.get("body_font_pt")),
    ("text_width_pt", "pt", lambda m, mp: m.get("text_width_pt")),
    ("column_gap_pt", "pt", lambda m, mp: m.get("column_gap_pt") if m.get("columns") == 2 else None),
    ("margins_left_mm", "mm", lambda m, mp: (m.get("margins_mm") or {}).get("left")),
    ("margins_right_mm", "mm", lambda m, mp: (m.get("margins_mm") or {}).get("right")),
    ("margins_top_mm", "mm", lambda m, mp: (m.get("margins_mm") or {}).get("top")),
    ("margins_bottom_mm", "mm", lambda m, mp: (m.get("margins_mm") or {}).get("bottom")),
    ("figures", "per_paper", lambda m, mp: m.get("figures")),
    ("tables", "per_paper", lambda m, mp: m.get("tables")),
    ("equations", "per_paper", lambda m, mp: m.get("equations")),
    ("algorithms", "per_paper", lambda m, mp: m.get("algorithms")),
    ("refs", "per_paper", lambda m, mp: m.get("refs")),
    ("footnotes_est", "per_paper", lambda m, mp: m.get("footnotes_est")),
    ("figs_per_page", "per_page",
     lambda m, mp: (m.get("figures") / m["content_pages"]) if m.get("content_pages") else None),
    ("tables_per_page", "per_page",
     lambda m, mp: (m.get("tables") / m["content_pages"]) if m.get("content_pages") else None),
    ("equations_per_page", "per_page",
     lambda m, mp: (m.get("equations") / m["content_pages"]) if m.get("content_pages") else None),
    ("fig_width_frac_median", "ratio",
     lambda m, mp: (m.get("figure_geometry") or {}).get("fig_width_frac_median")),
    ("fig_height_frac_median", "ratio",
     lambda m, mp: (m.get("figure_geometry") or {}).get("fig_height_frac_median")),
    ("full_width_fig_frac", "ratio",
     lambda m, mp: (m.get("figure_geometry") or {}).get("full_width_fig_frac")),
    ("caption_font_pt", "pt", lambda m, mp: m.get("caption_font_pt")),
    ("lines_per_page", "per_page", lambda m, mp: m.get("lines_per_page")),
]


def load(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def dump(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


# ---------------------------------------------------------------- 测量
def measure_sample(cid: str, paper: dict, max_pages: int, sleep_s: float,
                   do_measure: bool = True) -> dict:
    sid = paper["sample_id"]
    cache_file = os.path.join(CACHE, f"{sid}.json")
    cached = load(cache_file)
    if cached and cached.get("measured"):
        return cached
    if not do_measure:
        return {"sample_id": sid, "measured": None, "error": "跳过测量(--no-measure)"}
    url = paper.get("pdf_url")
    rec = {"sample_id": sid, "pdf_url": url}
    if not url:
        rec["error"] = "缺 pdf_url"
        return rec
    # 在**子进程**里测量并设硬超时：pdfminer 在个别病态 PDF（上百 MB / 图形碎片极多）上
    # 会跑到不可接受的时间；超时/崩溃只影响这一篇，不阻塞整个数据集构建。
    cmd = [sys.executable, os.path.join(ROOT, "tools", "measure_pdf.py"), url,
           "--pages", str(max_pages)]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=MAX_MEASURE_S)
        if p.returncode != 0:
            rec["error"] = f"measure_pdf 退出码 {p.returncode}: {(p.stderr or '')[-200:]}"
        else:
            res = json.loads(p.stdout)
            rec["measured"] = res["measured"]
            rec["method"] = res["method"]
            rec["warnings"] = res["warnings"]
    except subprocess.TimeoutExpired:
        rec["error"] = f"测量超时(>{MAX_MEASURE_S}s)：病态 PDF，已跳过"
    except Exception as ex:
        rec["error"] = f"{type(ex).__name__}: {ex}"
    if not rec.get("error"):
        time.sleep(sleep_s)
    dump(cache_file, rec)
    return rec


# ---------------------------------------------------------------- 统计聚合
def stats_of(values: list[float], unit: str, method: str, sids: list[str]) -> dict:
    v = sorted(x for x in values if x is not None)
    if not v:
        return {}
    def q(p):
        return round(v[min(len(v) - 1, int(len(v) * p))], 3)
    return {"mean": round(st.mean(v), 3), "median": round(st.median(v), 3),
            "p10": q(0.10), "p90": q(0.90), "n": len(v), "unit": unit,
            "min": round(v[0], 3), "max": round(v[-1], 3),
            "method": method, "samples": sids}


def aggregate(cid: str, records: list[dict]) -> dict:
    ok = [r for r in records if r.get("measured")]
    out = {}
    for name, unit, get in METRICS:
        vals, sids = [], []
        for r in ok:
            try:
                v = get(r["measured"], r["measured"])
            except Exception:
                v = None
            if isinstance(v, (int, float)):
                vals.append(float(v))
                sids.append(r["sample_id"])
        s = stats_of(vals, unit, "tools/measure_pdf.py (pdfminer 字形级几何)", sids)
        if s:
            out[name] = s
    return out


# ---------------------------------------------------------------- 逐年变化
def year_history(cid: str, conf: dict) -> dict:
    hist = conf.get("history", [])
    by_key: dict[str, list] = {}
    for ch in hist:
        by_key.setdefault(ch["key"], []).append(ch)
    for v in by_key.values():
        v.sort(key=lambda x: x["year"])
    cur_year = None
    for ch in hist:
        y = ch.get("year")
        if isinstance(y, int):
            cur_year = max(cur_year or y, y)
    stale = []
    for k, seq in by_key.items():
        last = seq[-1]
        if cur_year and last["year"] <= cur_year - 2 and len(seq) == 1:
            stale.append({"key": k, "last_year": last["year"],
                          "note": "该键只有一条历史记录且早于最近届次，可能已过时，需回官方页复核"})
    return {
        "conference": cid,
        "current_edition": conf.get("current_edition"),
        "generated_from": "conferences/%s.json history" % cid,
        "changes": hist,
        "by_key": {k: [{"year": c["year"], "value": c["value"], "edition": c["edition"],
                        "source_id": c["source_id"], "note": c.get("note", "")} for c in v]
                   for k, v in by_key.items()},
        "stale_warnings": stale,
    }


# ---------------------------------------------------------------- 模式提取
def extract_patterns(conf_by_id: dict, samples_by_id: dict) -> tuple[dict, dict]:
    floats, layout = {}, {}
    for cid, conf in conf_by_id.items():
        recs = [r for r in samples_by_id.get(cid, []) if r.get("measured")]
        if not recs:
            continue
        def vals(fn):
            return [fn(r["measured"]) for r in recs if fn(r["measured"]) is not None]
        fw_pos = {"top": 0, "bottom": 0, "mid": 0}
        fw_share, cap_pt, cap_align = [], [], {"left": 0, "center": 0}
        for r in recs:
            m = r["measured"]
            for k in fw_pos:
                fw_pos[k] += (m.get("full_width_float_pos") or {}).get(k, 0)
            if m.get("figure_geometry", {}).get("n_figs_geom"):
                fw_share.append(m["figure_geometry"].get("full_width_fig_frac") or 0)
            if m.get("caption_font_pt"):
                cap_pt.append(m["caption_font_pt"])
            for k in cap_align:
                cap_align[k] += (m.get("caption_align") or {}).get(k, 0)
        floats[cid] = {
            "n_samples": len(recs),
            "columns": st.median([r["measured"].get("columns", 1) for r in recs]),
            "columns_consistent": len({r["measured"].get("columns") for r in recs}) == 1,
            "fig_width_frac_median": round(st.median(vals(lambda m: (m.get("figure_geometry") or {}).get("fig_width_frac_median"))), 3)
            if vals(lambda m: (m.get("figure_geometry") or {}).get("fig_width_frac_median")) else None,
            "fig_height_frac_median": round(st.median(vals(lambda m: (m.get("figure_geometry") or {}).get("fig_height_frac_median"))), 3)
            if vals(lambda m: (m.get("figure_geometry") or {}).get("fig_height_frac_median")) else None,
            "full_width_fig_frac_mean": round(st.mean(fw_share), 3) if fw_share else None,
            "full_width_float_position": fw_pos,
            "full_width_float_position_ratio": (
                {k: round(v / max(1, sum(fw_pos.values())), 3) for k, v in fw_pos.items()}),
            "caption_font_pt_mode": max(set(cap_pt), key=cap_pt.count) if cap_pt else None,
            "caption_align_ratio": ({k: round(v / max(1, sum(cap_align.values())), 3)
                                     for k, v in cap_align.items()}),
            "note": "全部数值来自真实论文 PDF 的几何测量（tools/measure_pdf.py）",
        }
        layout[cid] = {
            "n_samples": len(recs),
            "figures_per_paper": round(st.mean(vals(lambda m: m.get("figures"))), 2) if vals(lambda m: m.get("figures")) else None,
            "tables_per_paper": round(st.mean(vals(lambda m: m.get("tables"))), 2) if vals(lambda m: m.get("tables")) else None,
            "equations_per_paper": round(st.mean(vals(lambda m: m.get("equations"))), 2) if vals(lambda m: m.get("equations")) else None,
            "algorithms_per_paper": round(st.mean(vals(lambda m: m.get("algorithms"))), 2) if vals(lambda m: m.get("algorithms")) else None,
            "refs_per_paper": round(st.mean(vals(lambda m: m.get("refs"))), 1) if vals(lambda m: m.get("refs")) else None,
            "footnotes_per_paper": round(st.mean(vals(lambda m: m.get("footnotes_est"))), 2) if vals(lambda m: m.get("footnotes_est")) else None,
            "content_pages_median": st.median(vals(lambda m: m.get("content_pages"))) if vals(lambda m: m.get("content_pages")) else None,
            "refs_style": sorted({r["measured"].get("ref_style") for r in recs
                                  if r["measured"].get("ref_style")}),
            "caption_font_pt_mode": max(set(cap_pt), key=cap_pt.count) if cap_pt else None,
        }
    return floats, layout


# ---------------------------------------------------------------- 自动汇总表
def write_tables(conf_by_id: dict, samples_by_id: dict, outdir: str):
    keys_order = ["page_limit_content", "page_limit_total", "references_counted",
                  "appendix_counted", "paper_size", "columns", "body_font_size_pt",
                  "bib_style", "anonymity", "figure_caption_position",
                  "table_caption_position", "page_numbering"]
    lines = ["# 跨会议硬性要求速查表（自动生成，勿手改）", "",
             "数值均取自 `conferences/*.json` 的 `hard_constraints`（每条可回溯到官方来源）。",
             "`—` = 未在该会议官方材料中找到明文/未收录。", "",
             "| 会议 | " + " | ".join(keys_order) + " |",
             "|---|" + "|".join(["---"] * len(keys_order)) + "|"]
    for cid, conf in sorted(conf_by_id.items()):
        row = [f"{conf.get('abbr', cid)}"]
        for k in keys_order:
            e = (conf.get("hard_constraints") or {}).get(k)
            v = e.get("value") if e else None
            if isinstance(v, dict):
                v = "/".join(str(v.get(x)) for x in ("top", "bottom", "left", "right"))
            row.append("—" if v in (None, "") else str(v))
        lines.append("| " + " | ".join(row) + " |")

    lines += ["", "## 实测统计（真实论文样本，自动生成）", "",
              "| 会议 | 样本数 | 栏数 | 版心宽(pt) | 正文字号(pt) | 左边距(mm) | 图/篇 | 表/篇 | 公式/篇 | 参考文献/篇 |",
              "|---|---|---|---|---|---|---|---|---|---|"]
    for cid, conf in sorted(conf_by_id.items()):
        stt = conf.get("statistics") or {}
        recs = [r for r in samples_by_id.get(cid, []) if r.get("measured")]
        def g(k, key="median"):
            v = (stt.get(k) or {}).get(key)
            return "—" if v is None else v
        cols = {r["measured"].get("columns") for r in recs}
        lines.append(f"| {conf.get('abbr', cid)} | {len(recs)} | "
                     f"{'/'.join(str(c) for c in sorted(cols)) if cols else '—'} | "
                     f"{g('text_width_pt')} | {g('body_font_pt')} | {g('margins_left_mm')} | "
                     f"{g('figures', 'mean')} | {g('tables', 'mean')} | {g('equations', 'mean')} | "
                     f"{g('refs', 'mean')} |")
    write_text(os.path.join(outdir, "cross-conf-table.md"), "\n".join(lines) + "\n")


def write_text(path: str, text: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


# ---------------------------------------------------------------- texopt 模板
def gen_texopt_templates(conf_by_id: dict, outdir: str):
    made = []
    for cid, conf in sorted(conf_by_id.items()):
        tmap = (conf.get("texopt_requirement_map") or {}).get("requirement_fields") or {}
        tpl = {k: v for k, v in tmap.items() if k in REQ_FIELDS}
        if not tpl:
            continue
        tpl = {"name": f"{conf.get('abbr', cid)} ({conf.get('current_edition', '')})",
               "desc": f"由数据集自动生成：{conf.get('current_edition')} 官方要求映射；"
                       f"来源见 datasets/conf-specs/conferences/{cid}.json",
               **tpl}
        dump(os.path.join(outdir, f"{cid}.json"), tpl)
        made.append(f"{cid}.json")
    return made


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--no-measure", action="store_true")
    ap.add_argument("--pages", type=int, default=25)
    ap.add_argument("--sleep", type=float, default=2.5)
    args = ap.parse_args()
    only = {x.strip() for x in args.only.split(",") if x.strip()}

    conf_files = sorted(f for f in os.listdir(os.path.join(ROOT, "conferences"))
                        if f.endswith(".json"))
    conf_by_id, samples_by_id = {}, {}
    for fn in conf_files:
        cid = fn[:-5]
        if only and cid not in only:
            continue
        conf_by_id[cid] = load(os.path.join(ROOT, "conferences", fn))
        lst = load(os.path.join(ROOT, "samples", f"{cid}.samples.list.json"), {})
        papers = lst.get("papers", [])
        recs = []
        print(f"[{cid}] 样本 {len(papers)} 篇，开始测量…", flush=True)
        for i, p in enumerate(papers, 1):
            r = measure_sample(cid, p, args.pages, args.sleep, not args.no_measure)
            m = r.get("measured") or {}
            print(f"   {i}/{len(papers)} {p['sample_id']}: "
                  f"{'OK pages=%s col=%s' % (m.get('pdf_pages'), m.get('columns')) if m else r.get('error')}",
                  flush=True)
            recs.append({**{k: p.get(k) for k in
                            ("sample_id", "title", "venue", "year", "url", "pdf_url", "note")},
                         **r})
        samples_by_id[cid] = recs
        # 1) jsonl
        with open(os.path.join(ROOT, "samples", f"{cid}.samples.jsonl"), "w", encoding="utf-8") as fh:
            for r in recs:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        # 2) 统计回写
        stats = aggregate(cid, recs)
        if stats:
            conf_by_id[cid]["statistics"] = stats
            dump(os.path.join(ROOT, "conferences", f"{cid}.json"), conf_by_id[cid])
        # 3) 逐年
        dump(os.path.join(ROOT, "years", f"{cid}.history.json"), year_history(cid, conf_by_id[cid]))

    floats, layout = extract_patterns(conf_by_id, samples_by_id)
    dump(os.path.join(ROOT, "patterns", "float_patterns.json"),
         {"schema_version": "1.0", "generated_by": "tools/build_dataset.py",
          "description": "figure/table/浮动体的尺寸·位置·题注统计（来自真实论文 PDF 测量）",
          "conferences": floats})
    dump(os.path.join(ROOT, "patterns", "layout_patterns.json"),
         {"schema_version": "1.0", "generated_by": "tools/build_dataset.py",
          "description": "常见版面元素密度与风格统计（来自真实论文 PDF 测量）",
          "conferences": layout})
    write_tables(conf_by_id, samples_by_id, os.path.join(ROOT, "summary"))
    made = gen_texopt_templates(conf_by_id, os.path.join(ROOT, "texopt-templates"))
    print(f"\n完成：{len(conf_by_id)} 个会议；生成 texopt 模板 {len(made)} 个", flush=True)


if __name__ == "__main__":
    main()
