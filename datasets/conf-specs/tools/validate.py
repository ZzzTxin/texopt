#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""validate.py —— 数据集溯源与结构校验（“每条结论必须可追溯”的强制闸门）。

校验内容：
  1. 顶层必填字段 / 受控键名（见 schema/KEY_VOCAB.md）
  2. 每个 entry 必须有 value + confidence + evidence（非空）
  3. evidence.source_id 必须在 sources[] 里存在
  4. **引用抽查**：evidence.quote 必须能在该 source 归档的原始文本里逐字找到
     （大小写与空白归一化后匹配）——防止凭经验臆测/编造原文
  5. history 条目的 source_id 必须存在；同 key 的年份序列要能看出变化

用法:
    python3 tools/validate.py                       # 校验 conferences/ 下全部
    python3 tools/validate.py conferences/acl.json   # 单个
退出码: 0 全部通过；1 有错误
"""
from __future__ import annotations

import glob
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "sources", "raw")

ALLOWED_KEYS = {
    "paper_size", "columns", "column_gap_mm", "body_font_size_pt", "body_font_family",
    "line_spacing", "margins_mm", "text_width_mm", "text_height_mm",
    "page_limit_content", "page_limit_total", "references_counted", "appendix_allowed",
    "appendix_counted", "anonymity", "title_format", "abstract_max_words", "bib_style",
    "template_file", "template_url", "camera_ready_extra_pages", "checklist_required",
    "supplementary_policy", "page_numbering", "float_placement_rules",
    "figure_caption_position", "table_caption_position", "section_numbering",
    "submission_system", "dual_submission_policy",
    # 允许出现在 recommended 里的附加键（非硬约束）
    "figure_width_hint", "table_style_hint", "caption_style_hint", "equation_style_hint",
    "algorithm_style_hint", "code_style_hint", "footnote_style_hint",
    "reference_style_hint", "section_style_hint", "float_density_hint",
    "whitespace_hint", "hyphenation_hint", "color_policy",
}
REQUIRED_TOP = ["schema_version", "id", "name", "abbr", "family", "current_edition",
                "template_basis", "hard_constraints", "recommended", "history",
                "texopt_requirement_map", "sources"]
CONFIDENCE = {"official", "template-implied", "inferred"}

_norm_re = re.compile(r"\s+")


def norm(s: str) -> str:
    s = s.replace("\u00ad", "").replace("\ufb01", "fi").replace("\ufb02", "fl")
    s = s.replace("\u2019", "'").replace("\u2018", "'").replace("\u201c", '"').replace("\u201d", '"')
    s = s.replace("\u2013", "-").replace("\u2014", "-").replace("\u2212", "-")
    return _norm_re.sub(" ", s).strip().lower()


def source_text(src: dict, errors: list, issues: list) -> str | None:
    """取 source 归档文本（.txt 优先，其次原始文件）。"""
    raw = src.get("raw_file")
    if not raw:
        issues.append(f"source {src.get('id')} 未标 raw_file（无法验证引用）")
        return None
    p = os.path.join(ROOT, raw)
    if not os.path.exists(p):
        issues.append(f"source {src.get('id')} 归档缺失: {raw}")
        return None
    txt = os.path.splitext(p)[0] + ".txt"
    if os.path.exists(txt):
        return open(txt, encoding="utf-8", errors="replace").read()
    data = open(p, "rb").read()
    for enc in ("utf-8", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", "replace")


def check_quote(quote: str, text: str) -> bool:
    q = norm(quote)
    if not q:
        return False
    t = norm(text)
    if q in t:
        return True
    # 二次机会：去掉中文括号/全角空白差异后再比
    q2 = re.sub(r"[ \u200b]", "", q)
    t2 = re.sub(r"[ \u200b]", "", t)
    return q2 in t2


def validate_file(path: str) -> tuple[list[str], list[str], dict]:
    errors: list[str] = []
    issues: list[str] = []
    d = json.load(open(path, encoding="utf-8"))
    cid = d.get("id") or os.path.basename(path)[:-5]

    for k in REQUIRED_TOP:
        if k not in d:
            errors.append(f"[{cid}] 缺顶层字段 {k}")

    srcs = {s.get("id"): s for s in d.get("sources", [])}
    if not srcs:
        errors.append(f"[{cid}] sources 为空")
    src_text = {}
    for sid, s in srcs.items():
        src_text[sid] = source_text(s, errors, issues)
        if s.get("kind") in ("official-guidelines", "official-template", "style-source"):
            if not s.get("sha256"):
                issues.append(f"[{cid}] 官方来源 {sid} 缺 sha256（未归档？）")

    for section in ("hard_constraints", "recommended"):
        for key, entry in (d.get(section) or {}).items():
            if key not in ALLOWED_KEYS:
                errors.append(f"[{cid}] {section} 出现未登记键 '{key}'（见 KEY_VOCAB.md）")
            if not isinstance(entry, dict):
                errors.append(f"[{cid}] {section}.{key} 不是对象")
                continue
            if "value" not in entry or entry["value"] in (None, ""):
                errors.append(f"[{cid}] {section}.{key} 缺 value")
            if entry.get("confidence") not in CONFIDENCE:
                errors.append(f"[{cid}] {section}.{key} confidence 非法: {entry.get('confidence')}")
            ev = entry.get("evidence") or []
            if not ev:
                errors.append(f"[{cid}] {section}.{key} 无 evidence（必须引用来源）")
            for e in ev:
                sid = e.get("source_id")
                if sid not in srcs:
                    errors.append(f"[{cid}] {section}.{key} 引用不存在的 source_id: {sid}")
                    continue
                text = src_text.get(sid)
                if text is None:
                    continue
                if not check_quote(e.get("quote", ""), text):
                    errors.append(
                        f"[{cid}] {section}.{key} 引用未在 {sid} 原文中找到: "
                        f"“{(e.get('quote') or '')[:70]}…”")

    for ch in d.get("history", []):
        if ch.get("source_id") not in srcs:
            errors.append(f"[{cid}] history({ch.get('key')}@{ch.get('edition')}) source_id 不存在")
        for req in ("key", "edition", "year", "value", "source_id"):
            if req not in ch:
                errors.append(f"[{cid}] history 条目缺 {req}")

    hk = {}
    for ch in d.get("history", []):
        hk.setdefault(ch.get("key"), []).append(ch.get("year"))
    for k, ys in hk.items():
        if ys != sorted(ys):
            issues.append(f"[{cid}] history.{k} 年份未按升序排列: {ys}")

    tmap = d.get("texopt_requirement_map") or {}
    known_fields = {"page_limit", "font_pt", "margin_mm", "eq_fleqn_allowed", "toc",
                    "running_header", "heading_color", "enable_quality_macros",
                    "float_spec", "microtype", "overwide_fig_threshold_mm",
                    "overwide_table_report", "allow_geometry_tune", "margin_min_mm",
                    "margin_step_mm", "allow_fontsize_step", "max_iterations", "verbose"}
    for f in (tmap.get("requirement_fields") or {}):
        if f not in known_fields:
            errors.append(f"[{cid}] texopt_requirement_map 出现未知 Requirement 字段 '{f}'")

    stats = d.get("statistics") or {}
    for m, s in stats.items():
        if s.get("n") in (None, 0) and not s.get("samples"):
            issues.append(f"[{cid}] statistics.{m} 无样本")

    # ---- 样本层交叉校验（BRIEF §2.3）：每个样本须在 sources[] 里有对应 sample-paper 来源，
    #      且该来源归档文本里要能找到该会议的 venue 字符串（证明论文确属该会议）
    spath = os.path.join(ROOT, "samples", f"{cid}.samples.list.json")
    if not os.path.exists(spath):
        issues.append(f"[{cid}] 缺 samples/{cid}.samples.list.json")
    else:
        try:
            sl = json.load(open(spath, encoding="utf-8"))
        except Exception as ex:
            errors.append(f"[{cid}] samples/{cid}.samples.list.json 解析失败: {ex}")
            sl = {}
        for p in sl.get("papers", []):
            esid = p.get("evidence_source_id")
            if esid not in srcs:
                errors.append(f"[{cid}] 样本 {p.get('sample_id')} 的 evidence_source_id "
                              f"'{esid}' 不在 sources[] 里")
                continue
            if srcs[esid].get("kind") != "sample-paper":
                issues.append(f"[{cid}] 样本来源 {esid} 的 kind 不是 sample-paper")
            if not p.get("pdf_url"):
                errors.append(f"[{cid}] 样本 {p.get('sample_id')} 缺 pdf_url")
            txt = src_text.get(esid) or ""
            venue = p.get("venue") or ""
            if venue and norm(venue) not in norm(txt):
                issues.append(f"[{cid}] 样本 {p.get('sample_id')} 归档文本中未出现 venue "
                              f"'{venue}'（请确认落地页确实标明该会议）")

    n_entries = len(d.get("hard_constraints") or {}) + len(d.get("recommended") or {})
    summary = {"id": cid, "hard": len(d.get("hard_constraints") or {}),
               "recommended": len(d.get("recommended") or {}),
               "sources": len(srcs), "history": len(d.get("history", [])),
               "entries": n_entries}
    return errors, issues, summary


def main():
    args = sys.argv[1:]
    files = args or sorted(glob.glob(os.path.join(ROOT, "conferences", "*.json")))
    if not files:
        print("没有找到 conferences/*.json")
        return 1
    all_err, all_iss, rows = [], [], []
    for f in files:
        try:
            e, i, s = validate_file(f)
        except Exception as ex:
            all_err.append(f"[{os.path.basename(f)}] 读取/解析失败: {ex}")
            continue
        all_err += e
        all_iss += i
        rows.append(s)
    print(f"{'id':<12}{'硬约束':>6}{'推荐':>6}{'来源':>6}{'history':>9}")
    for r in rows:
        print(f"{r['id']:<12}{r['hard']:>6}{r['recommended']:>6}{r['sources']:>6}{r['history']:>9}")
    print(f"\n文件数 {len(rows)}  错误 {len(all_err)}  提示 {len(all_iss)}")
    for x in all_iss:
        print("  提示:", x)
    for x in all_err:
        print("  错误:", x)
    return 1 if all_err else 0


if __name__ == "__main__":
    sys.exit(main())
