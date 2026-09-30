# -*- coding: utf-8 -*-
"""阶段 4 在线影子评估：把 A_profile 接到 texopt 的报告里（lambda = 0 影子模式）。

原则（设计方案 13.1 - 13.4）：
  * A = A_defect + lambda * A_profile；lambda 默认 **0**（影子模式：
    只报告、不参与验收、不改变任何接受/回滚判定）；
  * A_defect（score.py 的确定性缺陷加权计数）口径**完全不变**，回归照旧；
  * 目标冲突门控（13.2）：审美分改善不得让缺陷类指标变差 —— `gate()` 给判据；
  * 版本化（13.4）：报告带 profile_version / venue / role / n / 可信度。

成本（13.5）：底层指标本来就要提取（阶段 3 已缓存全库），在线只算待优化论文。
可用环境变量 `TEXOPT_NO_SHADOW=1` 关闭（例如在受限环境跑回归时）。
"""
from __future__ import annotations

import json
import os

from . import aesthetic as AE
from . import extract as EX

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROFILE_CANDIDATES = (
    os.path.join(ROOT, "datasets", "conf-specs", "metrics", "profiles",
                 "aesthetic_profile.json"),
)
LAMBDA = 0.0          # 影子模式：不参与验收


def enabled() -> bool:
    return os.environ.get("TEXOPT_NO_SHADOW", "") not in ("1", "true", "yes")


def default_profile_path():
    for p in PROFILE_CANDIDATES:
        if os.path.isfile(p):
            return p
    return None


def load_profile(path: str | None = None):
    """读档案；缺 mahalanobis 块（阶段 4 之前构建的档案）时返回 None 并说明。"""
    path = path or default_profile_path()
    if not path or not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            prof = json.load(f)
    except Exception:
        return None
    if not (prof.get("mahalanobis") or {}).get("level"):
        return None
    return prof


def evaluate_pdf(pdf_path: str, profile: dict, *, venue: str | None = None,
                 lambda_: float = LAMBDA, pages=None) -> dict:
    """PDF -> 提取页级指标 -> 档案判定（D^2 + 带外损失 + A_profile）。"""
    doc = EX.extract_pdf(pdf_path, venue=venue)
    rep = AE.evaluate_doc(doc, profile, venue=venue, lambda_=lambda_)
    rep["pdf"] = os.path.basename(pdf_path)
    return rep


def gate(base: dict | None, cur: dict | None, *, tol: float = 1e-9) -> dict:
    """目标冲突门控（方案 13.2）。

    仅当「缺陷类指标不变差」且「A_profile 确有改善」时才允许以审美为由接受改动。
    base/cur: {"a_defect": float, "a_profile": float|None, "hard": int}
    影子模式下该门控**不参与**主循环，只用于报告与后续阶段的接入。
    """
    if not base or not cur:
        return {"allow": True, "reason": "缺少可比快照（影子模式不影响主循环）"}
    d_defect = (cur.get("a_defect") or 0.0) - (base.get("a_defect") or 0.0)
    d_hard = (cur.get("hard") or 0) - (base.get("hard") or 0)
    ap0, ap1 = base.get("a_profile"), cur.get("a_profile")
    if d_hard > 0:
        return {"allow": False, "reason": f"缺陷类指标变差（hard +{d_hard}）",
                "d_defect": round(d_defect, 6), "d_hard": d_hard}
    if d_defect > tol:
        return {"allow": False, "reason": f"A_defect 变差（+{d_defect:.3f}）",
                "d_defect": round(d_defect, 6), "d_hard": d_hard}
    if ap0 is not None and ap1 is not None and ap1 >= ap0 - tol:
        return {"allow": False, "reason": "A_profile 无改善",
                "d_defect": round(d_defect, 6), "d_hard": d_hard}
    return {"allow": True, "reason": "缺陷不变差且 A_profile 改善",
            "d_defect": round(d_defect, 6), "d_hard": d_hard}


def summarize(rep: dict | None) -> list[str]:
    """影子报告 -> report.md 用的 markdown 行（无数据时如实说明）。"""
    if not rep:
        return ["- 未运行（无 PDF 或已用 `TEXOPT_NO_SHADOW=1` 关闭）"]
    if rep.get("status") == "error":
        return [f"- 运行失败（已隔离，不影响验收）：{rep.get('error')}"]
    if rep.get("status") == "no-profile":
        return ["- 未运行：档案缺 `mahalanobis` 块（需先跑 "
                "`tools/build_profile.py` 重建阶段 2/4 档案）"]
    paper = rep.get("paper") or {}
    dims = paper.get("dim_norm_p90") or {}
    worst = sorted(dims.items(), key=lambda kv: -kv[1])[:3]
    L = [f"- **A_defect**（现行口径，参与验收）：{rep.get('a_defect')}；"
         f"**A_profile**（档案偏离度，等权排序量）：{paper.get('a_profile')}"
         f"（λ={rep.get('lambda')}，影子：不影响验收）",
         f"- 页级：{rep.get('n_pages_scored')}/{rep.get('n_pages')} 页参与判定；"
         f"D² 中位 {paper.get('median_d2')}、P90 {paper.get('d2_p90')}；"
         f"异常页（p<0.05）{paper.get('n_anomalous_pages')} 页",
         "- 判定档：" + ("，".join(f"{k}→{v}" for k, v in (rep.get("levels_used") or {}).items())
                     or "—")]
    if worst:
        L.append("- 最偏离维度（相对档案 P90 的倍率）："
                 + "，".join(f"{k}={v}" for k, v in worst))
    L.append("> A_profile 只报告不参与验收（λ=0）；权重为方案 10.3「步骤一」等权，"
             "只保证排序可复现，不主张绝对分数可比。")
    return L
