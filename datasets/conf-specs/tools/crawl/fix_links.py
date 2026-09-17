#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fix_links.py —— 已入库样本 pdf_url 的体检 / 自动修复 / 丢弃。

它解决的是这个具体问题：`check_sample_links.py` 只能告诉你"某条不可用"，
而真正要改的是 `samples/*.samples.list.json` 与 `conferences/*.json → sources[].pdf_url`。
本脚本对每条 pdf_url 做 Range 探测，失败时按会议规则推导候选直链，命中就原地改写。

推导规则（按顺序试，第一个可用的胜出）：
  neurips   landing /hash/<h>-Abstract-<Track>.html → /file/<h>-Paper-<Track>.pdf
            （索引页没有 PDF 链接，PDF 名只能由 abstract 名推；非主会轨道同理）
  mlr       raw.githubusercontent.com/mlresearch/<vol>/main/assets/<s>/<s>.pdf
            → cdn.jsdelivr.net/gh/mlresearch/<vol>@main/assets/<s>/<s>.pdf（镜像）
            → proceedings.mlr.press/<vol>/<s>/<s>.pdf
  acl 系    landing aclanthology.org/<anth>/ → https://aclanthology.org/<anth>.pdf
  usenix    重新抓落地页，取首个非 slides 的 system/files/*.pdf
  arxiv     http://arxiv.org/pdf/<id> → https://arxiv.org/pdf/<id>

用法：
  python3 tools/crawl/fix_links.py                          # 全量体检（只报不改）
  python3 tools/crawl/fix_links.py --conference neurips
  python3 tools/crawl/fix_links.py --conference icml --apply      # 命中可修的就改写
  python3 tools/crawl/fix_links.py --drop s-neurips-2025-001,s-neurips-2025-003 --apply

改用例：--drop 会把样本条目和它的 sample-paper 来源一起从数据文件里摘掉
（已归档的 sources/raw/*.html 不删，留着当证据；samples/*.samples.jsonl 由
build_dataset.py 重新生成，无需手工改）。
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common                                            # noqa: E402

ACL_FAMILY = {"acl", "emnlp", "naacl", "coling"}


def candidates_for(cid: str, paper: dict, allow_net: bool) -> list[str]:
    """按会议规则推导可能可用的 PDF 直链（保持顺序：越可信的越前）。"""
    out: list[str] = []
    landing = str(paper.get("url") or "").strip()
    pdf = str(paper.get("pdf_url") or "").strip()

    # neurips：abstract 名 ↔ paper 名同构
    m = re.search(r"/hash/([0-9a-f]+)-Abstract-([A-Za-z_]+)\.html", landing)
    if m:
        out.append(f"https://proceedings.neurips.cc/paper_files/paper/"
                   f"{re.search(r'/paper/(\d{4})/', landing).group(1)}/file/"
                   f"{m.group(1)}-Paper-{m.group(2)}.pdf")

    # PMLR：raw.githubusercontent 抖动 → jsDelivr 镜像 / 官方站
    m = re.search(r"raw\.githubusercontent\.com/mlresearch/(v\d+)/[^/]+/assets/([^/]+)/", pdf)
    if m:
        vol, slug = m.group(1), m.group(2)
        out.append(f"https://cdn.jsdelivr.net/gh/mlresearch/{vol}@main/assets/{slug}/{slug}.pdf")
        out.append(f"https://proceedings.mlr.press/{vol}/{slug}/{slug}.pdf")
    m = re.search(r"proceedings\.mlr\.press/(v\d+)/([^/]+)\.html", landing)
    if m:
        vol, slug = m.group(1), m.group(2)
        out.append(f"https://cdn.jsdelivr.net/gh/mlresearch/{vol}@main/assets/{slug}/{slug}.pdf")
        out.append(f"https://proceedings.mlr.press/{vol}/{slug}/{slug}.pdf")

    # ACL Anthology：落地页 → PDF
    m = re.search(r"aclanthology\.org/([0-9A-Za-z.\-]+)/", landing)
    if m and cid in ACL_FAMILY:
        out.append(f"https://aclanthology.org/{m.group(1)}.pdf")

    # USENIX：重抓落地页找 PDF
    if cid in ("osdi", "nsdi", "atc", "fast", "security") and landing and allow_net:
        try:
            page = common.get_text(landing)
            pdfs = [p for p in re.findall(
                r'href="(https://www\.usenix\.org/system/files/[^"]+\.pdf)"', page)
                if "slides" not in p.lower()]
            out += pdfs[:1]
        except RuntimeError:
            pass

    # html/http 之类的小毛病
    if pdf.startswith("http://"):
        out.append("https://" + pdf[len("http://"):])
    if pdf.endswith(".PDF"):
        out.append(pdf[:-4] + ".pdf")

    seen, uniq = set(), []
    for u in out:
        if u and u != pdf and u not in seen:
            seen.add(u)
            uniq.append(u)
    return uniq


def main() -> int:
    ap = argparse.ArgumentParser(description="样本 pdf_url 体检 / 修复 / 丢弃")
    ap.add_argument("--conference", "-c", default="", help="只处理某会议（默认全部）")
    ap.add_argument("--apply", action="store_true", help="命中可修的直链就写回数据文件")
    ap.add_argument("--drop", default="", help="逗号分隔的 sample_id，直接从库里摘除（需 --apply）")
    ap.add_argument("--sleep", type=float, default=common.DEFAULT_INTERVAL)
    args = ap.parse_args()

    files = sorted(glob.glob(os.path.join(common.ROOT, "samples", "*.samples.list.json")))
    drop_ids = {x.strip() for x in args.drop.split(",") if x.strip()}
    n_ok = n_fixed = n_bad = n_dropped = 0
    report: list[str] = []

    for f in files:
        cid = os.path.basename(f).split(".")[0]
        if args.conference and cid != args.conference:
            continue
        slist = json.load(open(f, encoding="utf-8"))
        papers = slist.get("papers", [])
        if not papers:
            continue
        conf_path = os.path.join(common.ROOT, "conferences", f"{cid}.json")
        conf = common.load_json(conf_path, {}) or {}
        src_by_id = {s.get("id"): s for s in conf.get("sources", [])}
        changed = False          # 只有真发生改动才落盘（避免“末尾换行”这类空 diff）

        print(f"[{cid}] {len(papers)} 篇", flush=True)
        keep = []
        for p in papers:
            sid = p.get("sample_id")
            if sid in drop_ids:
                n_dropped += 1
                conf["sources"] = [s for s in conf.get("sources", [])
                                   if s.get("id") != p.get("evidence_source_id")]
                print(f"   - 摘除 {sid}（并删其 source {p.get('evidence_source_id')}）")
                changed = True
                continue
            url = p.get("pdf_url") or ""
            ok, info = common.probe_pdf(url, interval=args.sleep)
            if ok:
                n_ok += 1
                keep.append(p)
                continue
            fixed = None
            for cand in candidates_for(cid, p, allow_net=True):
                ok2, info2 = common.probe_pdf(cand, interval=args.sleep)
                if ok2:
                    fixed = cand
                    break
            if fixed:
                n_fixed += 1
                print(f"   ~ 修复 {sid}: {info} → {info2}\n       {fixed}")
                report.append(f"{cid}/{sid}: {url} → {fixed}")
                p["pdf_url"] = fixed
                src = src_by_id.get(p.get("evidence_source_id"))
                if src:
                    src["pdf_url"] = fixed
                if args.apply:
                    changed = True
            else:
                n_bad += 1
                print(f"   ! 修不了 {sid}: {info} {url}")
                report.append(f"{cid}/{sid}: 不可用({info}) {url}")
            keep.append(p)

        if changed and args.apply:
            slist["papers"] = keep
            common.dump_json(f, slist)
            if conf_path and os.path.exists(conf_path):
                common.dump_json(conf_path, conf)

    print(f"\n可用 {n_ok} / 已修复 {n_fixed} / 修不了 {n_bad} / 摘除 {n_dropped}")
    if n_fixed and not args.apply:
        print("（这是预览；加 --apply 才会写回 samples/*.list.json 与 conferences/*.json）")
    if report:
        out = os.path.join(common.ROOT, "summary", "link-repair-report.md")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "w", encoding="utf-8") as fh:
            fh.write("# 样本链接修复报告\n\n")
            fh.write(f"生成时间：{__import__('datetime').datetime.now().astimezone().isoformat(timespec='seconds')}\n\n")
            fh.write(f"可用 {n_ok} / 修复 {n_fixed} / 修不了 {n_bad} / 摘除 {n_dropped}\n\n")
            for line in report:
                fh.write(f"- {line}\n")
        print(f"报告 → summary/link-repair-report.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
