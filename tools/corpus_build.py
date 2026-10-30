# -*- coding: utf-8 -*-
"""语料层 Step 1：编译 paperfit-bench-originals 的 200 篇原件，抽缺陷与页面指标。

产物（默认 /mnt/d/texopt-corpus）：
  rows.jsonl      每篇一行（缺陷计数/幅度 + 每页软指标）
  progress.json   进度（供外部轮询汇报）
  pdf/<case>.pdf  编译产物
  log/<case>.log  最后一次编译日志
  work/           临时工作目录（用后删除）

用法：
  python3 tools/corpus_build.py --workers 8
  python3 tools/corpus_build.py --workers 8 --limit 3      # 试跑
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJ)

from texopt import perceive, visual            # noqa: E402

SRC = "/mnt/d/桌面/texopt/paperfit-bench-originals/paperfit-bench-originals"
META = "/mnt/d/桌面/texopt/paperfit-bench-originals/paperfit-bench/metadata/cases.jsonl"
OUT = "/mnt/d/texopt-corpus"
PDFLATEX = "/mnt/c/texlive/2024/bin/windows/pdflatex.exe"
BIBTEX = "/mnt/c/texlive/2024/bin/windows/bibtex.exe"
MUTOOL = shutil.which("mutool") or "mutool"

DPI = 40
COMPILE_TIMEOUT = 420

_lock = threading.Lock()


def read_manifest() -> list[dict]:
    rows = [json.loads(l) for l in open(os.path.join(SRC, "MANIFEST.jsonl"), encoding="utf-8")]
    return [r for r in rows if r.get("status") == "ok"]


def read_meta() -> dict:
    meta = {}
    for l in open(META, encoding="utf-8"):
        r = json.loads(l)
        meta[r["case_id"]] = r
    return meta


def find_main(work: str, hint: str) -> str | None:
    if hint and os.path.isfile(os.path.join(work, hint)):
        return hint
    best = None
    for root, _dirs, files in os.walk(work):
        for f in files:
            if not f.endswith(".tex"):
                continue
            p = os.path.join(root, f)
            try:
                txt = open(p, encoding="utf-8", errors="replace").read()
            except OSError:
                continue
            if "\\documentclass" in txt and "\\begin{document}" in txt:
                rel = os.path.relpath(p, work)
                bonus = 1 if "main" in f.lower() else 0
                score = (bonus, txt.count("\\section"))
                if best is None or score > best[0]:
                    best = (score, rel)
    return best[1] if best else None


def run(cmd: list[str], cwd: str, timeout: int) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, timeout=timeout)
        return p.returncode, p.stdout.decode("utf-8", "replace")
    except subprocess.TimeoutExpired as e:
        out = (e.stdout or b"").decode("utf-8", "replace")
        return 124, out + "\n[TIMEOUT]"


OVERFULL_ANY = re.compile(r"Overfull \\hbox \(([0-9.]+)pt too wide\)")
UNDERFULL_ANY = re.compile(r"Underfull \\hbox \(badness ([0-9]+)\)")
VBOX_ANY = re.compile(r"(Overfull|Underfull) \\vbox \(([0-9.]+)pt too (?:high|short)\)")


def raw_counts(log: str, issues: dict) -> dict:
    """原始正则计数（不要求 'in paragraph' 尾巴），与 perceive 口径并列记录。

    记录两套口径是有意的：perceive.parse_log() 的 OVERFULL_RE 只认
    'in paragraph at lines ...'，会漏掉 'detected at line N'（公式/盒子），
    这是检测器口径问题（Step 2 体检项），不应在语料里被悄悄掩盖。
    """
    ov = [float(x) for x in OVERFULL_ANY.findall(log)]
    un = [int(x) for x in UNDERFULL_ANY.findall(log)]
    vb = VBOX_ANY.findall(log)
    vb_pts = [float(p) for _k, p in vb]
    return {
        "raw_overfull": len(ov),
        "raw_overfull_pt_max": max(ov) if ov else 0.0,
        "raw_overfull_pt_mean": round(sum(ov) / len(ov), 2) if ov else 0.0,
        "raw_overfull_pt_all": ov,
        "raw_underfull": len(un),
        "raw_underfull_badness_max": max(un) if un else 0,
        "raw_vbox_over": sum(1 for k, _p in vb if k == "Overfull"),
        "raw_vbox_under": sum(1 for k, _p in vb if k == "Underfull"),
        "raw_vbox_pt_max": max(vb_pts) if vb_pts else 0.0,
        "perceive_overfull": len(issues["overfull"]),
        "perceive_underfull": len(issues["underfull"]),
        "perceive_vbox": len(issues["vbox"]),
        "perceive_floatwarn": len(issues["floats"]),
        "perceive_warn": len(issues["warnings"]),
    }


def page_stats(pdf: str, tmpdir: str) -> tuple[list[dict], str | None]:
    os.makedirs(tmpdir, exist_ok=True)
    for f in os.listdir(tmpdir):
        os.remove(os.path.join(tmpdir, f))
    rc, out = run([MUTOOL, "draw", "-q", "-c", "gray", "-r", str(DPI),
                   "-o", os.path.join(tmpdir, "p-%d.pnm"), os.path.basename(pdf)],
                  os.path.dirname(pdf), 900)
    files = sorted([f for f in os.listdir(tmpdir) if f.endswith(".pnm")],
                   key=lambda s: int(re.findall(r"(\d+)", s)[0]))
    pages = []
    for f in files:
        try:
            pages.append(visual.page_metrics(os.path.join(tmpdir, f)))
        except Exception as exc:                      # noqa: BLE001
            pages.append({"error": str(exc)[:80]})
    err = None if pages else f"render_failed rc={rc} {out[-200:]}"
    return pages, err


def one_case(man: dict, meta: dict, keep_work: bool) -> dict:
    case = man["case_id"]
    safe = case.replace("/", "__")
    work = os.path.join(OUT, "work", safe)
    t0 = time.time()
    row = {"case_id": case, "venue": man["venue"], "paper_id": man["paper_id"],
           "main_tex": man.get("main_tex_relpath"), "n_tex": man.get("n_tex")}
    m = meta.get(case, {})
    row.update({"column": m.get("column_type"), "target_pages": m.get("target_pages"),
                "profile": m.get("profile"), "documentclass": (m.get("documentclass") or "")[:120]})
    try:
        shutil.rmtree(work, ignore_errors=True)
        shutil.copytree(os.path.join(SRC, case), work)
        main = find_main(work, row["main_tex"])
        if not main:
            row.update({"compile_ok": False, "fail": "no_main_tex"})
            return row
        row["main_tex_used"] = main
        base = os.path.splitext(os.path.basename(main))[0]
        log = ""
        for attempt in range(3):
            rc, out = run([PDFLATEX, "-interaction=nonstopmode", main], work, COMPILE_TIMEOUT)
            log = out
            if os.path.isfile(os.path.join(work, base + ".pdf")):
                break
            if attempt == 0 and not os.path.isfile(os.path.join(work, base + ".bbl")):
                run([BIBTEX, base], work, 180)
        pdf = os.path.join(work, base + ".pdf")
        written = os.path.relpath(pdf, os.path.dirname(main)) if main != os.path.basename(main) else ""
        ok = os.path.isfile(pdf)
        row["compile_ok"] = ok
        row["compile_rc"] = rc
        if not ok:
            row["fail"] = "no_pdf"
            row["log_tail"] = log[-400:]
            return row
        os.makedirs(os.path.join(OUT, "pdf"), exist_ok=True)
        shutil.copy2(pdf, os.path.join(OUT, "pdf", safe + ".pdf"))
        os.makedirs(os.path.join(OUT, "log"), exist_ok=True)
        with open(os.path.join(OUT, "log", safe + ".log"), "w", encoding="utf-8") as fh:
            fh.write(log)
        issues = perceive.parse_log(log)
        cnt = raw_counts(log, issues)
        row["defects"] = {
            "overfull": cnt["raw_overfull"],
            "underfull": cnt["raw_underfull"],
            "vbox_over": cnt["raw_vbox_over"],
            "vbox_under": cnt["raw_vbox_under"],
            "floatwarn": cnt["perceive_floatwarn"],
            "warn": cnt["perceive_warn"],
            "errors": len(issues["errors"]),
            "macros_missing": int("microtype" not in log),
            "float_H": len(re.findall(r"\[H\]", log)),
        }
        row["amplitude"] = cnt
        row["warn_samples"] = issues["warnings"][:5]
        pages, perr = page_stats(pdf, os.path.join(OUT, "tmp", safe))
        row["pages"] = len(pages)
        row["page_metrics"] = pages
        if perr:
            row["render_error"] = perr
        row["pdf_bytes"] = os.path.getsize(os.path.join(OUT, "pdf", safe + ".pdf"))
        return row
    except Exception as exc:                          # noqa: BLE001
        row.update({"compile_ok": False, "fail": "exception: " + str(exc)[:200]})
        return row
    finally:
        row["seconds"] = round(time.time() - t0, 1)
        if not keep_work:
            shutil.rmtree(work, ignore_errors=True)
            shutil.rmtree(os.path.join(OUT, "tmp", safe), ignore_errors=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--keep-work", action="store_true")
    ap.add_argument("--tag", default="originals")
    args = ap.parse_args()

    os.makedirs(OUT, exist_ok=True)
    rows_path = os.path.join(OUT, f"rows_{args.tag}.jsonl")
    done = set()
    if os.path.isfile(rows_path):
        for l in open(rows_path, encoding="utf-8"):
            try:
                done.add(json.loads(l)["case_id"])
            except Exception:                          # noqa: BLE001
                pass
    man = read_manifest()
    meta = read_meta()
    todo = [r for r in man if r["case_id"] not in done]
    if args.limit:
        todo = todo[: args.limit]
    total = len(todo)
    state = {"total": total, "done": 0, "ok": 0, "fail": 0, "started": time.time(),
             "tag": args.tag, "running": [], "last": []}
    lock = threading.Lock()

    def dump():
        with open(os.path.join(OUT, "progress.json"), "w", encoding="utf-8") as fh:
            json.dump(state, fh, ensure_ascii=False, indent=1)

    dump()
    print(f"[corpus] {total} 篇待编译（已完成 {len(done)}），workers={args.workers}", flush=True)

    with open(rows_path, "a", encoding="utf-8") as fh, \
            ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = {}
        for r in todo:
            futs[pool.submit(one_case, r, meta, args.keep_work)] = r["case_id"]
        for fut in as_completed(futs):
            case = futs[fut]
            try:
                row = fut.result()
            except Exception as exc:                   # noqa: BLE001
                row = {"case_id": case, "compile_ok": False, "fail": str(exc)[:200]}
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            fh.flush()
            with lock:
                state["done"] += 1
                state["ok" if row.get("compile_ok") else "fail"] += 1
                state["last"] = (state["last"] + [{
                    "case": case, "ok": bool(row.get("compile_ok")),
                    "pages": row.get("pages"), "s": row.get("seconds")}])[-8:]
                dump()
            el = time.time() - state["started"]
            rate = state["done"] / max(el, 1e-6)
            eta = (total - state["done"]) / max(rate, 1e-6)
            print(f"[{state['done']}/{total} {100*state['done']/total:5.1f}%] {case} "
                  f"ok={row.get('compile_ok')} pages={row.get('pages')} "
                  f"{row.get('seconds')}s  elapsed={el/60:.1f}m eta={eta/60:.1f}m "
                  f"fail={state['fail']}", flush=True)
    state["finished"] = time.time()
    dump()
    print("[corpus] 完成", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
