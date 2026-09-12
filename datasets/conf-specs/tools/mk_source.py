#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""mk_source.py —— 从 sources/fetch_log.jsonl 生成 conferences/*.json 里的 Source 条目。

目的：sha256 / fetched_at / http_status / raw_file 一律从抓取日志读取，禁止手抄（防错、防伪造）。

用法:
    python3 tools/mk_source.py <src_id> --kind official-guidelines --title "NeurIPS 2025 CFP" \
        [--note "官方 CFP 页"] [--pdf-url U] [--venue "NeurIPS 2024"] [--year 2024] \
        [--anthology-id ID] [--indent 2]

    # 一次多个（逗号分隔），输出 JSON 数组：
    python3 tools/mk_source.py a,b,c --kind sample-paper --title "?"      # title 用 --title-map

只输出 JSON 到 stdout，可直接粘进文件的 sources[] 数组。
"""
from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = os.path.join(ROOT, "sources", "fetch_log.jsonl")

# kind 取值（见 KEY_VOCAB.md §5）
KINDS = {"official-guidelines", "official-template", "style-source", "sample-paper", "third-party"}


def load_log() -> dict:
    """后入覆盖先入：同一 src_id 重抓时以最后一次为准。"""
    recs: dict[str, dict] = {}
    if not os.path.exists(LOG):
        return recs
    for line in open(LOG, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        recs[r["src_id"]] = r
    return recs


def build(rec: dict, args: argparse.Namespace, title: str) -> dict:
    out = {
        "id": rec["src_id"],
        "kind": args.kind,
        "title": title,
        "url": rec["url"],
        "fetched_at": rec["fetched_at"],
        "http_status": rec["http_status"],
        "raw_file": rec["raw_file"],
        "sha256": rec["sha256"],
    }
    if args.kind == "sample-paper":
        out["pdf_url"] = args.pdf_url
        out["venue"] = args.venue
        out["year"] = args.year
        if args.anthology_id:
            out["anthology_id"] = args.anthology_id
    if args.note:
        out["note"] = args.note
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("src_ids", help="逗号分隔的 src-id（可在核心 id 前加 src- 前缀，只写核心也可）")
    ap.add_argument("--kind", required=True, choices=sorted(KINDS))
    ap.add_argument("--title", default="")
    ap.add_argument("--title-map", default="", help='JSON 对象：{"src-id":"Title", ...}')
    ap.add_argument("--note", default="")
    ap.add_argument("--pdf-url", default=None)
    ap.add_argument("--venue", default=None)
    ap.add_argument("--year", type=int, default=None)
    ap.add_argument("--anthology-id", default=None)
    ap.add_argument("--indent", type=int, default=2)
    args = ap.parse_args()

    log = load_log()
    tmap = json.loads(args.title_map) if args.title_map else {}
    ids = [s.strip() for s in args.src_ids.split(",") if s.strip()]
    out = []
    for sid in ids:
        key = sid if sid in log else (sid if sid.startswith("src-") else "src-" + sid)
        if key not in log:
            print(f"ERROR: {sid} 不在 fetch_log.jsonl（先用 tools/fetch_source.sh 抓取）", file=sys.stderr)
            return 1
        title = tmap.get(key) or tmap.get(sid) or args.title or key
        out.append(build(log[key], args, title))

    data = out[0] if len(out) == 1 else out
    print(json.dumps(data, ensure_ascii=False, indent=args.indent))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
