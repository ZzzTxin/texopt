#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""measure_pdf.py —— 从真实论文 PDF 量取排版特征（可复现、可追溯）。

只输出**几何量**（PDF 里可测的事实），不做主观判断；方法与不确定度写在
method/warnings 里，供 texopt 的 A（排版质量/审美代理）量化层与 requirements 层引用。

实现：pdfminer.six 的 layout 分析给出每个文本行/字符的精确包围盒与字号
（字形级坐标），因此页边距、栏宽、栏间距是**量出来的**而不是估出来的。
中文字体/图片内文字会被排除（只统计文本框内的行，跳过 LTFigure）。

用法:
    python3 measure_pdf.py <pdf文件或URL> [--pages N]
输出: JSON（stdout）

依赖: pdfminer.six（vendored，见 tools/bootstrap_py.sh）
"""
from __future__ import annotations

import collections
import json
import os
import re
import statistics as st
import sys
import urllib.request

TOOLS = os.environ.get("TEXOPT_TOOLS", os.path.expanduser("~/.local/lib/texopt-tools"))
sys.path.insert(0, TOOLS)
from pdfminer.high_level import extract_pages          # noqa: E402
from pdfminer.layout import LAParams, LTTextContainer, LTTextLine, LTChar, LTFigure  # noqa: E402

PT2MM = 25.4 / 72.0
CAP_RE = re.compile(r"^\s*(Figure|Fig\.|Table)\s*\d+\s*[:.]", re.I)
FOOT_RE = re.compile(r"^\s*(?:\d{1,2}|[†‡§¶*]|[a-z]\))\s+[A-Za-z(]")
SNAP = (7.0, 8.0, 9.0, 10.0, 11.0, 12.0)


def snap_size(pt: float) -> float:
    for c in SNAP:
        if abs(pt - c) <= 0.6:
            return c
    return round(pt, 1)


def _group_chars(chars: list[dict]) -> list[dict]:
    """字符级回退分组（用于 pdfminer 不对 Form XObject 内文本做行分组的情况）。

    两步：① 按基线聚类成“行带”；② 行带内按水平间隔切段（双栏版面的左右栏共享同一
    基线，必须靠间隔切开，否则会把两栏文字拼成一行）。
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
        ycen = sum((c["y0"] + c["y1"]) / 2 for c in cur) / len(cur)   # 行带基线跟随更新
    if cur:
        bands.append(cur)

    out: list[dict] = []
    for band in bands:
        seg: list[dict] = []
        for ch in sorted(band, key=lambda c: c["x0"]):
            if seg and ch["x0"] - seg[-1]["x1"] > 14.0:   # 栏间距/大空白 → 切段
                out.append(_row_to_line(seg))
                seg = []
            seg.append(ch)
        if seg:
            out.append(_row_to_line(seg))
    return out


def _row_to_line(row: list[dict]) -> dict:
    row = sorted(row, key=lambda c: c["x0"])
    txt, prev = [], None
    for ch in row:
        if prev is not None and ch["x0"] - prev > 1.2:   # 词间空格还原
            txt.append(" ")
        txt.append(ch["text"])
        prev = ch["x1"]
    return {
        "x0": round(min(c["x0"] for c in row), 2),
        "x1": round(max(c["x1"] for c in row), 2),
        "y0": round(min(c["y0"] for c in row), 2),
        "y1": round(max(c["y1"] for c in row), 2),
        "size": round(st.median([c["size"] for c in row]), 2),
        "text": "".join(txt).strip(),
        "nchars": len(row),
        "fig": False,
    }


def find_gutter(lines: list[dict], p_left: float, p_right: float) -> float | None:
    """在版心中部找“栏间空白沟”（几乎无行覆盖的 x 带），返回沟的右沿；找不到返回 None。

    双栏版面的 gutter 在列宽/行首抖动下仍然存在，比“行首峰”稳健得多。
    """
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
    limit = max(1, int(0.05 * len(lines)))      # 允许少量通栏行（满宽图/表）覆盖
    best = (0, 0)
    start = None
    for i, v in enumerate(cov):
        if v <= limit:
            if start is None:
                start = i
        else:
            if start is not None and i - start > best[1] - best[0]:
                best = (start, i)
            start = None
    if start is not None and n - start > best[1] - best[0]:
        best = (start, n)
    gs, ge = best[0] + lo, best[1] + lo
    span = p_right - p_left
    if ge - gs < 6:
        return None
    if gs < p_left + 0.25 * span or ge > p_right - 0.15 * span:
        return None
    return float(ge)


def gutter_vote(body: list[dict], p_left: float, p_right: float) -> float | None:
    """逐页找 gutter 并投票（页与页之间栏宽/栏位可能变化，全局剖面会被带偏）。

    取最多页数支持的 gutter 位置（±6pt 聚类），支持页数需 ≥ 30% 且 ≥3 页。
    """
    hits = []
    for p in body:
        ls = [ln for ln in p["lines"] if not ln["fig"]]
        if len(ls) < 15:
            continue
        g = find_gutter(ls, p_left, max(ln["x1"] for ln in ls))
        if g is not None:
            hits.append(g)
    if len(hits) < 3:
        return None
    hits.sort()
    clusters: list[list[float]] = []
    for g in hits:
        if clusters and g - clusters[-1][-1] <= 6:
            clusters[-1].append(g)
        else:
            clusters.append([g])
    best = max(clusters, key=len)
    if len(best) < max(3, 0.3 * len(hits)):
        return None
    return round(st.median(best), 1)


def collect_lines(path: str, max_pages: int | None = None):
    """返回 (pages, page_sizes)。pages[i] = {'lines': [...], 'figs': [...]}
    line = {'x0','x1','y0','y1','size','text','nchars','fig'(是否在图片/Form 内)}
    fig  = {'x0','y0','x1','y1','w','h'}（顶层 LTFigure 包围盒）"""
    pages, sizes = [], []
    params = LAParams(detect_vertical=False, line_overlap=0.5, char_margin=2.0,
                      line_margin=0.5, word_margin=0.1, boxes_flow=None)
    for pi, layout in enumerate(extract_pages(path, laparams=params)):
        if max_pages and pi >= max_pages:
            break
        sizes.append((float(layout.width), float(layout.height)))
        lines, figs, raw_chars = [], [], []
        page_area = max(layout.width * layout.height, 1.0)

        def walk(el, in_fig=False, big_fig=False):
            for child in el:
                if isinstance(child, LTTextContainer):
                    for ln in child:
                        if not isinstance(ln, LTTextLine):
                            continue
                        chars = [(c.x0, c.x1, c.size) for c in ln if isinstance(c, LTChar)]
                        txt = ln.get_text().strip()
                        if chars and txt:
                            lines.append({
                                "x0": round(min(c[0] for c in chars), 2),
                                "x1": round(max(c[1] for c in chars), 2),
                                "y0": round(ln.y0, 2), "y1": round(ln.y1, 2),
                                "size": round(st.median([c[2] for c in chars]), 2),
                                "text": txt,
                                "nchars": len(chars),
                                "fig": in_fig,
                            })
                elif isinstance(child, LTChar):
                    t = child.get_text()
                    if t.strip():
                        raw_chars.append({"x0": child.x0, "x1": child.x1, "y0": child.y0,
                                          "y1": child.y1, "size": child.size, "text": t,
                                          "big": big_fig})
                else:
                    if isinstance(child, LTFigure):
                        b = child.bbox
                        big = big_fig or ((b[2] - b[0]) * (b[3] - b[1]) >= 0.8 * page_area)
                        if not in_fig:            # 只记顶层图，避免嵌套重复计数
                            figs.append({"x0": round(b[0], 2), "y0": round(b[1], 2),
                                         "x1": round(b[2], 2), "y1": round(b[3], 2),
                                         "w": round(b[2] - b[0], 2), "h": round(b[3] - b[1], 2)})
                        if hasattr(child, "__iter__"):
                            walk(child, True, big)  # 图片内文字标记为 fig，不参与版心几何统计
                    elif hasattr(child, "__iter__"):
                        walk(child, in_fig, big_fig)

        walk(layout)
        # 回退：pdfminer 不对 Form XObject 内部做行分组（整页被包进一个 Form 的 PDF
        # 会几乎量不到行）。此时按字符重建行；只采用“覆盖整页的大 Form”里的字符，
        # 避免把真正的插图内文字当成正文。
        nchars_line = sum(ln["nchars"] for ln in lines)
        if len(raw_chars) > 200 and nchars_line < 0.5 * len(raw_chars):
            pick = [c for c in raw_chars if c["big"]] or raw_chars
            rebuilt = _group_chars(pick)
            if len(rebuilt) > len(lines):
                lines = rebuilt
                figs = [f for f in figs if f["w"] * f["h"] < 0.8 * page_area] or figs
        pages.append({"lines": lines, "figs": figs})
    return pages, sizes


def pct(vals, q):
    if not vals:
        return None
    v = sorted(vals)
    return v[min(len(v) - 1, int(len(v) * q))]


def mode_pt(vals, tol=1.0):
    """行尾/行首的众数位置（pt）：两端对齐版面里这是最稳健的版心边。“"""
    if not vals:
        return None
    bins: dict[int, int] = {}
    for v in vals:
        bins[round(v / tol)] = bins.get(round(v / tol), 0) + 1
    b = max(bins, key=lambda k: bins[k])
    near = [v for v in vals if abs(v - b * tol) <= tol]
    return round(sum(near) / len(near), 1)


def uniq(pat, txt):
    return len(set(re.findall(pat, txt, re.I)))


def merge_boxes(boxes: list[dict], tol: float = 8.0) -> list[dict]:
    """合并相互重叠/相邻的图形包围盒（并查集 + 空间哈希，O(n·k)）。

    矢量图常被拆成许多小 Form XObject，合并后才能得到“一个图”的真实尺寸。
    早期版本用“反复重启扫描”的写法，在图形碎片上千的 PDF（CVPR/ICCV 的矢量插图）
    上会退化成 O(n³)，导致单篇量化卡住数分钟；这里换成并查集求连通分量。
    """
    n = len(boxes)
    if n <= 1:
        return [dict(b) for b in boxes]
    cell = max(tol, 8.0)
    parent = list(range(n))

    def find(a: int) -> int:
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    grid: dict[tuple[int, int], list[int]] = {}
    for i, b in enumerate(boxes):
        for cx in range(int((b["x0"] - tol) // cell), int((b["x1"] + tol) // cell) + 1):
            for cy in range(int((b["y0"] - tol) // cell), int((b["y1"] + tol) // cell) + 1):
                grid.setdefault((cx, cy), []).append(i)

    def near(a: dict, b: dict) -> bool:
        return not (a["x0"] > b["x1"] + tol or a["x1"] < b["x0"] - tol
                    or a["y0"] > b["y1"] + tol or a["y1"] < b["y0"] - tol)

    for idxs in grid.values():
        for ii in range(len(idxs)):
            for jj in range(ii + 1, len(idxs)):
                a, b = idxs[ii], idxs[jj]
                if find(a) == find(b):
                    continue
                if near(boxes[a], boxes[b]):
                    parent[find(b)] = find(a)

    groups: dict[int, dict] = {}
    for i, b in enumerate(boxes):
        g = groups.setdefault(find(i), {"x0": b["x0"], "y0": b["y0"],
                                        "x1": b["x1"], "y1": b["y1"]})
        g["x0"] = min(g["x0"], b["x0"])
        g["y0"] = min(g["y0"], b["y0"])
        g["x1"] = max(g["x1"], b["x1"])
        g["y1"] = max(g["y1"], b["y1"])
    out = []
    for g in groups.values():
        g["w"] = round(g["x1"] - g["x0"], 2)
        g["h"] = round(g["y1"] - g["y0"], 2)
        out.append(g)
    return out


def measure(path_or_url: str, max_pages: int | None = None) -> dict:
    warnings: list[str] = []
    path = download(path_or_url) if path_or_url.startswith("http") else path_or_url
    pages, sizes = collect_lines(path, max_pages)
    n_pages_total = None
    try:
        from pypdf import PdfReader
        n_pages_total = len(PdfReader(path).pages)
    except Exception:
        pass

    pw, ph = st.median([s[0] for s in sizes]), st.median([s[1] for s in sizes])
    paper = ("letter" if abs(pw - 612) < 6 and abs(ph - 792) < 6 else
             "a4" if abs(pw - 595) < 6 and abs(ph - 842) < 6 else f"custom {pw:.0f}x{ph:.0f}pt")

    body = [p for p in pages[1:]] or pages      # 跳过首页（标题页噪声大）
    all_lines = [ln for p in body for ln in p["lines"]]
    lines = [ln for ln in all_lines if not ln["fig"]]   # 版心几何只用正文行（排除图片内文字）
    if not lines:
        lines = all_lines
    if not lines:
        raise RuntimeError(f"未抽取到文本行: {path}")

    # ---- 正文字号：字符数加权众数
    w: dict[float, int] = {}
    for ln in lines:
        w[snap_size(ln["size"])] = w.get(snap_size(ln["size"]), 0) + ln["nchars"]
    tot = sum(w.values()) or 1
    hist = {k: v / tot for k, v in sorted(w.items())}
    body_pt = max(hist.items(), key=lambda kv: kv[1])[0]
    if len([v for v in hist.values() if v > 0.05]) > 3:
        warnings.append("字号档位分散（正文/图注/脚注混杂），body_font_pt 取占比最大档")

    # ---- 左边界与栏结构：行首 x0 直方图取峰
    xs = sorted(ln["x0"] for ln in lines)
    # 不用“相邻≤6pt 链式聚类”：正文里缩进/公式/表格会造出连续的行首值，链式聚类
    # 会把左右两栏并成一个簇，导致双栏被漏判。改用 1pt 直方图 + 5% 阈值取峰。
    hist0: dict[int, int] = {}
    for x in xs:
        hist0[round(x)] = hist0.get(round(x), 0) + 1
    thr = max(3, 0.05 * len(lines))
    raw_peaks = sorted(p for p, c in hist0.items() if c >= thr)
    peaks: list[tuple[float, int]] = []          # (行首位置, 支持行数)
    for p in raw_peaks:
        if peaks and p - peaks[-1][0] <= 4:
            if hist0[p] > peaks[-1][1]:
                peaks[-1] = (float(p), hist0[p])
        else:
            peaks.append((float(p), hist0[p]))
    strong = peaks
    p_left = min(x for x, c in strong) if strong else xs[0]

    # 双栏判定：候选右栏起点取“靠右且行数最多”的行首峰，再用两条硬证据验证：
    #   (a) 左栏行确实止于候选点之前（被栏宽约束）
    #   (b) 候选点之后有足够多的行（真的是另一栏，而不是居中公式/表格）
    col2_left = None
    far = [(x, c) for x, c in strong if x - p_left > 0.22 * pw]
    if far:
        # 候选点取“行数最多”的靠右行首峰；再用两条相对化证据验证：
        #   左栏行占比 = 在候选点之前就结束的行（真正被栏宽约束）
        #   右栏行占比 = 从候选点附近开始的行
        # 注意：左栏行占比不能用“行首接近 p_left”定义——段落缩进/公式缩进会把大量
        # 左栏行首推离 p_left，导致真双栏被误判为单栏。
        cand, cand_cnt = max(far, key=lambda xc: xc[1])
        share_left = len([ln for ln in lines if ln["x1"] <= cand - 2]) / len(lines)
        share_right = len([ln for ln in lines if ln["x0"] >= cand - 4]) / len(lines)
        if share_left >= 0.25 and share_right >= 0.25:
            col2_left = cand
        else:
            warnings.append(
                f"发现靠右行首峰 {cand}pt 但未通过双栏验证"
                f"（左栏行占比 {share_left:.2f}，右栏行占比 {share_right:.2f}），按单栏处理")
    if col2_left is None and len(lines) >= 25:
        # 备用判据（更稳）：双栏版面在中部有一条“无文字覆盖的栏间空白沟”，逐页投票。
        g = gutter_vote(body, p_left, max(ln["x1"] for ln in lines))
        if g is not None:
            col2_left = g
            warnings.append(f"按栏间空白沟判定为双栏（沟右沿 {g}pt）")
    two_col = col2_left is not None

    # ---- 版心边界：用“行首 x0 最小值 + 行尾 x1 众数”定位（LaTeX 两端对齐，
    #      行尾众数即栏右沿；通栏行因 x1 > 栏宽而被排除）
    left = min((ln["x0"] for ln in lines if ln["x0"] <= p_left + 20), default=p_left)
    if two_col:
        col1 = [ln for ln in lines if ln["x0"] < col2_left - 2 and ln["x1"] < col2_left]
        col2 = [ln for ln in lines if ln["x0"] >= col2_left - 2]
        col1_right = mode_pt([ln["x1"] for ln in col1]) or col2_left
        col2_right = mode_pt([ln["x1"] for ln in col2]) or max(ln["x1"] for ln in lines)
        right = max(col1_right, col2_right)
        col_gap = round(col2_left - col1_right, 1)
        col_width = round(((col1_right - left) + (col2_right - col2_left)) / 2, 1)
        if col_gap < 4 or col_gap > 60:
            # 栏间距不合理（真双栏模板的 gutter 在 4~30pt）：判为单栏误报，回退
            warnings.append(f"候选双栏的栏间距不合理（{col_gap}pt），按单栏处理")
            two_col = False
            right = mode_pt([ln["x1"] for ln in lines]) or max(ln["x1"] for ln in lines)
            col_gap, col_width = None, round(right - left, 1)
    else:
        right = mode_pt([ln["x1"] for ln in lines]) or max(ln["x1"] for ln in lines)
        col_gap, col_width = None, round(right - left, 1)
    text_width = round(right - left, 1)

    tops = [ph - max(ln["y1"] for ln in p["lines"]) for p in body if p["lines"]]
    bots = [min(ln["y0"] for ln in p["lines"]) for p in body if p["lines"]]
    marg = {"left": round(left, 1), "right": round(pw - right, 1),
            "top": round(st.median(tops), 1) if tops else None,
            "bottom": round(st.median(bots), 1) if bots else None}
    if not two_col and abs(marg["left"] - marg["right"]) > 12:
        warnings.append("单栏左右边距差异较大（可能非居中版心或含通栏图）")

    # ---- 全文文本（计数类指标）
    full = "\n".join(ln["text"] for p in pages for ln in p["lines"])
    figures = max(uniq(r"(?:^|\n)\s*(?:Figure|Fig\.)\s*(\d+)\s*[:.]", full),
                  uniq(r"\b(?:Figure|Fig\.)\s*(\d+)\s*[:.]", full))
    tables = max(uniq(r"(?:^|\n)\s*Table\s*(\d+)\s*[:.]", full),
                 uniq(r"\bTable\s*(\d+)\s*[:.]", full))
    algorithms = uniq(r"\bAlgorithm\s*(\d+)\s*[:.]?", full)
    listings = uniq(r"\bListing\s*(\d+)", full)
    equations = len(set(re.findall(r"(?m)^\s*\((\d+)\)\s*$", full)))

    ref_page, refs, ref_style = None, 0, None
    for idx, p in enumerate(pages):
        t = "\n".join(ln["text"] for ln in p["lines"])
        if re.search(r"(?im)^[^\n]{0,4}(?:\d+\.?\s*)?references\b", t):
            ref_page = idx
            break
    if ref_page is not None:
        tail = "\n".join(ln["text"] for p in pages[ref_page:] for ln in p["lines"])
        num = set(re.findall(r"\[(\d{1,4})\]", tail))
        ay = re.findall(r"(?m)^\s*[A-Z][\w'’\-]+,\s.{0,240}?\b(?:19|20)\d{2}[a-z]?\b", tail)
        if ay:
            ref_style = "author-year"
        if num:
            ref_style = "numeric" if len(num) >= len(ay) else "author-year"
        refs = max(len(num), len(ay))
    content_pages = (ref_page + 1) if ref_page is not None else len(pages)

    # ---- 题注：字号与对齐（按栏判断）
    cap_sizes, cap_align = [], {"left": 0, "center": 0}
    for p in body:
        for ln in p["lines"]:
            if not CAP_RE.match(ln["text"]):
                continue
            cap_sizes.append(snap_size(ln["size"]))
            if two_col:
                unit, cstart = col_width, (col2_left if ln["x0"] >= col2_left - 4 else left)
            else:
                unit, cstart = text_width, left
            cap_align["left" if ln["x0"] <= cstart + 0.06 * unit else "center"] += 1
    caption_pt = max(set(cap_sizes), key=cap_sizes.count) if cap_sizes else None

    # ---- 通栏（跨双栏）浮动体与位置
    fw_floats, fw_pos = 0, {"top": 0, "bottom": 0, "mid": 0}
    if two_col:
        for p in body:
            ls = p["lines"]
            if not ls:
                continue
            ys = [ln["y1"] for ln in ls]
            ytop, ybot = max(ys), min(ln["y0"] for ln in ls)
            span = (ytop - ybot) or 1
            for ln in ls:
                if not CAP_RE.match(ln["text"]):
                    continue
                if not (ln["x0"] <= left + 0.08 * col_width and ln["x1"] >= col2_left + 0.15 * col_width):
                    continue            # 只统计跨栏的图/表题注
                fw_floats += 1
                d_top, d_bot = (ytop - ln["y1"]) / span, (ln["y0"] - ybot) / span
                key = "top" if d_top < 0.35 else ("bottom" if d_bot < 0.35 else "mid")
                fw_pos[key] += 1
    else:
        # 单栏：以“占版心 ≥85% 的图”作为满宽浮动体的代理，按其在版心中的位置分档
        for p in body:
            ls = [ln for ln in p["lines"] if not ln["fig"]] or p["lines"]
            if not ls:
                continue
            ytop, ybot = max(ln["y1"] for ln in ls), min(ln["y0"] for ln in ls)
            span = (ytop - ybot) or 1
            for f in merge_boxes(p.get("figs", [])):
                if f["w"] < 20 or f["h"] < 20 or f["w"] < 0.85 * max(text_width, 1):
                    continue
                fw_floats += 1
                cy = (f["y0"] + f["y1"]) / 2
                d_top, d_bot = (ytop - cy) / span, (cy - ybot) / span
                fw_pos["top" if d_top < 0.4 else ("bottom" if d_bot < 0.4 else "mid")] += 1

    # ---- 脚注：页底 25%、字号小于正文、以标记开头
    fn = 0
    for p in body:
        if not p["lines"]:
            continue
        low = ph * 0.25
        marks = {round(ln["y0"]) for ln in p["lines"]
                 if ln["size"] <= body_pt - 0.8 and ln["y0"] < low and FOOT_RE.match(ln["text"])}
        fn += len(marks)

    # ---- 图片几何：宽度占比 / 高度占比 / 在页面中的位置（顶/底）
    fig_w, fig_h, fig_pos = [], [], {"top": 0, "bottom": 0, "mid": 0}
    for p in body:
        ls = [ln for ln in p["lines"] if not ln["fig"]] or p["lines"]
        if not ls:
            continue
        ytop, ybot = max(ln["y1"] for ln in ls), min(ln["y0"] for ln in ls)
        span = (ytop - ybot) or 1
        for f in merge_boxes(p.get("figs", [])):
            if f["w"] < 20 or f["h"] < 20:      # 忽略装饰/图标
                continue
            fig_w.append(round(f["w"] / max(text_width, 1), 3))
            fig_h.append(round(f["h"] / (ph or 1), 3))
            cy = (f["y0"] + f["y1"]) / 2
            d_top, d_bot = (ytop - cy) / span, (cy - ybot) / span
            fig_pos["top" if d_top < 0.4 else ("bottom" if d_bot < 0.4 else "mid")] += 1
    fig_metrics = {
        "n_figs_geom": len(fig_w),
        "fig_width_frac_median": round(st.median(fig_w), 3) if fig_w else None,
        "fig_width_frac_p90": pct(fig_w, 0.9),
        "full_width_fig_frac": (round(len([x for x in fig_w if x >= 0.85]) / len(fig_w), 3)
                                if fig_w else None),
        "fig_height_frac_median": round(st.median(fig_h), 3) if fig_h else None,
        "fig_pos": fig_pos,
    }

    # ---- 公式/算法环境等版面元素密度
    mmp = {"pdf_pages": n_pages_total or len(pages),
           "measured_pages": len(pages),
           "page_size_pt": [round(pw, 1), round(ph, 1)],
           "paper_size": paper,
           "columns": 2 if two_col else 1,
           "column_left_pt": round(col2_left, 1) if col2_left else None,
           "column_width_pt": col_width,
           "column_gap_pt": col_gap,
           "text_width_pt": text_width,
           "text_height_pt": round(st.median([max(ln["y1"] for ln in p["lines"]) - min(ln["y0"] for ln in p["lines"])
                                              for p in body if p["lines"]]), 1) if body else None,
           "body_font_pt": round(body_pt, 1),
           "body_font_pt_snap": snap_size(body_pt),
           "font_size_hist": {str(k): round(v, 3) for k, v in list(hist.items())[:8]},
           "margins_pt": marg,
           "margins_mm": {k: (round(v * PT2MM, 1) if v is not None else None) for k, v in marg.items()},
           "caption_font_pt": caption_pt,
           "caption_align": cap_align,
           "figures": figures, "tables": tables,
           "algorithms": algorithms, "listings": listings, "equations": equations,
           "footnotes_est": fn, "refs": refs, "ref_style": ref_style,
           "content_pages": content_pages,
           "full_width_floats": fw_floats, "full_width_float_pos": fw_pos,
           "figure_geometry": fig_metrics,
           "lines_per_page": round(len(lines) / max(1, len(body)), 1),
           "x_line_starts_pt": [c[0] for c in strong][:6],
           }
    return {
        "pdf": path_or_url,
        "measured": mmp,
        "method": "pdfminer.six layout：行/字符级包围盒（字形精度）。栏数=行首 x 聚类；"
                  "版心右沿取行尾 x1 的 98 分位（排除通栏图/表格线造成的离群行）；"
                  "上下边距为正文页首末行位置（含页眉/页脚占位差异）；"
                  "figures/tables 等按题注正则计数（同一编号去重）；脚注为页底小字号带标记行。",
        "warnings": warnings,
    }


CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "sources", "raw", "pdfs")


def download(url: str) -> str:
    os.makedirs(CACHE, exist_ok=True)
    name = re.sub(r"[^A-Za-z0-9._-]", "_", url.split("//", 1)[-1])[-120:].strip("_")
    if not name.lower().endswith(".pdf"):
        name += ".pdf"
    out = os.path.join(CACHE, name)
    if os.path.exists(out) and os.path.getsize(out) > 1024:
        return out
    req = urllib.request.Request(url, headers={"User-Agent": "texopt-dataset/1.0 (academic layout research)"})
    with urllib.request.urlopen(req, timeout=90) as r, open(out, "wb") as fh:
        fh.write(r.read())
    return out


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print(__doc__)
        sys.exit(2)
    max_pages = None
    for a in sys.argv[1:]:
        if a.startswith("--pages="):
            max_pages = int(a.split("=", 1)[1])
    print(json.dumps(measure(args[0], max_pages), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
