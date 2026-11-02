# -*- coding: utf-8 -*-
"""单页打分 / 整篇打分的分层诊断（2026-11-02）。

**问题（用户 2026-11-02 提出）**：model1 的 P 是全文按次数求和，一个烂页
（同页 20 处溢出）和多页各 1 处溢出可以等价；而 model2 的 A_soft 已经有
「最差 k 页 + 全体均值」的局部/整体聚合。两条线的口径不一致，报告里也
看不出「哪一页最差、差在哪」。

**本模块的定位：只做归因与度量，不改任何判定。**
    - 不改 M1 口径（ρ=15 与 14 项 c* 标定保持有效）；
    - 不改 M2 口径；
    - 只额外产出 page_p / page_a 与三种读法（mean / topk / peak）。

归因怎么来的：
    - 日志缺陷（overfull / underfull / 表格超宽）→ 用 SyncTeX 把**源码行号**
      映到 **PDF 页号**（`engine.synctex_pages`）；
    - 源码卫生项（hygiene）→ 同样按行号映页；
    - 浮动体位置参数（spec_H / unstable_spec）→ 按浮动体所在行映页；
    - 渲染层视觉缺陷（stranded_block / near_empty）→ 本来就有页号；
    - **归不到页的**（vbox 垂直质量、浮动体警告、其余 Warning、质量宏缺失、
      超宽图表达式）→ 记入 unattr_p，明确标出，不硬塞给某一页。

局部 / 整体的三种读法（同一份数据，三种口径都给，不替人做选择）：
    mean : 全篇页均          —— 整体水平
    topk : 最差 k 页均值      —— 局部病灶（k = max(1, round(5%·总页数))）
    peak : 单页最差           —— 最坏情况
"""
from __future__ import annotations

import os

from . import engine
from . import score as S


def _page_of(per, lines) -> dict:
    """源码行号 -> 页号（缺 synctex 时返回空字典，降级为『归不到页』）。"""
    pdf = getattr(per.compile, "pdf_path", None)
    if not pdf:
        return {}
    tex = os.path.splitext(pdf)[0] + ".tex"
    if not os.path.isfile(tex):
        return {}
    try:
        return engine.synctex_pages(tex, lines)
    except Exception:
        return {}


def _log_items(per, req) -> list:
    """把 model1 的日志/源码类缺陷拆成条目：{kind, w, line}。"""
    w = S.PAGE_DEFECT_WEIGHT
    items = []
    for o in per.issues.get("overfull", []):
        items.append({"kind": "overfull", "w": w["overfull"], "line": o.get("line")})
    for o in per.issues.get("underfull", []):
        items.append({"kind": "underfull", "w": w["underfull"], "line": o.get("line")})
    for t in per.issues.get("tables_overwide", []):
        items.append({"kind": "tab_overwide", "w": w["tab_overwide"],
                      "line": t.get("line")})
    for fe in per.source.get("float_envs", []):
        spec = (fe.get("spec") or "").strip()
        if not spec:
            continue
        from . import actions as A
        if spec == "H":
            items.append({"kind": "spec_H", "w": w["spec_H"], "line": fe.get("line")})
        elif A._unstable_spec(spec):
            items.append({"kind": "unstable_spec", "w": w["unstable_spec"],
                          "line": fe.get("line")})
    for h in per.issues.get("hygiene", []):
        items.append({"kind": h.get("kind"),
                      "w": S.HYGIENE_WEIGHT.get(h.get("kind"),
                                                S.DEFAULT_HYGIENE_WEIGHT),
                      "line": h.get("line")})
    return items


def _doc_unattributed_p(per, req) -> tuple[float, list]:
    """文档级、无法归属到某页的 model1 项：(代价, 明细)。"""
    w = S.PAGE_DEFECT_WEIGHT
    total, detail = 0.0, []
    n_vbox = len(per.issues.get("vbox", []))          # 日志无行号
    if n_vbox:
        # 按 kind 分开计价（与 page_defect_score 一致）
        for v in per.issues.get("vbox", []):
            wt = w["vbox_over"] if v.get("kind") == "Overfull" else w["vbox_under"]
            total += wt
        detail.append({"kind": "vbox", "w": total, "n": n_vbox})
    n_float = len(per.issues.get("floats", []))
    if n_float:
        total += w["floatwarn"] * n_float
        detail.append({"kind": "floatwarn", "w": w["floatwarn"] * n_float, "n": n_float})
    n_warn = len(per.issues.get("warnings", []))
    if n_warn:
        total += w["warn"] * n_warn
        detail.append({"kind": "warn", "w": w["warn"] * n_warn, "n": n_warn})
    n_fig = len(S._overwide_figs(per, req))
    if n_fig:
        wt = w["fig_overwide"] * n_fig
        total += wt
        detail.append({"kind": "fig_overwide", "w": wt, "n": n_fig})
    if req.enable_quality_macros and "texopt: 排版质量宏" not in per.src:
        total += w["macros_missing"]
        detail.append({"kind": "macros_missing", "w": w["macros_missing"], "n": 1})
    return total, detail


def page_rows(per, req) -> dict:
    """逐页打分：{rows, unattributed, doc_p, page_a_available}。

    rows 每项：{page, p, a, defects:[{kind,w}], role=None}
      p —— 该页可归属的 model1 缺陷代价之和
      a —— 该页 A_soft 单页损失（SOFT_SPEC 求和，不做文档级聚合）
    """
    vis = (getattr(per, "visual", None) or {})
    vis_pages = {}
    for p in (vis.get("pages") or []):
        if isinstance(p, dict) and p.get("page") is not None:
            vis_pages[int(p["page"])] = p
    # 像素代理角色（2026-11-02）：给逐页诊断标注页类型，便于看出「差页是不是整页图」
    _inks = sorted(x["ink_ratio"] for x in vis_pages.values()
                   if x.get("ink_ratio") is not None)
    _med = _inks[len(_inks) // 2] if _inks else None
    _roles = {n: S.visual.pixel_role(p, n, len(vis_pages), doc_median_ink=_med)
              for n, p in vis_pages.items()}

    items = _log_items(per, req)
    mapping = _page_of(per, [it["line"] for it in items if it.get("line")])
    rows: dict = {n: {"page": n, "p": 0.0, "a": 0.0, "defects": [],
                      "role": (_roles.get(n) or {}).get("role"),
                      "role_source": "pixel-proxy"}
                  for n in vis_pages}
    unattr_items = []
    for it in items:
        pg = mapping.get(it["line"]) if it.get("line") else None
        if pg is None or pg not in rows:
            unattr_items.append(it)
            continue
        rows[pg]["p"] += it["w"]
        rows[pg]["defects"].append({"kind": it["kind"], "w": round(it["w"], 3)})

    # 视觉缺陷（本来就有页号）
    for d in S.visual.visual_defects(vis):
        pg = d.get("page")
        wt = S.VISUAL_DEFECT_M1.get(d.get("kind"))
        if pg is None or wt is None or int(pg) not in rows:
            continue
        sev = 1.0 if d.get("severity") == "high" else 0.6
        rows[int(pg)]["p"] += wt * sev
        rows[int(pg)]["defects"].append({"kind": d.get("kind"),
                                         "w": round(wt * sev, 3)})

    # 单页 A_soft（同一套 SOFT_SPEC，只是不做 top-k 聚合）
    has_a = False
    for n, row in rows.items():
        mp = vis_pages.get(n) or {}
        for metric, spec in S.SOFT_SPEC.items():
            if not spec.get("w"):
                continue
            loss = S.soft_metric_loss(metric, mp.get(metric))
            if loss is not None:
                row["a"] += loss
                has_a = True
        row["a"] = round(row["a"], 3)
        row["p"] = round(row["p"], 3)

    doc_p = S.page_defect_score(per, req)
    doc_unattr, doc_unattr_detail = _doc_unattributed_p(per, req)
    sum_page_p = round(sum(r["p"] for r in rows.values()), 3)
    residual = round(doc_p - sum_page_p, 3)
    return {
        "rows": [rows[n] for n in sorted(rows)],
        "page_p_sum": sum_page_p,
        "doc_p": round(doc_p, 3),
        "unattributed_p": residual,
        "unattributed_detail": doc_unattr_detail,
        "unattributed_log_items": unattr_items,
        "page_a_available": has_a,
        "note": ("attributed_p + unattributed_p 应当等于 doc_p；"
                 "差值来自取整或未能映页的条目（见 unattributed_log_items）。"),
    }


def _topk(values: list, k: int) -> float:
    if not values:
        return 0.0
    v = sorted(values, reverse=True)
    return sum(v[:k]) / max(1, min(k, len(v)))


def summary(per, req) -> dict:
    """局部 / 整体双口径摘要（同一份数据三种读法，不做取舍）。"""
    data = page_rows(per, req)
    rows = data["rows"]
    n = len(rows) or 1
    k = max(1, int(round(0.05 * n)))
    p_vals = [r["p"] for r in rows]
    a_vals = [r["a"] for r in rows] if data["page_a_available"] else []
    worst = sorted(rows, key=lambda r: (r["p"], r["a"]), reverse=True)[:3]
    return {
        **data,
        "pages": len(rows),
        "topk": k,
        "p": {
            "mean": round(sum(p_vals) / n, 3),
            "topk": round(_topk(p_vals, k), 3),
            "peak": round(max(p_vals) if p_vals else 0.0, 3),
            "total": data["doc_p"],
            "unattributed": data["unattributed_p"],
        },
        "a": ({
            "mean": round(sum(a_vals) / len(a_vals), 3),
            "topk": round(_topk(a_vals, k), 3),
            "peak": round(max(a_vals), 3),
        } if a_vals else None),
        "worst_pages": worst,
    }


def report_md(diag: dict) -> list:
    """报告里的「逐页诊断」小节（Markdown 行）。"""
    if not diag or not diag.get("rows"):
        return []
    pd = diag["p"]
    k = diag.get("topk", 1)
    out = ["### 逐页诊断（局部 vs 整体，仅诊断、不参与验收）\n",
           f"- 页数 {diag['pages']}，最差 k 页口径 k={k}（k = max(1, round(5%·页数))）",
           f"- **model1 · P 的三种读法**：页均 {pd['mean']} ｜ 最差{k}页 {pd['topk']} "
           f"｜ 单页峰值 {pd['peak']} ｜ 全篇 {pd['total']}"
           f"（其中 {pd['unattributed']} 归不到具体页）"]
    if diag.get("a"):
        ad = diag["a"]
        out.append(f"- **model2 · A_soft 的三种读法**：页均 {ad['mean']} ｜ "
                   f"最差{k}页 {ad['topk']} ｜ 单页峰值 {ad['peak']}")
    unattr = diag.get("unattributed_detail") or []
    if unattr:
        parts = [f"{u['kind']}×{u['n']}" for u in unattr]
        out.append(f"- 归不到页的缺陷：{', '.join(parts)}"
                   "（日志不给页号，或属文档级结构项）")
    out += ["", "| 页 | P（可归属） | A_soft | 主要缺陷 |", "|---|---|---|---|"]
    for r in diag["worst_pages"]:
        kinds = ", ".join(f"{d['kind']}" for d in r["defects"][:4]) or "—"
        out.append(f"| {r['page']} | {r['p']} | {r['a']} | {kinds} |")
    out.append("")
    return out
