"""导出 PiFold 全文复核结果与证据；不覆盖原有两次完整 PDF。"""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys

import fitz

ROOT = Path(__file__).resolve().parents[2]
BASE = Path(__file__).resolve().parent
REVIEW = ROOT / "workbench/case_studies/pifold_full_review"
CASE = ROOT / "workbench/case_studies/runs/pifold"
sys.path.insert(0,str(ROOT))
from texopt.core import Optimizer
from texopt.requirements import Requirement


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def clean(data):
    if isinstance(data,str): return data.replace(str(ROOT),"<REPO>").replace("/mnt/d/桌面/texopt","<REPO>")
    if isinstance(data,list): return [clean(x) for x in data]
    if isinstance(data,dict): return {k:clean(v) for k,v in data.items()}
    return data


final = read(REVIEW / "final.json")
assert final["stable_recompile"] and final["integrity"]["pass"]
old = read(CASE / "after.json")
history = read(REVIEW / "history.json")
steps = []
proposals = []
for row in history["rounds"]:
    for step in read(REVIEW / f"round{row['round']}_steps.json"):
        step["review_round"] = row["round"]
        steps.append(step)
    proposals.append(read(REVIEW / f"proposals_round{row['round']}.json"))

provenance = read(CASE / "provenance.json")
judge = Optimizer(str(ROOT / provenance["source"]), Requirement(**provenance["requirements"]),
                  str(REVIEW / "work"), resume=True)
judge.accepted = sum(s["accepted"] for s in old["records"] + steps)
judge.attempts = len(old["records"] + steps)
program_status = judge.exit_status(final["score"], final["visual_defects"])

full_pdf = REVIEW / "work/iclr2022_conference.pdf"
copies = BASE / "comparisons"
copies.mkdir(exist_ok=True)
export = copies / "pifold_full_review.pdf"
shutil.copy2(full_pdf,export)
assert sha(full_pdf) == sha(export)
with fitz.open(CASE / "after/iclr2022_conference.pdf") as old_doc, fitz.open(full_pdf) as new_doc:
    pages = []
    for i,p in enumerate(new_doc):
        same = i < len(old_doc) and p.get_text("dict") == old_doc[i].get_text("dict")
        pages.append({"page":i+1,"text_and_positions_equal_to_old_round2":same,
                      "interpretation":"相同" if same else "发生排布变化，不等于本页存在独立修复"})
    page9 = new_doc[8]
    headline = page9.search_for("GENERALIZATION (Q3)")[0]
    paragraph = page9.search_for("Objective & Results")[0]
    overlap = max(0,min(headline.y1,paragraph.y1)-max(headline.y0,paragraph.y0))
    assert overlap > 0
    appendix = new_doc[13].search_for("APPENDIX")[0]
    table = new_doc[13].search_for("Table 6:")[0]
    assert table.y0 < appendix.y0
    page_count = len(new_doc)

result = {
    "date":"2026-11-25", "scope":"完整审阅14页，在旧第二次排版之后执行3轮全文提案。",
    "previous_scope_correction":"旧第二次排版仅修正首页，第2—14页文字及位置未改变，不能作为整篇问题均已修复的证据。",
    "program_status":program_status, "visual_review_status":"NEEDS_REVIEW",
    "status_note":"程序评分仍判DONE，但模型逐页复核确认存在标题重叠等残余问题，案例展示按需复核报告。",
    "pages":page_count, "score_before_full_review":old["score"], "score_after_full_review":final["score"],
    "new_accepted":sum(bool(s["accepted"]) for s in steps),
    "new_rejected":sum(not s["accepted"] for s in steps),
    "new_skipped":sum(len(r["outcome"]["skipped"]) for r in history["rounds"]),
    "steps":steps,"proposals":proposals,"history":history,
    "page_comparison":pages,
    "directly_adjusted_pages":[7,8,9],
    "flow_affected_pages":[10,11,12,13],
    "remaining_issues":[
        {"page":9,"kind":"heading_text_overlap","severity":"high",
         "detail":"Generalization标题与Objective正文行框重叠，实际页面仍明显拥挤。",
         "line_box_overlap_pt":round(overlap,3),
         "cause":"源码中的负vspace；现有remove_excessive_vspace只删除正向过大间距，即使min_pt=1也无改动。",
         "status":"未修复；当前白名单动作覆盖不足，程序评分未检测该重叠。"},
        {"page":14,"kind":"appendix_table_before_heading","severity":"moderate",
         "detail":"表6仍浮到附录标题之前，末页留白仍存在。",
         "cause":"!b及!htbp未改善评分而回滚；H确实修正顺序，但H惩罚使M1从578.120升为593.615，因此被拒绝。",
         "rejected_candidate_m2":1.304,"status":"未修复；保留评分拒绝的实际候选证据。"},
        {"page":None,"kind":"underfull_hbox","count":4,"severity":"moderate",
         "detail":"仍有4条underfull日志，不能将版面重排表述为消除全部断行问题。","status":"未修复"}
    ],
    "integrity":final["integrity"],"stable_recompile":True,"stability_checks":final["stability_checks"],
    "pdf":"comparisons/pifold_full_review.pdf","pdf_sha256":sha(export),
    "old_pdfs_unchanged":{
        "round1":sha(copies/"pifold_round1_full.pdf")==read(BASE/"evidence/pifold.json")["pdf_sha256"]["rule_only"],
        "round2":sha(copies/"pifold_round2_full.pdf")==sha(CASE/"after/iclr2022_conference.pdf")
    }
}
assert all(result["old_pdfs_unchanged"].values())
(BASE/"evidence/pifold_full_review.json").write_text(json.dumps(clean(result),ensure_ascii=False,indent=2),encoding="utf-8")
shutil.copy2(REVIEW/"changes_from_round2.patch",BASE/"evidence/pifold_full_review.patch")
shutil.copy2(REVIEW/"attempts/R4-appendix-H_rejected.pdf",copies/"pifold_appendix_candidate_rejected.pdf")
version_path = copies/"full_pdf_versions.json"
versions = read(version_path)
versions["versions"] = [x for x in versions["versions"] if x.get("stage") != "full_review"]
versions["versions"].append({"stage":"full_review","description":"全文复核后的完整稿，仍有未决问题，NEEDS_REVIEW",
                           "file":export.name,"pages":page_count,"bytes":export.stat().st_size,
                           "sha256":sha(export),"identical_to_recorded_pdf":True})
version_path.write_text(json.dumps(versions,ensure_ascii=False,indent=2),encoding="utf-8")

spec = importlib.util.spec_from_file_location("render_cases",BASE/"render_cases.py")
renderer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(renderer)
renderer.vector_panels("pifold",[("after",7,"旧第二次排版｜第7页"),("full_review",7,"全文复核后｜第7页")],
                      BASE/"figures/pifold_page7_full_review.png")
print(json.dumps({"pages":page_count,"score":final["score"],"new_accepted":result["new_accepted"],
                  "new_rejected":result["new_rejected"],"review_status":result["visual_review_status"],
                  "changed_pages":[p["page"] for p in pages if not p["text_and_positions_equal_to_old_round2"]]},ensure_ascii=False))
