# -*- coding: utf-8 -*-
"""会议模板层：把 `datasets/conf-specs/templates-v2/<id>.json` 接进 texopt。

设计原则（2026-09-12，用户指定）：
  1. **统一入口，不为任何会议写单独代码**：会议之间的差异全部来自 json 字段，
     代码只做「字段 → Requirement」的通用投影；
  2. **官方规定 = 硬约束**：`hard_constraints`（confidence = official /
     template-implied / inferred）映射到 Requirement 的 L 字段，用于「是否违规」；
  3. **真实论文统计 = 只谈合理性**：`density_targets` / `*_observed` /
     `position_prior` 等 sample-stat 数据只进入 `reasonableness()` 的参考核对，
     ——绝不写进 L 字段、绝不参与 A 打分、绝不作为必须满足的条件；
  4. **接不上的内容明确登记**：所有当前 texopt 消费不了的字段进 `deferred`
     清单（带原因），不强行加入；
  5. 指定会议与不指定会议是同一套代码路径，只是要求来源不同 —— 不指定时行为
     与以前完全一致。

术语：
  违规（violation） = 违反官方硬约束（L 项，会导致投稿不合规）；
  合理（reasonable） = 落在真实论文的统计区间内（仅参考，不判定成败）。
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

# templates-v2 默认位置：<texopt 仓库根>/datasets/conf-specs/templates-v2
PKG_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_SUBDIR = os.path.join("datasets", "conf-specs", "templates-v2")

# basis 白名单：L 字段只接受「来自官方」的三种；派生值只允许用于 A/策略字段
L_BASES = ("official", "template-implied", "inferred")
ANY_BASES = L_BASES + ("derived",)


def templates_dir(explicit: str | None = None) -> str:
    """模板目录解析顺序：显式参数 > 环境变量 TEXOPT_CONFERENCES > 仓库默认。"""
    return (explicit or os.environ.get("TEXOPT_CONFERENCES")
            or os.path.join(PKG_ROOT, DEFAULT_SUBDIR))


def available(dirpath: str | None = None) -> dict:
    """返回 {会议 id: json 路径}。"""
    d = templates_dir(dirpath)
    out = {}
    if os.path.isdir(d):
        for fn in sorted(os.listdir(d)):
            if fn.endswith(".json"):
                out[fn[:-5]] = os.path.join(d, fn)
    return out


def list_conferences(dirpath: str | None = None) -> list[dict]:
    """列出可用会议模板（用于 --list-conferences）。"""
    rows = []
    for cid, path in available(dirpath).items():
        try:
            with open(path, encoding="utf-8") as f:
                d = json.load(f)
            rows.append({
                "id": cid,
                "conference": d.get("conference"),
                "edition": d.get("edition"),
                "family": d.get("family"),
                "n_samples": (d.get("data_basis") or {}).get("n_samples"),
                "level": (d.get("confidence") or {}).get("level"),
                "path": path,
            })
        except Exception as exc:                    # 坏文件不影响列表
            rows.append({"id": cid, "conference": cid, "edition": None,
                         "family": None, "n_samples": None, "level": None,
                         "path": path, "error": str(exc)})
    return rows


# ------------------------------------------------------------------ 字段投影
# Requirement 字段 ← 模板 json 路径。kind: L = 违规判定用；A/policy = 审美/策略。
PROJECTIONS = [
    {"field": "page_limit", "kind": "L",
     "path": "hard_constraints.page_limit_content",
     "alt": "hard_constraints.page_limit_total",
     "note": "官方正文页上限（references_counted=false 时按正文页口径判定）"},
    {"field": "font_pt", "kind": "L",
     "path": "typography.body_font_pt",
     "note": "官方正文字号档"},
    {"field": "margin_mm", "kind": "L",
     "path": "geometry.margin_floor_mm",
     "note": "四边最小边距：texopt 压页下限，不得低于此值"},
    {"field": "float_spec", "kind": "policy",
     "path": "float_policy.float_spec",
     "note": "浮动体位置参数规范档（[h]/[h!] 等不稳定写法被规范化）"},
    {"field": "overwide_fig_threshold_mm", "kind": "A",
     "path": "float_policy.figure_width.overwide_threshold_mm",
     "note": "超宽图归一阈值（= 版心全宽）"},
    {"field": "eq_fleqn_allowed", "kind": "policy", "flat": True,
     "note": "官方模板公式居中 → 移除 fleqn"},
    {"field": "enable_quality_macros", "kind": "policy", "flat": True,
     "note": "断行质量宏（孤行寡行/溢出的代理手段）"},
]

# 本版 texopt 实际消费的模板路径（其余一律进 deferred 记录）
CONSUMED = {
    "hard_constraints.page_limit_content",
    "hard_constraints.page_limit_total",
    "hard_constraints.references_counted",      # 用于页数口径
    "typography.body_font_pt",
    "geometry.margin_floor_mm",
    "float_policy.float_spec",
    "float_policy.figure_width.overwide_threshold_mm",
    "texopt_flat",
}

# 逐字段的「为什么接不上」说明
_UNUSED_REASON = {
    "hard_constraints.anonymity": "匿名要求：texopt 没有匿名检查/清理动作（不在白名单）",
    "hard_constraints.checklist_required": "checklist：texopt 不生成也不检查（内容层，不在白名单）",
    "hard_constraints.bib_style": "参考文献风格：需换 .bst/宏包，属跨文档类迁移（后续阶段）",
    "hard_constraints.page_numbering": "页码策略：需改模板页脚/样式（后续阶段）",
    "hard_constraints.title_format": "标题格式：需改文档类/模板（后续阶段）",
    "hard_constraints.abstract_max_words": "摘要字数限制：属内容层，texopt 不改内容",
    "hard_constraints.submission_system": "投稿系统信息：无排版动作",
    "hard_constraints.supplementary_policy": "补充材料策略：无排版动作",
    "hard_constraints.dual_submission_policy": "政策信息：无排版动作",
    "hard_constraints.camera_ready_extra_pages": "录用后加页规则：本次按投稿版口径，不加页",
    "hard_constraints.references_counted": "已用于页数口径（page_limit_scope），不单独作为动作",
    "hard_constraints.appendix_allowed": "附录政策：texopt 不改内容，仅记录",
    "hard_constraints.appendix_counted": "附录计页：仅用于口径说明",
    "hard_constraints.body_font_family": "字体族：需换文档类/宏包（跨类迁移，后续阶段）",
    "hard_constraints.line_spacing": "行距：当前无对应白名单动作（属版心参数）",
    "hard_constraints.text_width_mm": "版心宽：仅作参考（set_margin 只改边距，不改版心）",
    "hard_constraints.text_height_mm": "版心高：仅作参考",
    "hard_constraints.column_gap_mm": "栏间距：需改文档类/宏包（后续阶段）",
    "hard_constraints.columns": "栏数：需改 documentclass（texopt 明确不改文档类）",
    "hard_constraints.paper_size": "纸张尺寸：需改文档类/geometry 选项（后续阶段）",
    "hard_constraints.template_file": "官方模板文件名：溯源信息",
    "hard_constraints.template_url": "官方模板地址：溯源信息",
    "hard_constraints.float_placement_rules": "浮动体规则描述：已部分体现为 float_spec，其余为文字说明",
    "hard_constraints.figure_caption_position": "图题位置：无对应动作（不改 caption 样式）",
    "hard_constraints.table_caption_position": "表题位置：无对应动作",
    "hard_constraints.margins_mm": "四边边距明细：已折算为 margin_floor_mm（不对称边距需后续字段支持）",
    "hard_constraints.body_font_size_pt": "已用于 typography.body_font_pt 投影（不重复接入）",
    "hard_constraints.page_limit_content": "已用于 page_limit 投影（不重复接入）",
}
_UNUSED_DEFAULT = "本版 texopt 无对应字段/动作，仅记录（详见 summary/texopt-integration-report.md）"

_BLOCK_REASON = {
    "typography": "题注字号/位置等细节：本版无对应动作（不改 caption 样式），仅作参考",
    "geometry": "几何观测值与版心尺寸：仅作参考（texopt 只消费 margin_floor_mm）",
    "float_policy": "浮动体统计与位置先验：仅作参考（texopt 只消费 float_spec 与超宽阈值）",
    "density_targets": "样本统计量：只用于『排版是否合理』的参考核对，不作硬约束",
    "optimization_policy": "设计期优化建议（priority/actions/avoid/unsupported）：供人工与后续自动化消费",
    "confidence": "可信度元信息（样本量/可靠字段/冲突）：供报告展示",
    "sources": "来源清单：溯源信息",
    "traceability": "字段级 basis 登记：溯源信息",
    "data_basis": "统计口径：溯源信息",
    "generated_by": "生成器信息：溯源信息",
}


def _dig(d, path, default=None):
    cur = d
    for k in path.split("."):
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur


@dataclass
class ConferenceProfile:
    id: str
    conference: str
    edition: str | None
    family: str | None
    path: str
    requirement_fields: dict = field(default_factory=dict)   # → Requirement
    field_sources: dict = field(default_factory=dict)        # 字段 → {path,basis,note}
    page_limit_scope: str = "total"                          # total | content
    official_summary: dict = field(default_factory=dict)     # 官方硬约束摘要
    soft: dict = field(default_factory=dict)                 # 统计参考（只谈合理性）
    deferred: list = field(default_factory=list)             # 接不上的内容（含原因）
    warnings: list = field(default_factory=list)
    raw: dict = field(default_factory=dict)

    def describe(self) -> str:
        f = self.requirement_fields
        parts = [f"会议模板 {self.id}（{self.conference} {self.edition}）"]
        if f.get("page_limit"):
            scope = "正文页" if self.page_limit_scope == "content" else "总页"
            parts.append(f"页数上限 {f['page_limit']}（{scope}）")
        if f.get("font_pt"):
            parts.append(f"字号 {f['font_pt']}pt")
        if f.get("margin_mm"):
            parts.append(f"边距下限 {f['margin_mm']:g}mm")
        parts.append(f"浮动体 [{f.get('float_spec')}]")
        parts.append(f"超宽图阈值 {f.get('overwide_fig_threshold_mm'):g}mm")
        parts.append(f"参考统计 {len(self.soft)} 组")
        parts.append(f"未接入项 {len(self.deferred)}")
        return "，".join(parts)


def load(cid: str, dirpath: str | None = None) -> ConferenceProfile:
    """按会议 id 读取 templates-v2/<id>.json 并投影为 Requirement 字段。"""
    avail = available(dirpath)
    key = (cid or "").strip().lower()
    if key not in avail:
        raise ValueError(
            f"未知会议 '{cid}'：{len(avail)} 个可用会议 "
            f"({', '.join(sorted(avail))})；模板目录 {templates_dir(dirpath)}")
    with open(avail[key], encoding="utf-8") as fh:
        raw = json.load(fh)

    prof = ConferenceProfile(
        id=raw.get("id", key),
        conference=raw.get("conference", key),
        edition=raw.get("edition"),
        family=raw.get("family"),
        path=avail[key],
        raw=raw,
    )
    hard = raw.get("hard_constraints") or {}
    flat = raw.get("texopt_flat") or {}

    consumed_paths = set()
    for pj in PROJECTIONS:
        field_name, path = pj["field"], pj.get("path")
        if pj.get("flat"):
            if field_name in flat and flat[field_name] is not None:
                prof.requirement_fields[field_name] = flat[field_name]
                prof.field_sources[field_name] = {
                    "path": f"texopt_flat.{field_name}", "basis": "derived",
                    "note": pj["note"]}
                consumed_paths.add("texopt_flat")
            else:
                prof.deferred.append({
                    "path": f"texopt_flat.{field_name}", "reason":
                    "模板未给出该值（也可用默认值），仅记录"})
            continue
        node = _dig(raw, path)
        if node is None and pj.get("alt"):
            path = pj["alt"]
            node = _dig(raw, path)
        if not isinstance(node, dict) or node.get("value") is None:
            prof.deferred.append({
                "path": path, "reason": f"{pj['note']}：模板无此值，texopt 用默认值"})
            continue
        basis = node.get("confidence") or node.get("basis") or "unknown"
        allowed = L_BASES if pj["kind"] == "L" else ANY_BASES
        if basis not in allowed:
            prof.deferred.append({
                "path": path,
                "reason": f"{pj['note']}：basis={basis} 不是官方来源"
                          f"（仅 {allowed}），按任务要求不作硬约束"})
            prof.warnings.append(
                f"{field_name} 未采用：{path} 的 basis={basis}")
            continue
        prof.requirement_fields[field_name] = node["value"]
        prof.field_sources[field_name] = {
            "path": path, "basis": basis, "note": pj["note"],
            "evidence": node.get("evidence") or [],
        }
        consumed_paths.add(path)

    # ---- 页数口径：官方上限是「正文页」还是「总页」 ----
    if "hard_constraints.page_limit_content" in consumed_paths \
            or _dig(hard, "page_limit_content.value") is not None:
        prof.page_limit_scope = "content"
    else:
        prof.page_limit_scope = "total"
    prof.official_summary = {
        "page_limit_content": _dig(hard, "page_limit_content.value"),
        "page_limit_total": _dig(hard, "page_limit_total.value"),
        "references_counted": _dig(hard, "references_counted.value"),
        "appendix_allowed": _dig(hard, "appendix_allowed.value"),
        "appendix_counted": _dig(hard, "appendix_counted.value"),
        "camera_ready_extra_pages": _dig(hard, "camera_ready_extra_pages.value"),
        "page_limit_scope": prof.page_limit_scope,
        "columns": _dig(hard, "columns.value"),
        "paper_size": _dig(hard, "paper_size.value"),
        "body_font_size_pt": _dig(hard, "body_font_size_pt.value"),
        "margins_mm": _dig(hard, "margins_mm.value"),
        "anonymity": _dig(hard, "anonymity.value"),
        "bib_style": _dig(hard, "bib_style.value"),
        "checklist_required": _dig(hard, "checklist_required.value"),
    }

    # ---- 统计参考（只谈合理性） ----
    dens = raw.get("density_targets") or {}
    fp = raw.get("float_policy") or {}
    geo = raw.get("geometry") or {}
    prof.soft = {
        "figures_per_paper": _dig(dens, "figures.per_paper"),
        "tables_per_paper": _dig(dens, "tables.per_paper"),
        "equations_per_paper": _dig(dens, "equations.per_paper"),
        "figures_per_page": _dig(dens, "figures.per_content_page"),
        "tables_per_page": _dig(dens, "tables.per_content_page"),
        "content_pages": _dig(dens, "content_pages.per_paper"),
        "reliable": {
            "figures": _dig(dens, "figures.reliable"),
            "tables": _dig(dens, "tables.reliable"),
            "equations": _dig(dens, "equations.reliable"),
            "refs": _dig(dens, "refs.reliable"),
        },
        "float_position_ratio": _dig(fp, "position_prior.full_width_float_ratio"),
        "figure_width_frac": _dig(fp, "figure_width.typical_frac"),
        "margins_observed": _dig(geo, "observed.margins_left_mm"),
        "margins_observed_right": _dig(geo, "observed.margins_right_mm"),
        "sample_n": _dig(raw, "confidence.sample_n"),
        "level": _dig(raw, "confidence.level"),
    }

    # ---- 未接入清单 ----
    for key_ in sorted(hard):
        p = f"hard_constraints.{key_}"
        if p in consumed_paths or p in CONSUMED:
            continue
        prof.deferred.append({"path": p,
                              "reason": _UNUSED_REASON.get(p, _UNUSED_DEFAULT)})
    for block, reason in _BLOCK_REASON.items():
        if block in raw and block not in ("hard_constraints",):
            prof.deferred.append({"path": block, "reason": reason})
    prof.deferred.append({
        "path": "typography.caption_font_pt / caption_position",
        "reason": "题注字号与位置：本版无对应动作（只比对，不改）"})
    return prof


# ------------------------------------------------------------------ 合理性核对
def reasonableness(per, req) -> dict:
    """把「真实论文统计」与当前文档对照（**只作参考，不影响 L 与评分**）。

    只用源码层可测的量：图的张数、表的张数、浮动体位置参数偏好、显式页边距。
    数据不足（无 soft_targets）时返回空结论，不臆测。
    """
    soft = getattr(req, "soft_targets", None) or {}
    if not soft:
        return {"enabled": False, "checks": [], "deviations": []}
    src = getattr(per, "source", {}) or {}
    checks, dev = [], []

    def band(entry, label, observed, unit=""):
        if not isinstance(entry, dict) or entry.get("median") is None:
            return
        lo, hi, med = entry.get("p25"), entry.get("p75"), entry.get("median")
        if observed is None:
            return
        status = "in-band"
        if lo is not None and observed < lo - 1e-9:
            status = "below"
        elif hi is not None and observed > hi + 1e-9:
            status = "above"
        c = {"name": label, "observed": observed, "unit": unit,
             "reference": {"p25": lo, "median": med, "p75": hi},
             "status": status,
             "note": f"真实论文区间 P25–P75（n={entry.get('n')}），仅参考"}
        checks.append(c)
        if status != "in-band":
            dev.append(f"{label}：实测 {observed}{unit}，样本区间 "
                       f"{lo}–{hi}{unit}（{status}）—— 仅是『与常见论文不太一样』，"
                       "不判定为违规")

    floats = src.get("floats") or {}
    band(soft.get("figures_per_paper"), "图/篇", floats.get("figure"))
    band(soft.get("tables_per_paper"), "表/篇", floats.get("table"))

    # 浮动体位置偏好：源码里的 [t]/[b]/[!] 参数分布 vs 实测位置先验
    prior = soft.get("float_position_ratio") or {}
    specs = [(fe.get("spec") or "").lower()
             for fe in (src.get("float_envs") or [])]
    specs = [s for s in specs if s]
    if specs and prior:
        n = len(specs)
        t = sum(1 for s in specs if "t" in s) / n
        b = sum(1 for s in specs if "b" in s) / n
        checks.append({
            "name": "浮动体位置偏好（源码 [t]/[b] 占比）",
            "observed": {"top": round(t, 3), "bottom": round(b, 3)},
            "reference": {"实测 top 占比": prior.get("top"),
                          "实测 bottom 占比": prior.get("bottom")},
            "status": "in-band",
            "note": "真实论文以页顶为主；源码里 [b] 偏多时，浮动体更容易堆到页面底部",
        })
        if prior.get("top") is not None and b > prior.get("top", 0) + 0.3:
            dev.append(f"浮动体 [b] 占比 {b:.0%} 明显高于实测 top 占比 "
                       f"{prior.get('top'):.0%} —— 可考虑交给 [tbp] 全局放置（参考）")

    # 显式页边距 vs 实测边距区间
    gm = src.get("geometry_margin_mm")
    if gm is not None and src.get("geometry_explicit"):
        band(soft.get("margins_observed"), "页边距（等效单边）", gm, "mm")
    return {"enabled": True, "checks": checks, "deviations": dev,
            "level": soft.get("level"), "sample_n": soft.get("sample_n")}


def apply_to(req, profile: ConferenceProfile) -> ConferenceProfile:
    """把投影后的字段写进 Requirement（调用方决定时机与覆盖优先级）。"""
    for k, v in profile.requirement_fields.items():
        setattr(req, k, v)
    # 会议模板的边距是「官方最小边距（下限）」：低于才判违规，高于不干预
    req.margin_is_floor = True
    req.conference = profile.id
    req.page_limit_scope = profile.page_limit_scope
    req.official_constraints = dict(profile.official_summary)
    req.soft_targets = dict(profile.soft)
    req.unused_template_parts = [d["path"] for d in profile.deferred]
    return profile
