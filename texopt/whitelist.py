# -*- coding: utf-8 -*-
"""动作白名单注册表 —— LLM / 模型在环唯一可请求的修改面。

设计定位（对应 SRTP 主线「LLM 不应该拥有无限制的修改权限」）：
  * LLM 只能产出 **结构化提案**（proposal），不能直接改文件、不能跑 shell；
  * 提案里的 action 必须在下面的 WHITELIST 里；不在 → 直接 BLOCKED；
  * 每个 action 的参数都做类型/取值校验（正则白名单），拒绝注入；
  * 所有 action 都只落在排版面（preamble 参数/页边距/字号/浮动体位置参数/
    图片宽度/documentclass 选项/结构），不触及正文文字/公式/引用/图表内容。
  * 执行后一律由 core 编译 + 全局评分验收，变差即回滚（LLM 无权直接接受）。

三层次归属（level）：
  L1 硬性约束（规则直接处理，不需要 LLM）：字号/页边距/fleqn/内容完整…
  L2 可量化质量（程序检测+评分，允许程序搜索候选）：浮动体参数、超宽图…
  L3 复杂整体布局（需要 LLM 判断）：某张图浮到哪里、缩到多大等。

本模块只做「能不能请求 / 参数合不合法」，不做评分与验收（那是 core）。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from . import actions


# ---------------------------------------------------------------- 参数校验

def _v_int(v, lo=None, hi=None, choices=None):
    if isinstance(v, bool) or not isinstance(v, int):
        try:
            v = int(v)
        except (TypeError, ValueError):
            return None, "需要整数"
    if choices is not None and v not in choices:
        return None, f"取值必须是 {list(choices)} 之一"
    if lo is not None and v < lo:
        return None, f"过小（< {lo}）"
    if hi is not None and v > hi:
        return None, f"过大（> {hi}）"
    return v, ""


def _v_float(v, lo=None, hi=None):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None, "需要数值"
    if lo is not None and v < lo:
        return None, f"过小（< {lo}）"
    if hi is not None and v > hi:
        return None, f"过大（> {hi}）"
    return v, ""


def _v_str(v, pattern=None, maxlen=200):
    if not isinstance(v, str):
        return None, "需要字符串"
    if len(v) > maxlen:
        return None, f"过长（> {maxlen}）"
    if pattern is not None:
        import re
        if not re.fullmatch(pattern, v.strip()):
            return None, f"格式不合法：{v!r}"
    return v.strip(), ""


import re as _re

# 页眉文本：只允许普通文本 + 两个受控记号；禁止花括号与控制序列注入
_HEADER_RE = _re.compile(r"^[\w\s\-.,:;()\[\]/'\u4e00-\u9fff]*"
                         r"(?:(?:\\thepage|\\texopttitle)"
                         r"[\w\s\-.,:;()\[\]/'\u4e00-\u9fff]*)*$")
_COLOR_RE = _re.compile(r"^(?:[0-9]{1,3}\s*,\s*[0-9]{1,3}\s*,\s*[0-9]{1,3}"
                        r"|RGB:[0-9,\s]+|HTML:[0-9a-fA-F]{6}"
                        r"|[a-zA-Z][a-zA-Z0-9!.\-]{0,40})$")
_SPEC_RE = _re.compile(r"^[htbp!H]{1,5}$")
_TARGET_RE = _re.compile(r"^[A-Za-z]*#?\d*$")


def _v_header(v):
    return _v_str(v, _HEADER_RE.pattern, 120)


def _v_color(v):
    return _v_str(v, _COLOR_RE.pattern, 40)


def _v_spec(v):
    return _v_str(v, _SPEC_RE.pattern, 5)


def _v_width(v):
    w = actions._safe_width(v) if isinstance(v, str) else None
    return (w, "") if w else (None, "非法宽度表达式（如 \\linewidth / 0.8\\linewidth / 120mm）")


def _v_bool(v):
    if isinstance(v, bool):
        return v, ""
    if isinstance(v, str) and v.strip().lower() in ("true", "false"):
        return v.strip().lower() == "true", ""
    return None, "需要布尔值（true/false）"


def _v_target(v):
    if v is None:
        return None, ""
    if isinstance(v, int):
        return v, ""
    return _v_str(v, _TARGET_RE.pattern, 24)


# ---------------------------------------------------------------- 动作包装器
# 统一签名：wrapper(src, params) -> (new_src|None, applied: bool, note: str)

def _wrap_quality(src, p):
    return actions.inject_quality_macros(src)


def _wrap_drop_fleqn(src, p):
    return actions.drop_fleqn(src)


def _wrap_set_fontsize(src, p):
    new, ok, note, _ = actions.set_fontsize(src, int(p["pt"]))
    return new, ok, note


def _wrap_set_margin(src, p):
    new, ok, note, _ = actions.set_margin(src, float(p["mm"]))
    return new, ok, note


def _wrap_insert_toc(src, p):
    return actions.insert_toc(src)


def _wrap_add_header(src, p):
    return actions.add_header(src, p.get("left"), p.get("right"))


def _wrap_color_headings(src, p):
    return actions.color_headings(src, p.get("color", "0,62,120"))


def _wrap_strip_aids(src, p):
    return actions.strip_reading_aids(src)


def _wrap_strip_warn(src, p):
    return actions.remove_warning_boxes(src)


def _wrap_sanitize_float(src, p):
    return actions.sanitize_float_specs(src, p.get("spec", "tbp"),
                                        bool(p.get("include_H", False)))


def _wrap_pagebreak_rm(src, p):
    return actions.remove_manual_pagebreak(src)


def _wrap_vspace_rm(src, p):
    return actions.remove_excessive_vspace(src, float(p.get("min_pt", 28.35)))


def _wrap_local_font(src, p):
    return actions.normalize_local_font_size(src)


def _wrap_heading_size(src, p):
    return actions.normalize_heading_size(src)


def _wrap_list_spacing(src, p):
    return actions.reduce_list_spacing(src, float(p.get("max_pt", 8.0)))


def _wrap_hyphenate(src, p):
    return actions.add_hyphenation_points(src, int(p.get("min_chars", 80)),
                                          int(p.get("step", 12)))


def _wrap_url_break(src, p):
    return actions.break_long_urls(src)


def _wrap_table_width(src, p):
    return actions.fix_table_width(src)


def _wrap_balance_pages(src, p):
    return actions.balance_pages(src)


def _wrap_set_float_spec(src, p):
    new, ok, note, _ = actions.set_float_spec(
        src, p.get("spec", "tbp"), p.get("target"))
    return new, ok, note


def _wrap_normalize_fig(src, p):
    return actions.normalize_fig_width(src, float(p.get("threshold_mm", 150.0)))


def _wrap_set_fig_width(src, p):
    new, ok, note, _ = actions.set_fig_width(
        src, p.get("width", r"\linewidth"), p.get("target"))
    return new, ok, note


# ---------------------------------------------------------------- 注册表

@dataclass(frozen=True)
class Param:
    name: str
    type: str                 # int | float | str | target
    doc: str = ""
    required: bool = False
    default: object = None
    validator: Callable | None = None


@dataclass(frozen=True)
class ActionSpec:
    name: str
    level: int                # 1 硬约束 / 2 可量化 / 3 需 LLM 判断
    category: str             # L | A | structure | meta
    doc: str                  # 给 LLM 读的一句话说明
    func: Callable
    params: tuple = ()


WHITELIST: dict = {}


def _reg(spec: ActionSpec):
    WHITELIST[spec.name] = spec
    return spec


WHITELIST.clear()

_reg(ActionSpec(
    "inject_quality_macros", 2, "A",
    "注入断行/孤行寡行质量宏（club/widow penalty 等），全局生效，无损",
    _wrap_quality))
_reg(ActionSpec(
    "drop_fleqn", 1, "L",
    "移除 documentclass 的 fleqn 选项，公式恢复居中（硬性规范）",
    _wrap_drop_fleqn))
_reg(ActionSpec(
    "set_fontsize", 1, "L",
    "把文档正文字号设为 10/11/12 之一（硬性规范）",
    _wrap_set_fontsize,
    (Param("pt", "int", "目标字号档（10/11/12）", True,
           validator=lambda v: _v_int(v, choices=(10, 11, 12))),)))
_reg(ActionSpec(
    "set_margin", 1, "L",
    "把等效单边页边距设为 mm（会改变版面分布，慎用；程序夹在安全下限内）",
    _wrap_set_margin,
    (Param("mm", "float", "目标等效单边页边距（mm，建议 15-40）", True,
           validator=lambda v: _v_float(v, 8.0, 80.0)),)))
_reg(ActionSpec(
    "insert_toc", 1, "structure",
    "在正文首节前插入目录页（\\tableofcontents，单独成页）；幂等",
    _wrap_insert_toc))
_reg(ActionSpec(
    "add_header", 1, "structure",
    "注入页眉（fancyhdr）；left/right 为纯文本，可用 \\thepage、\\texopttitle",
    _wrap_add_header,
    (Param("left", "str", "页眉左文本（省略则用标题）", False, None, _v_header),
     Param("right", "str", "页眉右文本（省略则用页码）", False, None, _v_header))))
_reg(ActionSpec(
    "color_headings", 2, "A",
    "给 section/subsection 标题着色以建立层级突出（审美项）",
    _wrap_color_headings,
    (Param("color", "str", "颜色：'0,62,120' / 'RGB:...' / 'HTML:...' / 颜色名",
           False, "0,62,120", _v_color),)))
_reg(ActionSpec(
    "strip_reading_aids", 2, "meta",
    "删除阅读辅助内容（START READING HERE 等已知非正文模式）",
    _wrap_strip_aids))
_reg(ActionSpec(
    "remove_warning_boxes", 2, "meta",
    "删除 WARNING/CAUTION/ATTENTION 类告示块（编辑性提示，非正文）",
    _wrap_strip_warn))
_reg(ActionSpec(
    "sanitize_float_specs", 2, "A",
    "把所有不稳定的浮动体位置参数（[h]/[h!] 等）规范为含 t/b/p 的稳定档；"
    "include_H=true 时连 [H] 强排也一并规范",
    _wrap_sanitize_float,
    (Param("spec", "str", "目标位置参数，如 tbp/htbp/tb", False, "tbp", _v_spec),
     Param("include_H", "bool", "是否也规范 [H] 强排（默认 false）", False,
           False, _v_bool))))
_reg(ActionSpec(
    "remove_manual_pagebreak", 2, "A",
    "删除正文里的手动分页（\\newpage/\\clearpage/\\pagebreak），交回 "
    "LaTeX 全局断页；编译后全局评分不改善则回滚",
    _wrap_pagebreak_rm))
_reg(ActionSpec(
    "remove_excessive_vspace", 2, "A",
    "删除明显过大的手动垂直间距 \\vspace{...}（默认 ≥ 10mm）",
    _wrap_vspace_rm,
    (Param("min_pt", "float", "视为“过大”的下限（pt，默认 28.35=10mm）",
           False, 28.35, validator=lambda v: _v_float(v, 1.0, 300.0)),)))
_reg(ActionSpec(
    "normalize_local_font_size", 2, "A",
    "删除正文里孤立的行内字号切换（{\\Large ...} / {\\tiny ...}），把字号"
    "交回全局样式；数学/表格/verbatim 内的不处理",
    _wrap_local_font))
_reg(ActionSpec(
    "normalize_heading_size", 2, "A",
    "把超出层级上限的标题字号压回上限（section ≤ \\Large，subsection ≤ "
    "\\large，subsubsection ≤ \\normalsize），只动 \\titleformat/\\xxxfont",
    _wrap_heading_size))
_reg(ActionSpec(
    "reduce_list_spacing", 2, "A",
    "收紧列表环境里过大的垂直间距选项（itemsep/topsep/parsep/partopsep），"
    "回到文档类默认；列表结构与条目内容不动",
    _wrap_list_spacing,
    (Param("max_pt", "float", "视为“过大”的上限（pt，默认 8）", False, 8.0,
           validator=lambda v: _v_float(v, 1.0, 100.0)),)))
_reg(ActionSpec(
    "add_hyphenation_points", 2, "A",
    "给超长不可断词（默认 ≥ 80 字符）插入 \\- 断词点（TeX 合法机制，"
    "零宽可选断点，不改语义）",
    _wrap_hyphenate,
    (Param("min_chars", "int", "触发阈值（字符数，默认 80）", False, 80,
           validator=lambda v: _v_int(v, 20, 500)),
     Param("step", "int", "断点间隔（字符数，默认 12）", False, 12,
           validator=lambda v: _v_int(v, 2, 60)))))
_reg(ActionSpec(
    "break_long_urls", 2, "A",
    "给超长 URL（\\url/\\href/\\path 形式）注入 \\usepackage{xurl}，允许在"
    "任意位置断行；不改动 URL 文字",
    _wrap_url_break))
_reg(ActionSpec(
    "fix_table_width", 2, "A",
    "把列格式简单的超宽 tabular 改为 tabularx（\\linewidth 自适应列宽）；"
    "不使用 \\resizebox 压缩，不改表格数据/顺序/内容",
    _wrap_table_width))
_reg(ActionSpec(
    "balance_pages", 2, "A",
    "注入 \\raggedbottom，抑制“为凑满页而拉伸页面”造成的过大留白/垂直质量"
    "问题；不删内容、不手动分页凑页",
    _wrap_balance_pages))
_reg(ActionSpec(
    "set_float_spec", 3, "A",
    "【Level-3】定点设置某一个浮动体的位置参数：让指定图/表浮到页顶(t)/页底(b)/"
    "单独页(p)。target 形如 'figure#2' / 'table#1' / 1（1-based），省略=全部",
    _wrap_set_float_spec,
    (Param("spec", "str", "目标位置参数，如 tbp/htbp/tb", True, None, _v_spec),
     Param("target", "target", "目标浮动体：'figure#2' / 'table#1' / 1 / 省略",
           False, None, _v_target))))
_reg(ActionSpec(
    "normalize_fig_width", 2, "A",
    "把所有数值宽度超过阈值的插图归一化到 \\linewidth（修 overfull）",
    _wrap_normalize_fig,
    (Param("threshold_mm", "float", "超宽阈值 mm（默认 150）", False, 150.0,
           validator=lambda v: _v_float(v, 50.0, 500.0)),)))
_reg(ActionSpec(
    "set_fig_width", 3, "A",
    "【Level-3】定点设置某一张插图宽度（如缩到 0.8\\linewidth）；只改 width= 值，"
    "不动图片文件与内容。target 省略=全部",
    _wrap_set_fig_width,
    (Param("width", "str", "宽度表达式：\\linewidth / 0.8\\linewidth / 120mm",
           True, None, _v_width),
     Param("target", "target", "目标插图：'fig#2' / 2 / 省略", False, None,
           _v_target))))


# ---------------------------------------------------------------- 对外接口

def describe() -> list[dict]:
    """给 LLM 读的白名单说明（llm_request.json 的 allowed_actions）。"""
    out = []
    for name, s in WHITELIST.items():
        out.append({
            "action": name,
            "level": s.level,
            "category": s.category,
            "doc": s.doc,
            "params": [
                {"name": p.name, "type": p.type, "required": p.required,
                 "default": p.default, "doc": p.doc}
                for p in s.params],
        })
    return out


def validate(action: str, params: dict | None) -> dict:
    """校验一个动作请求。返回 {ok, params, errors}；不在此白名单 → ok=False。

    这是「LLM 不能随意改论文」的强制闸门：未知动作一律 BLOCKED。"""
    params = dict(params or {})
    spec = WHITELIST.get(action)
    if spec is None:
        return {"ok": False, "params": {}, "errors": [
            f"动作 '{action}' 不在白名单中（BLOCKED）：允许的动作见 "
            f"allowed_actions"], "blocked": True}
    errors = []
    clean = {}
    known = {p.name for p in spec.params}
    for extra in set(params) - known:
        errors.append(f"未知参数 '{extra}'（{action} 只接受 {sorted(known)}）")
    for p in spec.params:
        if p.name not in params or params[p.name] is None:
            if p.required:
                errors.append(f"缺少必填参数 '{p.name}'")
            elif p.default is not None:
                clean[p.name] = p.default
            continue
        v, err = p.validator(params[p.name]) if p.validator \
            else (params[p.name], "")
        if err:
            errors.append(f"参数 '{p.name}' 不合法：{err}")
        else:
            clean[p.name] = v
    return {"ok": not errors, "params": clean, "errors": errors,
            "blocked": bool(errors)}


def apply(action: str, src: str, params: dict | None = None) -> dict:
    """校验并执行白名单动作。返回 {ok, applied, note, errors, new_src}。

    绝不在校验失败时改源；返回 new_src 为 None 表示未执行。"""
    v = validate(action, params)
    if not v["ok"]:
        return {"ok": False, "applied": False, "note": "",
                "errors": v["errors"], "new_src": None}
    spec = WHITELIST[action]
    try:
        res = spec.func(src, v["params"])
    except Exception as exc:                      # 动作内部异常 -> 不落地
        return {"ok": False, "applied": False, "note": "",
                "errors": [f"动作执行异常：{exc}"], "new_src": None}
    new_src, applied, note = res[0], res[1], res[2]
    if applied and new_src is None:
        return {"ok": False, "applied": False, "note": note,
                "errors": ["动作返回了 applied 但无新源码"], "new_src": None}
    return {"ok": True, "applied": bool(applied), "note": note,
            "errors": [], "new_src": new_src if applied else None}
