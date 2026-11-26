"""Recompile final copies to stabilize references and synchronize evidence."""
from pathlib import Path
import importlib.util
import json
import sys

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT / "workbench/case_studies"
spec = importlib.util.spec_from_file_location("case_runner", Path(__file__).with_name("run_cases.py"))
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)
from texopt import engine, perceive as P, score as S
from texopt.core import Optimizer, _static_perception


def signature(snap):
    return {k: snap[k] for k in ["pages", "counts", "score"]}


engines = engine.engine_paths()
xetex = engines["xelatex"]
for name in sys.argv[1:]:
    engines["xelatex"] = xetex if name == "openstl" else str(Path(xetex).with_name("pdflatex.exe"))
    case = HERE / "runs" / name
    prior = json.loads((case / "after.json").read_text(encoding="utf-8"))
    before = json.loads((case / "before.json").read_text(encoding="utf-8"))
    source = R.source_path(name)
    original = _static_perception(str(source))
    previous = signature(prior)
    checks = []
    stable = False
    for repeat in range(3):
        per = P.perceive(str(case / "after" / source.name), R.req())
        current = R.snapshot(per, R.req(), original)
        now = signature(current)
        stable = now == previous
        checks.append({"repeat": repeat + 1, "matches_previous": stable, **now})
        previous = now
        if stable:
            break
    if not stable:
        R.write_json(case / "stability.json", {"stable": False, "checks": checks})
        raise RuntimeError(f"Final measurements did not stabilize for {name}")
    opt = Optimizer(str(source), R.req(), str(case / "after"), resume=True)
    opt.records = prior["records"]
    opt.iter = max((r["iteration"] for r in opt.records), default=0)
    opt.accepted = prior["optimizer_result"]["accepted"]
    opt.attempts = prior["optimizer_result"]["attempts"]
    sc = before["score"]
    opt.baseline = {"a": sc["a"], "i": sc["i"], "pages": before["pages"],
                    "l": len(sc["l"]), "p": sc["p"], "m1": sc["m1"], "m2": sc["m2"]}
    opt._blocked = set(prior["optimizer_result"].get("blocked", []))
    opt._ensure_orig()
    cur = S.total_score(per, R.req(), original)
    result = opt.finalize(per=per, cur=cur)
    current["optimizer_result"] = result
    current["records"] = opt.records
    for k in ["visual_refinement"]:
        if k in prior:
            current[k] = prior[k]
    current["stable_recompile"] = True
    R.write_json(case / "after.json", current)
    R.write_json(case / "run_result.json", result)
    R.write_json(case / "stability.json", {"stable": True, "checks": checks})
    audit = R.integrity(name)
    print(json.dumps({"case": name, "stable": stable, "pages": per.pages,
                      "score": current["score"], "integrity": audit}, ensure_ascii=False), flush=True)
