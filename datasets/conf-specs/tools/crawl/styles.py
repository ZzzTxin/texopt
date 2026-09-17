# -*- coding: utf-8 -*-
"""crawl/styles.py —— 新增样本的「命名与归属样式」单一来源。

为什么需要它：既有 107 篇样本的命名并不统一（是分批人工写的）：
    neurips/cvpr/iccv   venue="NeurIPS 2024"   src=src-s-neurips-2024-001-abs
    acl/emnlp           venue="ACL 2025"       src=src-acl-2025-paper-348（用 anthology 尾号）
    ijcai               venue="IJCAI 2025"     src=src-ijcai-2025-paper-50（用论文序号）
    osdi/nsdi           venue="OSDI '24"       src=src-osdi24-pres-<slug>
    icml                venue="International Conference on Machine Learning"
                                               src=src-s-icml-2025-001

新样本必须**贴着同一个会议既有样本的写法**追加，否则同一个会议里出现两套命名。
所以 venue 字符串与 src-id 模板都在这里按会议登记，venues.py 与 add_samples.py 共用。

模板占位符：{cid} {year} {yy}(两位年) {nnn:03d}(序号) {anth}(anthology 尾号)
            {num}(论文序号) {slug}(USENIX 落地页末段) {arxiv}
"""
from __future__ import annotations

import re

DEFAULT_STYLE = {
    "venue": "{abbr} {year}",
    "src": "src-s-{cid}-{year}-{nnn:03d}-abs",
}

CONF_STYLE: dict[str, dict] = {
    # ---- proceedings.neurips.cc
    "neurips": {"venue": "NeurIPS {year}", "src": "src-s-{cid}-{year}-{nnn:03d}-abs"},
    # ---- CVF open access
    "cvpr": {"venue": "CVPR {year}", "src": "src-s-{cid}-{year}-{nnn:03d}-abs"},
    "iccv": {"venue": "ICCV {year}", "src": "src-s-{cid}-{year}-{nnn:03d}-abs"},
    "wacv": {"venue": "WACV {year}", "src": "src-s-{cid}-{year}-{nnn:03d}-abs"},
    # ---- PMLR（既有样本用的是会议全称）
    "icml": {"venue": "International Conference on Machine Learning",
             "src": "src-s-{cid}-{year}-{nnn:03d}"},
    # ---- ACL Anthology（src 用 anthology 尾号）
    "acl": {"venue": "ACL {year}", "src": "src-{cid}-{year}-paper-{anth}"},
    "emnlp": {"venue": "EMNLP {year}", "src": "src-{cid}-{year}-paper-{anth}"},
    "naacl": {"venue": "NAACL {year}", "src": "src-{cid}-{year}-paper-{anth}"},
    "coling": {"venue": "COLING {year}", "src": "src-{cid}-{year}-paper-{anth}"},
    # ---- IJCAI（src 用论文序号）
    "ijcai": {"venue": "IJCAI {year}", "src": "src-{cid}-{year}-paper-{num}"},
    # ---- USENIX（venue 用 'YY 简写，src 用 presentation slug）
    "osdi": {"venue": "OSDI '{yy}", "src": "src-{cid}{yy}-pres-{slug}"},
    "nsdi": {"venue": "NSDI '{yy}", "src": "src-{cid}{yy}-pres-{slug}"},
    "atc": {"venue": "USENIX ATC '{yy}", "src": "src-{cid}{yy}-pres-{slug}"},
    "fast": {"venue": "FAST '{yy}", "src": "src-{cid}{yy}-pres-{slug}"},
    "security": {"venue": "USENIX Security '{yy}", "src": "src-{cid}{yy}-pres-{slug}"},
    # ---- AAAI OJS（既有样本：venue="AAAI-25"，src=src-s-aaai-2025-001 每篇一条）
    "aaai": {"venue": "AAAI-{yy}", "src": "src-s-{cid}-{year}-{nnn:03d}"},
    # ---- ECCV（既有样本：venue="ECCV 2024"，url 就是 ECVA 索引页）
    #     证据是「同一页索引」，全会议共用一条来源 src-eccv-papers-list。
    "eccv": {"venue": "ECCV {year}", "src": "src-eccv-papers-list"},
}

NOTES = {
    "neurips": "官方 proceedings 索引列出该论文（source 归档为该论文的官方 abstract 落地页）",
    "cvf": "CVF Open Access 论文落地页（官方论文集），用于证明属 {venue}",
    "mlr": "PMLR 官方 proceedings 论文落地页（含会议全称），用于证明属 {venue}",
    "acl": "ACL Anthology 论文落地页（含 venue 归属标注），用于证明属 {venue}",
    "ijcai": "IJCAI 官方 proceedings 论文落地页，用于证明属 {venue}",
    "usenix": "USENIX 官方 technical sessions 论文落地页，用于证明属 {venue}",
    "aaai": "AAAI 官方 proceedings（OJS）论文落地页，含卷期标注，用于证明属 {venue}",
    "ecva": "官方 ECVA 论文索引（papers.php）逐篇列出该论文，用于证明属 {venue}",
}


def style_for(cid: str) -> dict:
    return dict(DEFAULT_STYLE, **CONF_STYLE.get(cid, {}))


def venue_for(cid: str, year: int, abbr: str = "") -> str:
    return style_for(cid)["venue"].format(year=year, yy=f"{year % 100:02d}",
                                          abbr=abbr or cid.upper())


def shared_src(cid: str) -> bool:
    """该会议的 evidence source 是不是「全会议共用一条」（模板里没有逐篇占位符）。

    ECCV 就是这种：所有样本的 landing_url 都是 ECVA 索引页，来源固定为
    src-eccv-papers-list。add_samples 遇到已存在的共享来源要用它，而不是跳过该篇。
    """
    return not re.search(r"\{(nnn|anth|num|slug|arxiv)\b", style_for(cid)["src"])


def src_id_for(cid: str, year: int, nnn: int, cand: dict, note_family: str = "neurips") -> str:
    """按会议样式生成 src-id；缺失的占位符用安全回退值。"""
    if note_family == "acl":
        aid = str(cand.get("anthology_id") or "")
        anth = aid.rsplit(".", 1)[-1] if aid else str(nnn)
    else:
        anth = str(nnn)
    landing = str(cand.get("landing_url") or "").rstrip("/")
    slug = landing.rsplit("/", 1)[-1] if landing else str(nnn)
    num = slug if slug.isdigit() else str(nnn)
    if num == "0":
        num = str(nnn)
    return style_for(cid)["src"].format(
        cid=cid, year=year, yy=f"{year % 100:02d}", nnn=nnn,
        anth=anth, num=num, slug=slug,
        arxiv=str(cand.get("arxiv_id") or "") or str(nnn))
