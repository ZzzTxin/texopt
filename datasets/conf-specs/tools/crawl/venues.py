#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""venues.py —— 从官方索引页抓「候选论文清单」（每个会议一个 adapter，只出链接不出 PDF）。

产物：candidates/<conf>.jsonl，每行一篇：
    {"title","venue","year","landing_url","pdf_url","anthology_id","source_kind"}

它只做「列清单 + 均匀抽样 + 归档索引页」；写进 samples/ 与 conferences/ 由
tools/crawl/add_samples.py 负责（那一步才补 sources[] 溯源）。

支持（Tier A：官方索引页一页拿全量直链）：
    neurips                         proceedings.neurips.cc
    icml                            proceedings.mlr.press（用 --volume vNNN）
    cvpr | iccv | wacv              openaccess.thecvf.com
    acl | emnlp | naacl | coling    aclanthology.org（--volume 2024.acl-long 覆盖版本）
    ijcai                           ijcai.org/proceedings/<year>
    osdi | nsdi | atc | fast | security   usenix.org（每个会议多一次落地页请求拿 PDF）
    aaai                            ojs.aaai.org（OJS 归档分页 → 期号 → 论文页 → galley PDF）
    eccv                            ecva.net/papers.php（ECVA 官方开放索引，2018–2024 共一页）

用法示例：
    python3 tools/crawl/venues.py --list
    python3 tools/crawl/venues.py --conference neurips --year 2024 --limit 30
    python3 tools/crawl/venues.py --conference cvpr --year 2024 --limit 30
    python3 tools/crawl/venues.py --conference acl --year 2024 --volume 2024.acl-long --limit 30
    python3 tools/crawl/venues.py --conference icml --year 2024 --limit 30     # v235
    python3 tools/crawl/venues.py --conference osdi --year 2024 --limit 20
    python3 tools/crawl/venues.py --conference aaai --years 2024,2025 --limit 30
    python3 tools/crawl/venues.py --conference eccv --year 2024 --limit 30
"""
from __future__ import annotations

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common                                            # noqa: E402
import styles                                            # noqa: E402

SPECS: dict[str, dict] = {
    # ---- NeuroIPS / ICML
    "neurips": {"family": "neurips", "abbr": "NeurIPS", "years": [2024, 2025, 2023]},
    "icml": {"family": "mlr", "abbr": "ICML",
             "volumes": {2025: "v267", 2024: "v235", 2023: "v202"}},
    # ---- ACL Anthology
    "acl": {"family": "acl", "abbr": "ACL", "vol": "{year}.acl-long"},
    "emnlp": {"family": "acl", "abbr": "EMNLP", "vol": "{year}.emnlp-main"},
    "naacl": {"family": "acl", "abbr": "NAACL", "vol": "{year}.naacl-long"},
    "coling": {"family": "acl", "abbr": "COLING", "vol": "{year}.coling-main"},
    # ---- CVF open access
    "cvpr": {"family": "cvf", "abbr": "CVPR", "cvf": "CVPR"},
    "iccv": {"family": "cvf", "abbr": "ICCV", "cvf": "ICCV"},
    "wacv": {"family": "cvf", "abbr": "WACV", "cvf": "WACV"},
    # ---- IJCAI
    "ijcai": {"family": "ijcai", "abbr": "IJCAI"},
    # ---- AAAI（OJS proceedings；venue 沿用既有样本写法 "AAAI-25"）
    "aaai": {"family": "aaai", "abbr": "AAAI", "years": [2025, 2024, 2023]},
    # ---- ECVA（ECCV 官方开放索引；全部届次共用同一页，来源固定为 src-eccv-papers-list）
    "eccv": {"family": "ecva", "abbr": "ECCV", "years": [2024, 2022, 2020],
             "index_src": "src-eccv-papers-list"},
    # ---- USENIX
    "osdi": {"family": "usenix", "abbr": "OSDI"},
    "nsdi": {"family": "usenix", "abbr": "NSDI"},
    "atc": {"family": "usenix", "abbr": "USENIX ATC"},
    "fast": {"family": "usenix", "abbr": "FAST"},
    "security": {"family": "usenix", "abbr": "USENIX Security"},
}

HELP_NOT_READY = ("iclr/kdd/www/sosp/siggraph 走的是 Tier B 路线"
                  "（OpenReview/ACM 反爬或 JS 渲染），本脚本暂不覆盖；"
                  "见 tools/crawl/README.md。")


# ---------------------------------------------------------------- adapters
def adapt_neurips(cid, year, args, spec):
    """proceedings.neurips.cc：abstract 页名与 PDF 名同构，按后缀映射。

    索引页里**没有** PDF 链接，只有 abstract 链接，所以 PDF 直链只能由 abstract 文件名推：
        /hash/<hash>-Abstract-<Track>.html  →  /file/<hash>-Paper-<Track>.pdf
    早先硬编码 "-Paper-Conference.pdf" 会在非主会轨道（如 2025 的 Creative_AI_Track）全部 404。
    默认只取主会轨道（--track Conference），--track all 可关掉过滤。
    """
    base = f"https://proceedings.neurips.cc/paper_files/paper/{year}"
    html = common.get_text(base, interval=args.sleep)
    track = getattr(args, "track", "") or "Conference"
    rows, seen, tracks = [], set(), {}
    for m in re.finditer(
            r'href="(/paper_files/paper/%d/hash/([0-9a-f]{6,})-Abstract-([A-Za-z_]+)\.html)">([^<]{5,400})</a>'
            % year, html):
        h, suffix, title = m.group(2), m.group(3), common.clean_title(m.group(4))
        tracks[suffix] = tracks.get(suffix, 0) + 1
        if track != "all" and suffix != track:
            continue
        if not title or h in seen:
            continue
        seen.add(h)
        rows.append({
            "title": title,
            "landing_url": "https://proceedings.neurips.cc" + m.group(1),
            "pdf_url": f"{base}/file/{h}-Paper-{suffix}.pdf",
        })
    if not rows and tracks:
        print(f"  ! {year} 索引里的轨道是 {tracks}，没有 '{track}'。"
              f"（主会论文集可能尚未发布；--track all 可取消过滤）", flush=True)
    return rows, base


def adapt_mlr(cid, year, args, spec):
    """proceedings.mlr.press：按 <div class="paper"> 切块，块内取标题/落地页/PDF。"""
    vol = (args.volume or spec.get("volumes", {}).get(year) or "").lstrip("/")
    if not vol:
        raise SystemExit(f"[{cid}] {year} 需要 --volume vNNN（PMLR 卷号）")
    base = f"https://proceedings.mlr.press/{vol}/"
    html = common.get_text(base, interval=args.sleep)
    rows = []
    for block in html.split('<div class="paper">')[1:]:
        t = re.search(r'<p class="title">([^<]+)</p>', block)
        land = re.search(r'href="(https://proceedings\.mlr\.press/%s/[^"]+\.html)"' % re.escape(vol), block)
        pdf = re.search(r'href="([^"]+\.pdf)"', block)
        if not (t and land and pdf):
            continue
        rows.append({"title": common.clean_title(t.group(1)),
                     "landing_url": land.group(1), "pdf_url": pdf.group(1)})
    return rows, base


def adapt_cvf(cid, year, args, spec):
    """openaccess.thecvf.com：<CONF><YEAR>?day=all，html 页与 papers PDF 按 slug 配对。"""
    conf = spec["cvf"]
    base = f"https://openaccess.thecvf.com/{conf}{year}"
    html = common.get_text(base + "?day=all", interval=args.sleep)
    pdfs = {}
    for m in re.finditer(
            r"""href=['"]/content/%s%d/papers/([^'"]+?)_paper\.pdf['"]""" % (conf, year), html):
        pdfs[m.group(1)] = "https://openaccess.thecvf.com/content/%s%d/papers/%s_paper.pdf" % (conf, year, m.group(1))
    rows, seen = [], set()
    for m in re.finditer(
            r"""href=['"]/content/%s%d/html/([^'"]+?)_paper\.html['"]\s*>([^<]{5,400})<"""
            % (conf, year), html):
        slug, title = m.group(1), common.clean_title(m.group(2))
        if not title or slug in seen:
            continue
        seen.add(slug)
        rows.append({
            "title": title,
            "landing_url": "https://openaccess.thecvf.com/content/%s%d/html/%s_paper.html" % (conf, year, slug),
            "pdf_url": pdfs.get(slug) or
                       "https://openaccess.thecvf.com/content/%s%d/papers/%s_paper.pdf" % (conf, year, slug),
        })
    return rows, base + "?day=all"


def adapt_acl(cid, year, args, spec):
    """aclanthology.org/volumes/<vid>/：属性不带引号，落地页/PDF 由 anthology id 拼出。"""
    vid = args.volume or spec["vol"].format(year=year)
    base = f"https://aclanthology.org/volumes/{vid}/"
    html = common.get_text(base, interval=args.sleep)
    rows, seen = [], set()
    for m in re.finditer(r'<a class=align-middle href=/([0-9A-Za-z.\-]+?)/>([^<]{5,400})</a>', html):
        aid, title = m.group(1), common.clean_title(m.group(2))
        if not aid.startswith(vid + ".") or not title or aid in seen:
            continue
        # x.0 是整卷前置页（Proceedings 封面/编者），不是论文
        if aid.rsplit(".", 1)[-1] == "0":
            continue
        seen.add(aid)
        rows.append({
            "title": title,
            "landing_url": f"https://aclanthology.org/{aid}/",
            "pdf_url": f"https://aclanthology.org/{aid}.pdf",
            "anthology_id": aid,
        })
    return rows, base


def adapt_ijcai(cid, year, args, spec):
    """ijcai.org/proceedings/<year>/：paper_wrapper 里有 title 与 0001.pdf。"""
    base = f"https://www.ijcai.org/proceedings/{year}/"
    html = common.get_text(base, interval=args.sleep)
    rows = []
    for m in re.finditer(
            r'<div id="paper(\d+)" class="paper_wrapper"><div class="title">([^<]+)</div>', html):
        n = int(m.group(1))
        rows.append({
            "title": common.clean_title(m.group(2)),
            "landing_url": f"{base}{n}",
            "pdf_url": f"{base}{n:04d}.pdf",
        })
    return rows, base


def adapt_usenix(cid, year, args, spec):
    """usenix.org：索引页只有 presentation 链接，标题与 PDF 要逐个落地页取（多一次请求/篇）。"""
    slug = f"{cid}{year % 100:02d}"
    base = f"https://www.usenix.org/conference/{slug}/technical-sessions"
    html = common.get_text(base, interval=args.sleep)
    links, seen = [], set()
    for m in re.finditer(r'href="(/conference/%s/presentation/[^"]+)"' % re.escape(slug), html):
        if m.group(1) in seen:
            continue
        seen.add(m.group(1))
        links.append("https://www.usenix.org" + m.group(1))
    print(f"[{cid} {year}] 索引共 {len(links)} 个 presentation", flush=True)
    rows = []
    for i, url in enumerate(links, 1):
        try:
            page = common.get_text(url, interval=args.sleep)
        except RuntimeError as exc:
            print(f"  ! 跳过 {url}: {exc}", flush=True)
            continue
        tm = re.search(r"<title>([^<]*?)\s*\|\s*USENIX", page)
        pdfs = re.findall(r'href="(https://www\.usenix\.org/system/files/[^"]+\.pdf)"', page)
        pdfs = [p for p in pdfs if "slides" not in p.lower()]
        if not (tm and pdfs):
            continue
        rows.append({"title": common.clean_title(tm.group(1)),
                     "landing_url": url, "pdf_url": pdfs[0]})
    return rows, base


AAAI_BASE = "https://ojs.aaai.org/index.php/AAAI"
AAAI_ARCHIVE = AAAI_BASE + "/issue/archive"
AAAI_MAX_PAGES = 12


def _aaai_issue_links(year, args):
    """翻 OJS 「Archives」分页，找出 AAAI-<yy> 的期号。

    OJS 归档是「新→旧」分页，每页 25 期。默认只取 "AAAI-<yy> Technical Tracks N"
    主会轨道（与 neurips 的 --track Conference 同思路）；--track all 可把该届的
    special track / symposia 也一起收。翻到整页都比目标年份旧就停，不白跑请求。
    """
    yy = f"{year % 100:02d}"
    want_all = (getattr(args, "track", "") or "main").lower() == "all"
    pat = re.compile(r'<a class="title" href="[^"]*issue/view/(\d+)">\s*([^<]*)')
    issues, seen = [], set()
    for page in range(1, AAAI_MAX_PAGES + 1):
        html = common.get_text(f"{AAAI_ARCHIVE}/{page}", interval=args.sleep)
        found = [(i, common.clean_title(t)) for i, t in pat.findall(html)]
        if not found:
            break
        page_years = []
        for iid, title in found:
            m = re.match(r"AAAI-(\d\d)\b", title)
            if m:
                page_years.append(int(m.group(1)))
            if not m or m.group(1) != yy or iid in seen:
                continue
            if not want_all and not title.startswith(f"AAAI-{yy} Technical Tracks"):
                continue
            seen.add(iid)
            issues.append((iid, title))
        # 该页全部标注了届次且都早于目标届 → 目标届已经翻过去了
        if page_years and max(page_years) < int(yy):
            break
    return issues


def adapt_aaai(cid, year, args, spec):
    """ojs.aaai.org（Open Journal Systems）：论文页与 PDF galley 分成两级。

    每届 proceedings 拆成很多期（AAAI-25 Technical Tracks 1..N），期页里
    `obj_article_summary` 给论文页 `article/view/<aid>`，紧跟一条 `pdf` galley
    `article/view/<aid>/<gid>`；PDF 直链统一写成 `<aid>/<gid>` 的 download 形式
    （与既有样本 s-aaai-2025-00N 的 pdf_url 写法一致）。
    同一篇可能有多个 galley（Video/Poster/Slides），只认 class 带 pdf 的那个。
    """
    issues = _aaai_issue_links(year, args)
    if not issues:
        print(f"  ! {year} 在 OJS 归档里没找到 AAAI-{year % 100:02d} 的期号（论文集可能未发布）",
              flush=True)
        return [], AAAI_ARCHIVE
    print(f"[{cid} {year}] 命中 {len(issues)} 期：{', '.join(i for i, _ in issues[:6])}"
          + (" …" if len(issues) > 6 else ""), flush=True)
    art_re = re.compile(
        r'<a id="article-\d+" href="(https://ojs\.aaai\.org/index\.php/AAAI/article/view/(\d+))">\s*(.*?)\s*</a>',
        re.S)
    gal_re = re.compile(
        r'<a class="obj_galley_link pdf" href="https://ojs\.aaai\.org/index\.php/AAAI/article/view/'
        r'(\d+)/(\d+)"')
    rows = []
    for iid, title in issues:
        html = common.get_text(f"{AAAI_BASE}/issue/view/{iid}", interval=args.sleep)
        blocks = html.split('<div class="obj_article_summary">')[1:]
        n0 = len(rows)
        for block in blocks:
            a = art_re.search(block)
            g = gal_re.search(block)
            if not (a and g) or a.group(2) != g.group(1):
                continue
            title_txt = common.clean_title(re.sub(r"<[^>]+>", "", a.group(3)))
            if not title_txt:
                continue
            rows.append({
                "title": title_txt,
                "landing_url": a.group(1),
                "pdf_url": f"{AAAI_BASE}/article/download/{g.group(1)}/{g.group(2)}",
                "issue": title,
            })
        print(f"  · 期 {iid}（{title[:44]}）：{len(rows) - n0} 篇", flush=True)
    return rows, AAAI_ARCHIVE


ECVA_INDEX = "https://www.ecva.net/papers.php"


def adapt_ecva(cid, year, args, spec):
    """www.ecva.net/papers.php：ECVA 官方开放索引，一届一个 accordion 面板。

    条目形如：
        <dt class="ptitle"><br><a href=papers/eccv_2024/papers_ECCV/html/4_ECCV_2024_paper.php>
        TITLE</a></dt><dd>AUTHORS</dd><dd>[<a href='papers/eccv_2024/papers_ECCV/papers/00004.pdf'>pdf</a>]
    2018 届是单引号 + 作者名 slug 命名，2020 起是数字编号，两种都能吃。
    `-supp.pdf` 是补充材料，不当论文。

    landing_url 沿用既有 ECCV 样本的写法（都是索引页本身），所以 add_samples 那边
    用的是共享来源 src-eccv-papers-list，而不是每篇一条。
    """
    html = common.get_text(ECVA_INDEX, interval=args.sleep)
    ydir = f"eccv_{year}"
    page_re = re.compile(
        r"<a href=['\"]?(papers/%s/papers_ECCV/html/[^'\">]+\.php)['\"]?>(.*?)</a>" % ydir, re.S)
    pdf_re = re.compile(
        r"href=['\"](papers/%s/papers_ECCV/papers/[^'\"]+?\.pdf)['\"]" % ydir)
    rows = []
    for block in html.split('<dt class="ptitle">')[1:]:
        t = page_re.search(block)
        pdfs = [p for p in pdf_re.findall(block) if not p.lower().endswith("-supp.pdf")]
        if not (t and pdfs):
            continue
        title = common.clean_title(re.sub(r"<[^>]+>", " ", t.group(2)))
        if not title:
            continue
        rows.append({"title": title,
                     "landing_url": ECVA_INDEX,
                     "pdf_url": "https://www.ecva.net/" + pdfs[0]})
    if not rows:
        print(f"  ! {year} 在 ECVA 索引里没找到条目（届次可能尚未开放）", flush=True)
    return rows, ECVA_INDEX


ADAPTERS = {"neurips": adapt_neurips, "mlr": adapt_mlr, "cvf": adapt_cvf,
            "acl": adapt_acl, "ijcai": adapt_ijcai, "usenix": adapt_usenix,
            "aaai": adapt_aaai, "ecva": adapt_ecva}


# ---------------------------------------------------------------- main
def resolve_years(args, spec) -> list[int]:
    if args.years:
        return [int(x) for x in args.years.split(",") if x.strip()]
    if args.year:
        return [int(args.year)]
    if spec.get("years"):
        return spec["years"][:1]
    return [2024]


def main() -> int:
    ap = argparse.ArgumentParser(description="官方索引页 → 候选论文清单（candidates/<conf>.jsonl）")
    ap.add_argument("--list", action="store_true", help="列出本脚本支持的会议")
    ap.add_argument("--conference", "-c", default="", help="会议 id（见 --list）")
    ap.add_argument("--year", type=int, default=None)
    ap.add_argument("--years", default="", help="逗号分隔，如 2023,2024")
    ap.add_argument("--limit", type=int, default=30, help="每个年份取多少篇（默认 30，均匀抽样）")
    ap.add_argument("--volume", default="", help="PMLR 卷号(v235) 或 ACL 卷名(2024.acl-long)")
    ap.add_argument("--out", default="", help="输出路径，默认 candidates/<conf>.jsonl")
    ap.add_argument("--sleep", type=float, default=common.DEFAULT_INTERVAL,
                    help="每个域名两次请求的最小间隔秒数（默认 2.0）")
    ap.add_argument("--track", default="",
                    help="neurips 专用：取哪个轨道（默认 Conference 主会；all=不过滤）；"
                         "aaai 专用：默认只取 AAAI-<yy> Technical Tracks 主会轨道，all=含 special track")
    ap.add_argument("--no-verify-pdf", action="store_true",
                    help="不对选中的 pdf_url 做 Range 探测（默认会探测并丢弃 404/非 PDF 的条目）")
    ap.add_argument("--no-archive-index", action="store_true",
                    help="不归档索引页（默认归档为 src-<conf>-<year>-proceedings）")
    args = ap.parse_args()

    if args.list or not args.conference:
        print("支持的会议：")
        for cid, s in SPECS.items():
            ex = {"neurips": "(--year 2024)", "mlr": "(需 --volume)"}.get(s["family"], "")
            print(f"  {cid:<10} {s['abbr']:<14} family={s['family']} {ex}")
        print("\n暂未覆盖：" + HELP_NOT_READY)
        return 0

    cid = args.conference
    if cid not in SPECS:
        print(f"未知会议 '{cid}'。可用：{', '.join(SPECS)}", file=sys.stderr)
        return 2
    spec = SPECS[cid]
    adapter = ADAPTERS[spec["family"]]
    out = args.out or os.path.join(common.ROOT, "candidates", f"{cid}.jsonl")

    all_rows = []
    for year in resolve_years(args, spec):
        print(f"[{cid} {year}] 抓索引…", flush=True)
        try:
            rows, index_url = adapter(cid, year, args, spec)
        except (RuntimeError, SystemExit) as exc:
            print(f"  ! 失败：{exc}", file=sys.stderr)
            continue
        rows = common.dedupe(rows)
        picked = common.pick_even(rows, args.limit)
        if picked and not args.no_verify_pdf:
            good, dropped = [], []
            for r in picked:
                ok, info = common.probe_pdf(r["pdf_url"], interval=args.sleep)
                (good if ok else dropped).append(r if ok else (r, info))
            for r, info in dropped:
                print(f"  ! 丢弃（PDF 不可用 {info}）：{r['title'][:55]}", flush=True)
                print(f"      {r['pdf_url']}", flush=True)
            print(f"  PDF 校验：{len(good)} 可用 / {len(dropped)} 丢弃", flush=True)
            picked = good
        venue = styles.venue_for(cid, year, spec.get("abbr", ""))
        for r in picked:
            r.update(venue=venue, year=year, source_kind="proceedings-index",
                     note_family=spec["family"])
        print(f"  索引 {len(rows)} 篇 → 选中 {len(picked)} 篇（均匀抽样）", flush=True)
        if not args.no_archive_index:
            src_id = spec.get("index_src") or f"src-{cid}-{year}-proceedings"
            raw = os.path.join(common.ROOT, "sources", "raw", src_id + ".html")
            if spec.get("index_src") and os.path.exists(raw):
                print(f"  ✓ 索引已归档，复用 {src_id}（全届共用同一页）", flush=True)
            else:
                ok, msg = common.fetch_source(src_id, index_url, "html")
                print(("  ✓ 归档索引 " if ok else "  ! 索引归档失败 ") + msg[:120], flush=True)
        all_rows += picked

    all_rows = common.dedupe(all_rows)
    common.write_jsonl(out, all_rows)
    print(f"\n写出 {len(all_rows)} 条 → {out}")
    print("下一步：python3 tools/crawl/add_samples.py --conference "
          f"{cid} --from {os.path.relpath(out, common.ROOT)} --limit {args.limit}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
