"""Execute the visual model's bounded proposal for the PiFold opening page."""
from pathlib import Path
import difflib
import importlib.util
import json
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT / "workbench/case_studies"
spec = importlib.util.spec_from_file_location("case_runner", Path(__file__).with_name("run_cases.py"))
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)
from texopt import engine, perceive as P, proposal, score as S
from texopt.core import Optimizer, _static_perception

case = HERE / "runs/pifold"
source = R.source_path("pifold")
prior = json.loads((case / "after.json").read_text(encoding="utf-8"))
before = json.loads((case / "before.json").read_text(encoding="utf-8"))
if (case / "visual_refinement.json").exists():
    raise SystemExit("Refinement already recorded; refusing to overwrite the experiment")
R.write_json(case / "rule_only.json", prior)
shutil.copy2(case / "after" / source.name, case / "rule_only.tex")
shutil.copy2(case / "after" / source.with_suffix(".pdf").name, case / "rule_only.pdf")
engines = engine.engine_paths()
engines["xelatex"] = str(Path(engines["xelatex"]).with_name("pdflatex.exe"))
opt = Optimizer(str(source), R.req(), str(case / "after"), resume=True)
opt.records = list(prior["records"])
opt.iter = max((r["iteration"] for r in opt.records), default=0)
opt.accepted = prior["optimizer_result"]["accepted"]
opt.attempts = prior["optimizer_result"]["attempts"]
sc = before["score"]
opt.baseline = {"a": sc["a"], "i": sc["i"], "pages": before["pages"],
                "l": len(sc["l"]), "p": sc["p"], "m1": sc["m1"], "m2": sc["m2"]}
opt.emit_request(round_no=1, with_visual=True, visual_dpi=72)
doc = {
    "schema": "texopt.proposals/v1", "round": 1,
    "assessment": "The rule-only output moves the first figure above the paper title. The title and abstract should precede that figure.",
    "proposals": [{
        "id": "P1", "issue": "opening_page_float_placement", "location": "PDF page 1 / first figure",
        "severity": "high", "reason": "Actual page inspection shows the first figure above the title after generic float normalization. Restrict this figure to the bottom of a text page while preserving its original pixels and caption.",
        "proposal": {"action": "set_float_spec", "target": 1, "params": {"spec": "!b"}},
    }],
}
R.write_json(case / "proposals.json", doc)
parsed = proposal.parse_proposals(doc)
outcome = opt.apply_proposals(parsed["items"])
R.write_json(case / "visual_refinement.json", outcome)
per = P.perceive(str(case / "after" / source.name), R.req())
cur = S.total_score(per, R.req(), _static_perception(str(source)))
result = opt.finalize(per=per, cur=cur)
after = R.snapshot(per, R.req(), _static_perception(str(source)))
after["optimizer_result"] = result
after["records"] = opt.records
after["visual_refinement"] = outcome
R.write_json(case / "after.json", after)
R.write_json(case / "run_result.json", result)
original = (case / "before" / source.name).read_text(encoding="utf-8", errors="replace")
changed = (case / "after" / source.name).read_text(encoding="utf-8", errors="replace")
(case / "changes.patch").write_text("".join(difflib.unified_diff(original.splitlines(True), changed.splitlines(True), fromfile="before/"+source.name, tofile="after/"+source.name)), encoding="utf-8")
print(json.dumps({"proposal_outcome": outcome, "rule_only_score": prior["score"], "final_score": after["score"], "integrity": R.integrity("pifold")}, ensure_ascii=False), flush=True)
