# -*- coding: utf-8 -*-
"""视觉感知层（Phase 4）：PDF -> 页面图像，供具备视觉能力的模型消费。

定位（诚实标注，对应「视觉感知是未来重点」）：
  * 本模块把 PDF 逐页渲染为 PNG，附在 llm_request.json 的 page_images 里，
    交给有视觉理解能力的模型判断留白/视觉重心/图文关系/整体节奏等
    Level-3 问题。这是 Phase 4 的交付：**给 LLM 一双眼睛**。
  * 同时提供一组**像素代理指标**（whitespace/ink/vertical balance 等），
    用纯 stdlib 解析低分辨率 PGM 计算，用于可审计的粗略量化。
  * 明确边界：这些代理指标**不是人类审美评分**，且默认**不并入 A 分**
    （不改变 score.py 的语义）。它们只写进视觉报告，供参考与后续研究
    （Phase 5：逐步把 whitespace/content density/visual balance 等
    形式化并谨慎并入 A）。

依赖：pdftoppm（TeX Live 自带）；Windows 原生 exe 只能认真实盘符路径，
因此统一 cwd 到 PDF 所在目录、只传 basename。
"""
from __future__ import annotations

import glob
import os
import re
import shutil

from . import engine


def _pdftoppm() -> str | None:
    return engine.pdftoppm_path()


def _render(pdf_path: str, outdir: str, prefix: str, dpi: int,
            gray: bool, first: int | None, last: int | None,
            fmt: str) -> tuple[list[str], str | None]:
    """通用渲染：返回 (产出文件列表, 错误)。fmt: png|pgm。"""
    tool = _pdftoppm()
    if not tool:
        return [], "找不到 pdftoppm（TeX Live 应自带）"
    if not os.path.isfile(pdf_path):
        return [], f"找不到 PDF：{pdf_path}"
    os.makedirs(outdir, exist_ok=True)
    pdf_abs = os.path.abspath(pdf_path)
    cwd = os.path.dirname(pdf_abs)
    pdf_name = os.path.basename(pdf_abs)
    target_dir = os.path.abspath(outdir)
    # 输出到 outdir：先渲染到 cwd（Windows exe 可写），再搬到目标目录
    cmd = [tool]
    if gray:
        cmd.append("-gray")          # -gray 直接产出 PGM；pdftoppm 无 -pgm 选项
    elif fmt in ("png", "jpeg", "tiff"):
        cmd.append(f"-{fmt}")
    cmd += ["-r", str(dpi)]
    if first:
        cmd += ["-f", str(first)]
    if last:
        cmd += ["-l", str(last)]
    cmd += [pdf_name, prefix]
    rc, out_b, err_b = engine._run_with_timeout(cmd, cwd, 300)
    produced = sorted(glob.glob(os.path.join(cwd, prefix + "-*")))
    if not produced:
        msg = "pdftoppm 未产出图片" + (f"（rc={rc}）" if rc is not None else "（超时）")
        return [], msg
    moved = []
    for i, p in enumerate(produced, start=1):
        ext = os.path.splitext(p)[1]
        dst = os.path.join(target_dir, f"{prefix}-{i}{ext}")
        shutil.move(p, dst)
        moved.append(dst)
    return moved, None


def render_pages(pdf_path: str, outdir: str, dpi: int = 110,
                 first: int | None = None, last: int | None = None,
                 prefix: str = "page") -> tuple[list[str], str | None]:
    """逐页渲染 PDF 为 PNG（供视觉模型看）。返回 (图片路径列表, 错误)。"""
    return _render(pdf_path, outdir, prefix, dpi, gray=False,
                   first=first, last=last, fmt="png")


def render_gray(pdf_path: str, outdir: str, dpi: int = 40,
                prefix: str = "gray") -> tuple[list[str], str | None]:
    """低分辨率灰度 PGM（供像素代理指标用）。"""
    return _render(pdf_path, outdir, prefix, dpi, gray=True,
                   first=None, last=None, fmt="pgm")


# ---------------------------------------------------------------- PGM 解析

def _parse_pgm(path: str):
    """解析二进制 PGM(P5，maxval<=255) -> (w, h, data: bytes)。"""
    with open(path, "rb") as f:
        raw = f.read()
    # 头部：P5 后跟四个 token（含注释），再 1 个空白，随后是二进制数据
    i, tokens = 0, []
    while len(tokens) < 4:
        while i < len(raw) and raw[i:i + 1].isspace():
            i += 1
        if raw[i:i + 1] == b"#":                       # 注释行
            j = raw.find(b"\n", i)
            i = j + 1 if j >= 0 else len(raw)
            continue
        j = i
        while j < len(raw) and not raw[j:j + 1].isspace():
            j += 1
        tokens.append(raw[i:j])
        i = j
    if tokens[0] != b"P5":
        raise ValueError("仅支持 P5 二进制 PGM")
    w, h, maxval = int(tokens[1]), int(tokens[2]), int(tokens[3])
    i += 1                                              # 单个空白分隔符
    data = raw[i:i + w * h]
    return w, h, data


def page_proxy(pgm_path: str, ink_threshold: int = 200,
               empty_ratio: float = 0.004) -> dict:
    """单页像素代理（**实验性，非人类审美评分**）。

    返回：
      ink_ratio        墨迹占比（暗像素/总像素）
      top_bottom_ratio 上下半页墨迹比（视觉重心粗代理；越偏离 1 越失衡）
      max_empty_band   最大连续近空白行的长度占比（留白粗代理）
      max_empty_pos    该空白带的垂直中心位置（0=页顶,1=页底）
    """
    w, h, data = _parse_pgm(pgm_path)
    dark = bytearray(w * h)
    for p in range(w * h):
        dark[p] = 1 if data[p] < ink_threshold else 0
    total = w * h
    ink = sum(dark)
    rows = [sum(dark[r * w:(r + 1) * w]) for r in range(h)]
    # 上半 / 下半墨迹
    half = h // 2
    top = sum(rows[:half]) or 1
    bot = sum(rows[half:]) or 1
    # 最大连续近空白行带
    best_len = best_start = 0
    cur = 0
    for r in range(h):
        if rows[r] <= max(1, int(empty_ratio * w)):
            cur += 1
            if cur > best_len:
                best_len, best_start = cur, r - cur + 1
        else:
            cur = 0
    return {
        "ink_ratio": round(ink / total, 4),
        "top_bottom_ratio": round(top / bot, 3),
        "max_empty_band": round(best_len / h, 4) if h else 0.0,
        "max_empty_pos": round((best_start + best_len / 2) / h, 3) if h else 0.0,
    }


def visual_report(pdf_path: str, outdir: str, dpi: int = 110,
                  proxy_dpi: int = 40) -> dict:
    """渲染页面图 + 计算像素代理，返回结构化结果（供 report / llm_request）。

    返回 {images, proxies, metrics, defects, error}；proxies 为实验性代理指标，
    metrics/defects 为 Phase 2 的页面级视觉量化（已并入 A 分）。
    """
    pages_dir = os.path.join(outdir, "pages")
    imgs, err = render_pages(pdf_path, pages_dir, dpi=dpi)
    if err:
        return {"images": [], "proxies": [], "error": err}
    gdir = os.path.join(outdir, ".grayscale")
    grays, gerr = render_gray(pdf_path, gdir, dpi=proxy_dpi)
    proxies, metrics = [], []
    for i, g in enumerate(grays, start=1):
        try:
            m = page_proxy(g)
            m["page"] = i
            proxies.append(m)
        except Exception as exc:                        # 单页失败不影响整体
            proxies.append({"page": i, "error": str(exc)})
        try:
            mm = page_metrics(g)
            mm["page"] = i
            metrics.append(mm)
        except Exception as exc:
            metrics.append({"page": i, "error": str(exc)})
    for g in grays:
        try:
            os.remove(g)
        except OSError:
            pass
    try:
        os.rmdir(gdir)
    except OSError:
        pass
    out = {"images": imgs, "proxies": proxies,
           "metrics": metrics, "defects": find_defects(metrics)}
    _write_visual_md(os.path.join(outdir, "visual.md"), out)
    return out


def _write_visual_md(path: str, res: dict) -> None:
    L = ["# 视觉感知报告（页面级量化，已并入 A 分）\n",
         "> 说明：下表由**编译后的 PDF** 逐页渲染（灰度 PGM）直接量取，"
         "A 分已包含这些视觉缺陷（见 score.aesthetic_score）。\n",
         "| 页 | 墨迹占比 | 顶部空白 | 底部空白 | 内容高度 | 最大空白带 | "
         "位置 | 最大内容带 | 上/下半墨迹比 | 图片 |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    imgs = res.get("images", [])
    ms = res.get("metrics") or res.get("proxies", [])
    for i, m in enumerate(ms):
        img = imgs[i] if i < len(imgs) else ""
        if "error" in m:
            L.append(f"| {m.get('page')} | — | — | — | — | — | — | — | — | {img} |")
            continue
        L.append(
            f"| {m['page']} | {m.get('ink_ratio', m.get('ink'))} | "
            f"{m.get('top_blank', '—')} | {m.get('bottom_blank', '—')} | "
            f"{m.get('content_height', '—')} | {m.get('max_gap', '—')} | "
            f"{m.get('max_gap_at', '—')} | {m.get('band', '—')} | "
            f"{m.get('top_bottom_ratio', '—')} | `{os.path.basename(img)}` |")
    L.append("")
    ds = res.get("defects", [])
    if ds:
        L.append("## 视觉缺陷（程序判定，已计入 A）\n")
        for d in ds:
            pag = f"第{d['page']}页 " if d.get("page") else ""
            L.append(f"- [{d['severity']}] {pag}{d['kind']}：{d['detail']}")
        L.append("")
    L.append("量取口径：低分辨率灰度渲染后统计行/列墨迹；`最大内容带`="
             "行墨迹≥50%行宽的最长连续段（图/表/公式块）；`最大空白带`="
             "行墨迹≤0.4%行宽的最长连续段。这些量取自实际编译结果，不是源码猜测。")
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(L))


# =====================================================================
# Phase 2（2026-09-11）：页面级视觉量化 —— 从**实际编译后的 PDF**量取
#   ink / bbox / 上下留白 / 最大空白带 / 最大内容带（图-表-公式块）/
#   页间密度失衡 / 孤立大块内容 / 页面密度失衡
# 这些指标**并入 A 分**（score.aesthetic_score），并驱动出口状态判定。
# 诚实口径：它不是人类审美评分，而是可复现、可审计的版面缺陷量；
# 阈值取「明显差」的粗档，避免把正常排版判成缺陷。
# =====================================================================

BAND_DARK_RATIO = 0.5      # 行墨迹 ≥ 50% 行宽 -> “实在内容带”（图/表/公式块）
ROW_EMPTY_RATIO = 0.004    # 行墨迹 ≤ 0.4% 行宽 -> 空白行

SEVERITY_FACTOR = {"high": 1.0, "moderate": 0.6}

# A 分里各类视觉缺陷的权重（× severity 系数）
DEFECT_WEIGHT = {
    "giant_content": 1.5,        # 单一大块内容（巨大图/表）占据页面
    "stranded_block": 1.2,       # 内容孤零零 + 大面积留白
    "bottom_blank": 1.0,         # 页底大面积空白
    "mid_gap": 0.8,              # 页面中部巨大空洞
    "near_empty": 0.6,           # 几乎空白页
    "density_imbalance": 1.0,    # 页间密度严重失衡
}


def page_metrics(pgm_path: str, ink_threshold: int = 200,
                 row_empty_ratio: float = ROW_EMPTY_RATIO,
                 band_dark_ratio: float = BAND_DARK_RATIO) -> dict:
    """单页几何/密度量（全部为占页面的比例，0-1）。"""
    w, h, data = _parse_pgm(pgm_path)
    if w <= 0 or h <= 0:
        raise ValueError("空图像")
    dark = [1 if b < ink_threshold else 0 for b in data]
    total = w * h
    ink = sum(dark)
    rows = [sum(dark[r * w:(r + 1) * w]) for r in range(h)]
    thr = max(1, int(row_empty_ratio * w))

    nz = [r for r, v in enumerate(rows) if v > thr]
    top_blank = (nz[0] / h) if nz else 1.0
    bottom_blank = ((h - 1 - nz[-1]) / h) if nz else 1.0
    content_height = (((nz[-1] - nz[0] + 1) / h) if nz else 0.0)

    # 最大连续空白带
    gap_len = gap_at = 0
    cur = cur_start = 0
    for r in range(h):
        if rows[r] <= thr:
            if cur == 0:
                cur_start = r
            cur += 1
            if cur > gap_len:
                gap_len, gap_at = cur, cur_start
        else:
            cur = 0

    # 最大「实在内容带」（图/表/公式块）：
    bthr = max(1, int(band_dark_ratio * w))
    band_len = band_at = 0
    cur = cur_start = 0
    for r in range(h):
        if rows[r] >= bthr:
            if cur == 0:
                cur_start = r
            cur += 1
            if cur > band_len:
                band_len, band_at = cur, cur_start
        else:
            cur = 0

    # 左右空白（内容宽度占比）
    cols = [0] * w
    for r in range(h):
        base = r * w
        for c in range(w):
            if dark[base + c]:
                cols[c] += 1
    cthr = max(1, int(0.002 * h))
    cnz = [c for c, v in enumerate(cols) if v > cthr]
    left_blank = (cnz[0] / w) if cnz else 1.0
    right_blank = ((w - 1 - cnz[-1]) / w) if cnz else 1.0

    half = h // 2
    top_ink = sum(rows[:half]) or 1
    bot_ink = sum(rows[half:]) or 1
    return {
        "ink_ratio": round(ink / total, 4),
        "top_blank": round(top_blank, 3),
        "bottom_blank": round(bottom_blank, 3),
        "content_height": round(content_height, 3),
        "max_gap": round(gap_len / h, 3),
        "max_gap_at": round((gap_at + gap_len / 2) / h, 3) if gap_len else 0.0,
        "band": round(band_len / h, 3),
        "band_at": round((band_at + band_len / 2) / h, 3) if band_len else 0.0,
        "left_blank": round(left_blank, 3),
        "right_blank": round(right_blank, 3),
        "top_bottom_ratio": round(top_ink / bot_ink, 3),
    }


def find_defects(pages: list) -> list:
    """从页面量判定的「视觉缺陷」（带 severity）。阈值取“明显差”的粗档。"""
    ds: list = []
    ok = [p for p in pages if "error" not in p]
    for p in ok:
        n = p["page"]
        if p["band"] >= 0.40:
            ds.append({"kind": "giant_content", "page": n, "severity": "high",
                       "metric": p["band"],
                       "detail": f"第{n}页有单一块内容占据 {p['band'] * 100:.0f}% 页高"
                                 f"（巨大图片/表格）"})
        bb = p["bottom_blank"]
        if bb >= 0.35:
            ds.append({"kind": "bottom_blank", "page": n, "severity": "high",
                       "metric": bb,
                       "detail": f"第{n}页底部空白达 {bb * 100:.0f}%"})
        elif bb >= 0.25 and p["ink_ratio"] > 0.01:
            ds.append({"kind": "bottom_blank", "page": n, "severity": "moderate",
                       "metric": bb,
                       "detail": f"第{n}页底部空白 {bb * 100:.0f}%"})
        if p["max_gap"] >= 0.28 and 0.15 < p["max_gap_at"] < 0.85:
            ds.append({"kind": "mid_gap", "page": n,
                       "severity": "high" if p["max_gap"] >= 0.50 else "moderate",
                       "metric": p["max_gap"],
                       "detail": f"第{n}页中部有 {p['max_gap'] * 100:.0f}% 页高的"
                                 f"连续空洞（位置 {p['max_gap_at']:.2f}）"})
        if 0 < p["ink_ratio"] <= 0.06 and p["band"] >= 0.05 and bb >= 0.30:
            ds.append({"kind": "stranded_block", "page": n, "severity": "high",
                       "metric": p["ink_ratio"],
                       "detail": f"第{n}页内容孤立（墨迹仅 {p['ink_ratio'] * 100:.1f}%）"
                                 f"且底部大半空白"})
        if 0 < p["ink_ratio"] <= 0.02:
            # 几乎空白页属**明显**缺陷（high）：典型成因是手动分页/孤立浮动体/
            # 末页内容过少；后两者需作者决策，纯排版手段无法在不改内容前提下消除，
            # 因此宁可报 NEEDS_REVIEW 也不报 DONE（不伪造"优化完成"）
            ds.append({"kind": "near_empty", "page": n, "severity": "high",
                       "metric": p["ink_ratio"],
                       "detail": f"第{n}页几乎空白（墨迹 {p['ink_ratio'] * 100:.2f}%）"})
    inks = [p["ink_ratio"] for p in ok]
    positive = [x for x in inks if x > 0.005]
    if len(inks) >= 3 and positive:
        hi, lo = max(inks), min(positive)
        if hi / lo >= 10 or (hi - lo) >= 0.30:
            ds.append({"kind": "density_imbalance", "page": 0, "severity": "moderate",
                       "metric": round(hi / lo, 1),
                       "detail": f"页间内容密度严重失衡（最高 {hi * 100:.1f}% vs "
                                 f"最低 {lo * 100:.1f}%，相差 {hi / lo:.0f} 倍）"})
    return ds


def summarize_metrics(pages: list) -> dict:
    """聚合页面量 -> {n, ink_mean/min/max, pages, defects, severity_max}。"""
    ok = [p for p in pages if "error" not in p]
    inks = [p["ink_ratio"] for p in ok]
    defects = find_defects(pages)
    return {
        "n": len(pages),
        "pages": pages,
        "ink_mean": round(sum(inks) / len(inks), 4) if inks else None,
        "ink_min": min(inks) if inks else None,
        "ink_max": max(inks) if inks else None,
        "defects": defects,
        "severity_max": ("high" if any(d["severity"] == "high" for d in defects)
                         else ("moderate" if defects else None)),
    }


def analyze_pdf(pdf_path: str, tmpdir: str, dpi: int = 50,
                keep: bool = False) -> dict:
    """渲染灰度页图 -> 页面级视觉量 -> 聚合指标 + 缺陷清单。

    失败时返回 {"error": ...}（调用方按“无视觉信息”降级处理，不抛异常）。
    """
    grays, err = render_gray(pdf_path, tmpdir, dpi=dpi)
    if err:
        return {"error": err, "pages": [], "defects": [], "n": 0}
    pages = []
    for i, g in enumerate(grays, start=1):
        try:
            m = page_metrics(g)
            m["page"] = i
            pages.append(m)
        except Exception as exc:
            pages.append({"page": i, "error": str(exc)})
    if not keep:
        for g in grays:
            try:
                os.remove(g)
            except OSError:
                pass
        try:
            os.rmdir(tmpdir)
        except OSError:
            pass
    return summarize_metrics(pages)


def visual_defects(metrics: dict | None) -> list:
    """便捷取值：视觉缺陷清单（无指标时返回空）。"""
    if not metrics or metrics.get("error"):
        return []
    return list(metrics.get("defects") or [])


def defect_penalty(defects: list) -> float:
    """视觉缺陷 -> A 分惩罚（权重 × severity 系数）。"""
    return round(sum(DEFECT_WEIGHT.get(d["kind"], 0.5)
                     * SEVERITY_FACTOR.get(d["severity"], 0.6)
                     for d in defects), 3)
