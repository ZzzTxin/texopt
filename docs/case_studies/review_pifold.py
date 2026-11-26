"""对 PiFold 全文继续执行白名单视觉提案，保留原有两次输出作为历史证据。"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys

import fitz

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location("case_runner", Path(__file__).with_name("run_cases.py"))
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)
from texopt import engine, perceive as P, proposal, score as S
from texopt.core import Optimizer, _static_perception

CASE = ROOT / "workbench/case_studies/runs/pifold"
REVIEW = ROOT / "workbench/case_studies/pifold_full_review"
WORK = REVIEW / "work"
MAIN = "iclr2022_conference.tex"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def configure():
    engines = engine.engine_paths()
    engines["xelatex"] = str(Path(engines["xelatex"]).with_name("pdflatex.exe"))


def original():
    return R.source_path("pifold")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def integrity():
    src = original()
    a, b = src.read_text(encoding="utf-8"), (WORK / MAIN).read_text(encoding="utf-8")
    saved = read(CASE / "provenance.json")["input_hashes"]
    changed = [p for p,h in saved.items() if p != MAIN and not p.endswith((".synctex", ".brf"))
               and (not (WORK / p).exists() or sha(WORK / p) != h)]
    out = {"original_tree_unchanged": R.tree_hashes(src.parent) == saved,
           "normalized_main_text_preserved": S.semantic_diff(a,b,R.req())["preserved"],
           "display_math_contents_preserved": R.display_math(a) == R.display_math(b),
           "non_main_original_files_unchanged": not changed, "changed_files": changed}
    out["pass"] = all(out[k] for k in ["original_tree_unchanged", "normalized_main_text_preserved",
                    "display_math_contents_preserved", "non_main_original_files_unchanged"])
    R.write_json(REVIEW / "integrity.json", out)
    return out


def prepare():
    if WORK.exists():
        raise SystemExit("工作目录已存在，不覆盖已有审阅结果")
    WORK.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(CASE / "after", WORK)
    before = read(CASE / "after.json")
    before["review_starting_stage"] = "仅修正首图的旧第二次排版"
    R.write_json(REVIEW / "start.json", before)
    R.write_json(REVIEW / "history.json", {"rounds": [], "failed_proposals": []})
    print(json.dumps({"prepared": str(WORK), "starting_score": before["score"]}, ensure_ascii=False),flush=True)


def run_round(path):
    configure()
    history = read(REVIEW / "history.json")
    request = read(path)
    no = request["round"]
    if any(r["round"] == no for r in history["rounds"]):
        raise SystemExit("本轮已记录，拒绝重复执行")
    opt = Optimizer(str(original()), R.req(), str(WORK), resume=True)
    opt._llm_failed = set(history["failed_proposals"])
    baseline = P.perceive(str(WORK / MAIN), R.req())
    before = R.snapshot(baseline, R.req(), _static_perception(str(original())))
    R.write_json(REVIEW / f"round{no}_before.json", before)
    result = {"applied": [], "rejected": [], "blocked": [], "skipped": []}
    for item in proposal.parse_proposals(request)["items"]:
        before_iter = opt.iter
        outcome = opt.apply_proposals([item])
        for key in result:
            result[key].extend(outcome.get(key, []))
        if opt.iter > before_iter:
            # 此时 PDF 对应刚尝试的候选；拒绝动作的源码已回滚，但 PDF 仍可归档复核。
            # 文件明确标注 rejected，绝不当作已接受的输出。
            phase = "rejected" if outcome.get("rejected") else "accepted"
            candidate = REVIEW / "attempts" / f"{item['id']}_{phase}.pdf"
            candidate.parent.mkdir(exist_ok=True)
            shutil.copy2(WORK / Path(MAIN).with_suffix(".pdf"), candidate)
    R.write_json(REVIEW / f"round{no}_outcome.json", result)
    R.write_json(REVIEW / f"round{no}_steps.json", opt.records)
    per = P.perceive(str(WORK / MAIN), R.req())
    snapshot = R.snapshot(per, R.req(), _static_perception(str(original())))
    snapshot["records"] = opt.records
    snapshot["proposal_outcome"] = result
    R.write_json(REVIEW / f"round{no}_after.json", snapshot)
    shutil.copy2(WORK / MAIN, REVIEW / f"round{no}.tex")
    shutil.copy2(WORK / Path(MAIN).with_suffix(".pdf"), REVIEW / f"round{no}.pdf")
    history["failed_proposals"] = sorted(opt._llm_failed)
    history["rounds"].append({"round": no, "before": before["score"], "after": snapshot["score"],
                              "pages": snapshot["pages"], "outcome": result})
    R.write_json(REVIEW / "history.json", history)
    audit = integrity()
    assert audit["pass"], audit
    # 生成下一轮的真实请求包；页面来自当前 PDF 的逐页渲染。
    from texopt import advise
    pages_dir = REVIEW / f"round{no}_pages"
    pages_dir.mkdir(exist_ok=True)
    images = []
    with fitz.open(WORK / Path(MAIN).with_suffix(".pdf")) as doc:
        for i,p in enumerate(doc):
            dest = pages_dir / f"page-{i+1}.png"
            p.get_pixmap(dpi=90, alpha=False).save(dest)
            images.append({"page": i+1, "path": str(dest)})
    adv = advise.build_advisory(original().read_text(encoding="utf-8"), per, R.req())
    packet = proposal.build_request(per, R.req(), snapshot["score"], no+1, images, adv,
               {"original_tex": str(original()), "work_tex": str(WORK / MAIN),
                "pdf": str(WORK / Path(MAIN).with_suffix(".pdf")), "outdir": str(WORK)})
    R.write_json(REVIEW / f"round{no+1}_request.json", packet)
    print(json.dumps({"round": no, "outcome": result,"final_score": snapshot["score"],
                      "visual_defects": snapshot["visual_defects"],"integrity": audit},ensure_ascii=False),flush=True)


def finalize():
    configure()
    orig = _static_perception(str(original()))
    last = None
    checks = []
    for repeat in range(3):
        per = P.perceive(str(WORK / MAIN),R.req())
        current = R.snapshot(per,R.req(),orig)
        signature = {k:current[k] for k in ["score","counts","pages"]}
        checks.append(signature)
        if signature == last:
            break
        last = signature
    else:
        raise RuntimeError("最终重编译测量尚未稳定")
    current["stable_recompile"] = True
    current["stability_checks"] = checks
    current["history"] = read(REVIEW / "history.json")
    current["integrity"] = integrity()
    assert current["integrity"]["pass"]
    R.write_json(REVIEW / "final.json",current)
    old = (CASE / "after" / MAIN).read_text(encoding="utf-8")
    new = (WORK / MAIN).read_text(encoding="utf-8")
    (REVIEW / "changes_from_round2.patch").write_text("".join(difflib.unified_diff(
        old.splitlines(True),new.splitlines(True),fromfile="old_round2/"+MAIN,
        tofile="full_review/"+MAIN)),encoding="utf-8")
    print(json.dumps({"stable":True,"pages":current["pages"],"score":current["score"],
                      "counts":current["counts"],"integrity":current["integrity"]},ensure_ascii=False),flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("mode",choices=["prepare","round","finalize"])
    ap.add_argument("proposals",nargs="?")
    a = ap.parse_args()
    if a.mode == "prepare": prepare()
    elif a.mode == "round": run_round(Path(a.proposals))
    else: finalize()


if __name__ == "__main__": main()
