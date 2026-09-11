# -*- coding: utf-8 -*-
"""模型在环提案层：LLM ↔ texopt 的结构化接口（advisory / proposal）。

两个方向：
  1. 出向（texopt -> LLM）：`build_request` 把当前文档状态、残余问题、
     可用白名单动作、页面图像路径、约束与验收规则打包成 `llm_request.json`，
     交给有视觉/语言能力的模型判断。
  2. 入向（LLM -> texopt）：`parse_proposals` 读取模型产出的
     `proposals.json`，规范化为统一条目，再逐条交 whitelist 校验、
     core 执行、编译验收（变差回滚）。

重要语义（对应「Model-in-the-loop 的正确含义」）：
  LLM 不是一次性改论文，而是每轮拿到「重新感知后的新状态」，提出候选
  修改；程序执行→编译→重评→保留/回滚，再把新状态交回 LLM —— 这个循环
  由 CLI 的 --emit-request / --proposals 往返驱动，构成真正的
  感知 → 判断 → 修改 → 编译 → 验证 → 再判断 闭环。

提案 JSON 形态（宽松，兼容两种写法）：
{
  "schema": "texopt.proposals/v1",
  "round": 1,
  "assessment": "整体判断……",
  "proposals": [
    {"id": "p1", "issue": "page_balance", "location": "page 5",
     "severity": "moderate", "reason": "页面下半部分空白过大",
     "proposal": {"action": "set_float_spec", "target": "figure#2",
                  "params": {"spec": "tbp"},
                  "suggestion": "让该图可浮到页顶，填补空白"}},
    {"issue": "overwide_figure", "action": "set_fig_width",
     "params": {"width": "0.8\\linewidth", "target": "fig#1"},
     "reason": "图宽超出版心"}
  ]
}
"""
from __future__ import annotations

import json
import os

from . import whitelist

REQUEST_SCHEMA = "texopt.llm_request/v1"
PROPOSALS_SCHEMA = "texopt.proposals/v1"

SEVERITIES = ("cosmetic", "moderate", "content")


# ---------------------------------------------------------------- 入向：解析

def _pick(d: dict, *keys, default=None):
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return default


def normalize_item(raw: dict, idx: int) -> dict:
    """把一条（可能嵌套或扁平）提案规范化为统一结构。"""
    p = raw.get("proposal") if isinstance(raw.get("proposal"), dict) else raw
    action = _pick(p, "action", "name")
    params = dict(_pick(p, "params", "parameters", default={}) or {})
    target = _pick(p, "target")
    if target is not None and "target" not in params:
        params["target"] = target
    # 允许把 params 直接摊在 proposal 上（如 {"spec": "tbp"}）
    for k in ("spec", "mm", "pt", "width", "threshold_mm", "color",
              "left", "right", "include_H", "min_pt", "max_pt",
              "min_chars", "step"):
        if k in p and k not in params:
            params[k] = p[k]
    return {
        "id": str(_pick(raw, "id", default=f"P{idx}")),
        "issue": _pick(raw, "issue", "kind", default="layout"),
        "location": _pick(raw, "location", "page", default=""),
        "severity": (_pick(raw, "severity", default="moderate") or "moderate")
        if (_pick(raw, "severity", default="moderate") in SEVERITIES)
        else "moderate",
        "reason": _pick(raw, "reason", "rationale", default=""),
        "suggestion": _pick(p, "suggestion", "note", default=""),
        "action": action,
        "params": params,
    }


def parse_proposals(doc: dict | str) -> dict:
    """读取 proposals.json（dict 或路径/文本），返回 {meta, items, schema}。"""
    if isinstance(doc, str):
        if os.path.isfile(doc):
            with open(doc, encoding="utf-8") as f:
                doc = json.load(f)
        else:
            doc = json.loads(doc)
    raw_items = doc.get("proposals") or doc.get("items") or []
    if isinstance(raw_items, dict):                 # 容忍 {'p1': {...}}
        raw_items = [dict(v, id=k) for k, v in raw_items.items()]
    items = [normalize_item(r, i + 1) for i, r in enumerate(raw_items)]
    return {
        "schema": doc.get("schema", PROPOSALS_SCHEMA),
        "round": doc.get("round"),
        "assessment": doc.get("assessment") or doc.get("reasoning") or "",
        "items": items,
    }


# ---------------------------------------------------------------- 出向：请求包

def build_request(per, req, cur, round_no: int, page_images: list | None,
                  advisory: list | None, doc_paths: dict) -> dict:
    """打包交给 LLM 的请求：状态 + 残余问题 + 白名单 + 页面图像 + 约束。"""
    return {
        "schema": REQUEST_SCHEMA,
        "round": round_no,
        "objective": "在保证正文内容零改动与编译/要求达标（L）的前提下，"
                     "让整篇论文排版质量/布局更优（A↓，I 最小干预）。",
        "document": doc_paths,
        "state": {
            "pages": per.pages,
            "l_violations": list(cur.get("l", [])),
            "A_quality_proxy": cur.get("a"),
            "I_intervention": cur.get("i"),
            "total": cur.get("total"),
            "note": "A 是排版质量/审美代理指标，不是人类审美评分；total 越"
                    "小越好。所有提案都会整篇重编译后全局重评，变差即回滚。",
        },
        "residual_issues": advisory or [],
        "page_images": page_images or [],
        "page_images_note": "每页 PDF 渲染图（如模型具备视觉能力可据此判断"
                            "留白/视觉重心/图与正文关系；本版尚未做视觉量化）。",
        "allowed_actions": whitelist.describe(),
        "constraints": {
            "protect": ["正文文字", "数学公式", "引用/citation", "label/reference",
                        "图表内容", "图表文件", "章节结构"],
            "rule": "只能请求 allowed_actions 中的动作；未知动作一律 BLOCKED。"
                    "程序执行后编译验证，L 变差或总分不改善一律回滚。",
            "do_not": ["改写正文语义", "重绘/换算图形", "虚构题注/引用/数据",
                       "执行任意 shell 或文件操作"],
        },
        "proposal_schema": {
            "schema": PROPOSALS_SCHEMA,
            "round": round_no,
            "assessment": "对整篇布局的整体判断（一句话）",
            "proposals": [{
                "id": "p1", "issue": "page_balance", "location": "page 5",
                "severity": "moderate",
                "reason": "页面下半部分存在明显空白",
                "proposal": {"action": "set_float_spec",
                             "target": "figure#2",
                             "params": {"spec": "tbp"},
                             "suggestion": "允许该图浮到页顶/页底以填补空白"},
            }],
        },
        "instructions": [
            "1) 阅读 state 与 residual_issues，必要时查看 page_images。",
            "2) 只针对难以用规则决定的问题（留白/视觉重心/图文关系/整体节奏）"
            "提出提案；硬约束问题由程序闭环处理，无需重复提。",
            "3) 每条提案给出 issue/location/severity/reason 与 action/target/params。",
            "4) 输出严格符合 proposal_schema 的 JSON（保存为 proposals.json）。",
            "5) 不确定或需改动正文内容的，不要提（留给作者）；宁少勿滥。",
        ],
    }


def write_json(path: str, obj) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
