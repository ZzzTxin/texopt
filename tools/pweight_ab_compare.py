#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P 权重回填 A/B：同一批靶稿分别在旧权重（stage 11 human×corpus）与现行权重
（阶段 14 无差异点 + 口径 A 缩放）下跑完整闭环，对比 accepted / 页数 / L / M1 / 状态。

用法： python3 tools/pweight_ab_compare.py [--modes old,cur] [--docs demo,issues,...]
产物： workbench-pweight-ab/<doc>-<mode>/ + summary.json
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
MODES = ["old", "cur"]


def run(doc, rel, mode):
    outdir = os.path.join(ROOT, "workbench-pweight-ab", f"{doc}-{mode}")
    cmd = [sys.executable, os.path.join(HERE, "pweight_ab_run.py"), mode,
           os.path.join(ROOT, rel), "--outdir", outdir, "--quiet", "--json"]
    p = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT, timeout=3600)
    if p.returncode not in (0, 1):
        return {"doc": doc, "mode": mode, "error": p.stderr[-1500:]}
    try:
        res = json.loads(p.stdout[p.stdout.index("{"):])
    except Exception:
        return {"doc": doc, "mode": mode,
                "error": "no json: " + p.stdout[-800:] + p.stderr[-800:]}
    recs = []
    st = os.path.join(outdir, "state.json")
    if os.path.isfile(st):
        with open(st, encoding="utf-8") as f:
            d = json.load(f)
        recs = [{"action": r.get("action"), "accepted": r.get("accepted"),
                 "source": r.get("source")} for r in d.get("steps", [])]
    return {"doc": doc, "mode": mode, "status": res.get("status"),
            "accepted": res.get("accepted"), "attempts": res.get("attempts"),
            "pages": res.get("pages"), "l": res.get("l"), "p": res.get("p"),
            "i": res.get("i"), "m1": res.get("m1"), "m2": res.get("m2"),
            "records": recs}


def main():
    global MODES
    ap = argparse.ArgumentParser()
    ap.add_argument("--modes", default=",".join(MODES))
    ap.add_argument("--docs", default="", help="逗号分隔的 doc 名，缺省=全部")
    a = ap.parse_args()
    MODES = [x.strip() for x in a.modes.split(",") if x.strip()]
    docs = DOCS
    if a.docs:
        want = {x.strip() for x in a.docs.split(",") if x.strip()}
        docs = [d for d in DOCS if d[0] in want]
    out = []
    for doc, rel in docs:
        for mode in MODES:
            print(f"[run] {doc} {mode}", flush=True)
            r = run(doc, rel, mode)
            out.append(r)
            print("   ->", {k: r.get(k) for k in
                            ("status", "accepted", "pages", "l", "p", "m1")},
                  flush=True)
    path = os.path.join(ROOT, "workbench-pweight-ab", "summary.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"schema": "texopt.pweight_ab.v1", "modes": MODES, "rows": out},
                  f, ensure_ascii=False, indent=2)
    print("saved", path)


if __name__ == "__main__":
    raise SystemExit(main())
