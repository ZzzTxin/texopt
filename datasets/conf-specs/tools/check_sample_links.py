#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_sample_links.py —— 逐个校验 samples/*.samples.list.json 里的 pdf_url 是否可下载。

对每个 URL 发 Range 请求（不下载整篇），记录 http 状态与 content-type。
输出人类可读表格 + summary/sample-link-check.md（供数据集使用者参考哪些样本可用）。

用法:
    python3 tools/check_sample_links.py            # 全部会议
    python3 tools/check_sample_links.py iclr acl   # 指定会议
    python3 tools/check_sample_links.py icml --retries 3   # 弱网下多加几次重试

注意：000 通常是本机网络抖动（例如 raw.githubusercontent.com 在部分网络下时通时断），
不是数据错误，所以默认会对 000/429/5xx 重试 2 次再判失败。
"""
from __future__ import annotations

import glob
import json
import os
import subprocess
import sys
import tempfile
import time

RETRY_CODES = {"000", "ERR", "429", "500", "502", "503", "504"}

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UA = "Mozilla/5.0 (X11; Linux x86_64) texopt-dataset/1.0 (+academic layout research)"


def probe_once(url: str) -> tuple[str, str]:
    """单次探测，返回 (http_code, 说明)。用前 4 字节校验是否真是 PDF（GitHub raw 等会返回
    application/octet-stream，只看 content-type 会误报）。

    临时文件用 mkstemp 唯一命名：多个进程（或多会议并行）同时跑时，
    共用 /tmp/_probe 会互相覆盖，把“可用”误报成 [非 PDF!]。
    """
    fd, tmp = tempfile.mkstemp(prefix="texopt-probe-", suffix=".bin")
    os.close(fd)
    try:
        out = subprocess.run(
            ["curl", "-sSL", "-m", "30", "-A", UA, "-r", "0-2047",
             "-o", tmp, "-w", "%{http_code} %{content_type}", url],
            capture_output=True, text=True, timeout=45)
        parts = (out.stdout or "").strip().split(None, 1)
        code = parts[0] if parts else "000"
        ctype = parts[1] if len(parts) > 1 else ""
        head = open(tmp, "rb").read(5)
        if head[:4] == b"%PDF":
            ctype = (ctype + " [%PDF✓]").strip()
        elif code in ("200", "206"):
            ctype = (ctype + " [非 PDF!]").strip()
        return code, ctype
    except Exception as ex:
        return "ERR", type(ex).__name__
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass


def probe(url: str, retries: int = 2, sleep: float = 2.0) -> tuple[str, str]:
    """带重试的探测：000/429/5xx 抖动不算失败（弱网下 raw.githubusercontent 常这样）。"""
    code, ctype = "000", ""
    for attempt in range(retries + 1):
        code, ctype = probe_once(url)
        if code not in RETRY_CODES:
            return code, ctype
        if attempt < retries:
            time.sleep(sleep * (2 ** attempt))
    return code, ctype


def main() -> int:
    argv = sys.argv[1:]
    retries, sleep = 2, 2.0
    rest = []
    i = 0
    while i < len(argv):
        if argv[i] == "--retries" and i + 1 < len(argv):
            retries = int(argv[i + 1]); i += 2; continue
        if argv[i] == "--sleep" and i + 1 < len(argv):
            sleep = float(argv[i + 1]); i += 2; continue
        rest.append(argv[i]); i += 1
    want = {a.strip() for a in rest if a.strip()}
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
            code, ctype = probe(url, retries=retries, sleep=sleep)
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
