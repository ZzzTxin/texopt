# -*- coding: utf-8 -*-
"""阶段 8：外部验证（方案 13）。

三件事，全部复用现有感知/评分层，**不引入新的模型或新的分数定义**：

E1 端到端退化（真实文档 + 真实优化器）
    取真实 `.tex` 文档（含真实论文工程），注入**源码级**退化，跑真实闭环
    （编译 → 感知 → 评分 → 动作 → 重编译），检验：
      * 退化使整篇 A 上升（对退化档数单调不降）；
      * 优化器能把 A 拉回 ≤ 原始（干净稿）水平；
      * 影子 A_profile（λ=0）随退化上升、随修复回落。
    这与阶段 5 的 12.1 不同：12.1 在**缓存页指标**上注入；这里走**真编译**。

E2 第二套工具链复测
    同一批真实论文页，用两条独立测量路径分别量取：
      ① 矢量/文本层：pdfminer（`texopt/extract.py`）→ `page_metrics.v1`
      ② 像素层：pdftoppm 灰图（`texopt/visual.py` + `page_metrics.page_metrics`）
    比较三个同义量的**排序一致性**（Spearman）与绝对偏差，给出分歧最大的页。
    诚实边界：两条路径读的是同一批 PDF，只是**渲染/解析路径不同**，
    不是两套完全独立的工具链；量纲不同的量只比较排序。

E3 论文级报告
    按**论文**（而非按页池化）聚合档案判定，输出每篇的 A_profile / D² / 异常页数，
    并与页级池化口径对照 —— 直接回应阶段 7 记录的局限 L4（池化稀释）。

所有函数都是纯计算，不写盘、不发请求；写盘由 `tools/eval_external.py` 负责。
"""
from __future__ import annotations

import json
import math
import os
import re

from . import aesthetic as AE
from . import evalproto as EP
from . import extract as EX
from . import profile as PF
from . import visual

# ---------------------------------------------------------------- E2 口径

#: (矢量层 flat key, 像素层 key, 是否同量纲可比较绝对值, 说明)
COMPARABLE = [
    ("whitespace.total_ratio", "non_ink_ratio", False,
     "整页留白占比（矢量：留白结构量 / 像素：1-墨迹占比；量纲不同，只比排序）"),
    ("whitespace.trailing_ratio", "bottom_blank", True,
     "页尾留白：矢量=版心内页尾留白区域占比（排满页恒 0）；像素=最后一行墨迹以下的整页高度占比（含页码带）"),
    ("balance.visual_centroid_y", "centroid_y", True,
     "视觉重心纵向位置（0=页底,1=页顶；两边同约定，可比较绝对值）"),
]


def pixel_centroid(m: dict) -> float | None:
    """像素层：上下半页墨迹比 -> 视觉重心纵向位置。

    约定与矢量层 `balance.visual_centroid_y` **一致**：0 = 页底，1 = 页顶
    （矢量层是 `(格子中心 y - frame.bottom) / height`，y 向上）。
    近似：上半页中心 0.75、下半页中心 0.25，按墨迹加权。
    """
    r = m.get("top_bottom_ratio")
    if r is None:
        return None
    try:
        r = float(r)
    except (TypeError, ValueError):
        return None
    if r < 0 or r != r:
        return None
    return round(1.0 - (0.25 * r + 0.75) / (r + 1.0), 4)


def vector_pages(pdf_path: str, *, max_pages: int | None = None) -> list[dict]:
    """矢量/文本层量取（path ①）：pdfminer -> page_metrics.v1。"""
    doc = EX.extract_pdf(pdf_path, max_pages=max_pages)
    out = []
    for p in doc.get("pages") or []:
        flat = dict(PF.page_metric_items(p))
        flat["page"] = p.get("page") or p.get("no")
        out.append(flat)
    return out


def pixel_pages(pdf_path: str, *, dpi: int = 50, tmpdir: str,
                max_pages: int | None = None) -> list[dict]:
    """像素层量取（path ②）：pdftoppm 灰图 -> page_metrics。"""
    res = visual.analyze_pdf(pdf_path, tmpdir, dpi=dpi)
    if res.get("error"):
        raise RuntimeError(res["error"])
    out = []
    for m in res.get("pages") or []:
        if "error" in m:
            continue
        m = dict(m)
        m["non_ink_ratio"] = round(1.0 - float(m.get("ink_ratio") or 0.0), 4)
        m["centroid_y"] = pixel_centroid(m)
        out.append(m)
        if max_pages and len(out) >= max_pages:
            break
    return out


def _median(values: list[float]) -> float | None:
    v = sorted(x for x in values if x is not None)
    if not v:
        return None
    n = len(v)
    return v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2.0


def _p90(values: list[float]) -> float | None:
    v = sorted(x for x in values if x is not None)
    if not v:
        return None
    i = min(len(v) - 1, int(round(0.9 * (len(v) - 1))))
    return v[i]


def _rank_corr(x: list[float], y: list[float]) -> float | None:
    """Spearman 秩相关（n≥3 即可）。

    不用 `profile.spearman`：那个函数是给**全库档案统计**用的，对样本量有
    n≥8 的硬门槛；这里比较的是单篇论文的几页，6 页也要给结论。
    """
    if len(x) != len(y) or len(x) < 3:
        return None
    rx, ry = PF._rank(x), PF._rank(y)
    n = len(rx)
    mx, my = sum(rx) / n, sum(ry) / n
    dx = math.sqrt(sum((a - mx) ** 2 for a in rx))
    dy = math.sqrt(sum((b - my) ** 2 for b in ry))
    if dx == 0 or dy == 0:                       # 常数序列：无秩信息
        return None
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    return round(num / (dx * dy), 4)


def compare_pair(vec: list[dict], pix: list[dict], vkey: str, pkey: str,
                 same_unit: bool) -> dict:
    """两个同义量的页级比较（按页号对齐）。"""
    vmap = {p["page"]: p.get(vkey) for p in vec if p.get("page")}
    pmap = {p["page"]: p.get(pkey) for p in pix if p.get("page")}
    pages = sorted(set(vmap) & set(pmap))
    xs, ys, diffs, worst = [], [], [], []
    for n in pages:
        a, b = vmap[n], pmap[n]
        if a is None or b is None:
            continue
        xs.append(float(a))
        ys.append(float(b))
        d = float(b) - float(a)
        diffs.append(abs(d))
        worst.append({"page": n, "vector": round(float(a), 4),
                      "pixel": round(float(b), 4), "delta": round(d, 4)})
    rho = _rank_corr(xs, ys)
    worst.sort(key=lambda w: -abs(w["delta"]))
    # 退化（无秩信息）：某一侧在整篇里是常数 —— 秩相关没有定义。
    # 典型例子：矢量层 `whitespace.trailing_ratio` 在**排满的正文页**上恒为 0
    #（版心内没有页尾留白区域），此时「比较」只在末页之类的页上才有意义。
    const_v = len(set(xs)) <= 1
    const_p = len(set(ys)) <= 1
    side = "both" if (const_v and const_p) else ("vector" if const_v
                                                else ("pixel" if const_p else None))
    return {"vector_key": vkey, "pixel_key": pkey, "same_unit": bool(same_unit),
            "n_pages": len(xs), "spearman": rho,
            "median_abs_delta": round(_median(diffs), 4) if diffs else None,
            "p90_abs_delta": round(_p90(diffs), 4) if diffs else None,
            "degenerate": bool(side and len(xs) >= 3),
            "constant_side": side,
            "worst": worst[:5]}


def _last_page_compare(rows: list[dict]) -> dict:
    """E2 补充：**抽样范围内最后一页**的 trailing_ratio vs bottom_blank（跨论文）。

    注意：E2 只取每篇前 `max_pages` 页，所以这里的「末页」是**抽样范围的最后一页**，
    不是论文真正的最后一页；正文页排满时矢量侧 trailing_ratio 恒为 0，该量的
    可辨识性在抽样窗口内就是 0，如实列出。
    """
    pairs = [(r["vector"], r["pixel"]) for r in rows
             if isinstance(r.get("vector"), (int, float))
             and isinstance(r.get("pixel"), (int, float))]
    xs = [float(a) for a, _ in pairs]
    ys = [float(b) for _, b in pairs]
    diffs = [abs(b - a) for a, b in pairs]
    return {"metric": "whitespace.trailing_ratio vs bottom_blank（抽样范围最后一页）",
            "n_papers": len(pairs),
            "n_nonzero_vector": sum(1 for a in xs if a > 0),
            "spearman": _rank_corr(xs, ys),
            "median_abs_delta": round(_median(diffs), 4) if diffs else None,
            "rows": rows}


def compare_toolchains(pdf_paths: list[dict], *, dpi: int = 50, tmpdir: str,
                       max_pages: int | None = None) -> dict:
    """E2：多篇真实论文页，两条测量路径逐量比较。

    pdf_paths: [{"pdf": path, "paper": sid}]（paper 仅用于报告）
    """
    os.makedirs(tmpdir, exist_ok=True)
    papers, acc = [], {c[0]: [] for c in COMPARABLE}
    last_rows = []            # 末页对照（trailing_ratio 在排满页上恒 0，只在末页非平凡）
    for item in pdf_paths:
        pdf = item["pdf"]
        try:
            vec = vector_pages(pdf, max_pages=max_pages)
            pix = pixel_pages(pdf, dpi=dpi, tmpdir=tmpdir, max_pages=max_pages)
        except Exception as exc:                       # 单篇失败不拖垮整批
            papers.append({"paper": item.get("paper") or os.path.basename(pdf),
                           "status": "error", "error": f"{type(exc).__name__}: {exc}"})
            continue
        row = {"paper": item.get("paper") or os.path.basename(pdf),
               "status": "ok", "n_vector": len(vec), "n_pixel": len(pix),
               "pages": []}
        for vkey, pkey, same, _doc in COMPARABLE:
            cmp = compare_pair(vec, pix, vkey, pkey, same)
            acc[vkey].append(cmp)
            row["pages"].append({k: cmp[k] for k in
                                 ("vector_key", "pixel_key", "n_pages",
                                  "spearman", "median_abs_delta", "p90_abs_delta",
                                  "degenerate", "constant_side")})
        if vec and pix:
            last_rows.append({"paper": row["paper"], "page": vec[-1].get("page"),
                              "vector": vec[-1].get("whitespace.trailing_ratio"),
                              "pixel": pix[-1].get("bottom_blank")})
        papers.append(row)

    summary = []
    for vkey, pkey, same, doc in COMPARABLE:
        rows = acc[vkey]
        rhos = [c["spearman"] for c in rows if c["spearman"] is not None]
        md = [c["median_abs_delta"] for c in rows if c["median_abs_delta"] is not None]
        summary.append({
            "vector_key": vkey, "pixel_key": pkey, "same_unit": same,
            "doc": doc, "n_papers": len(rows),
            "n_with_rank": len(rhos),
            "n_degenerate": sum(1 for c in rows if c.get("degenerate")),
            "spearman_median": round(_median(rhos), 4) if rhos else None,
            "spearman_min": round(min(rhos), 4) if rhos else None,
            "median_abs_delta_overall": round(_median(md), 4) if md else None,
        })
    return {"schema": "stage8.toolchains.v1", "dpi": dpi,
            "max_pages": max_pages, "papers": papers, "summary": summary,
            "last_page_trailing": _last_page_compare(last_rows)}


# ---------------------------------------------------------------- E1 退化

def _insert_before(src: str, match: re.Match, text: str) -> str:
    return src[:match.start()] + text + src[match.start():]


def deg_vspace(src: str) -> str:
    """在第二个 \\section 前插入 \\vspace{3cm}（过大手动垂直间距）。"""
    ms = list(re.finditer(r"\\section\*?\{", src))
    if len(ms) < 2:
        return src
    return _insert_before(src, ms[1], "\\vspace{3cm}\n")


def deg_pagebreak(src: str) -> str:
    """在第二个 \\section 前插入 \\newpage（手动分页）。"""
    ms = list(re.finditer(r"\\section\*?\{", src))
    if len(ms) < 2:
        return src
    return _insert_before(src, ms[1], "\\newpage\n")


def deg_float_H(src: str) -> str:
    """把浮动体位置参数改成 [H]（强排）。float 宏包缺失时补上。"""
    out, n = re.subn(
        r"\\begin\{(figure|table)(\*?)\}\s*\[[^\]]*\]",
        lambda m: "\\begin{%s%s}[H]" % (m.group(1), m.group(2)), src)
    if not n:
        return src
    if "\\usepackage{float}" not in out and "\\usepackage{placeins}" not in out:
        if re.search(r"\\usepackage(?:\[[^\]]*\])?\{[^}]*\}", out):
            out = re.sub(r"(\\usepackage(?:\[[^\]]*\])?\{[^}]*\})",
                         lambda m: m.group(1) + "\n\\usepackage{float}", out, count=1)
        else:                       # 没有任何 \usepackage：插在 \begin{document} 前
            out = out.replace("\\begin{document}",
                              "\\usepackage{float}\n\\begin{document}", 1)
    return out


def deg_overwide(src: str) -> str:
    """第一处 \\includegraphics 的宽度放大到 1.25\\linewidth（超宽图）。"""
    m = re.search(r"\\includegraphics\s*\[[^\]]*\]", src)
    if not m:
        return src
    return src[:m.start()] + "\\includegraphics[width=1.25\\linewidth]" + src[m.end():]


DEGRADERS = {
    "vspace": deg_vspace,
    "pagebreak": deg_pagebreak,
    "float_H": deg_float_H,
    "overwide": deg_overwide,
}

#: 默认退化档：逐档累加（用于检验 A 对退化档数单调不降）
LADDER = [("vspace",), ("vspace", "pagebreak"),
          ("vspace", "pagebreak", "float_H"),
          ("vspace", "pagebreak", "float_H", "overwide")]


def degrade_source(src: str, kinds) -> str:
    """按顺序施加源码级退化；未知名字抛 ValueError（不静默跳过）。"""
    out = src
    for k in kinds:
        fn = DEGRADERS.get(k)
        if fn is None:
            raise ValueError(f"未知退化：{k}")
        out = fn(out)
    return out


def measure_pipeline(tex_path: str, outdir: str, req, *, src_override: str | None = None) -> dict:
    """把一个 .tex 跑完整闭环，返回可比较的结果摘要。

    src_override：把改过的源码先写进工作目录再跑（退化稿），避免污染原件。
    """
    import shutil
    from .core import Optimizer

    if src_override is not None:
        os.makedirs(outdir, exist_ok=True)
        work_dir = os.path.join(outdir, "_src")
        os.makedirs(work_dir, exist_ok=True)
        for name in os.listdir(os.path.dirname(tex_path)):
            src = os.path.join(os.path.dirname(tex_path), name)
            if os.path.abspath(src) == os.path.abspath(os.path.dirname(tex_path) + "/workbench"):
                continue
            dst = os.path.join(work_dir, name)
            if os.path.isdir(src):
                shutil.copytree(src, dst, dirs_exist_ok=True)
            else:
                shutil.copy2(src, dst)
        with open(os.path.join(work_dir, os.path.basename(tex_path)), "w",
                  encoding="utf-8") as f:
            f.write(src_override)
        tex_path = os.path.join(work_dir, os.path.basename(tex_path))

    opt = Optimizer(tex_path, req, os.path.join(outdir, "run"))
    res = opt.run()
    sh = (res.get("aesthetic_shadow") or {})
    shb = (res.get("aesthetic_shadow_baseline") or {})
    paper_b = (shb.get("paper") or {})
    return {"status": res.get("status"), "a": res.get("a"), "l": res.get("l"),
            "a_before": res.get("a_before"), "pages": res.get("pages"),
            "pages_before": res.get("pages_before"),
            "total": res.get("total"), "total_before": res.get("total_before"),
            "accepted": res.get("accepted"), "attempts": res.get("attempts"),
            "a_profile": sh.get("a_profile"), "d2_p90": sh.get("d2_p90"),
            "n_anomalous": sh.get("n_anomalous_pages"),
            # 退化态（修复前）的量：E1 的单调性看这一组
            "a_profile_before": paper_b.get("a_profile"),
            "d2_p90_before": paper_b.get("d2_p90"),
            "n_anomalous_before": paper_b.get("n_anomalous_pages"),
            "shadow_before_status": shb.get("status"),
            "pdf": res.get("pdf"), "tex": res.get("tex"),
            "conference_status": (res.get("conference") or {}).get("page_advisory")}


def sequential_monotone(vals) -> bool | None:
    """非降序列判定；任一值为 None 则返回 None（未知，不算通过）。"""
    if not vals or any(v is None for v in vals):
        return None
    try:
        return all(float(vals[i]) <= float(vals[i + 1]) + 1e-9
                   for i in range(len(vals) - 1))
    except (TypeError, ValueError):
        return None


def end_to_end_doc(doc: dict, *, req=None, outdir: str, levels=None) -> dict:
    """E1 单篇：干净 → 逐档退化 → 每档都跑完整闭环。

    每档记两组量：
      * `a_before` / `a_profile_before` —— 退化态（闭环**修复前**）的 A 与影子 A_profile；
      * `a` / `a_profile`         —— 闭环修复后的终态量。
    单调性看前者（退化是否真的变差），修复能力看后者是否回到干净稿水平。
    只看终态会因闭环把源码级退化修回去而“测不出退化”——这是本实验原先的缺陷。
    """
    from .requirements import Requirement

    req = req or Requirement(verbose=False)
    levels = list(levels if levels is not None else LADDER)
    tex = doc["tex"]
    src = open(tex, encoding="utf-8", errors="replace").read()

    clean = measure_pipeline(tex, os.path.join(outdir, "clean"), req)
    seq = []
    for i, kinds in enumerate(levels):
        degraded = degrade_source(src, kinds)
        m = measure_pipeline(tex, os.path.join(outdir, f"deg{i + 1}"), req,
                             src_override=degraded)
        m["kinds"] = list(kinds)
        seq.append(m)

    worst = seq[-1]
    a_clean = clean.get("a")
    before_series = [m.get("a_before") for m in seq]
    prof_series = [m.get("a_profile_before") for m in seq]
    mono = sequential_monotone(before_series)
    prof_mono = sequential_monotone(prof_series)
    visible = None
    if before_series[0] is not None and before_series[-1] is not None:
        visible = bool(before_series[-1] >= before_series[0] - 1e-9)
    repaired_ok = (a_clean is not None and worst.get("a") is not None
                   and worst["a"] <= a_clean + 1e-9)
    below_before = (worst.get("a") is not None and worst.get("a_before") is not None
                    and worst["a"] <= worst["a_before"] + 1e-9)
    return {"name": doc.get("name") or os.path.basename(tex),
            "tex": tex, "clean": clean, "levels": seq,
            "series": {"a_before": before_series,
                       "a": [m.get("a") for m in seq],
                       "a_profile_before": prof_series,
                       "a_profile": [m.get("a_profile") for m in seq],
                       "pages_before": [m.get("pages_before") for m in seq],
                       "pages": [m.get("pages") for m in seq]},
            "checks": {"degradation_monotone": mono,
                       "degradation_visible": visible,
                       "shadow_monotone_before": prof_mono,
                       "repaired_back_to_clean": bool(repaired_ok),
                       "repaired_below_before": bool(below_before)}}


# ---------------------------------------------------------------- E3 论文级

def paper_docs(metrics_dir: str, *, limit: int | None = None,
               sids: list[str] | None = None) -> list[dict]:
    """读缓存 page_metrics -> [{sid, doc}]（保持原始文档结构，供 evaluate_doc）。"""
    out = []
    names = sorted(fn for fn in os.listdir(metrics_dir) if fn.endswith(".json"))
    if sids:
        want = set(sids)
        names = [n for n in names if n[:-5] in want]
    for fn in names:
        try:
            with open(os.path.join(metrics_dir, fn), encoding="utf-8") as f:
                doc = json.load(f)
        except Exception:
            continue
        if not doc.get("pages"):
            continue
        out.append({"sid": fn[:-5], "doc": doc})
        if limit and len(out) >= limit:
            break
    return out


#: 可辨识性抽查的原始量（非损失）：这类量如果在语料上恒为 0，页级比较就没意义
COVERAGE_DIMS = ("whitespace.trailing_ratio", "whitespace.total_ratio",
                 "balance.visual_centroid_y", "balance.d_mid",
                 "density.coverage_text", "ratio.fig_text")


def paper_level_report(metrics_dir: str, profile: dict, *,
                       limit: int | None = None, sids: list[str] | None = None,
                       venue: str | None = None, drop_dims=None) -> dict:
    """E3：按论文聚合档案判定，并与**页级池化**口径对照。"""
    docs = paper_docs(metrics_dir, limit=limit, sids=sids)
    papers, pooled_pages = [], []
    cov = {d: {"n": 0, "n_nonzero": 0} for d in COVERAGE_DIMS}
    for item in docs:
        doc = item["doc"]
        for p in (doc.get("pages") or []):
            flat = dict(PF.page_metric_items(p))
            for d in COVERAGE_DIMS:
                v = flat.get(d)
                if v is None:
                    continue
                try:
                    v = float(v)
                except (TypeError, ValueError):
                    continue
                cov[d]["n"] += 1
                if abs(v) > 1e-12:
                    cov[d]["n_nonzero"] += 1
        meta = doc.get("doc") or {}
        v = venue or meta.get("venue")
        rep = AE.evaluate_doc(doc, profile, venue=v, lambda_=0.0,
                              drop_dims=drop_dims)
        paper = rep.get("paper") or {}
        pages = [p for p in (rep.get("per_page") or []) if p.get("status") == "ok"]
        for p in pages:
            for ln, x in (p.get("losses") or {}).items():
                if isinstance(x, (int, float)):
                    pooled_pages.append({"paper": item["sid"], "page": p.get("page"),
                                         "dim": ln, "loss": float(x)})
        papers.append({
            "sid": item["sid"], "venue": v, "n_pages": meta.get("pages"),
            "n_scored": len(pages),
            "a_profile": paper.get("a_profile"),
            "d2_p90": paper.get("d2_p90"),
            "median_d2": paper.get("median_d2"),
            "n_anomalous_pages": paper.get("n_anomalous_pages"),
            "dim_norm_p90": paper.get("dim_norm_p90"),
        })
    a_vals = [p["a_profile"] for p in papers if isinstance(p["a_profile"], (int, float))]
    per_dim = {}
    for r in pooled_pages:
        per_dim.setdefault(r["dim"], []).append(r["loss"])
    pooled = []
    for dim, vals in sorted(per_dim.items()):
        pooled.append({"dim": dim, "n_page_values": len(vals),
                       "page_pooled_median": round(_median(vals), 4) if vals else None})
    return {"schema": "stage8.paper_level.v1", "n_papers": len(papers),
            "papers": papers,
            "paper_a_profile_median": round(_median(a_vals), 4) if a_vals else None,
            "paper_a_profile_p90": round(_p90(a_vals), 4) if a_vals else None,
            "page_pooled_by_dim": pooled,
            "metric_coverage": {d: {"n": r["n"], "n_nonzero": r["n_nonzero"],
                                    "share_nonzero": (round(r["n_nonzero"] / r["n"], 4)
                                                      if r["n"] else None)}
                                for d, r in cov.items()}}


# ---------------------------------------------------------------- 汇总入口

def run_all(*, pdf_items=None, metrics_dir: str | None = None, profile: dict | None = None,
            tmpdir: str | None = None, e2_dpi: int = 50, e2_max_pages: int | None = None,
            e3_limit: int | None = None, e3_venue: str | None = None,
            drop_dims=None, docs: list[dict] | None = None,
            e1_outdir: str | None = None, e1_levels=None) -> dict:
    """跑齐 E1/E2/E3（各段可单独缺省）。"""
    out = {"schema": "stage8.external.v1"}
    if docs and e1_outdir:
        out["e1_end_to_end"] = [end_to_end_doc(d, outdir=os.path.join(e1_outdir, d["name"]),
                                               levels=e1_levels) for d in docs]
    if pdf_items and tmpdir:
        out["e2_toolchains"] = compare_toolchains(pdf_items, dpi=e2_dpi,
                                                  tmpdir=tmpdir,
                                                  max_pages=e2_max_pages)
    if metrics_dir and profile:
        out["e3_paper_level"] = paper_level_report(metrics_dir, profile,
                                                   limit=e3_limit, venue=e3_venue,
                                                   drop_dims=drop_dims)
    return out
