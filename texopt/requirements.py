# -*- coding: utf-8 -*-
"""要求规格层：把「投稿对象的要求」结构化为一组 Requirement。

主线定位（2026-09-09 用户重对齐）：
  texopt 是「论文整体排版优化 Agent」，不是页数压缩器。
  Page Limit 只是要求规格里的一个可选字段（L 硬约束之一）。

要求来源（三层对接接口）：
  1. 期刊/会议模板预设：--template ieee|acm|springer-llncs|...（templates/*.json）
  2. 自定义要求文件：--require my_reqs.json（自由给出详细要求）
  3. CLI 参数 / settings.json（旧字段 target_pages 等仍然兼容）

期刊模板 = 一组结构化要求。当前版以「不动 documentclass、不改正文」为界，
落地可执行参数（字号/页数/边距/浮动体策略/超宽阈值/质量开关）；
跨文档类的模板迁移（如 article -> IEEEtran）属后续阶段，见 README。
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict

# 内置模板兜底；外置模板放 templates/<id>.json（同名外置会覆盖内置项）
BUILTIN_TEMPLATES = {
    "ieee": {
        "name": "IEEE (conference/journal)",
        "desc": "IEEE 会议/期刊基调：紧凑版面、小字号正文",
        "font_pt": 10, "float_spec": "tbp",
        "overwide_fig_threshold_mm": 120.0,
    },
    "acm": {
        "name": "ACM (conference)",
        "desc": "ACM 会议基调：10pt 正文、规范浮动体",
        "font_pt": 10, "float_spec": "tbp",
        "overwide_fig_threshold_mm": 120.0,
    },
    "springer-llncs": {
        "name": "Springer LNCS",
        "desc": "LNCS 基调：10pt 正文（跨类迁移后续阶段支持）",
        "font_pt": 10, "float_spec": "tbp",
        "overwide_fig_threshold_mm": 120.0,
    },
    "custom": {
        "name": "自定义要求",
        "desc": "无预设，完全由 --require 文件 / --settings 给定",
    },
    "report": {
        "name": "学位/技术报告 (report)",
        "desc": "报告基调：目录页 + 页眉 + 彩色标题，并清理阅读辅助/告示块",
        "toc": True, "running_header": True,
        "heading_color": "0,62,120",
        "strip_reading_aids": True, "remove_warning_boxes": True,
        "float_spec": "tbp",
    },
}


@dataclass
class Requirement:
    # ---- L：基础逻辑量化（硬约束） ----
    page_limit: int | None = None        # 页数上限；None = 不约束页数
    # ---- 硬性排版规范（要求明确指定才作为 L 项执行；None = 尊重原稿） ----
    font_pt: int | None = None           # 期望正文字号档（10/11/12）
    margin_mm: float | None = None       # 期望等效单边页边距（mm）
    margin_is_floor: bool = False        # True：margin_mm 是「下限」（会议模板口径）——
                                         #   低于下限才判违规，高于下限不干预；
                                         # False：与 margin_mm 不等即违规（旧行为）
    eq_fleqn_allowed: bool = False       # False：移除 fleqn，公式保持居中
    # ---- 结构规范（前置结构 / 版面规范，2026-09-10 新增） ----
    toc: bool = False                    # 需要目录页（\tableofcontents）
    toc_min_sections: int = 3            # 章节数达该值时才要求目录
    running_header: bool = False         # 需要页眉（fancyhdr）
    header_left: str | None = None       # 页眉左（默认 \@title）
    header_right: str | None = None      # 页眉右（默认 \thepage）
    heading_color: str | None = None     # 标题强调色："0,62,120"/"RGB:.."/颜色名
    strip_reading_aids: bool = True      # 删阅读辅助内容（START READING HERE 等）
    remove_warning_boxes: bool = True    # 删 WARNING/CAUTION/ATTENTION 告示块
    preserve_figures: bool = True        # 图形内容保真（不得重绘/修改）
    # ---- 审美 / 质量策略 ----
    enable_quality_macros: bool = True   # 注入断行质量宏（防孤行寡行/连字符堆叠）
    float_spec: str = "tbp"              # 浮动体参数规范（[h]/[h!] 不稳定写法被规范化）
    microtype: bool | None = None        # None = 按原稿现状不干预
    # ---- 超宽检测（A 项；表格超宽只报告不自动改） ----
    overwide_fig_threshold_mm: float = 150.0   # 插图数值宽度超过即归一
    overwide_table_report: bool = True         # 超宽表：检测并在报告列出
    # ---- 页数压缩参数（仅当 page_limit 设定且超页时启用） ----
    allow_geometry_tune: bool = False    # 允许为压页调整全局版心（页边距/字号）
    margin_min_mm: float = 20.0          # 压缩页边距安全下限（不得低于要求 margin）
    margin_step_mm: float = 2.0          # 每档步长
    allow_fontsize_step: bool = True     # 允许把字号降到要求档以下（下限 10pt）
    # ---- 运行参数 ----
    max_iterations: int = 40
    verbose: bool = True
    # ---- 阶段 6：审美档案影子接入（λ=0，仅报告；不影响任何接受/回滚判定） ----
    aesthetic_shadow: bool = True          # 关：不跑影子评估（省时/离线回归用）
    shadow_profile: str | None = None      # 档案路径覆盖（None=随附档案）
    # ---- 确定性排版修复策略（2026-09-11 新增；默认开，均可单独关闭） ----
    # 这些是「检测 -> 动作」补齐后新增的白名单动作开关；关闭即不生成候选。
    tidy_manual_pagebreaks: bool = True    # 删正文 \newpage/\clearpage
    tidy_manual_vspace: bool = True        # 删过大的 \vspace{...}
    vspace_min_mm: float = 10.0            # “过大”垂直间距阈值（mm）
    normalize_heading_size: bool = True    # 标题字号压回层级上限
    normalize_local_font_size: bool = True  # 删正文行内字号乱标
    reduce_list_spacing: bool = True       # 收紧列表垂直间距
    list_spacing_max_pt: float = 8.0       # 列表间距“过大”阈值（pt）
    break_long_words: bool = True          # 为超长不可断词插入 \- 断词点
    break_long_urls: bool = True           # 超长 URL 注入 xurl（允许任意位置断行）
    fix_overwide_tables: bool = True       # 超宽表格改 tabularx 自适应
    balance_pages: bool = True             # 注入 \raggedbottom（页面平衡）
    free_floating_H: bool = True           # [H] 强排 -> [tbp]（交给全局放置）
    # ---- Phase 2：页面级视觉量化与版面级修复（2026-09-11 新增） ----
    visual_metrics: bool = True            # 从编译后的 PDF 量取页面视觉指标（并入 A）
    visual_dpi: int = 50                   # 视觉量化渲染 DPI（越低越快）
    normalize_title: bool = True           # \title{\Huge ...} 压回层级上限
    title_size_cap: str = "LARGE"          # 标题允许的最大字号
    normalize_parskip: bool = True         # 收敛过大的 \parskip
    parskip_max_pt: float = 8.0
    normalize_header: bool = True          # 清空过长页眉内容
    header_max_chars: int = 40
    remove_mid_multicols: bool = True      # 移除正文中途的局部双栏
    reduce_oversized_figures: bool = True  # 过大图片高度/子图并排超版心
    max_fig_height_frac: float = 0.40
    subfig_max_sum: float = 0.95
    narrow_table_min_frac: float = 0.6     # 列宽合计 < 该比例×版心 -> 判为窄表
    tune_float_placement: bool = True      # 浮动体放置/页面平衡调优
    shrink_oversized_figures: bool = True   # 按视觉信号缩小满宽大图（巨大内容块）
    fig_shrink_factor: float = 0.85         # 每次缩放系数
    done_max_a: float | None = None        # A 绝对上限（None=不设，靠视觉缺陷清单判定）
    min_stall_rounds: int = 2              # 连续无改善轮数达到才停（避免过早收敛）
    # ---- 会议要求（会议模板 templates-v2；2026-09-12 新增） ----
    # 会议之间的差异全部由 json 字段驱动，不为任何会议写单独代码。
    conference: str | None = None          # 会议 id（aaai/icml/...）；None = 未指定
    page_limit_scope: str = "total"        # total=总页数口径；content=正文页口径
    official_constraints: dict | None = None   # 官方硬约束摘要（违规判定/报告用）
    soft_targets: dict | None = None           # 真实论文统计（只作合理性核对）
    unused_template_parts: list | None = None  # 模板中本版接不上的字段（明确记录）

    # ------------------------------------------------------------ 来源合并
    @classmethod
    def load(cls, tex_dir: str = ".", template: str | None = None,
             require_file: str | None = None,
             settings: dict | None = None,
             base: dict | None = None) -> "Requirement":
        """按优先级合并：会议/模板预设 < 要求文件 < settings < CLI（None 字段忽略）。

        base：会议模板（texopt.conference）投影出的扁平字段，优先级最低，
        只提供默认值；用户显式给定的 --require / --settings / CLI 一律覆盖它。
        """
        base_d: dict = {}

        def merge(d: dict):
            for k, v in (d or {}).items():
                if v is None or k in ("template", "name", "desc"):
                    continue            # 模板选择/描述信息由调用方决定，非规格字段
                base_d[k] = v

        merge(base)                     # 会议模板（若有）优先级最低

        tpl = template or "custom"
        builtin = BUILTIN_TEMPLATES.get(tpl)
        if builtin:
            merge(builtin)
        else:
            f = os.path.join(tex_dir, "templates", f"{tpl}.json")
            if os.path.isfile(f):
                with open(f, encoding="utf-8") as fh:
                    merge(json.load(fh))
            else:
                raise ValueError(
                    f"未知模板 '{tpl}'：不在内置预设，且 {f} 不存在")

        if require_file:
            p = require_file if os.path.isabs(require_file) \
                else os.path.join(tex_dir, require_file)
            with open(p, encoding="utf-8") as fh:
                merge(json.load(fh))

        if settings:
            s = dict(settings)
            if "target_pages" in s and "page_limit" not in s:
                s["page_limit"] = s.pop("target_pages")
            merge(s)

        known = set(cls.__dataclass_fields__)
        extra = set(base_d) - known
        if extra:
            raise ValueError(f"要求规格里有未知字段：{sorted(extra)}")
        obj = cls(**base_d)
        obj._template = tpl
        return obj

    @property
    def name(self) -> str:
        return getattr(self, "_template", None) or "custom"

    def to_dict(self) -> dict:
        return asdict(self)


def list_templates(tex_dir: str = ".") -> list[dict]:
    """列出可用模板：内置 + templates/ 目录下的 *.json（外置覆盖同名内置）。"""
    merged = {k: {**v, "id": k} for k, v in BUILTIN_TEMPLATES.items()}
    tdir = os.path.join(tex_dir, "templates")
    if os.path.isdir(tdir):
        for fn in sorted(os.listdir(tdir)):
            if not fn.endswith(".json"):
                continue
            tid = fn[:-5]
            try:
                with open(os.path.join(tdir, fn), encoding="utf-8") as fh:
                    d = json.load(fh)
                merged[tid] = {"id": tid, "name": d.get("name", tid),
                               "desc": d.get("desc", "")}
            except Exception:
                merged[tid] = {"id": tid, "name": tid, "desc": "(解析失败)"}
    return [{"id": v["id"], "name": v.get("name", v["id"]),
             "desc": v.get("desc", "")}
            for v in merged.values()]
