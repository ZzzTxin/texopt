"""Reproducible, unperturbed real-paper case studies for the texopt appendix.

Run from WSL at the repository root. Originals are only read. All compilations
and optimizer writes are confined to workbench/case_studies/runs/.
"""
from __future__ import annotations

import argparse
from collections import Counter
import difflib
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from texopt import engine, perceive as P, score as S
from texopt.core import Optimizer, _static_perception
from texopt.requirements import Requirement

HERE = ROOT / "workbench/case_studies"
RUNS = HERE / "runs"
CORPUS = ROOT / "paperfit-bench-originals/paperfit-bench-originals"
CASES = {
    "pifold": ("ICLR/arXiv-2209.12643v4", "iclr2022_conference.tex"),
    "simvp": ("CVPRICCV/arXiv-2206.05099v1", "arxiv.tex"),
    "omniview": ("ECCV/arXiv-2404.12139v1", "arxiv_version.tex"),
    "antibody": ("AAAI/arXiv-2305.09480v5", "aaai24_antibody.tex"),
    "openstl": ("NeurIPS/arXiv-2306.11249v2", "openstl.tex"),
    "laser": ("examples/test0913", "main.tex"),
    "silent_revision": ("examples/NeurlPS examples", "main.tex"),
}
BUILD_SUFFIXES = {".aux", ".log", ".out", ".toc", ".lof", ".lot", ".fls",
                  ".fdb_latexmk", ".xdv", ".blg", ".bcf"}


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def source_path(name):
    group, main = CASES[name]
    base = ROOT / group if group.startswith("examples/") else CORPUS / group
    return base / main


def req():
    # No page budget, geometry tuning, template migration or editorial deletion.
    # Preserve explicit content with the existing gate and an additional audit.
    return Requirement(content_hard=True, preserve_figures=True,
                       allow_geometry_tune=False, strip_reading_aids=False,
                       remove_warning_boxes=False, aesthetic_shadow=False,
                       max_iterations=24, verbose=True)


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def tree_hashes(directory):
    return {p.relative_to(directory).as_posix(): sha(p)
            for p in sorted(directory.rglob("*")) if p.is_file()
            and p.suffix.lower() not in BUILD_SUFFIXES
            and not p.name.endswith((".synctex.gz", ".run.xml"))}


def copy_project(src, destination):
    destination = destination.resolve()
    assert destination.is_relative_to(RUNS.resolve())
    if destination.exists():
        raise FileExistsError(f"Refusing to overwrite existing project: {destination}")
    shutil.copytree(src, destination)


def snapshot(per, requirement, original):
    sc = S.total_score(per, requirement, original)
    iss = per.issues
    visual = per.visual or {}
    return {
        "pages": per.pages, "score": sc,
        "counts": {"overfull": len(iss.get("overfull", [])),
                   "underfull": len(iss.get("underfull", [])),
                   "vbox": len(iss.get("vbox", [])),
                   "float_warnings": len(iss.get("floats", [])),
                   "tables_overwide": len(iss.get("tables_overwide", [])),
                   "warnings": len(iss.get("warnings", []))},
        "hygiene": dict(Counter(h["kind"] for h in iss.get("hygiene", []))),
        "issues": iss,
        "visual_pages": visual.get("pages", []),
        "visual_defects": S.visual_defects(per),
        "source_summary": per.source,
        "compile_ok": per.ok,
        "first_error": per.compile.first_error,
        "pdf": per.compile.pdf_path,
    }


def baseline(name):
    src = source_path(name)
    case = RUNS / name
    case.mkdir(parents=True, exist_ok=True)
    manifest = case / "provenance.json"
    if (case / "before.json").exists():
        previous = json.loads((case / "before.json").read_text(encoding="utf-8"))
        if not previous.get("compile_ok") and not (case / "initial_compile_failure.json").exists():
            write_json(case / "initial_compile_failure.json", previous)
            if (case / "baseline_compile.txt").exists():
                shutil.copy2(case / "baseline_compile.txt", case / "initial_compile_failure.txt")
    if not manifest.exists():
        write_json(manifest, {
            "case": name, "source": str(src.relative_to(ROOT)),
            "origin": CASES[name][0], "perturbations_injected": False,
            "input_hashes": tree_hashes(src.parent),
            "requirements": req().to_dict(),
            "engine": engine.engine_paths(),
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        })
    else:
        provenance = json.loads(manifest.read_text(encoding="utf-8"))
        provenance["engine"] = engine.engine_paths()
        provenance["compiler_adapter"] = "pdfLaTeX selected for author sources; same engine before/after"
        write_json(manifest, provenance)
    target = case / "before"
    if not target.exists():
        copy_project(src.parent, target)
    tex = target / src.name
    print(f"BASELINE {name}: {src}", flush=True)
    compiled = engine.compile_tex(str(tex), passes=2, timeout=45)
    (case / "baseline_compile.txt").write_text(compiled.log, encoding="utf-8")
    if not compiled.ok:
        data = {"compile_ok": False, "first_error": compiled.first_error,
                "returncode": compiled.returncode}
    else:
        per = P.perceive(str(tex), req())
        data = snapshot(per, req(), _static_perception(str(src)))
    write_json(case / "before.json", data)
    print(json.dumps({"case": name, "baseline": True,
                      **{k: data.get(k) for k in ["compile_ok", "first_error", "pages", "counts", "hygiene"]}},
                     ensure_ascii=False), flush=True)
    return data


def display_math(src):
    # Existing _norm_body masks display-math contents. Check those contents
    # independently, allowing only the $$ -> \[ wrapper normalization.
    src = re.sub(r"(?<!\\)%[^\n]*", "", src)
    matches = re.finditer(r"\$\$(.*?)\$\$|\\\[(.*?)\\\]", src, re.S)
    return ["".join((m.group(1) if m.group(1) is not None else m.group(2)).split())
            for m in matches]


def integrity(name):
    src = source_path(name)
    case = RUNS / name
    original = src.read_text(encoding="utf-8", errors="replace")
    changed = (case / "after" / src.name).read_text(encoding="utf-8", errors="replace")
    recorded = json.loads((case / "provenance.json").read_text(encoding="utf-8"))["input_hashes"]
    now = tree_hashes(src.parent)
    # All pre-existing files except the main .tex must retain their exact bytes.
    # This includes included .tex, .bib/.bbl, styles, figures and tables.
    regenerated = (".synctex", ".brf")
    mismatches = [rel for rel, digest in recorded.items()
                  if rel != src.name and not rel.endswith(regenerated)
                  and (not (case / "after" / rel).is_file()
                                         or sha(case / "after" / rel) != digest)]
    sem = S.semantic_diff(original, changed, req())
    maths = display_math(original) == display_math(changed)
    result = {"original_tree_unchanged": recorded == now,
              "normalized_main_text_preserved": sem["preserved"],
              "display_math_contents_preserved": maths,
              "non_main_original_files_unchanged": not mismatches,
              "changed_non_main_files": mismatches,
              "original_file_count": len(recorded),
              "excluded_regenerated_files": [rel for rel in recorded if rel.endswith(regenerated)],
              "display_math_block_count": len(display_math(original))}
    result["pass"] = all(result[k] for k in ["original_tree_unchanged",
        "normalized_main_text_preserved", "display_math_contents_preserved",
        "non_main_original_files_unchanged"])
    write_json(case / "integrity.json", result)
    return result


def optimize(name):
    case = RUNS / name
    before = json.loads((case / "before.json").read_text(encoding="utf-8"))
    if not before.get("compile_ok"):
        print(f"SKIP {name}: baseline cannot compile", flush=True)
        return
    src = source_path(name)
    if not (case / "after").exists():
        # Warm bibliography/cross-reference state identical to the baseline.
        copy_project(case / "before", case / "after")
    optimizer = Optimizer(str(src), req(), str(case / "after"), resume=True)
    print(f"OPTIMIZE {name}", flush=True)
    result = optimizer.run()
    write_json(case / "run_result.json", result)
    if not (case / "after" / src.name).exists():
        return
    per = P.perceive(str(case / "after" / src.name), req())
    after = snapshot(per, req(), _static_perception(str(src)))
    after["optimizer_result"] = result
    after["records"] = optimizer.records
    write_json(case / "after.json", after)
    before_src = (case / "before" / src.name).read_text(encoding="utf-8", errors="replace")
    after_src = (case / "after" / src.name).read_text(encoding="utf-8", errors="replace")
    patch = "".join(difflib.unified_diff(before_src.splitlines(True), after_src.splitlines(True),
                                        fromfile="before/" + src.name, tofile="after/" + src.name))
    (case / "changes.patch").write_text(patch, encoding="utf-8")
    audit = integrity(name)
    print(json.dumps({"case": name, "status": result.get("status"),
                      "before": {k: before.get(k) for k in ["pages", "score", "counts"]},
                      "after": {k: after.get(k) for k in ["pages", "score", "counts"]},
                      "integrity": audit}, ensure_ascii=False), flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("mode", choices=["environment", "baseline", "optimize", "integrity", "experiment"])
    ap.add_argument("names", nargs="*", choices=list(CASES))
    args = ap.parse_args()
    if args.mode == "environment":
        print(json.dumps({"root": str(ROOT), "engine": engine.engine_paths(),
                          "environment": engine.check_environment(),
                          "outdir": engine.check_output_dir(str(RUNS)),
                          "pdftoppm": engine.pdftoppm_path()}, ensure_ascii=False))
        return
    # These public author projects use pdfTeX primitives (e.g. \pdfoutput),
    # and axessibility also requires pdfTeX. The optimizer's compile interface
    # accepts the same flags for pdfLaTeX. Only this experiment's tool selection
    # is adapted; no paper source or production optimizer module is changed.
    engines = engine.engine_paths()
    xetex = engines["xelatex"]
    pdftex = Path(xetex).with_name("pdflatex.exe")
    if not pdftex.is_file():
        raise FileNotFoundError(f"Author-compatible compiler missing: {pdftex}")
    for name in args.names:
        # OpenSTL was originally measured with XeLaTeX; reproduce that engine.
        engines["xelatex"] = xetex if name == "openstl" else str(pdftex)
        if args.mode == "experiment":
            if (RUNS / name / "after").exists():
                print(f"SKIP {name}: optimization directory already exists (completed or active)", flush=True)
                continue
            try:
                baseline(name)
                optimize(name)
            except Exception as exc:
                write_json(RUNS / name / "experiment_error.json",
                           {"error": type(exc).__name__, "detail": str(exc)})
                print(f"ERROR {name}: {type(exc).__name__}: {exc}", flush=True)
        elif args.mode == "baseline": baseline(name)
        elif args.mode == "optimize": optimize(name)
        else: print(json.dumps(integrity(name), ensure_ascii=False))


if __name__ == "__main__":
    main()
