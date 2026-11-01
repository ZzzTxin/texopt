#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ρ A/B：同一份靶稿在 ρ=0.341（旧口径）与 ρ=15（无差异点）下各跑一遍，
对比 accepted / pages / L / M1 / 状态，检验重标定是否把行为带偏。

用法： python3 tools/rho_ab_compare.py [--rhos 0.341,15] [--docs demo,issues,...]
产物： workbench-rho-ab/<doc>-<rho>/（完整运行产物）+ summary.json
"""
import argparse
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.join(ROOT, "tools")
DOCS = [
    ("demo", "examples/demo.tex"),
    ("issues", "examples/issues.tex"),
    ("aidtest", "examples/aidtest.tex"),
    ("nightmare", "examples/nightmare.tex"),
    ("chaos", "examples/test0911/chaotic_layout_test.tex"),
]
RHOS = [0.341, 15.0]


def run(doc, rel, rho):
    outdir = os.path.join(ROOT, "workbench-rho-ab", f"{doc}-{rho:g}")
    cmd = [sys.executable, os.path.join(HERE, "rho_ab_run.py"), str(rho),
           os.path.join(ROOT, rel), "--outdir", outdir, "--quiet", "--json"]
    p = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT,
                       timeout=3600)
    if p.returncode not in (0, 1):
        return {"doc": doc, "rho": rho, "error": p.stderr[-1500:]}
    try:
        res = json.loads(p.stdout[p.stdout.index("{"):])
    except Exception:
        return {"doc": doc, "rho": rho,
                "error": "no json: " + p.stdout[-800:] + p.stderr[-800:]}
    recs = []
    st = os.path.join(outdir, "state.json")
    if os.path.isfile(st):
        with open(st, encoding="utf-8") as f:
            d = json.load(f)
        recs = [{"action": r.get("action"), "accepted": r.get("accepted"),
                 "source": r.get("source")} for r in d.get("steps", [])]
    return {"doc": doc, "rho": rho, "status": res.get("status"),
            "accepted": res.get("accepted"), "attempts": res.get("attempts"),
            "pages": res.get("pages"), "l": res.get("l"), "p": res.get("p"),
            "i": res.get("i"), "m1": res.get("m1"), "m2": res.get("m2"),
            "records": recs}


def main():
    global RHOS
    ap = argparse.ArgumentParser()
    ap.add_argument("--rhos", default=",".join(str(r) for r in RHOS))
    ap.add_argument("--docs", default="", help="逗号分隔的 doc 名，缺省=全部")
    a = ap.parse_args()
    RHOS = [float(x) for x in a.rhos.split(",") if x.strip()]
    docs = DOCS
    if a.docs:
        want = {x.strip() for x in a.docs.split(",") if x.strip()}
        docs = [d for d in DOCS if d[0] in want]
    out = []
    for doc, rel in docs:
        for rho in RHOS:
            print(f"[run] {doc} rho={rho}", flush=True)
            r = run(doc, rel, rho)
            out.append(r)
            print("   ->", {k: r.get(k) for k in
                            ("status", "accepted", "pages", "l", "m1")},
                  flush=True)
    path = os.path.join(ROOT, "workbench-rho-ab", "summary.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"schema": "texopt.rho_ab.v1", "rhos": RHOS, "rows": out},
                  f, ensure_ascii=False, indent=2)
    print("saved", path)


if __name__ == "__main__":
    main()
