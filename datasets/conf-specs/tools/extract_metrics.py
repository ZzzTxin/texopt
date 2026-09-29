#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""extract_metrics.py —— 阶段 1：全库逐篇提取 page_metrics.v1 并缓存。

输入：`samples/*.samples.list.json`（含 sample_id / venue / year / pdf_url）
      + `sources/raw/pdfs/*.pdf`（下载缓存，文件名由 pdf_url 归一而来）
输出：`metrics/pages/<sample_id>.json`（page_metrics.v1）
      `metrics/index.json`（逐篇：venue/year/页数/角色分布/耗时/错误）

特性
  * **可续跑**：已存在的输出默认跳过（`--force` 覆盖），长任务中断不丢进度。
  * **单篇隔离**：任一篇失败只记 error，不中断全库。
  * **诚实计数**：index 里同时记 ok / failed / missing-pdf，便于核对覆盖率。

用法：
    python3 tools/extract_metrics.py                 # 全库（跳过已完成）
    python3 tools/extract_metrics.py --limit 20       # 只跑前 20 篇
    python3 tools/extract_metrics.py --venues cvpr,acl
    python3 tools/extract_metrics.py --force --limit 5
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
DS = os.path.dirname(HERE)                      # datasets/conf-specs
ROOT = os.path.dirname(os.path.dirname(DS))     # texopt 仓库根
sys.path.insert(0, ROOT)

PDFS = os.path.join(DS, "sources", "raw", "pdfs")
OUTDIR = os.path.join(DS, "metrics", "pages")
INDEX = os.path.join(DS, "metrics", "index.json")


def pdf_cache_name(url: str) -> str:
    """与 measure_pdf.download() 完全一致的缓存命名（保持可复现）。"""
    name = re.sub(r"[^A-Za-z0-9._-]", "_", url.split("//", 1)[-1])[-120:].strip("_")
    if not name.lower().endswith(".pdf"):
        name += ".pdf"
    return name


def load_samples():
    out = []
    for f in sorted(glob.glob(os.path.join(DS, "samples", "*.samples.list.json"))):
        d = json.load(open(f, encoding="utf-8"))
        venue = (d.get("conference") or os.path.basename(f).split(".")[0]).lower()
        for s in d.get("papers") or []:
            url = s.get("pdf_url") or ""
            out.append({
                "sample_id": s.get("sample_id"),
                "venue": venue,
                "year": s.get("year"),
                "title": (s.get("title") or "")[:120],
                "pdf_url": url,
                "pdf": os.path.join(PDFS, pdf_cache_name(url)) if url else None,
            })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--venues", default="")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--pixels", action="store_true",
                    help="同时算像素层（慢很多；默认只用矢量/文本层）")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    from texopt import extract as E
    from texopt import page_metrics as PM

    samples = load_samples()
    if args.venues:
        want = {v.strip().lower() for v in args.venues.split(",") if v.strip()}
        samples = [s for s in samples if s["venue"] in want]
    if args.limit:
        samples = samples[:args.limit]

    os.makedirs(OUTDIR, exist_ok=True)
    idx = {}
    if os.path.isfile(INDEX):
        try:
            idx = json.load(open(INDEX, encoding="utf-8"))
        except Exception:
            idx = {}
    recs = idx.setdefault("papers", {})
    t_all = time.time()
    ok = failed = missing = skipped = 0

    for i, s in enumerate(samples, 1):
        sid = s["sample_id"]
        dst = os.path.join(OUTDIR, f"{sid}.json")
        if os.path.isfile(dst) and not args.force:
            skipped += 1
            continue
        if not s["pdf"] or not os.path.isfile(s["pdf"]):
            missing += 1
            recs[sid] = {**{k: v for k, v in s.items() if k != "pdf"},
                         "status": "missing-pdf"}
            continue
        t0 = time.time()
        try:
            doc = E.extract_pdf(s["pdf"], venue=s["venue"], year=s["year"],
                                pixels=args.pixels)
            errs = PM.validate(doc)
            if errs:
                raise RuntimeError("schema 校验失败：" + "; ".join(errs[:3]))
            PM.dump(doc, dst)
            recs[sid] = {
                "venue": s["venue"], "year": s["year"], "title": s["title"],
                "status": "ok", "pages": doc["doc"]["pages"],
                "layout": doc["doc"]["layout"],
                "roles": doc["paper"]["roles_hist"],
                "seconds": doc["meta"]["extract_seconds"],
                "bytes": os.path.getsize(dst),
            }
            ok += 1
        except Exception as exc:                      # 单篇失败不中断全库
            failed += 1
            recs[sid] = {**{k: v for k, v in s.items() if k != "pdf"},
                         "status": "failed", "error": f"{type(exc).__name__}: {exc}"[:300]}
            if not args.quiet:
                print(f"  [FAIL] {sid}: {type(exc).__name__}: {exc}"[:160])
        if not args.quiet and (i % 10 == 0 or i == len(samples)):
            el = time.time() - t_all
            print(f"  {i}/{len(samples)}  ok={ok} failed={failed} missing={missing} "
                  f"skip={skipped}  {el:.0f}s  ({el / max(1, ok + failed):.1f}s/篇)")
        if i % 20 == 0:                               # 定期落盘 index，防丢进度
            idx["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            idx["counts"] = {"ok": ok, "failed": failed, "missing_pdf": missing,
                             "skipped": skipped}
            with open(INDEX, "w", encoding="utf-8") as f:
                json.dump(idx, f, ensure_ascii=False, indent=1)

    idx["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    idx["counts"] = {"ok": ok, "failed": failed, "missing_pdf": missing,
                     "skipped": skipped, "total_samples": len(samples)}
    idx["schema"] = "page_metrics.v1"
    with open(INDEX, "w", encoding="utf-8") as f:
        json.dump(idx, f, ensure_ascii=False, indent=1)
    print(f"\n完成：ok={ok} failed={failed} missing={missing} skipped={skipped} "
          f"共 {len(samples)} 篇，用时 {time.time() - t_all:.0f}s")
    print(f"输出：{OUTDIR}  |  索引：{INDEX}")


if __name__ == "__main__":
    main()
