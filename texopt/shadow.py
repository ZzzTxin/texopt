# -*- coding: utf-8 -*-
"""阶段 4/6 在线影子评估：把 A_profile 接到 texopt 的报告里（lambda = 0 影子模式）。

阶段 6（影子模式接入 texopt，λ=0，仅报告）在本模块上的增量：
  * `evaluate_pdf(..., profile_path=...)`：档案路径可指定（默认随附档案）；
  * `snapshot(rep)`：写 state.json 的**版本化**快照（13.4：profile_version /
    venue / 判定档 / 页数 / 可信度口径都在，跨时间可比）；
  * `report_md(...)`：人读影子报告（`aesthetic_shadow.md`），带逐轮 trace、
    最偏离维度、异常页与**人工核对清单**；
  * λ 永远为 0，本模块**不提供**改变判定口径的入口——接入点是 `core.py` 里
    「已经判定完接受/回滚之后」的观测钩子，因此影子不可能影响优化走向。

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
GATE_CANDIDATES = (
    os.path.join(ROOT, "datasets", "conf-specs", "metrics", "profiles",
                 "eval_gate.json"),
)


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


def load_gate(path: str | None = None) -> dict | None:
    """读阶段 5 门槛（方案 12.6）；缺文件 → None（不剔除任何维）。"""
    path = path or default_gate_path()
    if not path or not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            g = json.load(f)
    except Exception:
        return None
    return g if g.get("schema") == "eval_gate.v1" else None


def default_gate_path():
    for p in GATE_CANDIDATES:
        if os.path.isfile(p):
            return p
    return None


def gate_drop_dims(path: str | None = None) -> list:
    """阶段 5 门槛里未通过的维度（方案 12.6：只能作报告项，不得参与 A）。"""
    g = load_gate(path)
    return list((g or {}).get("dropped") or [])


def evaluate_pdf(pdf_path: str, profile: dict, *, venue: str | None = None,
                 lambda_: float = LAMBDA, pages=None, drop_dims=None,
                 profile_path: str | None = None) -> dict:
    """PDF -> 提取页级指标 -> 档案判定（D^2 + 带外损失 + A_profile）。

    `drop_dims=None` 时**自动**载入阶段 5 门槛（eval_gate.json），未通过的维不参与判定。
    """
    if drop_dims is None:
        drop_dims = gate_drop_dims()
    doc = EX.extract_pdf(pdf_path, venue=venue)
    rep = AE.evaluate_doc(doc, profile, venue=venue, lambda_=lambda_,
                          drop_dims=drop_dims)
    rep["pdf"] = os.path.basename(pdf_path)
    rep["mode"] = "shadow"
    if profile_path:
        rep["profile_file"] = os.path.basename(profile_path)
    return rep


def snapshot(rep: dict | None) -> dict | None:
    """影子结果 -> state.json 用的**版本化**快照（方案 13.4）。

    只留可跨时间比较的字段：档案版本 / 会议 / 判定档 / 页数 / 分数 / 门槛剔除。
    """
    if not rep:
        return None
    if rep.get("status"):                       # error / no-profile
        return {"status": rep.get("status"),
                "error": rep.get("error"), "lambda": LAMBDA, "mode": "shadow"}
    paper = rep.get("paper") or {}
    return {
        "schema": "aesthetic_shadow.v1",
        "mode": "shadow", "lambda": rep.get("lambda", LAMBDA),
        "profile_version": rep.get("profile_version"),
        "profile_file": rep.get("profile_file"),
        "venue": rep.get("venue"),
        "a_defect": rep.get("a_defect"),          # 现行口径（参与验收的那个 A）
        "a_profile": paper.get("a_profile"),      # 档案偏离度（只报告）
        "a_effective": rep.get("a_effective"),
        "n_pages": rep.get("n_pages"),
        "n_pages_scored": rep.get("n_pages_scored"),
        "d2_p90": paper.get("d2_p90"), "median_d2": paper.get("median_d2"),
        "n_anomalous_pages": paper.get("n_anomalous_pages"),
        "levels_used": rep.get("levels_used"),
        "dropped_dims": rep.get("dropped_dims"),
    }


def _worst_dims(rep: dict, k: int = 3):
    paper = rep.get("paper") or {}
    dims = paper.get("dim_norm_p90") or paper.get("dim_norm_top") or {}
    return sorted(dims.items(), key=lambda kv: -kv[1])[:k]


def report_md(rep: dict | None, *, baseline: dict | None = None,
              trace: list | None = None, gate_res: dict | None = None,
              title: str = "审美档案影子评估（阶段 6，λ=0，仅报告）") -> list[str]:
    """影子结果 -> 人读 markdown 行（`workbench/<run>/aesthetic_shadow.md`）。

    人工核对要看的东西按顺序摆好：版本/档 → 分数 → 页级统计 → 最偏离维度 →
    异常页 → 门槛剔除 → 逐轮 trace → 门控 → 核对清单。无数据时如实说明，不包装。
    """
    L = [f"## {title}", ""]
    if not rep:
        return L + ["- 未运行（无 PDF，或该轮已被 `TEXOPT_NO_SHADOW=1` / "
                    "`--no-aesthetic-shadow` 关闭）", ""]
    if rep.get("status") == "error":
        return L + [f"- 运行失败（已隔离，不影响验收）：{rep.get('error')}", ""]
    if rep.get("status") == "no-profile":
        return L + ["- 未运行：档案缺 `mahalanobis` 块（需先跑 "
                    "`tools/build_profile.py` 重建阶段 2/4 档案）", ""]
    paper = rep.get("paper") or {}
    L += [f"- 档案版本：**{rep.get('profile_version')}**"
          + (f"（{rep.get('profile_file')}）" if rep.get("profile_file") else "")
          + f"；会议档：{rep.get('venue') or '（无）'}；模式：`{rep.get('mode')}`，"
          f"λ=**{rep.get('lambda')}**（只报告，不参与验收）",
          f"- 分数：A_defect（现行口径，参与验收）=**{rep.get('a_defect')}**；"
          f"A_profile（档案偏离度）=**{paper.get('a_profile')}**；"
          f"a_effective = {rep.get('a_effective')}（= A_defect + λ·A_profile）",
          f"- 页级：{rep.get('n_pages_scored')}/{rep.get('n_pages')} 页参与判定；"
          f"D² 中位 {paper.get('median_d2')}、P90 {paper.get('d2_p90')}、"
          f"最大 {paper.get('d2_max')}；异常页（p<0.05）"
          f"**{paper.get('n_anomalous_pages')}** 页"]
    lv = rep.get("levels_used") or {}
    L.append("- 判定档（venue|role 优先，低可信度自动回退）："
             + ("，".join(f"{k}→`{v}`" for k, v in lv.items()) or "—"))
    worst = _worst_dims(rep)
    if worst:
        L.append("- 最偏离维度（相对档案 P90 的带外损失倍率）："
                 + "，".join(f"{k}={v}" for k, v in worst))
    tops = (paper.get("top_anomalous") or [])[:3]
    if tops:
        L.append("- 最异常页（供人工核对）：" + "；".join(
            f"p{t.get('page')} {t.get('role')} D²={t.get('d2')} "
            f"p={t.get('p_value')} 主因 {t.get('worst_dim')}" for t in tops))
    if rep.get("dropped_dims"):
        L.append(f"- 阶段 5 门槛（12.6）剔除、**不参与判定**的维度："
                 f"{'、'.join(rep['dropped_dims'])}")
    if trace:
        L += ["", "### 逐轮 trace（每次整篇重编译后的观测值；不影响判定）", "",
              "| 轮次 | 事件 | A_defect | A_profile | D² P90 | 异常页 | 页数 |",
              "|---|---|---|---|---|---|---|"]
        for r in trace:
            L.append(f"| {r.get('round')} | {r.get('label')} | {r.get('a_defect')} | "
                     f"{r.get('a_profile')} | {r.get('d2_p90')} | "
                     f"{r.get('n_anomalous_pages')} | {r.get('n_pages')} |")
        L.append("")
    if gate_res is not None:
        L.append(f"- 目标冲突门控（13.2，仅报告）："
                 f"{'允许' if gate_res.get('allow') else '不允许'} —— "
                 f"{gate_res.get('reason')}（影子模式下该门控**不参与**主循环判定）")
    b = baseline or {}
    b_ap = ((b.get("paper") or {}).get("a_profile"))
    L += ["", "### 人工核对清单（阶段 6 产出，逐条看）", "",
          f"1. λ 是否为 0、A_defect 是否与 `state.json` 的 `scores.a` 一致"
          f"（现行口径未被改动）",
          f"2. 基线 A_profile={b_ap} → 终态 A_profile={paper.get('a_profile')}，"
          f"若终态**变差**而 A_defect 未变差，说明动作把版面推离了会议常态，需人工判断",
          "3. 逐条看「最偏离维度」是否对应人眼可见的问题（若无可见问题 → 疑似误报，"
          "记入台账，阶段 7 用作假阳率复核）",
          "4. 逐条看「最异常页」：是否真的是排版异常页（而非数据/合订本问题）",
          "5. 门槛剔除维度是否合理（12.1 未覆盖 / 稳定性或假阳率未过 → 只报告）",
          "6. 档案版本与会议档是否与本次运行的论文匹配", ""]
    return L


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
    if rep.get("dropped_dims"):
        L.append(f"> 阶段 5 门槛（12.6）剔除的维度（只报告不参与判定）："
                 f"{'、'.join(rep['dropped_dims'])}")
    return L
