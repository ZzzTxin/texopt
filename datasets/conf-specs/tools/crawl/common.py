# -*- coding: utf-8 -*-
"""crawl/common.py —— 论文爬取公共层（只用标准库，无需 pip）。

与 datasets/conf-specs 既有工具链保持同一套约定：
  * 限速：每个域名独立节流（默认 2.0s），可用 CRAWL_INTERVAL 环境变量或 --sleep 调整
  * 重试：429/5xx 指数退避；其他 4xx 直接报错，由调用方跳过该条
  * 归档：索引页 / 论文落地页一律走 tools/fetch_source.sh
    （产出 sha256 + fetch_log.jsonl 记录），保证新增来源与既有 107 篇的溯源格式完全一致
  * 候选池：candidates/<conf>.jsonl，一行一篇

候选池字段（CANDIDATE_FIELDS）：
    title, venue, year, landing_url, pdf_url, anthology_id, source_kind
"""
from __future__ import annotations

import html as _html
import gzip
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TOOLS = os.path.join(ROOT, "tools")
UA = "Mozilla/5.0 (X11; Linux x86_64) texopt-dataset/1.0 (+academic layout research)"
CANDIDATE_FIELDS = ("title", "venue", "year", "landing_url", "pdf_url",
                    "anthology_id", "source_kind")
DEFAULT_INTERVAL = float(os.environ.get("CRAWL_INTERVAL", "2.0"))

_last_host: dict[str, float] = {}
_last_any = [0.0]


# ---------------------------------------------------------------- HTTP
def _wait(url: str, interval: float) -> None:
    host = urllib.parse.urlparse(url).netloc
    now = time.time()
    delay = max(0.0,
                _last_host.get(host, 0.0) + interval - now,
                _last_any[0] + 0.2 - now)
    if delay > 0:
        time.sleep(delay)
    _last_host[host] = time.time()
    _last_any[0] = _last_host[host]


def _decompress(data: bytes, content_encoding: str) -> bytes:
    """按 Content-Encoding（或 magic 字节）解压。

    ojs.aaai.org 无视 `Accept-Encoding: identity`，一律回 gzip，所以必须自己解，
    否则拿到的是 gzip 二进制，正则一条也匹配不到（表现就像「索引里没内容」）。
    """
    enc = (content_encoding or "").lower()
    if "gzip" in enc or data[:2] == b"\x1f\x8b":
        return gzip.decompress(data)
    if "deflate" in enc:
        try:
            return zlib.decompress(data)
        except zlib.error:
            return zlib.decompress(data, -zlib.MAX_WBITS)
    return data


def get_text(url: str, *, timeout: int = 60, retries: int = 3,
             interval: float | None = None, encoding: str = "utf-8") -> str:
    """抓取 URL 并返回文本（礼貌限速 + 指数退避 + 自动解压 gzip/deflate）。"""
    iv = DEFAULT_INTERVAL if interval is None else float(interval)
    last_err = None
    for attempt in range(retries + 1):
        _wait(url, iv)
        req = urllib.request.Request(url, headers={
            "User-Agent": UA,
            "Accept-Encoding": "gzip, deflate",
            "Accept": "text/html,application/xhtml+xml,*/*",
        })
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = resp.read()
                enc = resp.headers.get("Content-Encoding", "")
            return _decompress(data, enc).decode(encoding, "replace")
        except urllib.error.HTTPError as exc:
            last_err = exc
            if exc.code in (429, 500, 502, 503, 504) and attempt < retries:
                time.sleep(iv * (2 ** attempt) + 1.0)
                continue
            raise RuntimeError(f"HTTP {exc.code} {url}")
        except Exception as exc:                      # 超时 / 连接重置
            last_err = exc
            if attempt < retries:
                time.sleep(iv * (2 ** attempt) + 1.0)
                continue
            raise RuntimeError(f"{exc.__class__.__name__} {url}: {exc}")
    raise RuntimeError(f"重试耗尽 {url}: {last_err}")


# ---------------------------------------------------------------- 归档
def fetch_source(src_id: str, url: str, ext: str | None = None) -> tuple[bool, str]:
    """调用 tools/fetch_source.sh 归档来源（同一套 sha256/fetch_log 格式）。"""
    cmd = ["bash", os.path.join(TOOLS, "fetch_source.sh"), src_id, url]
    if ext:
        cmd.append(ext)
    p = subprocess.run(cmd, capture_output=True, text=True)
    out = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode == 0, re.sub(r"\s+", " ", out)


def src_entry(src_id: str, *, kind: str, title: str, note: str = "",
              pdf_url: str | None = None, venue: str | None = None,
              year: int | None = None, anthology_id: str | None = None) -> dict:
    """复用 mk_source.py 从 fetch_log 生成 Source 条目（sha256 一律不许手抄）。"""
    cmd = [sys.executable, os.path.join(TOOLS, "mk_source.py"), src_id,
           "--kind", kind, "--title", title]
    if note:
        cmd += ["--note", note]
    if pdf_url:
        cmd += ["--pdf-url", pdf_url]
    if venue:
        cmd += ["--venue", venue]
    if year:
        cmd += ["--year", str(year)]
    if anthology_id:
        cmd += ["--anthology-id", anthology_id]
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"mk_source.py 失败：{p.stderr.strip()}")
    return json.loads(p.stdout)


# ---------------------------------------------------------------- 链接探测
def probe_pdf(url: str, *, interval: float | None = None,
              retries: int = 2, timeout: int = 25) -> tuple[bool, str]:
    """Range 探测 PDF 直链（看前 4 字节 %PDF）。返回 (ok, 说明)。

    用在写入数据前做最后一道门：一个 404 的 pdf_url 到后面测量阶段才会爆，
    那时已经写进了 samples/，修起来很麻烦。
    """
    iv = DEFAULT_INTERVAL if interval is None else float(interval)
    info = ""
    for attempt in range(retries + 1):
        _wait(url, iv)
        req = urllib.request.Request(url, headers={
            "User-Agent": UA,
            "Range": "bytes=0-2047",
            "Accept-Encoding": "identity",
        })
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                head = resp.read(2048)
            ok = head[:4] == b"%PDF"
            return ok, f"HTTP {getattr(resp, 'status', '?')}" + ("" if ok else f" 非PDF {head[:16]!r}")
        except urllib.error.HTTPError as exc:
            info = f"HTTP {exc.code}"
            if exc.code in (429, 500, 502, 503, 504) and attempt < retries:
                time.sleep(iv * (2 ** attempt))
                continue
            return False, info
        except Exception as exc:
            info = exc.__class__.__name__
            if attempt < retries:
                time.sleep(iv * (2 ** attempt))
                continue
            return False, info
    return False, info


# ---------------------------------------------------------------- 文件 IO
def load_json(path: str, default=None):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def dump_json(path: str, data) -> None:
    """原子写：先写临时文件再 os.replace，避免中断写坏数据文件。"""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    os.replace(tmp, path)


def read_jsonl(path: str) -> list[dict]:
    rows = []
    if not os.path.exists(path):
        return rows
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_jsonl(path: str, rows: list[dict]) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------- 文本小工具
def clean_title(s: str) -> str:
    s = _html.unescape(s or "")
    s = re.sub(r"\s+", " ", s)
    return s.strip().strip(".·-")


def strip_tags(s: str) -> str:
    return clean_title(re.sub(r"<[^>]+>", "", s or ""))


def pick_even(rows: list[dict], limit: int) -> list[dict]:
    """均匀抽样：从整份索引等间隔取 limit 条。

    直接取前 N 条会全落在字母序靠前的作者/单一主题上，统计会系统性偏斜。
    """
    if limit <= 0 or limit >= len(rows):
        return rows
    step = len(rows) / float(limit)
    idx = sorted({int(i * step) for i in range(limit)})
    return [rows[i] for i in idx]


def dedupe(rows: list[dict], key: str = "pdf_url") -> list[dict]:
    seen, out = set(), []
    for r in rows:
        k = (r.get(key) or "") or (r.get("title") or "")
        if not k or k in seen:
            continue
        seen.add(k)
        out.append(r)
    return out
