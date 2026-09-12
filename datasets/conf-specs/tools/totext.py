#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""totext.py —— 把 html/pdf/sty 归档文件抽取为纯文本（用于引用校验/人工核对）。
用法: python3 totext.py <file>
"""
import sys, re, os, html

def from_html(data: str) -> str:
    data = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", data)
    data = re.sub(r"(?is)<br\s*/?>", "\n", data)
    data = re.sub(r"(?is)</(p|div|li|tr|h[1-6]|section|article)>", "\n", data)
    data = re.sub(r"(?s)<[^>]+>", " ", data)
    data = html.unescape(data)
    data = re.sub(r"[ \t\xa0]+", " ", data)
    data = re.sub(r"\n\s*\n\s*\n+", "\n\n", data)
    return data.strip()

def from_pdf(path: str) -> str:
    sys.path.insert(0, os.environ.get("TEXOPT_TOOLS", os.path.expanduser("~/.local/lib/texopt-tools")))
    from pypdf import PdfReader
    r = PdfReader(path)
    out = []
    for i, p in enumerate(r.pages):
        out.append(f"\n===== PAGE {i+1} =====\n")
        try:
            out.append(p.extract_text() or "")
        except Exception as e:
            out.append(f"[extract_text failed: {e}]")
    return "".join(out)

def main():
    p = sys.argv[1]
    ext = os.path.splitext(p)[1].lower()
    if ext == ".pdf":
        print(from_pdf(p))
        return
    raw = open(p, "rb").read()
    for enc in ("utf-8", "latin-1"):
        try:
            txt = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        txt = raw.decode("utf-8", "replace")
    sys.stdout.write(from_html(txt) if ext in (".html", ".htm", "") else txt)

if __name__ == "__main__":
    main()
