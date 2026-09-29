# -*- coding: utf-8 -*-
"""页面级指标提取器（阶段 1）：PDF -> page_metrics.v1。

证据层
  * vector/text：pdfminer.six（vendored，`TEXOPT_TOOLS`）—— 文本行包围盒、字形字号、
    字体名（判断加粗/数学字形）、图形/图片框。所有几何量**量自 PDF 而不是源码**。
  * pixel（可选）：复用 `visual.page_metrics`（低分辨率灰度）—— 墨迹占比、最大空白带。
  * log（可选）：有编译日志时才可用（overfull/underfull/vbox）；语料 PDF 没有日志，
    因此 `microtype` 在语料上是 `unavailable`，不假装有。

关键口径（**精确定义**，避免指标不可比）
  * `A_usable`（版心）= 由「正文页的正文尺寸行」测出的文本框：左右取行首/行尾众数，
    上下取正文尺寸行的分位位置（排除页眉/页码/脚注这些非正文小字号行）；
    双栏时 = 左栏面积 + 右栏面积（**栏间距不计入**）。
  * 覆盖率/留白率的分母一律用 `A_usable`。
  * 面积一律用 4pt 网格掩码累计（同一像素格不被重复计入），避免框重叠导致 >100%。

不做的（诚实标注，见 `status` 字段）
  * 表格覆盖用「**题注锚定**的浮动区」近似：不解析表格结构，只量"这块区域多大"。
  * 留白的**分类**由 `texopt/whitespace.py`（阶段 3）完成：空白掩码连通域 +
    结构规则 → 五类留白 + region 列表；本模块只负责把元素与几何递过去。
  * 微观排版（断行 badness/连字）需要 TeX 侧信息，语料 PDF 上 unavailable。
"""
from __future__ import annotations

import os
import re
import statistics as st
import sys
import time

from . import page_metrics as PM
from .roles import THRESH as ROLES_THRESH

TOOLS = os.environ.get("TEXOPT_TOOLS", os.path.expanduser("~/.local/lib/texopt-tools"))
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)

PT2MM = 25.4 / 72.0
SNAP_PT = (7.0, 8.0, 9.0, 10.0, 11.0, 12.0)
# 题注识别（阶段 3 实测修正）：原版漏掉三类常见写法——
#   * 大写缩写带句点："FIG. 1." / "TABLE II."（APS/PRL 系）
#   * 罗马数字编号："TABLE I."（\d+ 匹配不到）
#   * 中文无分隔符："图 1 系统架构" / "表 2 对比"
CAP_RE = re.compile(
    r"^\s*(?:Figure|FIGURE|Fig|FIG|Table|TABLE|Tab|TAB|图|表)\.?\s*"
    r"(?:\d+|[IVXLC]{1,6}\b)", re.ASCII)
MATH_FONT_RE = re.compile(r"(CMMI|CMSY|CMEX|CMMIB|MSAM|MSBM|EUSM|EUFM|RSFS|"
                          r"Math|Symbol|MTMI|MTSY)", re.I)
_REF_RE = None


def _re_mod():
    import re as _r
    return _r


# ---------------------------------------------------------------- pdfminer 采集

def _laparams():
    from pdfminer.layout import LAParams
    return LAParams(detect_vertical=False, line_overlap=0.5, char_margin=2.0,
                    line_margin=0.5, word_margin=0.1, boxes_flow=None)


def _row_to_line(row: list[dict]) -> dict:
    """字符簇 -> 行（恢复词间空格；字号取中位；bold/math 由字体名判定）。"""
    row = sorted(row, key=lambda c: c["x0"])
    txt, prev = [], None
    for ch in row:
        if prev is not None and ch["x0"] - prev > 1.2:
            txt.append(" ")
        txt.append(ch["text"])
        prev = ch["x1"]
    names = " ".join(str(c.get("font") or "") for c in row)
    math_n = sum(1 for c in row if MATH_FONT_RE.search(str(c.get("font") or "")))
    return {
        "x0": round(min(c["x0"] for c in row), 2),
        "x1": round(max(c["x1"] for c in row), 2),
        "y0": round(min(c["y0"] for c in row), 2),
        "y1": round(max(c["y1"] for c in row), 2),
        "size": round(st.median([c["size"] for c in row]), 2),
        "text": "".join(txt).strip(), "nchars": len(row), "fig": False,
        "bold": ("Bold" in names or "bold" in names),
        "math": round(math_n / max(1, len(row)), 3),
    }


def group_chars(chars: list[dict], gap: float = 14.0) -> list[dict]:
    """字符重建行（Form XObject 回退）。

    两步：① 按基线聚成"行带"；② 行带内按水平间隔切段（双栏共享同一基线，
    必须靠间隔切开，否则会把两栏文字拼成一行）。方法与 `tools/measure_pdf.py`
    一致 —— 那套实现已经在 608 篇语料上跑过。
    """
    bands: list[list[dict]] = []
    cur: list[dict] = []
    ycen = 0.0
    for ch in sorted(chars, key=lambda c: (-(c["y0"] + c["y1"]) / 2, c["x0"])):
        yc = (ch["y0"] + ch["y1"]) / 2
        if cur and abs(yc - ycen) > max(2.0, 0.6 * ch["size"]):
            bands.append(cur)
            cur = []
        if not cur:
            ycen = yc
        cur.append(ch)
        ycen = sum((c["y0"] + c["y1"]) / 2 for c in cur) / len(cur)
    if cur:
        bands.append(cur)
    out: list[dict] = []
    for band in bands:
        seg: list[dict] = []
        for ch in sorted(band, key=lambda c: c["x0"]):
            if seg and ch["x0"] - seg[-1]["x1"] > gap:
                out.append(_row_to_line(seg))
                seg = []
            seg.append(ch)
        if seg:
            out.append(_row_to_line(seg))
    return out


def collect_page_items(pdf_path: str, max_pages: int | None = None):
    """PDF -> (pages, sizes)。pages[i] = {lines, figs, drawings, images, texts}。

    line: {x0,x1,y0,y1,size,text,nchars,fig,bold,math}（坐标为 pt，原点左下）
    fig : {x0,y0,x1,y1,w,h}（顶层 LTFigure）
    drawing: {x0,y0,x1,y1,w,h,kind}（LTRect/LTLine/LTCurve）
    image: {x0,y0,x1,y1,w,h,src_w,src_h}
    textbox: {x0,y0,x1,y1}（LTTextBox，用于框选版面块）
    """
    from pdfminer.high_level import extract_pages
    from pdfminer.layout import (LTTextContainer, LTTextLine, LTChar, LTFigure,
                                 LTImage, LTLine, LTRect, LTCurve)

    pages, sizes = [], []
    for pi, layout in enumerate(extract_pages(pdf_path, laparams=_laparams())):
        if max_pages and pi >= max_pages:
            break
        sizes.append((float(layout.width), float(layout.height)))
        P = {"lines": [], "figs": [], "drawings": [], "images": [], "texts": [],
             "raw": []}
        pw0, ph0 = float(layout.width), float(layout.height)
        page_area0 = max(pw0 * ph0, 1.0)

        def walk(el, in_fig=False, in_wrap=False):
            for child in el:
                tn = type(child).__name__
                if isinstance(child, LTTextContainer):
                    b = child.bbox
                    P["texts"].append({"x0": round(b[0], 2), "y0": round(b[1], 2),
                                       "x1": round(b[2], 2), "y1": round(b[3], 2)})
                    for ln in child:
                        if not isinstance(ln, LTTextLine):
                            continue
                        chars = [c for c in ln if isinstance(c, LTChar)]
                        txt = ln.get_text().strip()
                        if not chars or not txt:
                            continue
                        nm = " ".join(str(c.fontname) for c in chars)
                        math_n = sum(1 for c in chars
                                     if MATH_FONT_RE.search(str(c.fontname)))
                        P["lines"].append({
                            "x0": round(min(c.x0 for c in chars), 2),
                            "x1": round(max(c.x1 for c in chars), 2),
                            "y0": round(ln.y0, 2), "y1": round(ln.y1, 2),
                            "size": round(st.median([c.size for c in chars]), 2),
                            "text": txt, "nchars": len(chars),
                            "fig": in_fig,
                            "bold": ("Bold" in nm or "bold" in nm),
                            "math": round(math_n / max(1, len(chars)), 3),
                        })
                        if in_wrap:          # 供 Form XObject 回退重建行
                            for c in chars:
                                P["raw"].append({
                                    "x0": c.x0, "x1": c.x1, "y0": c.y0, "y1": c.y1,
                                    "size": c.size, "text": c.get_text(),
                                    "font": str(c.fontname)})
                    continue
                if isinstance(child, LTFigure):
                    b = child.bbox
                    # 有些 PDF（典型如 ACL Anthology）把**整页内容**包进一个 Form
                    # XObject，pdfminer 会给出一个"面积≈整页"的 LTFigure。它是版面
                    # 容器而不是插图：若把它当图，页内正文行会被标成 fig=True 而
                    # 全部丢弃（实测 ACL 论文只抽得到页眉页脚 → 无 References 可言）。
                    wrapper = (b[2] - b[0]) * (b[3] - b[1]) >= 0.75 * page_area0
                    if not in_fig and not wrapper:
                        P["figs"].append({"x0": round(b[0], 2), "y0": round(b[1], 2),
                                          "x1": round(b[2], 2), "y1": round(b[3], 2),
                                          "w": round(b[2] - b[0], 2),
                                          "h": round(b[3] - b[1], 2)})
                    walk(child, in_fig or not wrapper, in_wrap or wrapper)
                    continue
                if isinstance(child, LTImage):
                    b = child.bbox
                    sw = sh = None
                    try:
                        sw, sh = child.srcsize
                    except Exception:
                        pass
                    P["images"].append({"x0": round(b[0], 2), "y0": round(b[1], 2),
                                        "x1": round(b[2], 2), "y1": round(b[3], 2),
                                        "w": round(b[2] - b[0], 2),
                                        "h": round(b[3] - b[1], 2),
                                        "src_w": sw, "src_h": sh})
                    continue
                if isinstance(child, LTChar):
                    # Form XObject 内部的字符：pdfminer 不做行分组，这里直接裸\u63d0字符；
                    # 页面后处理会用 group_chars() 重建行（见 collect_page_items 末尾）。
                    if in_wrap and child.get_text().strip():
                        P["raw"].append({
                            "x0": child.x0, "x1": child.x1, "y0": child.y0,
                            "y1": child.y1, "size": child.size,
                            "text": child.get_text(), "font": str(child.fontname)})
                    continue
                if isinstance(child, (LTLine, LTRect, LTCurve)):
                    b = child.bbox
                    w, h = b[2] - b[0], b[3] - b[1]
                    if w > 0.5 or h > 0.5:
                        P["drawings"].append({
                            "x0": round(b[0], 2), "y0": round(b[1], 2),
                            "x1": round(b[2], 2), "y1": round(b[3], 2),
                            "w": round(w, 2), "h": round(h, 2),
                            "kind": tn.replace("LT", "").lower()})
                    continue
                if hasattr(child, "__iter__"):
                    walk(child, in_fig, in_wrap)

        walk(layout)
        # Form XObject 回退：pdfminer 不对 Form 内部做行分组，整页被包进一个 Form 的
        # PDF（实测 ACL 论文即如此）几乎量不到正文行。此时用**包装内字符**重建行。
        nchars_line = sum(ln["nchars"] for ln in P["lines"] if not ln["fig"])
        if len(P["raw"]) > 200 and nchars_line < 0.5 * len(P["raw"]):
            rebuilt = group_chars(P["raw"])
            if len(rebuilt) > 0:
                P["lines"] = rebuilt + [ln for ln in P["lines"] if ln["fig"]]
                P["figs"] = [f for f in P["figs"]
                             if f["w"] * f["h"] < 0.75 * page_area0]
                P["rebuilt"] = True
        pages.append(P)
    return pages, sizes


# ---------------------------------------------------------------- 小工具

def snap_size(pt: float) -> float:
    for c in SNAP_PT:
        if abs(pt - c) <= 0.6:
            return c
    return round(pt, 1)


def mode_pt(vals, tol: float = 1.0):
    if not vals:
        return None
    bins: dict[int, int] = {}
    for v in vals:
        bins[round(v / tol)] = bins.get(round(v / tol), 0) + 1
    b = max(bins, key=lambda k: bins[k])
    near = [v for v in vals if abs(v - b * tol) <= tol]
    return round(sum(near) / len(near), 1)


def median(vals):
    v = [x for x in vals if x is not None]
    return round(float(st.median(v)), 3) if v else None


def std(vals):
    v = [x for x in vals if x is not None]
    return round(float(st.pstdev(v)), 3) if len(v) >= 2 else None


def cv(vals):
    v = [float(x) for x in vals if x]
    if len(v) < 2:
        return None
    m = sum(v) / len(v)
    return round(float(st.pstdev(v)) / m, 4) if m else None


class GridMask:
    """4pt 网格掩码：累计"被覆盖的面积"，同一格不重复计入。

    `exclude_x` 用于把**栏间距**从版心里挖掉 —— 这样掩码可用面积与
    `A_usable`（=帧面积−栏间距）天然一致，覆盖率不会超过 100%。
    """

    CELL = 4.0

    def __init__(self, x0, y0, x1, y1, exclude_x=None):
        self.x0, self.y0 = x0, y0
        self.x1, self.y1 = x1, y1          # 真实边界：越界的格心不计入
        self.nx = max(1, int((x1 - x0) / self.CELL) + 1)
        self.ny = max(1, int((y1 - y0) / self.CELL) + 1)
        self.cells = set()
        self.excl = list(exclude_x or [])

    def _skip(self, xcen: float) -> bool:
        return any(a <= xcen <= b for a, b in self.excl)

    def add(self, box):
        x0 = max(box["x0"], self.x0)
        y0 = max(box["y0"], self.y0)
        x1 = min(box["x1"], self.x0 + self.nx * self.CELL)
        y1 = min(box["y1"], self.y0 + self.ny * self.CELL)
        if x1 <= x0 or y1 <= y0:
            return
        c = self.CELL
        for i in range(int((x0 - self.x0) // c), int((x1 - self.x0 - 1e-9) // c) + 1):
            cxc = self.x0 + (i + 0.5) * c
            # 2026-09-28：格心超出帧边界不计 —— 否则最后一个不满格会把掩码面积
            # 撑到解析值 A_usable 之外，覆盖率出现 1.0116 这种 >100% 的假值。
            if cxc > self.x1 or cxc < self.x0 or self._skip(cxc):
                continue
            for j in range(int((y0 - self.y0) // c), int((y1 - self.y0 - 1e-9) // c) + 1):
                cyc = self.y0 + (j + 0.5) * c
                if cyc > self.y1 or cyc < self.y0:
                    continue
                self.cells.add((i, j))

    def area(self) -> float:
        return len(self.cells) * self.CELL * self.CELL


def frame_usable_pt2(frame: dict) -> float:
    """版心面积（pt²）——与 GridMask 可用格数一致的解析式。"""
    h = frame["height_pt"]
    w = frame["right"] - frame["left"]
    if frame["columns"] == 2 and frame.get("col_gap"):
        w -= frame["col_gap"]
    return max(1.0, w * h)


def frame_excl_x(frame: dict):
    """栏间距要从掩码里挖掉的 x 区间。"""
    if frame["columns"] == 2 and frame.get("col_gap"):
        return [(frame["col1_right"], frame["col2_left"])]
    return []


def box_area(b: dict) -> float:
    return max(0.0, b["x1"] - b["x0"]) * max(0.0, b["y1"] - b["y0"])


def overlap_frac(box: dict, band: tuple) -> float:
    """box 与纵向区间 (lo,hi) 的重叠比例（0-1）。"""
    lo, hi = band
    a = max(box["y0"], lo)
    b = min(box["y1"], hi)
    h = box["y1"] - box["y0"]
    if h <= 0 or b <= a:
        return 0.0
    return (b - a) / h


# ---------------------------------------------------------------- 版心测量

def find_gutter(lines: list[dict], p_left: float, p_right: float):
    """版心中部找"栏间空白沟"（几乎无行覆盖的 x 带），返回沟右沿或 None。"""
    lo, hi = int(p_left), int(p_right)
    if hi - lo < 120 or len(lines) < 15:
        return None
    n = hi - lo + 1
    diff = [0] * (n + 2)
    for ln in lines:
        a = max(lo, int(ln["x0"]))
        b = min(hi, int(ln["x1"]))
        if b > a:
            diff[a - lo] += 1
            diff[b - lo + 1] -= 1
    cov, cur = [0] * n, 0
    for i in range(n):
        cur += diff[i]
        cov[i] = cur
    limit = max(1, int(0.05 * len(lines)))
    best, start = (0, 0), None
    for i, v in enumerate(cov):
        if v <= limit:
            start = i if start is None else start
        else:
            if start is not None and i - start > best[1] - best[0]:
                best = (start, i)
            start = None
    if start is not None and n - start > best[1] - best[0]:
        best = (start, n)
    gs, ge = best[0] + lo, best[1] + lo
    span = p_right - p_left
    if ge - gs < 6 or gs < p_left + 0.25 * span or ge > p_right - 0.15 * span:
        return None
    return float(ge)


def measure_frame(pages: list[dict], sizes: list[tuple]) -> dict:
    """量出版心（A_usable 的几何）与栏数。口径见模块 docstring。"""
    if not sizes:
        raise RuntimeError("PDF 无可读页面")
    pw = float(st.median([s[0] for s in sizes]))
    ph = float(st.median([s[1] for s in sizes]))
    body_pages = pages[1:] or pages
    all_lines = [ln for p in body_pages for ln in p["lines"]]
    lines = [ln for ln in all_lines if not ln["fig"]] or all_lines
    if not lines:
        raise RuntimeError("未抽取到文本行（可能是纯图像 PDF）")

    w: dict[float, int] = {}
    for ln in lines:
        w[snap_size(ln["size"])] = w.get(snap_size(ln["size"]), 0) + ln["nchars"]
    body_pt = max(w.items(), key=lambda kv: kv[1])[0] if w else 10.0

    # 正文尺寸行（用于版心上下沿；排除页眉/页码/脚注等小字号行）
    main_lines = [ln for ln in lines if ln["size"] >= body_pt - 0.6] or lines
    left = min(ln["x0"] for ln in main_lines)
    xs = [ln["x0"] for ln in main_lines]
    hist0: dict[int, int] = {}
    for x in xs:
        hist0[round(x)] = hist0.get(round(x), 0) + 1
    thr = max(3, 0.05 * len(main_lines))
    peaks = sorted(p for p, c in hist0.items() if c >= thr)
    p_left = min(peaks) if peaks else left

    # 双栏：栏间空白沟逐页投票
    hits = []
    for p in body_pages:
        ls = [ln for ln in p["lines"] if not ln["fig"]]
        if len(ls) < 15:
            continue
        g = find_gutter(ls, p_left, max(x["x1"] for x in ls))
        if g:
            hits.append(g)
    gutter = None
    if len(hits) >= 3:
        hits.sort()
        clusters: list[list[float]] = []
        for g in hits:
            if clusters and g - clusters[-1][-1] <= 6:
                clusters[-1].append(g)
            else:
                clusters.append([g])
        best = max(clusters, key=len)
        if len(best) >= max(3, 0.3 * len(hits)):
            gutter = round(st.median(best), 1)

    two_col = gutter is not None
    if two_col:
        c1 = [ln for ln in main_lines if ln["x1"] <= gutter - 2]
        c2 = [ln for ln in main_lines if ln["x0"] >= gutter - 2]
        r1 = mode_pt([ln["x1"] for ln in c1]) or max(
            (ln["x1"] for ln in c1), default=gutter)
        r2 = mode_pt([ln["x1"] for ln in c2]) or max(
            (ln["x1"] for ln in c2), default=pw - left)
        right = max(r1, r2)
        col_gap = round(gutter - r1, 1)
        if col_gap < 4 or col_gap > 60 or r2 - gutter < 40:
            two_col, gutter, col_gap = False, None, None
            right = mode_pt([ln["x1"] for ln in main_lines]) or max(
                ln["x1"] for ln in main_lines)
    else:
        right = mode_pt([ln["x1"] for ln in main_lines]) or max(
            ln["x1"] for ln in main_lines)
        r1 = r2 = right
        col_gap = None

    tops = [max(ln["y1"] for ln in p["lines"]
                if ln["size"] >= body_pt - 0.6) for p in body_pages
            if any(ln["size"] >= body_pt - 0.6 for ln in p["lines"])]
    bots = [min(ln["y0"] for ln in p["lines"]
                if ln["size"] >= body_pt - 0.6) for p in body_pages
            if any(ln["size"] >= body_pt - 0.6 for ln in p["lines"])]
    top = median(tops) or ph
    bottom = median(bots) or 0.0
    height = max(1.0, top - bottom)
    if two_col:
        usable = (r1 - left) * height + (r2 - gutter) * height
        col_width = ((r1 - left) + (r2 - gutter)) / 2
    else:
        usable = (right - left) * height
        col_width = right - left
    return {
        "pw": round(pw, 2), "ph": round(ph, 2),
        "left": round(left, 2), "right": round(right, 2),
        "top": round(top, 2), "bottom": round(bottom, 2),
        "columns": 2 if two_col else 1,
        "gutter": gutter, "col_gap": col_gap,
        "col1_right": round(r1, 2), "col2_left": gutter,
        "col_width": round(col_width, 2),
        "usable_pt2": round(usable, 1),
        "body_pt": body_pt,
        "height_pt": round(height, 2),
    }


# ---------------------------------------------------------------- 浮动区（题注锚定）

def caption_kind(text: str):
    """题注 → "figure" / "table" / None。"""
    m = CAP_RE.match(text or "")
    if not m:
        return None
    kw = m.group(0).strip().lower()
    return "table" if kw.startswith(("tab", "表")) else "figure"


def _clip_box(b, x_lo, x_hi, frame):
    return {"x0": max(b["x0"], x_lo), "y0": max(b["y0"], frame["bottom"]),
            "x1": min(b["x1"], x_hi), "y1": min(b["y1"], frame["top"])}


def _graphic_ok(g, A, frame):
    """过滤掉不可能属于某个浮动体的图形元素。

    两个真实坑（2026-09-28 实测发现）：
      * **整页 Form 包装**：有些 PDF 把整页内容包进一个 Form XObject，pdfminer 会给出
        一个“面积=100% 页面”的 LTFigure；它一旦参与链式扩张，浮动区直接吃满整页。
        判据：面积 ≥ 0.75 页面（真图不会盖住页边距）。
      * **细节线条**：章节分隔线/表格横线又细又小（h≈0.5pt），会把不相干的区域链条起来。
    """
    w = g.get("w", g["x1"] - g["x0"])
    h = g.get("h", g["y1"] - g["y0"])
    if w * h >= 0.75 * (frame["pw"] * frame["ph"]):
        return False
    return w >= 12 and h >= 3 and w * h >= 0.004 * A


def anchor_floats(page: dict, frame: dict) -> list[dict]:
    """用题注把"浮动区"锚出来。

    修正（2026-09-28 实测发现）：早期版本把**所有文本行**纳入链式扩张，
    正文行的行距远小于 gap_max，于是链会一路吃穿整页 → 覆盖率出现 104%。
    现在只在**图形元素**（图形/图片/LTFigure）上做连续链扩张，再把完全落在
    区域内的文本行（轴标签/图例/题注续行）计入；并且限制在题注所在栏内。
    """
    lines = [ln for ln in page["lines"] if not ln["fig"]]
    A = frame_usable_pt2(frame)
    graphics = [g for g in (page["drawings"] + page["images"] + page["figs"])
                if _graphic_ok(g, A, frame)]
    caps = [(ln, caption_kind(ln["text"])) for ln in lines if caption_kind(ln["text"])]
    out = []
    gap_max = max(3.0 * frame["body_pt"], 30.0)
    for ln, kind in caps:
        if frame["columns"] == 2 and frame.get("col2_left") \
                and ln["x0"] >= frame["col2_left"] - 4:
            x_lo, x_hi = frame["col2_left"], frame["right"]
        elif frame["columns"] == 2:
            x_lo, x_hi = frame["left"], frame["col1_right"]
        else:
            x_lo, x_hi = frame["left"], frame["right"]
        box = _clip_box(ln, x_lo, x_hi, frame)
        changed = True
        while changed:
            changed = False
            for g in graphics:
                if min(g["x1"], x_hi) - max(g["x0"], x_lo) < 2:
                    continue
                if g["y1"] < box["y0"] - gap_max or g["y0"] > box["y1"] + gap_max:
                    continue
                nb = {"x0": min(box["x0"], max(g["x0"], x_lo)),
                      "y0": min(box["y0"], max(g["y0"], frame["bottom"])),
                      "x1": max(box["x1"], min(g["x1"], x_hi)),
                      "y1": max(box["y1"], min(g["y1"], frame["top"]))}
                if nb != box:
                    box = nb
                    changed = True
        out.append({"kind": kind, "caption": ln["text"][:120], "bbox": box,
                    "area_pt2": round(box_area(box), 1)})
    return out


# ---------------------------------------------------------------- 单页指标

def page_metrics_from_items(page: dict, frame: dict, *,
                            pixel: dict | None = None,
                            page_ctx: dict | None = None) -> dict:
    """一页的 v1 指标（除 role 外）。page_ctx: {"is_last": bool, ...}"""
    A = frame_usable_pt2(frame)
    excl = frame_excl_x(frame)
    lines = [ln for ln in page["lines"] if not ln["fig"]]
    caps = [ln for ln in lines if caption_kind(ln["text"])]
    # 页眉/页脚（页码、running head）按**版心上下沿**识别（阶段 3 补 L5）：
    # 完全落在版心之上/之下的行。它们不属于 A_usable，因此不算正文覆盖、
    # 不参与密度/平衡统计，也不作为留白的"结构解释"。
    _furn = {id(ln) for ln in lines
             if ln["y0"] >= frame["top"] - 0.5 or ln["y1"] <= frame["bottom"] + 0.5}
    hdr = [ln for ln in lines if id(ln) in _furn and ln["y0"] >= frame["top"] - 0.5]
    ftr = [ln for ln in lines if id(ln) in _furn and ln["y1"] <= frame["bottom"] + 0.5]
    content_lines = [ln for ln in lines if id(ln) not in _furn]
    # 页内正文尺寸（字符数加权众数）：参考文献/附录页会用更小字号，
    # 若用**文档级**字号过滤，这些页就只剩标题行 → cpl/行距/方差全成假值。
    pw_mode: dict = {}
    for ln in lines:
        if ln["size"] >= 6:
            k = snap_size(ln["size"])
            pw_mode[k] = pw_mode.get(k, 0) + ln["nchars"]
    page_pt = max(pw_mode.items(), key=lambda kv: kv[1])[0] if pw_mode else frame["body_pt"]
    main = [ln for ln in lines if ln["size"] >= page_pt - 0.6] or lines

    # 文本/浮动覆盖（网格掩码，已挖掉栏间距；同一格不重复计入）
    tm = GridMask(frame["left"], frame["bottom"], frame["right"], frame["top"], excl)
    for ln in content_lines:
        tm.add(ln)
    floats = anchor_floats(page, frame)
    fmask = GridMask(frame["left"], frame["bottom"], frame["right"], frame["top"], excl)
    tmask = GridMask(frame["left"], frame["bottom"], frame["right"], frame["top"], excl)
    for f in floats:
        (tmask if f["kind"] == "table" else fmask).add(f["bbox"])
    # 阶段 3 修正：**未被题注锚到的图形**（无题注的图、矢量插图）也是版面内容。
    # 原版只看"题注锚出的浮动区"→ 无题注/题注写法不识别时，整幅图被当成空白，
    # 既低估覆盖率，又会在留白分类里炸出一个"异常空洞"（实测 original.pdf 第 2 页）。
    # 落在表格浮动区内的图形元素跳过（避免图/表重复计入）。
    table_boxes = [f["bbox"] for f in floats if f["kind"] == "table"]
    loose_graphics = []
    for g in (page["drawings"] + page["images"] + page["figs"]):
        if not _graphic_ok(g, A, frame):
            continue
        cx, cy = (g["x0"] + g["x1"]) / 2, (g["y0"] + g["y1"]) / 2
        if any(b["x0"] <= cx <= b["x1"] and b["y0"] <= cy <= b["y1"]
               for b in table_boxes):
            continue
        loose_graphics.append({"kind": "figure",
                               "bbox": {"x0": g["x0"], "y0": g["y0"],
                                        "x1": g["x1"], "y1": g["y1"]},
                               "caption": None})
        fmask.add(g)
    text_area = tm.area()
    fig_area = fmask.area()
    tab_area = tmask.area()

    # 三段密度 / 视觉重心（按内容面积份额，和恒为 1）
    bands = ((frame["bottom"], frame["bottom"] + frame["height_pt"] / 3),
             (frame["bottom"] + frame["height_pt"] / 3,
              frame["bottom"] + 2 * frame["height_pt"] / 3),
             (frame["bottom"] + 2 * frame["height_pt"] / 3, frame["top"]))
    dm = GridMask(frame["left"], frame["bottom"], frame["right"], frame["top"], excl)
    for ln in content_lines:
        dm.add(ln)
    for f in floats:
        dm.add(f["bbox"])
    tot_cells = len(dm.cells) or 1
    band_counts = [0, 0, 0]
    cy_sum = 0.0
    for (i, j) in dm.cells:
        ycen = frame["bottom"] + (j + 0.5) * GridMask.CELL
        cy_sum += ycen
        rel = (ycen - frame["bottom"]) / frame["height_pt"]
        band_counts[0 if rel < 1 / 3 else (1 if rel < 2 / 3 else 2)] += 1
    d_top = round(band_counts[2] / tot_cells, 4)   # 注意：y 向上，band0 是底部
    d_mid = round(band_counts[1] / tot_cells, 4)
    d_bot = round(band_counts[0] / tot_cells, 4)
    centroid = round((cy_sum / tot_cells - frame["bottom"]) / frame["height_pt"], 4)

    # 左右密度
    left_cells = sum(1 for (i, j) in dm.cells
                     if frame["left"] + (i + 0.5) * GridMask.CELL
                     < (frame["left"] + frame["right"]) / 2)
    left_right = round(left_cells / tot_cells, 4)

    # 分栏
    per_col = []
    if frame["columns"] == 2:
        for ci, (a, b) in enumerate(((frame["left"], frame["col1_right"]),
                                     (frame["col2_left"], frame["right"])), 1):
            gm = GridMask(a, frame["bottom"], b, frame["top"])
            for ln in lines:
                if ln["x0"] >= a - 2 and ln["x1"] <= b + 2:
                    gm.add(ln)
            for f in floats:
                gm.add(f["bbox"])
            n = len(gm.cells) or 1
            cnt = [0, 0, 0]
            for (i, j) in gm.cells:
                ycen = frame["bottom"] + (j + 0.5) * GridMask.CELL
                rel = (ycen - frame["bottom"]) / frame["height_pt"]
                cnt[0 if rel < 1 / 3 else (1 if rel < 2 / 3 else 2)] += 1
            per_col.append({"col": ci, "top": round(cnt[2] / n, 4),
                            "mid": round(cnt[1] / n, 4),
                            "bottom": round(cnt[0] / n, 4),
                            "cells": len(gm.cells)})

    # 对齐：按栏 + **按行类型**分别算（阶段 2 校准）
    #   * 满行（两栏对齐的正文）→ 左沿/右沿的一致性才是有意义的对齐质量；
    #   * 短行（题注/标题/公式/段末）→ 只看"是否居中"，用中心偏移量度。
    #   混在一起算时，悬挂缩进的参考文献与居中题注会把方差推到 130pt（无意义）。
    al_all = [ln for ln in main if ln["nchars"] >= 3]
    col_ranges = ([(frame["left"], frame["col1_right"]),
                   (frame["col2_left"], frame["right"])]
                  if frame["columns"] == 2 and frame.get("col2_left")
                  else [(frame["left"], frame["right"])])
    lv, rv, cvv, nel, n_full, n_short = [], [], [], 0, 0, 0
    for (a, b) in col_ranges:
        sel = [ln for ln in al_all if ln["x0"] >= a - 2 and ln["x1"] <= b + 2]
        full = [ln for ln in sel if ln["x1"] >= b - 2 and ln["nchars"] >= 8]
        short = [ln for ln in sel if ln["x1"] < b - 8 and ln["nchars"] >= 3]
        n_full += len(full)
        n_short += len(short)
        nel += len(sel)
        if len(full) >= 2:
            lv.append(std([ln["x0"] - a for ln in full]))
            rv.append(std([b - ln["x1"] for ln in full]))
        if len(short) >= 2:
            cvv.append(std([(ln["x0"] + ln["x1"]) / 2 - (a + b) / 2 for ln in short]))
    left_var = median(lv) if lv else None
    right_var = median(rv) if rv else None
    center_var = median(cvv) if cvv else None

    # 可读性（行距用**同行边**的相邻差，即基线间距）
    cpl = [ln["nchars"] for ln in main]
    leads = []
    by_col = {}
    for ln in main:
        key = 0 if (frame["columns"] == 1 or ln["x0"] < (frame["col2_left"] or 1e9)) else 1
        by_col.setdefault(key, []).append(ln)
    for ls in by_col.values():
        ls = sorted(ls, key=lambda x: -x["y1"])
        for a1, a2 in zip(ls, ls[1:]):
            d = a1["y0"] - a2["y0"]
            if 0 < d < 3.0 * frame["body_pt"]:
                leads.append(d)
    leading = median(leads)
    leading_ratio = (round(leading / frame["body_pt"], 3)
                     if leading and frame["body_pt"] else None)
    para_lines = []
    for ls in by_col.values():
        ls = sorted(ls, key=lambda x: -x["y1"])
        run = 1
        for a1, a2 in zip(ls, ls[1:]):
            d = a1["y0"] - a2["y0"]
            if leading and d <= 1.45 * leading:
                run += 1
            else:
                para_lines.append(run)
                run = 1
        para_lines.append(run)

    # 一致性
    widths = [f["bbox"]["x1"] - f["bbox"]["x0"] for f in floats]
    cap_sizes = [snap_size(ln["size"]) for ln in caps]

    # 图件质量
    dpis, stretched, n_img = [], 0, 0
    for im in page["images"]:
        n_img += 1
        if im.get("src_w") and im["w"] > 1:
            dpi = im["src_w"] / (im["w"] / 72.0)
            dpis.append(round(dpi, 1))
        if im.get("src_w") and im.get("src_h") and im["w"] > 1 and im["h"] > 1:
            src_ar = im["src_w"] / im["src_h"]
            box_ar = im["w"] / im["h"]
            if src_ar and abs(box_ar - src_ar) / src_ar > 0.15:
                stretched += 1

    # 数学密度
    nchars = sum(ln["nchars"] for ln in lines) or 1
    math_ratio = sum(ln["math"] * ln["nchars"] for ln in lines) / nchars

    # 章节标题信号
    head = None
    for ln in sorted(main, key=lambda x: -x["y1"]):
        from . import roles as R
        if R.is_section_head(ln["text"], size=ln["size"], body_pt=frame["body_pt"],
                             bold=ln["bold"], col_width_pt=frame["col_width"]):
            head = ln
            break
    head_top = None
    if head:
        head_top = (head["y0"] - frame["bottom"]) / frame["height_pt"]
    refs_head = any(_re_mod().match(r"(?i)^\s*(references|bibliography)\s*$",
                                    " ".join(ln["text"].split()))
                    for ln in main)
    app_head = any(_re_mod().match(r"(?i)^\s*(appendix|appendices|supplementary)\b",
                                   " ".join(ln["text"].split()))
                   for ln in main)

    # 留白上界的**正确**算法：三个掩码的**并集**（各自去重会重复计重叠区，
    # 直接把三个 ratio 相加会低估空白 —— 2026-09-29 实测踩到）。
    umask = GridMask(frame["left"], frame["bottom"], frame["right"], frame["top"], excl)
    for ln in content_lines:
        umask.add(ln)
    for f in floats:
        umask.add(f["bbox"])
    for g in loose_graphics:
        umask.add(g["bbox"])
    ws_total = max(0.0, 1.0 - umask.area() / A)

    pg = PM.blank_page(page.get("no") or 1)
    pg["units"] = {
        "page_w_mm": round(frame["pw"] * PT2MM, 2),
        "page_h_mm": round(frame["ph"] * PT2MM, 2),
        "usable_w_mm": round(frame["col_width"] * PT2MM, 2),
        "usable_h_mm": round(frame["height_pt"] * PT2MM, 2),
        "columns": frame["columns"],
    }
    pg["density"] = {
        "ink_ratio_page": (pixel or {}).get("ink_ratio"),
        "ink_ratio_text": None,                      # 需像素遮罩，阶段 2
        "coverage_text": round(text_area / A, 4),
        "coverage_figure": round(fig_area / A, 4),
        "coverage_table": round(tab_area / A, 4),
        "coverage_other": None,
        "status": "partial",                         # ink_ratio_text 仍缺
    }
    pg["ratio"] = {
        "fig_text": round(fig_area / text_area, 4) if text_area else None,
        "figtab_text": round((fig_area + tab_area) / text_area, 4) if text_area else None,
        "status": "extracted",
    }
    pg["balance"] = {
        "d_top": d_top, "d_mid": d_mid, "d_bot": d_bot,
        "left_right": left_right,
        "visual_centroid_y": centroid,
        "per_column": per_col,
        "status": "extracted",
    }
    # 留白结构化（阶段 3）：四类不惩罚，只有 anomalous 进惩罚项
    from . import whitespace as WS
    ws_lines = []
    for ln in content_lines:
        from . import roles as R
        if caption_kind(ln["text"]):
            kind = "caption"
        elif R.is_section_head(ln["text"], size=ln["size"],
                               body_pt=frame["body_pt"], bold=ln["bold"],
                               col_width_pt=frame["col_width"]):
            kind = "head"
        else:
            kind = "text"
        ws_lines.append({"x0": ln["x0"], "y0": ln["y0"], "x1": ln["x1"],
                         "y1": ln["y1"], "kind": kind})
    pg["whitespace"] = WS.analyze(frame, excl, ws_lines,
                                   list(floats) + loose_graphics, leading,
                                   page_ctx=page_ctx)
    pg["alignment"] = {
        "left_var": left_var, "right_var": right_var, "center_var": center_var,
        "n_elements": nel, "n_full_lines": n_full, "n_short_lines": n_short,
        "status": "extracted",
    }
    pg["consistency"] = {
        "figure_width_cv": cv(widths),
        "caption_style_cv": cv(cap_sizes),
        "status": "extracted",
    }
    pg["readability"] = {
        "chars_per_line_mean": round(sum(cpl) / len(cpl), 1) if cpl else None,
        "leading_ratio": leading_ratio,
        "font_pt": frame["body_pt"],
        "font_pt_page": page_pt,
        "para_lines_mean": round(sum(para_lines) / len(para_lines), 2) if para_lines else None,
        "status": "extracted",
    }
    pg["figure_quality"] = {
        "min_effective_dpi": min(dpis) if dpis else None,
        "aspect_outliers": stretched if n_img else None,
        "status": "extracted" if n_img else "placeholder",
    }
    pg["_signals"] = {
        "n_lines": len(main), "n_chars": nchars,
        # 与 whitespace.total_ratio 互校：用「内容并集」的补集作为留白率的**上界**
        # （whitespace 会丢掉 <0.4% 版心的碎片区域，因此恒有 ws ≤ 本值）
        "ws_blank_complement": round(ws_total, 4),
        "header_lines": len(hdr), "footer_lines": len(ftr),
        "header_text": hdr[0]["text"][:80] if hdr else None,
        "footer_text": ftr[0]["text"][:80] if ftr else None,
        "n_ws_regions": pg["whitespace"].get("n_regions"),
        "n_ws_anomalous": pg["whitespace"].get("n_anomalous"),
        "body_pt": frame["body_pt"],
        "text_coverage": pg["density"]["coverage_text"],
        "fig_coverage": pg["density"]["coverage_figure"],
        "tab_coverage": pg["density"]["coverage_table"],
        "math_ratio": round(math_ratio, 4),
        "page_pt": page_pt,
        "section_head": bool(head is not None and head_top is not None
                             and head_top >= 1.0 - ROLES_THRESH["head_top_frac"]),
        "section_head_text": head["text"] if head else None,
        "refs_heading": bool(refs_head), "appendix_heading": bool(app_head),
        "n_floats": len(floats), "floats": floats,
        "n_images": n_img,
        "n_loose_graphics": len(loose_graphics),
    }
    return pg


# ---------------------------------------------------------------- 整篇

def extract_pdf(pdf_path: str, *, venue: str | None = None, year: int | None = None,
                pixels: bool = False, dpi: int = 50, max_pages: int | None = None,
                log_text: str | None = None) -> dict:
    """PDF -> page_metrics.v1 文档。失败抛异常（调用方决定降级）。"""
    t0 = time.time()
    pages, sizes = collect_page_items(pdf_path, max_pages)
    if not pages:
        raise RuntimeError("PDF 无页面")
    frame = measure_frame(pages, sizes)

    pix = {}
    if pixels:
        try:
            from . import visual
            import tempfile
            with tempfile.TemporaryDirectory() as td:
                vis = visual.analyze_pdf(pdf_path, td, dpi=dpi)
            for m in (vis.get("pages") or []):
                if isinstance(m, dict) and "page" in m and "error" not in m:
                    pix[int(m["page"])] = m
        except Exception:
            pix = {}

    doc = PM.blank_document()
    doc["doc"].update({
        "pdf": os.path.basename(pdf_path), "tex": None,
        "venue": venue, "year": year,
        "layout": "twocolumn" if frame["columns"] == 2 else "onecolumn",
        "pages": len(pages),
        "render": {"tool": "pdfminer.six", "dpi_pixel": dpi if pixels else None},
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    })
    sigs = []
    for i, p in enumerate(pages, start=1):
        p["no"] = i
        pg = page_metrics_from_items(p, frame, pixel=pix.get(i),
                                     page_ctx={"page_no": i, "is_first": i == 1,
                                               "is_last": i == len(pages)})
        sig = pg.pop("_signals")
        sig["page"] = i
        sig["is_first"] = (i == 1)
        sig["is_last"] = (i == len(pages))
        sigs.append(sig)
        doc["pages"].append(pg)

    # 角色标注
    from . import roles as R
    rs = R.classify_pages(sigs)
    for pg, r in zip(doc["pages"], rs):
        pg["role"] = r["role"]
        pg["role_confidence"] = r["role_confidence"]
        pg["role_source"] = "rule"
        pg["role_reason"] = r["role_reason"]
        pg["role_flags"] = r["role_flags"]

    # 微观排版：只有拿到编译日志才填，否则 unavailable
    mt = {"overfull": None, "underfull": None, "vbox_overfull": None,
          "vbox_underfull": None, "status": "unavailable"}
    if log_text:
        try:
            from . import perceive as P
            iss = P.parse_log(log_text)
            mt = {"overfull": len(iss["overfull"]), "underfull": len(iss["underfull"]),
                  "vbox_overfull": sum(1 for v in iss["vbox"] if v["kind"] == "Overfull"),
                  "vbox_underfull": sum(1 for v in iss["vbox"] if v["kind"] == "Underfull"),
                  "status": "extracted"}
        except Exception:
            pass
    for pg in doc["pages"]:
        pg["microtype"] = dict(mt)

    # 论文级：document 级补充量
    all_floats = [f for s in sigs for f in s["floats"]]
    doc["paper"]["frame"] = frame
    doc["paper"]["n_floats"] = len(all_floats)
    doc["paper"]["n_images"] = sum(s["n_images"] for s in sigs)
    doc["paper"]["consistency"] = {
        "figure_width_cv": cv([f["bbox"]["x1"] - f["bbox"]["x0"] for f in all_floats]),
        "floats_per_page": round(len(all_floats) / len(pages), 2),
    }
    doc["meta"]["notes"] = [
        "阶段 1+3 提取：vector/text 层（pdfminer）为主；像素层可选",
        "表格/图覆盖用题注锚定的浮动区近似，不解析表格结构",
        "留白已结构化（阶段 3）：五类 + region 列表；只有 anomalous 进惩罚项",
        "页眉/页脚行按版心上下沿识别（不在版心内的行）；微观排版需编译日志",
        f"版心由正文页测得：columns={frame['columns']}，"
        f"usable={frame['usable_pt2']:.0f}pt²，body={frame['body_pt']}pt",
    ]
    doc["meta"]["extract_seconds"] = round(time.time() - t0, 2)
    return PM.finalize(doc)


def page_signals(pdf_path: str, max_pages: int | None = None) -> list[dict]:
    """只跑信号（不含指标），用于快速验证角色标注器。"""
    pages, sizes = collect_page_items(pdf_path, max_pages)
    frame = measure_frame(pages, sizes)
    out = []
    for i, p in enumerate(pages, start=1):
        p["no"] = i
        pg = page_metrics_from_items(p, frame, pixel=None)
        sig = pg["_signals"]
        sig.update(page=i, is_first=(i == 1), is_last=(i == len(pages)))
        out.append(sig)
    return out
