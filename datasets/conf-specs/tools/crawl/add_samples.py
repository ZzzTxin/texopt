#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""add_samples.py —— 把候选论文「入库」：补溯源来源 + 追加样本清单。

这一步是新增论文与既有 107 篇保持**同一格式**的关键环节。每篇候选按顺序做三件事：

  1. 归档落地页：tools/fetch_source.sh <src-id> <landing_url> html
     → sources/raw/<src-id>.html/.txt + sources/fetch_log.jsonl（sha256/http/时间）
  2. 生成 Source 条目（kind=sample-paper）：tools/mk_source.py（sha256 从日志读取，禁止手抄）
     → 追加进 conferences/<cid>.json 的 sources[]
  3. 追加样本条目进 samples/<cid>.samples.list.json 的 papers[]
     → 字段顺序与既有样本一致：sample_id/title/venue/year/url/pdf_url/anthology_id/
       evidence_source_id/note

命名规则（与既有样本对齐）：
    sample_id = s-<cid>-<year>-<NNN>          NNN 按 (会议,年份) 递增，不覆盖已有编号
    src-id    = 默认 src-s-<cid>-<year>-<NNN>-abs
                ACL 系（acl/emnlp/naacl/coling）= src-<cid>-<year>-paper-<anthology 尾号>
                AAAI = src-s-<cid>-<year>-<NNN>（既有样本不带 -abs）
                ECCV = src-eccv-papers-list（全会议共用一条：证据就是 ECVA 索引页本身）
                ICLR（Tier B，arXiv 版）= src-s-iclr-<year>-arxiv-<arxiv_id>

幂等：已在 papers[] 里出现过的 pdf_url/标题会跳过；同一 src-id 已存在也跳过
      （共享来源的会议---如 ECCV---改为复用该来源，不跳过该篇）。
每写入一篇就落盘一次（原子写），中断不会丢进度，重跑可续。

用法：
    python3 tools/crawl/add_samples.py --conference neurips --from candidates/neurips.jsonl --limit 30
    python3 tools/crawl/add_samples.py --conference cvpr --from candidates/cvpr.jsonl --year 2024
    python3 tools/crawl/add_samples.py --conference acl --from candidates/acl.jsonl --dry-run
"""
from __future__ import annotations

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common                                            # noqa: E402
import styles                                            # noqa: E402

FAMILY_BY_CID = {"neurips": "neurips", "cvpr": "cvf", "iccv": "cvf", "wacv": "cvf",
                 "icml": "mlr", "acl": "acl", "emnlp": "acl", "naacl": "acl",
                 "coling": "acl", "ijcai": "ijcai", "osdi": "usenix",
                 "nsdi": "usenix", "atc": "usenix", "fast": "usenix",
                 "security": "usenix", "aaai": "aaai", "eccv": "ecva"}


def family_of(cid: str, cand: dict) -> str:
    return cand.get("note_family") or FAMILY_BY_CID.get(cid) or "neurips"


def next_index(papers: list[dict], cid: str, year: int) -> int:
    pat = re.compile(rf"^s-{re.escape(cid)}-{year}-(\d+)$")
    mx = 0
    for p in papers:
        m = pat.match(str(p.get("sample_id") or ""))
        if m:
            mx = max(mx, int(m.group(1)))
    return mx + 1


def main() -> int:
    ap = argparse.ArgumentParser(description="候选清单 → samples/ + conferences/ sources[]")
    ap.add_argument("--conference", "-c", required=True)
    ap.add_argument("--from", dest="src", default="", help="候选 jsonl（默认 candidates/<cid>.jsonl）")
    ap.add_argument("--limit", type=int, default=30, help="本次最多入库多少篇")
    ap.add_argument("--year", type=int, default=None, help="只入库某年")
    ap.add_argument("--sleep", type=float, default=common.DEFAULT_INTERVAL)
    ap.add_argument("--dry-run", action="store_true", help="只打印计划，不联网不写文件")
    ap.add_argument("--no-verify-pdf", action="store_true",
                    help="不先探测 pdf_url（默认先 Range 探测，PDF 不可用就跳过，避免把坏链接写进库）")
    args = ap.parse_args()

    cid = args.conference
    conf_path = os.path.join(common.ROOT, "conferences", f"{cid}.json")
    list_path = os.path.join(common.ROOT, "samples", f"{cid}.samples.list.json")
    cand_path = args.src or os.path.join(common.ROOT, "candidates", f"{cid}.jsonl")

    conf = common.load_json(conf_path)
    if conf is None:
        print(f"没有 conferences/{cid}.json（新会议要先按 BRIEF_research.md 建规范层）", file=sys.stderr)
        return 2
    slist = common.load_json(list_path)
    if slist is None:
        slist = {"conference": cid, "selection_rule": "（待补：样本挑选规则）", "papers": []}
    papers = slist.setdefault("papers", [])
    sources = conf.setdefault("sources", [])

    cands = common.read_jsonl(cand_path)
    if not cands:
        print(f"候选清单为空或不存在：{cand_path}", file=sys.stderr)
        return 2

    have_pdf = {p.get("pdf_url") for p in papers}
    have_title = {(p.get("title") or "").strip().lower() for p in papers}
    have_src = {s.get("id") for s in sources}

    todo = []
    for c in cands:
        if args.year and c.get("year") != args.year:
            continue
        if not c.get("pdf_url") or not c.get("landing_url") or not c.get("title"):
            continue
        if c["pdf_url"] in have_pdf or (c["title"] or "").strip().lower() in have_title:
            continue
        todo.append(c)
    todo = todo[:args.limit] if args.limit > 0 else todo

    print(f"[{cid}] 已有样本 {len(papers)} 篇；候选 {len(cands)} 条；本次计划入库 {len(todo)} 篇")
    if not todo:
        return 0

    cur_year, nnn = None, 1
    added = 0
    for i, c in enumerate(todo, 1):
        year = int(c["year"])
        if year != cur_year:
            cur_year, nnn = year, next_index(papers, cid, year)
        fam = family_of(cid, c)
        sid = styles.src_id_for(cid, year, nnn, c, note_family=fam)
        sample_id = f"s-{cid}-{year}-{nnn:03d}"
        note = styles.NOTES.get(fam, styles.NOTES["neurips"]).format(venue=c.get("venue"))
        if args.dry_run:
            print(f"  [{i}/{len(todo)}] {sample_id}  {sid}\n      {c['title'][:70]}\n      {c['landing_url']}")
            nnn += 1
            continue
        reuse = sid in have_src
        if reuse and not styles.shared_src(cid):
            print(f"  - 跳过（source {sid} 已存在）")
            nnn += 1
            continue
        if not args.no_verify_pdf:
            ok, info = common.probe_pdf(c["pdf_url"], interval=args.sleep)
            if not ok:
                print(f"  ! 跳过（PDF 不可用 {info}）{c['title'][:55]}", file=sys.stderr)
                nnn += 1
                continue
        if not reuse:
            ok, msg = common.fetch_source(sid, c["landing_url"], "html")
            if not ok:
                print(f"  ! 归档失败 {sid}: {msg[:140]}", file=sys.stderr)
                nnn += 1
                continue
        try:
            entry = common.src_entry(sid, kind="sample-paper", title=c["title"], note=note,
                                     pdf_url=c["pdf_url"], venue=c.get("venue"),
                                     year=year, anthology_id=c.get("anthology_id"))
        except RuntimeError as exc:
            print(f"  ! 生成 Source 失败 {sid}: {exc}", file=sys.stderr)
            nnn += 1
            continue
        if not reuse:
            sources.append(entry)
            have_src.add(sid)
        papers.append({
            "sample_id": sample_id,
            "title": c["title"],
            "venue": c.get("venue"),
            "year": year,
            "url": c["landing_url"],
            "pdf_url": c["pdf_url"],
            "anthology_id": c.get("anthology_id"),
            "evidence_source_id": sid,
            "note": note,
        })
        have_pdf.add(c["pdf_url"])
        have_title.add((c["title"] or "").strip().lower())
        common.dump_json(conf_path, conf)          # 每篇落盘一次，可中断可续跑
        common.dump_json(list_path, slist)
        added += 1
        print(f"  [{i}/{len(todo)}] ✓ {sample_id} ← {sid}{'（复用共享来源）' if reuse else ''}  {c['title'][:60]}")
        nnn += 1

    if not args.dry_run:
        print(f"\n[{cid}] 本次新增 {added} 篇；样本共 {len(papers)} 篇，sources 共 {len(sources)} 条")
        print("下一步（溯源闸门 → 测量聚合 → 模板链）：")
        print(f"  python3 tools/validate.py conferences/{cid}.json")
        print(f"  python3 tools/check_sample_links.py {cid}")
        print(f"  python3 tools/build_dataset.py --only {cid}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
