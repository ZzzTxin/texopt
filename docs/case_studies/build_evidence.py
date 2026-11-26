"""Build appendix tables and compact evidence from measured real-paper runs."""
from __future__ import annotations
import hashlib
import difflib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
WORK = ROOT / "workbench/case_studies"
RUNS = WORK / "runs"
CASES = {
    "openstl": ("OpenSTL", "OpenSTL: A Comprehensive Benchmark of Spatio-Temporal Predictive Learning", "2306.11249v2", "openstl.tex"),
    "simvp": ("SimVP", "SimVP: Simpler yet Better Video Prediction", "2206.05099v1", "arxiv.tex"),
    "pifold": ("PiFold", "PiFold: Toward Effective and Efficient Protein Inverse Folding", "2209.12643v4", "iclr2022_conference.tex"),
    "omniview": ("Omniview-Tuning", "Omniview-Tuning: Boosting Viewpoint Invariance of Vision-Language Pre-training Models", "2404.12139v1", "arxiv_version.tex"),
}


def read(p):
    return json.loads(p.read_text(encoding="utf-8"))


def write(p, data):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def compact(snapshot):
    return {k: snapshot[k] for k in ["compile_ok", "pages", "score", "counts", "hygiene", "visual_pages", "visual_defects"]}


def clean_paths(value):
    if isinstance(value, str):
        for prefix in [str(ROOT), ROOT.as_posix(), "/mnt/d/桌面/texopt"]:
            value = value.replace(prefix, "<REPO>")
        return value
    if isinstance(value, list):
        return [clean_paths(v) for v in value]
    if isinstance(value, dict):
        return {k: clean_paths(v) for k,v in value.items()}
    return value


rows = []
for key, (label, title, arxiv, main) in CASES.items():
    case = RUNS / key
    before, after = read(case / "before.json"), read(case / "after.json")
    audit, stability = read(case / "integrity.json"), read(case / "stability.json")
    reviewed = None
    whitespace_review = None
    after_dir = case / "after"
    review_path = OUT / "evidence/pifold_full_review.json"
    if key == "openstl":
        review_file = ROOT / "真实稿件排版案例集/01_OpenSTL/运行证据/结构留白复核_不采用.json"
        if review_file.is_file():
            whitespace_review = read(review_file)
    if key == "pifold" and review_path.is_file():
        reviewed = read(review_path)
        stage1 = after
        after = read(WORK / "pifold_full_review/final.json")
        merged = list(stage1["records"])
        for rec in reviewed["steps"]:
            merged.append({**rec, "iteration": len(merged) + 1})
        after["records"] = merged
        after["optimizer_result"] = {"status": reviewed["program_status"]}
        audit = reviewed["integrity"]
        stability = {"stable": reviewed["stable_recompile"], "checks": reviewed["stability_checks"]}
        after_dir = WORK / "pifold_full_review/work"
    assert before["compile_ok"] and after["compile_ok"], key
    assert audit["pass"] and stability["stable"] and after["stable_recompile"], key
    assert not after["score"]["l"], key
    assert len(after["visual_pages"]) == after["pages"], key
    style_keys = ["documentclass", "class", "font_pt", "class_options", "geometry_margin_mm"]
    style = {k: {"before": before["source_summary"].get(k), "after": after["source_summary"].get(k)}
             for k in style_keys if k in before["source_summary"]}
    assert all(v["before"] == v["after"] for v in style.values()), key
    steps = after["records"]
    detail = {
        "id": key, "label": label, "title": title,
        "source_url": f"https://arxiv.org/abs/{arxiv}", "arxiv_version": arxiv,
        "input_was_perturbed": False,
        "provenance": read(case / "provenance.json"),
        "before": compact(before), "after": compact(after),
        "status": reviewed["visual_review_status"] if reviewed else after["optimizer_result"]["status"],
        "program_status": after["optimizer_result"]["status"],
        "accepted_actions": [r for r in steps if r["accepted"]],
        "rolled_back_actions": [r for r in steps if not r["accepted"]],
        "integrity": audit, "style_comparison": style, "stability": stability,
        "pdf_sha256": {"before": digest(case / "before" / Path(main).with_suffix(".pdf")),
                       "after": digest(after_dir / Path(main).with_suffix(".pdf"))},
    }
    if reviewed:
        detail["full_review"] = reviewed
        detail["status_basis"] = "案例状态采用模型全文复核结论；程序原始状态为DONE，尚未检测到第9页标题重叠。"
    if whitespace_review:
        detail["status"] = "NEEDS_REVIEW"
        detail["adoption_decision"] = "REJECTED_VISUAL"
        detail["preferred_version"] = "原稿"
        detail["whitespace_review"] = whitespace_review
        detail["status_basis"] = "必要结构留白与图文分组被破坏，不采用历史处理尝试；保留程序DONE及原始评分供审计。"
    if (case / "proposals.json").exists():
        detail["visual_proposals"] = read(case / "proposals.json")
        detail["visual_proposal_result"] = read(case / "visual_refinement.json")
        rule = read(case / "rule_only.json")
        detail["rule_only_score"] = rule["score"]
        detail["pdf_sha256"]["rule_only"] = digest(case / "rule_only.pdf")
    detail = clean_paths(detail)
    write(OUT / "evidence" / (key + ".json"), detail)
    if reviewed:
        original_text = (case / "before" / main).read_text(encoding="utf-8")
        final_text = (after_dir / main).read_text(encoding="utf-8")
        patch = "".join(difflib.unified_diff(original_text.splitlines(True),final_text.splitlines(True),
                                          fromfile="before/"+main,tofile="full_review/"+main))
        (OUT / "evidence" / (key + ".patch")).write_text(patch,encoding="utf-8")
    else:
        shutil.copy2(case / "changes.patch", OUT / "evidence" / (key + ".patch"))
    rows.append({"id": key, "label": label, "source_url": detail["source_url"],
                 "pages_before": before["pages"], "pages_after": after["pages"],
                 "counts_before": before["counts"], "counts_after": after["counts"],
                 "score_before": before["score"], "score_after": after["score"],
                 "accepted": len(detail["accepted_actions"]),
                 "rolled_back": len(detail["rolled_back_actions"]),
                 "status": detail["status"], "adoption_decision": detail.get("adoption_decision"),
                 "integrity_pass": audit["pass"]})

table = [r"\begin{table*}[!htbp]", r"\centering",
    r"\caption{四份真实作者稿件的实测处理结果，按“原稿 $\to$ 处理尝试”列示。评分越低不保证视觉更好；OpenSTL不采用，PiFold需复核，程序状态另存证据。}",
    r"\label{tab:real-case-outcomes}", r"\small", r"\setlength{\tabcolsep}{4pt}",
    r"\begin{tabular}{@{}lrrrrrl@{}}", r"\toprule",
    r"稿件 & 页数 & 浮动警告 & 垂直警告 & $M_1$ & $M_2$ & 状态 \\", r"\midrule"]
for row in rows:
    b, a = row["score_before"], row["score_after"]
    cb, ca = row["counts_before"], row["counts_after"]
    values = [row["label"], f"${row['pages_before']}\\to{row['pages_after']}$",
              f"${cb['float_warnings']}\\to{ca['float_warnings']}$",
              f"${cb['vbox']}\\to{ca['vbox']}$",
              f"${b['m1']:.3f}\\to{a['m1']:.3f}$",
              f"${b['m2']:.3f}\\to{a['m2']:.3f}$",
              ("不采用" if row.get("adoption_decision") == "REJECTED_VISUAL" else
               {"DONE": "已完成", "NEEDS_REVIEW": "需复核"}.get(row["status"], row["status"].replace("_", r"\_")))]
    table.append(" & ".join(values) + r" \\")
table += [r"\bottomrule", r"\end{tabular}", r"\end{table*}", ""]
(OUT / "case_metrics_table.tex").write_text("\n".join(table), encoding="utf-8")
write(OUT / "case_summary.json", {"schema": "texopt.case_studies.v1", "date": "2026-11-25", "language": "zh-CN",
      "selection": "四份未注入排版缺陷的公开作者稿件，用于案例展示，不作为测试集整体效果的估计。",
      "excluded_input": {"id": "local_laser_manuscript", "reason": "缺少原始 introduction_figure.pdf，基线无法编译。"},
      "rho": 15, "lambda": 0, "content_hard": True, "geometry_tuning": False,
      "page_budget": None, "cases": rows})
figures = []
for p in sorted((OUT / "figures").glob("*.pdf")):
    figures.append({"file": "figures/" + p.name, "sha256": digest(p), "bytes": p.stat().st_size,
                    "method": "直接导入实际编译 PDF 的页面，仅在页外增加中文面板标签，未重绘论文图形。"})
write(OUT / "figures/manifest.json", {"language": "zh-CN", "figures": figures})
for name in ["run_cases.py", "render_cases.py", "refine_pifold.py", "stabilize_cases.py"]:
    if (WORK / name).is_file():
        shutil.copy2(WORK / name, OUT / name)
print(json.dumps({"cases": len(rows), "integrity_pass": all(r['integrity_pass'] for r in rows),
                  "vector_figures": len(figures), "output": str(OUT)}, ensure_ascii=False))
