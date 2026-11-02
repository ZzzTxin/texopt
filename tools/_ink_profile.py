#!/usr/bin/env python3
"""墨迹行剖面：直接看某页 ink 覆盖到页面纵向哪个位置（判断是否压进下边距）。

输出：first_ink / last_ink（占页高比例）、每 5% 带是否有点墨。
版心底 = 1 - bottom_margin/page_height（A4 297mm，底边距 25.4mm → 0.914）。
"""
import glob
import os
import sys

sys.path.insert(0, "/mnt/d/桌面/texopt")
sys.path.insert(0, "/mnt/d/桌面/texopt/tools")
from texopt import visual                 # noqa: E402

PDFS = sys.argv[1:]
if not PDFS:
    PDFS = sorted(glob.glob("/mnt/d/桌面/texopt/workbench-pweight/build/*/main.pdf"))

for pdf in PDFS:
    tag = os.path.basename(os.path.dirname(pdf))
    out = os.path.join(os.path.dirname(pdf), "_prof")
    files, err = visual.render_gray(pdf, out, dpi=72, prefix="p")
    if err or not files:
        print(f"[{tag}] render err={err}")
        continue
    for idx, f in enumerate(files, start=1):
        if idx == 1:
            continue
        w, h, data = visual._parse_pgm(f)          # noqa: SLF001
        rows = [y for y in range(h) if any(v < 160 for v in data[y * w:(y + 1) * w])]
        if not rows:
            print(f"[{tag}] p{idx}: 空白页")
            continue
        first, last = rows[0] / h, rows[-1] / h
        bands = []
        for b in range(20):
            lo, hi = b / 20 * h, (b + 1) / 20 * h
            bands.append("#" if any(lo <= y < hi for y in rows) else ".")
        print(f"[{tag}] p{idx}: first={first:.3f} last={last:.3f} |{''.join(bands)}|")
