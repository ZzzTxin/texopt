#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_sample_links.py —— 逐个校验 samples/*.samples.list.json 里的 pdf_url 是否可下载。

对每个 URL 发 Range 请求（不下载整篇），记录 http 状态与 content-type。
输出人类可读表格 + summary/sample-link-check.md（供数据集使用者参考哪些样本可用）。

用法:
    python3 tools/check_sample_links.py            # 全部会议
    python3 tools/check_sample_links.py iclr acl   # 指定会议
"""
from __future__ import annotations

import glob
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UA = "Mozilla/5.0 (X11; Linux x86_64) texopt-dataset/1.0 (+academic layout research)"


def probe(url: str) -> tuple[str, str]:
    """返回 (http_code, 说明)。用前 4 字节校验是否真是 PDF（GitHub raw 等会返回
    application/octet-stream，只看 content-type 会误报）。"""
    try:
        out = subprocess.run(
            ["curl", "-sSL", "-m", "30", "-A", UA, "-r", "0-2047",
             "-o", "/tmp/_probe", "-w", "%{http_code} %{content_type}", url],
            capture_output=True, text=True, timeout=45)
        parts = (out.stdout or "").strip().split(None, 1)
        code = parts[0] if parts else "000"
        ctype = parts[1] if len(parts) > 1 else ""
        head = b""
        if os.path.exists("/tmp/_probe"):
            head = open("/tmp/_probe", "rb").read(5)
            os.remove("/tmp/_probe")
        if head[:4] == b"%PDF":
            ctype = (ctype + " [%PDF✓]").strip()
        elif code in ("200", "206"):
            ctype = (ctype + " [非 PDF!]").strip()
        return code, ctype
    except Exception as ex:
        return "ERR", type(ex).__name__


def main() -> int:
    want = {a.strip() for a in sys.argv[1:] if a.strip()}
    files = sorted(glob.glob(os.path.join(ROOT, "samples", "*.samples.list.json")))
    lines = ["# 样本 PDF 链接可用性检查（自动生成）", "",
             "| 会议 | sample | http | content-type | pdf_url |", "|---|---|---|---|---|"]
    bad = []
    for f in files:
        cid = os.path.basename(f).split(".")[0]
        if want and cid not in want:
            continue
        data = json.load(open(f, encoding="utf-8"))
        print(f"[{cid}] {len(data.get('papers', []))} 篇", flush=True)
        for p in data.get("papers", []):
            url = p.get("pdf_url") or ""
            code, ctype = probe(url)
            ok = code in ("200", "206") and "%PDF" in (ctype or "")
            print(f"   {p['sample_id']}: {code} {ctype}", flush=True)
            lines.append(f"| {cid} | {p['sample_id']} | {code} | {ctype} | {url} |")
            if not ok:
                bad.append((cid, p["sample_id"], code, ctype, url))
    out = os.path.join(ROOT, "summary", "sample-link-check.md")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print(f"\n不可用链接 {len(bad)} 条：")
    for cid, sid, code, ctype, url in bad:
        print(f"  {cid}/{sid}: {code} {ctype} {url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
