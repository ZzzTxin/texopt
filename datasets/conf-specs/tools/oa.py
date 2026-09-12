#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""oa.py —— 通过 OpenAlex 按标题查论文元数据（找 arXiv id / 落地页）。

用途：为样本论文找到可下载的 PDF 直链（arXiv），本地无法用 arXiv API（限流）时的替代。
用法: python3 tools/oa.py "Title one" "Title two" ...
"""
import json
import sys
import urllib.parse
import urllib.request

UA = "texopt-dataset/1.0 (mailto:noreply@example.org)"


def q(title: str):
    url = ("https://api.openalex.org/works?per-page=3&search="
           + urllib.parse.quote(title))
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=40) as fh:
        d = json.load(fh)
    out = []
    for w in d.get("results", [])[:3]:
        locs = w.get("locations") or []
        pdf = None
        for l in locs:
            if l.get("pdf_url"):
                pdf = l["pdf_url"]
                break
        ids = w.get("ids") or {}
        out.append({"title": (w.get("title") or "")[:90],
                    "doi": w.get("doi"), "arxiv": ids.get("arxiv"),
                    "landing": (w.get("primary_location") or {}).get("landing_page_url"),
                    "pdf": pdf, "year": w.get("publication_year"),
                    "venue": ((w.get("primary_location") or {}).get("source") or {}).get("display_name")})
    return out


for t in sys.argv[1:]:
    print("##", t)
    try:
        for r in q(t):
            print("   ", json.dumps(r, ensure_ascii=False))
    except Exception as ex:
        print("    ERR", type(ex).__name__, ex)
