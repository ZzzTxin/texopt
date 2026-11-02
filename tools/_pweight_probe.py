#!/usr/bin/env python3
"""快速迭代 harness：编译单个构造的 A/B 两版，打印每页字数与告警，不渲染图。"""
import os
import re
import subprocess
import sys

sys.path.insert(0, "/mnt/d/桌面/texopt")
sys.path.insert(0, "/mnt/d/桌面/texopt/tools")
import make_pweight_sheet as M          # noqa: E402
from texopt import engine               # noqa: E402

OUT = "/mnt/d/桌面/texopt/workbench-pweight/_probe"


def compile_one(tag, src):
    d = os.path.join(OUT, tag)
    os.makedirs(d, exist_ok=True)
    tex = os.path.join(d, "main.tex")
    open(tex, "w", encoding="utf-8").write(src)
    r = engine.compile_tex(tex, passes=1, timeout=120)
    if not r.ok:
        return {"ok": False, "err": r.first_error}
    txt = os.path.join(d, "pages.txt")
    tool = M.T._pdftotext()
    subprocess.run([tool, "-layout", os.path.basename(r.pdf_path), "pages.txt"],
                   cwd=d, capture_output=True)
    pages = open(txt, encoding="utf-8", errors="replace").read().split("\f")
    log = open(os.path.join(d, "main.log"), encoding="utf-8", errors="replace").read()
    return {"ok": True, "pages": len([p for p in pages if p.strip()]),
            "words": [len(p.split()) for p in pages],
            "warn_underfull": len(re.findall(r"Underfull \\hbox", log)),
            "warn_overfull": len(re.findall(r"Overfull \\hbox", log)),
            "warn_vbox": len(re.findall(r"Overfull \\vbox", log)),
            "warn_float": len(re.findall(r"Float too large", log)),
            "dir": d}


def main():
    ids = sys.argv[1:] or [d["id"] for d in M.DEFECTS]
    for dfx in M.DEFECTS:
        if dfx["id"] not in ids:
            continue
        a = compile_one(f"{dfx['id']}-A", M._variant_src(dfx["defect"], M.MARGIN0))
        print(f"== {dfx['id']} A: {a}")
        for cost in (dfx.get("cost_override") or M.COSTS):
            b = compile_one(f"{dfx['id']}-B{cost}",
                            M._variant_src(dfx["fixed"], M.MARGIN0 + cost * 2))
            print(f"   B@{cost}: {b}")


if __name__ == "__main__":
    main()
