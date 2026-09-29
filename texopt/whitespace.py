# -*- coding: utf-8 -*-
"""留白结构化识别（阶段 3）：空白掩码连通域 + 结构规则分类。

设计方案第七章 7.2 的落地：
  1）版面元素图：文本行（含标题/题注/正文）、图/表浮动体 bbox；
  2）空白掩码：版心（A_usable，已挖掉栏间距）减去元素并集，做**连通域分解**；
  3）规则分类：五类 —— structural / boundary / float / trailing / anomalous；
  4）输出 region 列表（位置、面积、高度、类别、邻接证据、置信度）。

铁律（方案 7.4）：一个空白区域只有「尺寸超阈」**且**「无结构解释」同时成立，
才计为 `anomalous`；其余四类都是肖像特征，**不惩罚**（White Space ≠ Bad Space）。
这一门控是防止「为提高页面利用率而过度压缩正常视觉间距」的关键。

分类优先级（自上而下，先命中先归类）：
  structural（邻接标题 / 两行之间的正常行距）
  > float（邻接图/表浮动体或题注）
  > trailing（落在一栏底部：栏末/章节末/文末）
  > boundary（贴合版心左右上边界或栏缝）
  > anomalous（无任何结构解释且尺寸超阈）
  > structural/spacing（零碎、无结构解释但尺寸很小 → 归为间距噪声）

诚实口径：
  * 全部量自 PDF 矢量/文本层 + 4pt 网格，可复现；不用像素猜测。
  * 「结构性」的判定是**邻接证据**（谁挨着它），不是语义理解；confidence 反映证据强度。
  * 本模块只做量，不做修改决策（动作见 texopt/actions.py 白名单）。
"""
from __future__ import annotations

from . import page_metrics as PM

CELL = 4.0                 # 网格边长（pt），与 extract.GridMask 一致
TOL = 5.0                  # 邻接判定容差（pt）：≥1 个网格 + 余量
SPACING_MAX = 2.4          # 空白高度 ≤ 2.4×行距 → 正常行距（结构性）
PARAGRAPH_MAX = 3.2        # ≤ 3.2×行距 → 正常段间距（结构性）
HEAD_MAX_H = 0.25          # 邻接标题的空白超过该高度就不算「标题间距」
FLOAT_MAX_H = 0.35         # 邻接浮动体的空白超过该高度→仍记 float，但置信度下调
MIN_AREA_RATIO = 0.004     # 小于版心面积 0.4% 的空白不单列（网格量化噪声）
ANOM_HEIGHT = 0.22         # 无解释空白的「高」阈值（占版心高）
ANOM_AREA = 0.10           # 无解释空白的「面积」阈值（占版心面积）
BOTTOM_ANOM = 0.35         # 栏底空白超过该比例、且正文行尚未结束 → 异常分页
FLOAT_TOL = 8.0            # 与浮动体/题注的邻接容差（pt）
SHORT_LINE = 0.75          # 行宽 < 75% 栏宽 → 段末/短行（用于判断「内容是否继续」）

CLASSES = ("structural", "boundary", "float", "trailing", "anomalous")


# ---------------------------------------------------------------- 几何 / 网格

def _geom(frame: dict, excl) -> dict:
    return {
        "x0": frame["left"], "y0": frame["bottom"],
        "x1": frame["right"], "y1": frame["top"],
        "nx": max(1, int((frame["right"] - frame["left"]) / CELL) + 1),
        "ny": max(1, int((frame["top"] - frame["bottom"]) / CELL) + 1),
        "excl": [(float(a), float(b)) for a, b in (excl or [])],
    }


def _skip_x(g: dict, xcen: float) -> bool:
    return any(a <= xcen <= b for a, b in g["excl"])


def _all_cells(g: dict) -> set:
    """版心（挖掉栏缝）的全部网格。与 GridMask 的格心口径一致。"""
    out = set()
    for i in range(g["nx"]):
        cx = g["x0"] + (i + 0.5) * CELL
        if cx < g["x0"] or cx > g["x1"] or _skip_x(g, cx):
            continue
        for j in range(g["ny"]):
            cy = g["y0"] + (j + 0.5) * CELL
            if cy < g["y0"] or cy > g["y1"]:
                continue
            out.add((i, j))
    return out


def _cells_for_box(g: dict, box: dict) -> list:
    """一个 bbox 覆盖的网格（与 extract.GridMask.add 同一套口径）。"""
    x0 = max(box["x0"], g["x0"])
    y0 = max(box["y0"], g["y0"])
    x1 = min(box["x1"], g["x0"] + g["nx"] * CELL)
    y1 = min(box["y1"], g["y0"] + g["ny"] * CELL)
    if x1 <= x0 or y1 <= y0:
        return []
    out = []
    for i in range(int((x0 - g["x0"]) // CELL), int((x1 - g["x0"] - 1e-9) // CELL) + 1):
        cx = g["x0"] + (i + 0.5) * CELL
        if cx < g["x0"] or cx > g["x1"] or _skip_x(g, cx):
            continue
        for j in range(int((y0 - g["y0"]) // CELL), int((y1 - g["y0"] - 1e-9) // CELL) + 1):
            cy = g["y0"] + (j + 0.5) * CELL
            if cy < g["y0"] or cy > g["y1"]:
                continue
            out.append((i, j))
    return out


def _components(cells: set) -> list:
    """4-邻接连通域分解。返回 [(cells 集合, bbox 网格索引), ...]。"""
    seen = set()
    comps = []
    for start in cells:
        if start in seen:
            continue
        stack = [start]
        seen.add(start)
        comp = []
        while stack:
            c = stack.pop()
            comp.append(c)
            i, j = c
            for nb in ((i + 1, j), (i - 1, j), (i, j + 1), (i, j - 1)):
                if nb in cells and nb not in seen:
                    seen.add(nb)
                    stack.append(nb)
        ii = [c[0] for c in comp]
        jj = [c[1] for c in comp]
        comps.append((comp, (min(ii), min(jj), max(ii), max(jj))))
    return comps


def _shape(cells: set, full_rows: set) -> tuple:
    """区域的「连续空白带」尺度。

    连通域可能是 L 形/环形（例如居中的首页大标题周围，或浮动体旁边的窄条），
    它的 bbox 高度没有意义（会算出 1.0），旁边那条窄条也不能算「一整页的空洞」。
    因此只统计**整行全空**（该行在本栏范围内一个内容格都没有）的那些行：
      band_run   区域内最长的连续整行全空带（格数）
      bottom_run 其中从**栏底（j=0）往上**的那条（0 表示未触底）
    阈值判定一律用这两个尺度，bbox/面积只用于报告。
    """
    js = sorted({j for (_, j) in cells if j in full_rows})
    band_run = bottom_run = 0
    if js:
        run, start = 1, js[0]
        for a, b in zip(js, js[1:]):
            if b == a + 1:
                run += 1
            else:
                band_run = max(band_run, run)
                if start == 0:
                    bottom_run = max(bottom_run, run)
                run, start = 1, b
        band_run = max(band_run, run)
        if start == 0:
            bottom_run = max(bottom_run, run)
    return band_run, bottom_run


def _box_of(g: dict, bbox_idx) -> dict:
    i0, j0, i1, j1 = bbox_idx
    return {"x0": round(g["x0"] + i0 * CELL, 2),
            "y0": round(g["y0"] + j0 * CELL, 2),
            "x1": round(g["x0"] + (i1 + 1) * CELL, 2),
            "y1": round(g["y0"] + (j1 + 1) * CELL, 2)}


def _x_overlap(a: dict, b: dict) -> float:
    return max(0.0, min(a["x1"], b["x1"]) - max(a["x0"], b["x0"]))


# ---------------------------------------------------------------- 邻接收集

def _elements(lines, floats, header_lines):
    """整理为统一的元素列表 [{kind, x0,y0,x1,y1}]（kind: head/caption/text/float）。"""
    els = []
    for ln in lines:
        els.append({"kind": ln.get("kind", "text"), "x0": ln["x0"], "y0": ln["y0"],
                    "x1": ln["x1"], "y1": ln["y1"]})
    for f in floats or []:
        b = f.get("bbox") or f
        els.append({"kind": "float", "x0": b["x0"], "y0": b["y0"],
                    "x1": b["x1"], "y1": b["y1"], "label": f.get("kind")})
    for ln in header_lines or []:      # 页眉/页脚：只作为「非结构解释」的旁观者
        els.append({"kind": "furniture", "x0": ln["x0"], "y0": ln["y0"],
                    "x1": ln["x1"], "y1": ln["y1"]})
    return els


def _neighbors(reg: dict, els: list, kind: str | None = None,
               gap: float = TOL) -> list:
    """与空白区域**纵向相邻**的元素（要求横向有重叠）。"""
    out = []
    for e in els:
        if kind and e["kind"] != kind:
            continue
        if _x_overlap(reg, e) <= 0:
            continue
        if e["y1"] <= reg["y0"] + gap and e["y1"] >= reg["y0"] - gap:
            out.append(("below", e))
        elif e["y0"] >= reg["y1"] - gap and e["y0"] <= reg["y1"] + gap:
            out.append(("above", e))
    return out


def _near(reg: dict, e: dict, gap: float) -> bool:
    """两个矩形「挨着或重叠」（两轴上的间隙都 ≤ gap）。"""
    hx = max(0.0, max(reg["x0"], e["x0"]) - min(reg["x1"], e["x1"]))
    vy = max(0.0, max(reg["y0"], e["y0"]) - min(reg["y1"], e["y1"]))
    return hx <= gap and vy <= gap


def _beside(reg: dict, els: list, kind: str | None = None,
            gap: float = FLOAT_TOL) -> list:
    """与空白区域**横向相邻**的元素（纵向区间有重叠）—— 浮动体两侧的空白。"""
    out = []
    for e in els:
        if kind and e["kind"] != kind:
            continue
        v = min(reg["y1"], e["y1"]) - max(reg["y0"], e["y0"])
        if v <= 0:
            continue
        if e["x1"] <= reg["x0"] + gap and e["x1"] >= reg["x0"] - gap:
            out.append(("left", e))
        elif e["x0"] >= reg["x1"] - gap and e["x0"] <= reg["x1"] + gap:
            out.append(("right", e))
    return out


def _last_above(reg: dict, els: list, frame: dict) -> dict | None:
    """区域**上沿之上、最靠近**的一条内容元素（reg["y1"] 为上沿）。

    判据用元素的**下沿** e["y0"] ≥ 上沿 − TOL（而不是元素上沿）：紧贴空白区
    上方的那一行，其下沿正好等于空白区的上沿，若用「元素上沿 ≤ 区域上沿」比较
    会把它自己排除掉（2026-09-29 实测：末页最后一行被漏掉 → 留白被误报异常）。
    """
    best = None
    for e in els:
        if e["kind"] == "furniture":
            continue
        if _x_overlap(reg, e) <= 0:
            continue
        if e["y0"] >= reg["y1"] - TOL:
            if best is None or e["y0"] < best["y0"]:
                best = e
    return best


def _col_of(reg: dict, frame: dict) -> int:
    if frame["columns"] != 2 or not frame.get("col2_left"):
        return 1
    return 1 if reg["x0"] < frame["col2_left"] - 2 else 2


def _col_width(frame: dict, col: int) -> float:
    if frame["columns"] != 2 or not frame.get("col2_left"):
        return frame["right"] - frame["left"]
    if col == 1:
        return frame["col1_right"] - frame["left"]
    return frame["right"] - frame["col2_left"]


def _touches(reg: dict, frame: dict, side: str) -> bool:
    if side == "left":
        return reg["x0"] <= frame["left"] + TOL
    if side == "right":
        return reg["x1"] >= frame["right"] - TOL
    if side == "top":
        return reg["y1"] >= frame["top"] - TOL
    if side == "bottom":
        return reg["y0"] <= frame["bottom"] + TOL
    return False


# ---------------------------------------------------------------- 分类

def _classify(reg: dict, els: list, frame: dict, leading: float | None,
              page_ctx: dict | None) -> tuple:
    """-> (class, adjacent 证据列表, confidence)。"""
    A = reg["_area_ratio"]
    # 注意：0.0 是合法值（区域内没有整行全空的带），不能用 `or` 回退到 bbox 高度
    h = reg["_band_ratio"] if reg.get("_band_ratio") is not None else reg["_height_ratio"]
    ctx = page_ctx or {}
    adj: list = []

    # 1) 邻接标题（章节/小节标题）→ 结构性留白（仅限「标题间距」尺度）
    if h <= HEAD_MAX_H and _neighbors(reg, els, kind="head", gap=FLOAT_TOL):
        return "structural", ["heading"], 0.9

    # 2) 邻接浮动体 / 题注（上下或左右）→ 浮动体留白
    #    （巨大者仍记 float，置信度下调：是否真异常需引用距离，交阶段 4）
    #    * 纵向相邻 / 横向相邻 / 「把浮动体包住的 L 形空白」（_near）三种情形都算浮动体留白
    nf = (_neighbors(reg, els, kind="float", gap=FLOAT_TOL)
          or _beside(reg, els, kind="float")
          or [1 for e in els if e["kind"] == "float" and _near(reg, e, FLOAT_TOL)])
    nc = (_neighbors(reg, els, kind="caption", gap=FLOAT_TOL)
          or _beside(reg, els, kind="caption")
          or [1 for e in els if e["kind"] == "caption" and _near(reg, e, FLOAT_TOL)])
    if nf or nc:
        return "float", (["float"] if nf else []) + (["caption"] if nc else []), \
            (0.85 if h < FLOAT_MAX_H else 0.6)

    # 3) 正常行距/段距（上下都是文本，且空白高度在正常间距尺度内）→ 结构性留白
    ntext = _neighbors(reg, els, kind="text")
    aboves = [e for pos, e in ntext if pos == "above"]
    belows = [e for pos, e in ntext if pos == "below"]
    gap_pt = reg["_band_pt"] if reg.get("_band_pt") is not None else reg_height_pt(reg)
    #    要求 gap_pt > 0：贴边窄条（行末参差余量）没有「整行全空带」，属边界留白
    if leading and 0 < gap_pt <= SPACING_MAX * leading and (aboves or belows):
        return "structural", ["spacing"], 0.8
    if leading and aboves and belows and 0 < gap_pt <= PARAGRAPH_MAX * leading:
        return "structural", ["paragraph", "paragraph"], 0.7

    # 4) 落在栏底 → 页末留白（结合「内容是否继续」再决定是否升级为异常）
    col = _col_of(reg, frame)
    if reg.get("_bottom_band_pt"):
        last = _last_above(reg, els, frame)   # 本栏内容的最下沿（不是整行全空带的上沿）
        cw = _col_width(frame, col)
        short = bool(last) and (last["x1"] - last["x0"]) < SHORT_LINE * cw
        # 首页（标题+摘要）下方的空白是正常版面（方案 12.2「首页大标题」）
        at_end = bool(ctx.get("is_last")) or bool(ctx.get("is_first")) or short
        if last is None:
            # 栏底那条全空带上方根本没有内容（例如居中标题旁的窄条）：
            # 这不是「内容到此结束」，交给后续 boundary / anomalous 判
            pass
        elif not at_end and reg["_bottom_band_ratio"] >= BOTTOM_ANOM:
            # 正文行还没结束（满行）却留下巨大栏底空白 → 坏分页/浮动体被顶走
            return "anomalous", ["column-end", "text-continues"], 0.7
        else:
            ev = ["column-end"]
            if bool(ctx.get("is_last")):
                ev.append("doc-end")
            elif short:
                ev.append("section-end")
            else:
                ev.append("page-continue")
            return "trailing", ev, 0.85 if at_end else 0.6

    # 5) 首页顶部的整块空白：首页大标题/作者/摘要本来就从页中下部开始，
    #    方案 12.2 明确把「首页大标题」列为「合法但特殊」的版面，不得报异常
    if ctx.get("is_first") and _touches(reg, frame, "top"):
        return "structural", ["title-page"], 0.7

    # 6) 无任何结构解释且尺寸超阈 → 异常连续留白（唯一进入惩罚项）
    #    尺度用「全宽连续空白带」而不是 bbox 高度（L 形/环形空白不冤杆）；
    #    且必须是**被上方内容夹住**的空洞：整列/整半页本来就空（无上方内容）
    #    不算「异常空洞」，交给边界留白（否则末页空栏会被误报）。
    if (h >= ANOM_HEIGHT or (A >= ANOM_AREA and h >= 0.12)) \
            and _last_above(reg, els, frame) is not None:
        return "anomalous", ["unexplained"], 0.75

    # 7) 贴合版心边界（左右/上）或栏缝 → 边界留白（窄条：页边/栏边的正常余量）
    sides = [s for s in ("left", "right", "top") if _touches(reg, frame, s)]
    if sides:
        return "boundary", [f"boundary:{s}" for s in sides], 0.8

    # 7) 零碎、无结构解释但尺寸很小 → 记为间距噪声（不惩罚）
    return "structural", ["spacing"], 0.5


def reg_height_pt(reg: dict) -> float:
    return reg["bbox"][3] - reg["bbox"][1]


def reg_bottom(reg: dict, frame: dict) -> dict:
    """用于「栏底上方最近元素」的检索窗口：栏底那条连续带的高度范围。"""
    y1 = frame["bottom"] + (reg.get("_bottom_band_pt") or 0.0)
    return {"x0": reg["x0"], "x1": reg["x1"], "y0": frame["bottom"], "y1": y1}


# ---------------------------------------------------------------- 主入口

def analyze(frame: dict, excl, lines: list, floats: list, leading: float | None,
            page_ctx: dict | None = None) -> dict:
    """一页的留白结构化结果（page_metrics.v1 的 `whitespace` 块）。

    lines : [{"x0","y0","x1","y1","kind"}]（kind: head/caption/text；页眉页脚请勿传入）
    floats: anchor_floats() 的输出（含 bbox）
    leading: 该页行距（pt），用于判断「正常行距」
    page_ctx: {"is_last": bool, ...}（文档末页信息；缺省视为未知）
    """
    ws = PM.blank_whitespace()
    A = max(1.0, _area(frame))
    els = _elements(lines, floats, None)
    g = _geom(frame, excl)
    cells = _all_cells(g)
    row_total: dict = {}
    for (_, j) in cells:
        row_total[j] = row_total.get(j, 0) + 1
    for e in els:
        if e["kind"] == "furniture":
            continue
        for c in _cells_for_box(g, e):
            cells.discard(c)
    # 「整行全空」的行 = 该行在本栏范围内一个内容格都没有（真正的横向空白带）
    blank_rows: dict = {}
    for (_, j) in cells:
        blank_rows[j] = blank_rows.get(j, 0) + 1
    full_rows = {j for j, n in row_total.items()
                 if n > 0 and blank_rows.get(j, 0) == n}
    comps = _components(cells)

    regions = []
    frag_area = 0.0          # 被过滤的碎片空白（<0.4% 版心，逐格凑起来不可忽略）
    frag_n = 0
    for comp, bbox_idx in comps:
        bbox = _box_of(g, bbox_idx)
        area = len(comp) * CELL * CELL
        ar = area / A
        if ar < MIN_AREA_RATIO:
            frag_area += area
            frag_n += 1
            continue
        hr = (bbox["y1"] - bbox["y0"]) / max(1.0, frame["height_pt"])
        run, br = _shape(comp, full_rows)
        band_pt = run * CELL
        bottom_pt = br * CELL
        reg = {"bbox": [bbox["x0"], bbox["y0"], bbox["x1"], bbox["y1"]],
               "x0": bbox["x0"], "y0": bbox["y0"],
               "x1": bbox["x1"], "y1": bbox["y1"],
               "_area_ratio": ar, "_height_ratio": hr,
               "_band_pt": band_pt, "_band_ratio": band_pt / max(1.0, frame["height_pt"]),
               "_bottom_band_pt": bottom_pt,
               "_bottom_band_ratio": bottom_pt / max(1.0, frame["height_pt"]),
               "area_ratio": round(ar, 4),
               # 报告用「最长连续空白带」高度（bbox 高度对 L 形区域会虚高）
               "height_ratio": round(band_pt / max(1.0, frame["height_pt"]), 3)}
        klass, adj, conf = _classify(reg, els, frame, leading, page_ctx)
        regions.append(PM.blank_region(
            bbox=reg["bbox"], area_ratio=reg["area_ratio"],
            height_ratio=reg["height_ratio"], klass=klass,
            adjacent=adj, confidence=conf))
    regions.sort(key=lambda r: -(r["area_ratio"] or 0))

    by = {k: 0.0 for k in CLASSES}
    for r in regions:
        by[r["class"]] += r["area_ratio"] or 0.0
    # 碎片（未单列的小空白）本质是行距/字距噪声，计入结构性留白；
    # 这样 **Σ 五类比率 == total_ratio == 版面空白格的完整量**，可与
    # extract 的「内容并集补集」逐页互校（恒等式，round 前精确相等）。
    by["structural"] += frag_area / A
    ws.update({
        "total_ratio": round(sum(by.values()), 4),
        "structural_ratio": round(by["structural"], 4),
        "boundary_ratio": round(by["boundary"], 4),
        "float_ratio": round(by["float"], 4),
        "trailing_ratio": round(by["trailing"], 4),
        "anomalous_ratio": round(by["anomalous"], 4),
        "regions": regions,
        "status": "extracted",
        "n_regions": len(regions),
        "n_fragments": frag_n,          # 未单列的小碎片区域数（已计入结构性留白）
        "n_anomalous": sum(1 for r in regions if r["class"] == "anomalous"),
        "max_anomalous_height_ratio": max(
            [r["height_ratio"] for r in regions if r["class"] == "anomalous"] or [0.0]),
    })
    return ws


def _area(frame: dict) -> float:
    w = frame["right"] - frame["left"]
    if frame["columns"] == 2 and frame.get("col_gap"):
        w -= frame["col_gap"]
    return w * frame["height_pt"]
