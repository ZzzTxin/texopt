# -*- coding: utf-8 -*-
"""page_metrics.v1 —— 审美量化模型的统一页面级数据结构（阶段 0 交付）。

本模块**只定义数据结构与校验/序列化**，不做任何提取、不接入 A 分。
它的作用是给后续阶段（阶段 1-4）一个固定的落盘 schema，避免各阶段
各自发明字段、互相不兼容。

诚实标注（与 score.py / visual.py 的口径一致）：
  * 这里定义的量是**版面特征与常态偏离的载体**，不是人类审美评分。
  * 每个指标组带 status 字段，取值：
      extracted   —— 已能从现有实现算出（多为像素层）
      partial     —— 有代理量或只有部分子项
      placeholder —— 字段已定义、尚无实现（后续阶段填）
      unavailable —— 当前证据层无法获得（需新的提取手段）
  * 阶段 0 结算时：`visual.py` 已能提供的量都会经 `from_legacy_visual()`
    映射进 v1（status=extracted/partial），其余一律 placeholder。
    不允许把 placeholder 当成"已实现"上报。

分层原则（对应设计方案第五章）：统计与比对必须在 role 分层内进行，
因此 page 级对象**强制携带 role 字段**（未知时用 "unknown"）。

来源层标记（provenance）：source / log / pdf / vector / text / pixel。
其中 vector=PDF 矢量坐标、text=PDF 文本块、pixel=灰度位图。
凡由 pixel 得到的量，精度受渲染 dpi 限制，必须在 provenance 里写明。
"""
from __future__ import annotations

import json
import os

SCHEMA_ID = "page_metrics.v1"
EXTRACTOR_VERSION = "0.2.0"   # 0.2.0：阶段 3 留白结构化 + 页眉页脚排除 + 未锚图形计入覆盖

ROLES = ("title", "section-head", "body", "math-heavy", "figure-page",
         "table-page", "references", "appendix", "last-page", "unknown")

STATUS_VALUES = ("extracted", "partial", "placeholder", "unavailable")

# 指标 → 证据层（决定精度与是否可复现）
GROUP_PROVENANCE = {
    "density": "pixel",      # 阶段 2 起应升级为 text/vector 分离统计
    "ratio": "vector",
    "balance": "pixel",
    "whitespace": "vector",
    "alignment": "vector",
    "consistency": "vector",
    "readability": "text",
    "microtype": "log",
    "figure_quality": "vector",
}


# ---------------------------------------------------------------- 构造

def blank_whitespace() -> dict:
    """空白模型（设计方案第七章）：五类留白 + 区域清单。"""
    return {
        "total_ratio": None,        # 版心空白占比
        "structural_ratio": None,   # 结构性留白
        "boundary_ratio": None,     # 边界留白
        "float_ratio": None,        # 浮动体留白
        "trailing_ratio": None,     # 页面末尾留白
        "anomalous_ratio": None,    # 异常连续留白（唯一进入惩罚项的类别）
        "regions": [],              # 见 blank_region()
        "status": "placeholder",
        # 阶段 3 派生量（便于聚合与 LLM 直接消费）
        "n_regions": None,          # 列出的空白区域数（已过滤 <0.4% 版心的噪声）
        "n_fragments": None,        # 未单列的小碎片数（其面积已计入 structural_ratio）
        "n_anomalous": None,        # 其中异常连续留白的个数
        "max_anomalous_height_ratio": None,   # 最大异常空白的高度占版心高
    }


def blank_region(bbox=None, area_ratio=None, height_ratio=None,
                 klass="unknown", adjacent=None, confidence=None) -> dict:
    """单个空白区域。

    bbox: [x0, y0, x1, y1]（PDF pt，原点左下）或 None
    area_ratio: 区域面积 ÷ A_usable（空白掩码连通域的实际格数）
    height_ratio: **区域内最长的一条连续空白带**高度 ÷ 版心高（不是 bbox 高：
        L 形/环形空白——如首页大标题周围——的 bbox 高会虚高到 1.0）
    klass: structural | boundary | float | trailing | anomalous
    adjacent: 邻接元素类型列表（heading/float/caption/paragraph/spacing/boundary:*）
    """
    return {
        "bbox": bbox,
        "area_ratio": area_ratio,
        "height_ratio": height_ratio,
        "class": klass,
        "adjacent": list(adjacent or []),
        "confidence": confidence,
    }


def blank_page(page: int, role: str = "unknown") -> dict:
    """单页指标容器（所有量默认 placeholder，由提取器回填）。"""
    if role not in ROLES:
        role = "unknown"
    return {
        "page": page,
        "role": role,
        "role_confidence": None,
        "role_source": None,          # rule | manual | model
        "units": {                    # 页面与版心几何（mm），A_usable 的定义见方案 6.1
            "page_w_mm": None, "page_h_mm": None,
            "usable_w_mm": None, "usable_h_mm": None,
            "columns": None,          # 1 / 2 / ...
        },
        "density": {
            "ink_ratio_page": None,   # 全页暗像素占比（含图，仅作参照）
            "ink_ratio_text": None,   # 文本区墨迹率
            "coverage_text": None, "coverage_figure": None,
            "coverage_table": None, "coverage_other": None,
            "status": "placeholder",
        },
        "ratio": {
            "fig_text": None, "figtab_text": None,
            "status": "placeholder",
        },
        "balance": {
            "d_top": None, "d_mid": None, "d_bot": None,
            "left_right": None, "visual_centroid_y": None,
            "per_column": [],         # 双栏：每栏独立上下密度（方案 6.4）
            "status": "placeholder",
        },
        "whitespace": blank_whitespace(),
        "alignment": {
            "left_var": None, "right_var": None, "center_var": None,
            "n_elements": None,
            "status": "placeholder",
        },
        "consistency": {
            "figure_width_cv": None, "caption_style_cv": None,
            "status": "placeholder",
        },
        "readability": {
            "chars_per_line_mean": None, "leading_ratio": None,
            "font_pt": None, "para_lines_mean": None,
            "status": "placeholder",
        },
        "microtype": {
            "overfull": None, "underfull": None, "vbox_overfull": None,
            "vbox_underfull": None,
            "status": "placeholder",
        },
        "figure_quality": {
            "min_effective_dpi": None, "aspect_outliers": None,
            "status": "placeholder",
        },
        # 现有实现（visual.py）已能给出的量在此保留原样，便于回归对比；
        # 它们不是 v1 的正式字段，阶段 2 起逐步被上面的组取代。
        "legacy": {},
    }


def blank_document() -> dict:
    """整份文档的 v1 容器。"""
    return {
        "schema": SCHEMA_ID,
        "extractor_version": EXTRACTOR_VERSION,
        "profile_version": None,       # 阶段 2 起写入 profile 版本
        "doc": {
            "pdf": None, "tex": None,
            "venue": None, "year": None,
            "layout": None,            # onecolumn | twocolumn
            "pages": None,
            "render": {"tool": None, "dpi_pixel": None},
            "generated_at": None,
        },
        "pages": [],
        "paper": {
            "n_pages": None,
            "roles_hist": {},
            "float_ref_distance": {"mean": None, "max": None, "n": None},
            "aggregates": {},          # 指标 -> {median,mean,max,p90}
            "by_role": {},             # role -> 同上（分层聚合）
            "status": "placeholder",
        },
        "meta": {
            "notes": [],
            "unknown_fields": [],      # 未能取到的字段路径清单
        },
    }


# ---------------------------------------------------------------- 校验

def validate(doc: dict) -> list[str]:
    """结构校验：返回问题清单（空 = 通过）。不做数值合理性判断。"""
    errs: list[str] = []
    if not isinstance(doc, dict):
        return ["根对象不是 dict"]
    if doc.get("schema") != SCHEMA_ID:
        errs.append(f"schema 应为 {SCHEMA_ID!r}，实际 {doc.get('schema')!r}")
    pages = doc.get("pages")
    if not isinstance(pages, list):
        errs.append("pages 必须是 list")
        return errs
    seen: set = set()
    for i, p in enumerate(pages):
        if not isinstance(p, dict):
            errs.append(f"pages[{i}] 不是 dict")
            continue
        n = p.get("page")
        if not isinstance(n, int) or n < 1:
            errs.append(f"pages[{i}].page 必须是 >=1 的整数")
        elif n in seen:
            errs.append(f"pages[{i}].page 重复：{n}")
        else:
            seen.add(n)
        if p.get("role") not in ROLES:
            errs.append(f"pages[{i}].role 非法：{p.get('role')!r}")
        for grp in GROUP_PROVENANCE:
            g = p.get(grp)
            if not isinstance(g, dict):
                errs.append(f"pages[{i}].{grp} 缺失或不是 dict")
                continue
            st = g.get("status")
            if st not in STATUS_VALUES:
                errs.append(f"pages[{i}].{grp}.status 非法：{st!r}")
    if not isinstance(doc.get("doc"), dict):
        errs.append("doc 缺失或不是 dict")
    if not isinstance(doc.get("paper"), dict):
        errs.append("paper 缺失或不是 dict")
    return errs


def missing_fields(doc: dict) -> list[str]:
    """列出仍为 None / placeholder 的字段路径（阶段 0 的缺口清单来源）。"""
    out: list[str] = []

    def walk(node, path):
        if isinstance(node, dict):
            if node.get("status") == "placeholder":
                out.append(path + ".status")
            for k, v in node.items():
                if k == "status":
                    continue
                walk(v, f"{path}.{k}")
        elif isinstance(node, list):
            for j, v in enumerate(node):
                walk(v, f"{path}[{j}]")
        elif node is None and not path.endswith(".status"):
            out.append(path)

    walk(doc, "$")
    return out


# ---------------------------------------------------------------- 聚合

def _agg(values: list) -> dict:
    vals = sorted(float(v) for v in values if isinstance(v, (int, float)))
    if not vals:
        return {"median": None, "mean": None, "max": None, "p90": None, "n": 0}
    n = len(vals)

    def q(p):                                     # 线性插值分位（与 numpy 默认一致）
        if n == 1:
            return vals[0]
        pos = (n - 1) * p
        lo = int(pos)
        hi = min(lo + 1, n - 1)
        return round(vals[lo] + (vals[hi] - vals[lo]) * (pos - lo), 6)

    return {"median": q(0.5), "mean": round(sum(vals) / n, 6),
            "max": vals[-1], "p90": q(0.9), "n": n}


PAPER_METRICS = (
    ("density", "ink_ratio_page"), ("density", "ink_ratio_text"),
    ("density", "coverage_text"), ("density", "coverage_figure"),
    ("balance", "visual_centroid_y"),
    ("whitespace", "total_ratio"), ("whitespace", "anomalous_ratio"),
    ("alignment", "left_var"), ("alignment", "right_var"),
    ("consistency", "figure_width_cv"),
    ("readability", "chars_per_line_mean"), ("readability", "leading_ratio"),
)


def summarize_pages(pages: list) -> tuple[dict, dict]:
    """页面列表 -> (paper.aggregates, by_role)。

    聚合量同时给 median/mean/max/p90 —— 均值会掩盖局部问题，
    异常判定用 max/p90（最差页），整体画像用 median（设计方案第八章）。
    """
    def bucket(ps):
        acc = {}
        for grp, key in PAPER_METRICS:
            vals = [(p.get(grp) or {}).get(key) for p in ps]
            agg = _agg([v for v in vals if v is not None])
            if agg["n"]:
                acc[f"{grp}.{key}"] = agg
        return acc

    ok = [p for p in pages if isinstance(p, dict) and "page" in p]
    overall = bucket(ok)
    by_role: dict = {}
    for r in ROLES:
        sub = [p for p in ok if p.get("role") == r]
        if sub:
            by_role[r] = bucket(sub)
    return overall, by_role


def finalize(doc: dict) -> dict:
    """回填 paper 级聚合、role 直方图与缺口清单（阶段 0 用；可重复调用）。"""
    pages = [p for p in doc.get("pages", []) if isinstance(p, dict)]
    hist: dict = {}
    for p in pages:
        hist[p.get("role", "unknown")] = hist.get(p.get("role", "unknown"), 0) + 1
    agg, by_role = summarize_pages(pages)
    paper = doc.setdefault("paper", {})
    paper["n_pages"] = len(pages)
    paper["roles_hist"] = hist
    paper["aggregates"] = agg
    paper["by_role"] = by_role
    paper["status"] = "partial" if pages else "placeholder"
    doc.setdefault("meta", {})["unknown_fields"] = missing_fields(doc)
    return doc


# ---------------------------------------------------------------- 适配现有实现

_LEGACY_KEYS = ("ink_ratio", "top_blank", "bottom_blank", "content_height",
                "max_gap", "max_gap_at", "band", "band_at",
                "left_blank", "right_blank", "top_bottom_ratio")


def from_legacy_visual(vis: dict, doc: dict | None = None,
                       roles: dict | None = None) -> dict:
    """把 visual.analyze_pdf()/visual_report() 的输出映射为 v1 文档。

    能映射的（status=extracted/partial）：
      legacy.*            <- 现有 page_metrics 全部字段（原样保留）
      density.ink_ratio_page <- legacy.ink_ratio      （含图污染，标 partial）
      whitespace.regions  <- 只在存在 max_gap 时给一条粗区域（标 partial）
    其余组一律 placeholder —— 阶段 1 起才有真实提取器。

    roles: {page_no: role} 可选，阶段 1 的角色标注器接入点。
    """
    if vis is None:
        return None
    doc = blank_document() if doc is None else doc
    if vis.get("error"):
        doc["meta"]["notes"].append(f"视觉层不可用：{vis['error']}")
        return finalize(doc)
    roles = roles or {}
    for m in vis.get("pages") or vis.get("metrics") or []:
        if "error" in m or "page" not in m:
            continue
        n = int(m["page"])
        pg = blank_page(n, roles.get(n, "unknown"))
        pg["role_source"] = "rule" if n in roles else None
        pg["legacy"] = {k: m.get(k) for k in _LEGACY_KEYS}
        if isinstance(m.get("ink_ratio"), (int, float)):
            pg["density"]["ink_ratio_page"] = m["ink_ratio"]
            pg["density"]["status"] = "partial"      # 未区分文本/图/表
        if isinstance(m.get("max_gap"), (int, float)) and m["max_gap"] > 0:
            pg["whitespace"]["regions"] = [blank_region(
                area_ratio=None, height_ratio=m.get("max_gap"),
                klass="unknown", confidence=None)]
            pg["whitespace"]["status"] = "partial"   # 单一最大带，无分类
        doc["pages"].append(pg)
    doc["meta"]["notes"].append("由 visual.py 旧输出适配；仅 legacy 与部分字段可用")
    return finalize(doc)


# ---------------------------------------------------------------- 序列化

def dump(doc: dict, path: str) -> str:
    """写 JSON（UTF-8，缩进 2，中文不转义）。"""
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2, sort_keys=False)
        f.write("\n")
    return path


def load(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def coverage_report(doc: dict) -> dict:
    """统计各指标组的 fill/placeholder 情况（阶段 0 缺口盘点用）。"""
    pages = [p for p in doc.get("pages", []) if isinstance(p, dict)]
    out = {}
    for grp in GROUP_PROVENANCE:
        st: dict = {}
        for p in pages:
            s = (p.get(grp) or {}).get("status", "missing")
            st[s] = st.get(s, 0) + 1
        out[grp] = {"provenance": GROUP_PROVENANCE[grp], "status_counts": st}
    return out
