# -*- coding: utf-8 -*-
"""Step 2：检测器体检（注入 → 感知 → 响应方向）。

对每个要进权重/带的指标做三件事：
  1. 合成图注入：造一个**已知真值**的页面，看指标测得准不准（误差表）。
  2. 日志注入：造已知缺陷日志行，看解析器认不认（含真实日志漏检率）。
  3. 真实语料：看指标在实际 3898 页里的分位、区分度、现有带命中率。

用法：
  python3 tools/detector_check.py --only synth
  python3 tools/detector_check.py --only log   --logdir /mnt/d/texopt-corpus/log
  python3 tools/detector_check.py --only corpus --rows /mnt/d/texopt-corpus/rows_originals.jsonl
  python3 tools/detector_check.py --only band  --pdfdir /mnt/d/texopt-corpus/pdf --limit 12
  python3 tools/detector_check.py --only all

产物：
  workbench-detector/detector_check.json   机器可读
  workbench-detector/report.md             人读
  workbench-detector/progress.json         进度（供外部汇报）
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import statistics
import sys
import tempfile

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJ)

from texopt import perceive, score, visual  # noqa: E402

WORK = os.path.join(PROJ, "workbench-detector")
OUT_JSON = os.path.join(WORK, "detector_check.json")
OUT_MD = os.path.join(WORK, "report.md")
PROGRESS = os.path.join(WORK, "progress.json")

W, H = 330, 468          # 40 dpi 下的 A4 像素尺寸
TOL = 0.02               # 几何量允许误差（占页面比例）


# ---------------------------------------------------------------- 工具

def progress(stage: str, pct: int, msg: str) -> None:
    os.makedirs(WORK, exist_ok=True)
    with open(PROGRESS, "w", encoding="utf-8") as f:
        json.dump({"stage": stage, "pct": pct, "msg": msg}, f, ensure_ascii=False)
    print(f"[{pct:3d}%] {stage}: {msg}", flush=True)


class Canvas:
    """极简灰度画布；所有真值都从像素直接数出来，不依赖被测实现。"""

    def __init__(self, w=W, h=H):
        self.w, self.h = w, h
        self.px = bytearray([255]) * (w * h)

    def solid(self, x0, x1, y0, y1, val=0):
        for y in range(max(0, y0), min(self.h, y1)):
            base = y * self.w
            for x in range(max(0, x0), min(self.w, x1)):
                self.px[base + x] = val

    def textline(self, y, x0, x1, density=0.38, period=3):
        """模拟一行正文：4 个像素高，逐行墨迹约为行宽的 20%/35%/30%/15%。

        真值标定自真实 40 dpi 页面（文本行 span≈214px，行墨迹 46–90px）。
        """
        span = max(1, x1 - x0)
        for dy, frac in enumerate((0.20, 0.35, 0.30, 0.15)):
            yy = y + dy
            if yy >= self.h:
                break
            base = yy * self.w
            step = max(1, int(round(1.0 / max(frac * density / 0.35, 0.02))))
            for x in range(x0, x1, step):
                self.px[base + x] = 0

    def save(self, path):
        with open(path, "wb") as f:
            f.write(b"P5\n%d %d\n255\n" % (self.w, self.h) + bytes(self.px))
        return path

    # ---- 真值：从像素直接统计（与 page_metrics 同口径但不是同一份代码）
    def truth(self, solid_band_px=0):
        w, h, px = self.w, self.h, self.px
        dark = [1 if b < 200 else 0 for b in px]
        rows = [sum(dark[r * w:(r + 1) * w]) for r in range(h)]
        nz = [r for r, v in enumerate(rows) if v > max(1, int(0.004 * w))]
        top = (nz[0] / h) if nz else 1.0
        bottom = ((h - 1 - nz[-1]) / h) if nz else 1.0
        height = ((nz[-1] - nz[0] + 1) / h) if nz else 0.0
        gap = cur = 0
        for r in rows:
            if r <= max(1, int(0.004 * w)):
                cur += 1
                gap = max(gap, cur)
            else:
                cur = 0
        cols = [0] * w
        for r in range(h):
            for c in range(w):
                if dark[r * w + c]:
                    cols[c] += 1
        cnz = [c for c, v in enumerate(cols) if v > max(1, int(0.002 * h))]
        left = (cnz[0] / w) if cnz else 1.0
        right = ((w - 1 - cnz[-1]) / w) if cnz else 1.0
        half = h // 2
        ti = sum(rows[:half]) or 1
        bi = sum(rows[half:]) or 1
        return {
            "ink_ratio": sum(dark) / (w * h),
            "top_blank": top,
            "bottom_blank": bottom,
            "content_height": height,
            "max_gap": gap / h,
            "left_blank": left,
            "right_blank": right,
            "top_bottom_ratio": ti / bi,
            "band": solid_band_px / h,
        }


def _mk_text_page(c: Canvas, x0=58, x1=272, y0=30, y1=430, density=0.38):
    for y in range(y0, y1, 7):
        c.textline(y, x0, x1, density)


# ---------------------------------------------------------------- A. 合成图注入

def run_synth() -> dict:
    progress("A 合成图注入", 10, "生成已知真值的合成页")
    os.makedirs(WORK, exist_ok=True)
    cases = []

    def add(name, desc, canvas, band_px, expect_band_dir=None):
        p = canvas.save(os.path.join(WORK, f"synth_{name}.pgm"))
        m = visual.page_metrics(p)
        t = canvas.truth(band_px)
        cases.append({"name": name, "desc": desc, "truth": t, "meas": m,
                      "band_dir": expect_band_dir})

    c = Canvas(); add("empty", "全空白页", c, 0)
    c = Canvas(); _mk_text_page(c); add("text", "正文页（页边距 17.6%/文本宽 65%）", c, 0)
    c = Canvas(); _mk_text_page(c); c.solid(40, 290, 150, 330); add(
        "text_fig", "正文页 + 页高 38.5% 的实心图块", c, 180)
    c = Canvas(); _mk_text_page(c, y0=30, y1=350); add("text_short", "正文提前结束（页底留白 25%）", c, 0)
    c = Canvas(); _mk_text_page(c, x0=120, x1=330); add("shift_right", "正文整体右移（左留白 36%）", c, 0)
    c = Canvas()
    for y in range(30, 430, 7):
        c.textline(y, 25, 150, 0.38); c.textline(y, 180, 305, 0.38)
    add("two_col", "双栏页（栏间空 9%）", c, 0)
    c = Canvas(); c.solid(20, 310, 20, 448); add("solid_full", "整页实心大图", c, 428)
    c = Canvas(); _mk_text_page(c, y0=30, y1=230); add("top_heavy", "只有上半页有正文", c, 0)
    c = Canvas(); c.textline(200, 100, 200, 0.3); add("near_empty", "几乎空白（仅一行短句）", c, 0)

    progress("A 合成图注入", 45, "逐例比对真值")
    metrics = ["ink_ratio", "top_blank", "bottom_blank", "content_height",
               "max_gap", "left_blank", "right_blank", "top_bottom_ratio", "band"]
    err = {}
    for mt in metrics:
        e = []
        for cs in cases:
            tv, mv = cs["truth"][mt], cs["meas"].get(mt)
            if mv is None:
                e.append(99.0)
                continue
            e.append(abs(float(mv) - tv))
        err[mt] = {"max_abs_err": round(max(e), 4), "mean_abs_err": round(sum(e) / len(e), 4),
                   "worst_case": cases[e.index(max(e))]["name"],
                   "pass": max(e) <= TOL}
    # band 单独用更松的容差（1 像素行 = 1/468 ≈ 0.002，
    # 但实心块边界在低分辨率下会有 1-2 行毛边）
    e = [abs(cs["meas"]["band"] - cs["truth"]["band"]) for cs in cases]
    err["band"]["max_abs_err"] = round(max(e), 4)
    err["band"]["pass"] = max(e) <= 0.01
    progress("A 合成图注入", 60, "误差表完成")
    return {"cases": cases, "error": err,
            "pass": all(v["pass"] for v in err.values())}


# ---------------------------------------------------------------- B. 日志注入

LOG_CASES = [
    ("overfull_para", "Overfull \\hbox (12.34pt too wide) in paragraph at lines 42--44",
     "overfull", 1),
    ("overfull_detected", "Overfull \\hbox (3.21pt too wide) detected at line 88",
     "overfull", 1),
    ("overfull_alignment", "Overfull \\hbox (20.00pt too wide) in alignment at lines 10--20",
     "overfull", 1),
    ("underfull_para", "Underfull \\hbox (badness 10000) in paragraph at lines 5--7",
     "underfull", 1),
    ("vbox_over", "Overfull \\vbox (14.5pt too high) has occurred while \\output is active []",
     "vbox_over", 1),
    ("vbox_under", "Underfull \\vbox (badness 10000) has occurred while \\output is active [2 <./fig.pdf>]",
     "vbox_under", 1),
    ("vbox_over_detected", "Overfull \\vbox (9.10pt too high) detected at line 314",
     "vbox_over", 1),
    ("float_warn", "LaTeX Warning: Float too large for page by 12.3pt on input line 55.",
     "floatwarn", 1),
    ("float_spec_changed", "LaTeX Warning: `h' float specifier changed to `ht'.",
     "floatwarn", 1),
]


def _count(issues: dict) -> dict:
    return {
        "overfull": len(issues.get("overfull") or []),
        "underfull": len(issues.get("underfull") or []),
        "vbox_over": sum(1 for v in issues.get("vbox") or [] if v.get("kind") == "Overfull"),
        "vbox_under": sum(1 for v in issues.get("vbox") or [] if v.get("kind") == "Underfull"),
        "floatwarn": len(issues.get("floats") or []),
    }


def run_log(logdir: str | None = None) -> dict:
    progress("B 日志注入", 62, "逐条注入已知缺陷日志行")
    unit = []
    for name, line, key, want in LOG_CASES:
        got = _count(perceive.parse_log(line))[key]
        unit.append({"case": name, "line": line, "key": key, "want": want, "got": got,
                     "pass": got == want})
    progress("B 日志注入", 70, "统计真实日志漏检率")
    corpus = None
    if logdir and os.path.isdir(logdir):
        import re
        raw_re = re.compile(
            r"(Overfull|Underfull) \\[hv]box \(([^)]*)\)"
            r"(?:[^\n]*(?:in paragraph|in alignment) at lines (\d+)|[^\n]*detected at line (\d+))?")
        tot = {"log_lines": 0, "detected_form": 0, "alignment_form": 0,
               "overfull_raw": 0, "overfull_perceived": 0,
               "vbox_raw": 0, "vbox_perceived": 0}
        for f in sorted(glob.glob(os.path.join(logdir, "*.log"))):
            txt = open(f, errors="ignore").read()
            tot["log_lines"] += 1
            tot["detected_form"] += len(re.findall(r"detected at line \d+", txt))
            tot["alignment_form"] += len(re.findall(r"in alignment at lines", txt))
            cnt = _count(perceive.parse_log(txt))
            tot["overfull_raw"] += len(re.findall(r"Overfull \\hbox", txt))
            tot["overfull_perceived"] += cnt["overfull"]
            tot["vbox_raw"] += len(re.findall(r"(?:Overfull|Underfull) \\vbox", txt))
            tot["vbox_perceived"] += cnt["vbox_over"] + cnt["vbox_under"]
        for k in ("overfull", "vbox"):
            r, p = tot[f"{k}_raw"], tot[f"{k}_perceived"]
            tot[f"{k}_miss_rate"] = round(1 - p / r, 4) if r else 0.0
        corpus = tot
    progress("B 日志注入", 76, "日志体检完成")
    return {"unit": unit, "pass": all(u["pass"] for u in unit), "corpus": corpus}


# ---------------------------------------------------------------- C. 真实语料

def _pct(vals, q):
    if not vals:
        return None
    s = sorted(vals)
    i = min(len(s) - 1, max(0, int(round(q * (len(s) - 1)))))
    return s[i]


def run_corpus(rows_path: str) -> dict:
    progress("C 真实语料", 78, "读取 rows_originals.jsonl")
    pages = []
    papers = 0
    for line in open(rows_path, encoding="utf-8"):
        r = json.loads(line)
        papers += 1
        for p in r.get("page_metrics") or []:
            p = dict(p)
            p["_column"] = r.get("column")
            p["_venue"] = r.get("venue")
            pages.append(p)
    progress("C 真实语料", 84, f"{papers} 篇 / {len(pages)} 页，算分位与区分度")
    out = {"papers": papers, "pages": len(pages), "metrics": {}}
    for mt, (lo, hi, _w) in score.SOFT_BANDS.items():
        vals = [float(p[mt]) for p in pages if isinstance(p.get(mt), (int, float))]
        if not vals:
            out["metrics"][mt] = {"n": 0}
            continue
        mean = sum(vals) / len(vals)
        sd = statistics.pstdev(vals)
        lo_p, hi_p = _pct(vals, 0.05), _pct(vals, 0.95)
        below = sum(1 for v in vals if v < lo) / len(vals)
        above = sum(1 for v in vals if v > hi) / len(vals)
        out["metrics"][mt] = {
            "n": len(vals), "p5": round(lo_p, 4), "p50": round(_pct(vals, 0.5), 4),
            "p95": round(hi_p, 4), "p99": round(_pct(vals, 0.99), 4),
            "max": round(max(vals), 4), "min": round(min(vals), 4),
            "stdev": round(sd, 4), "cv": round(sd / mean, 3) if mean else None,
            "cur_band": [lo, hi], "below_frac": round(below, 4), "above_frac": round(above, 4),
            "in_band_frac": round(1 - below - above, 4),
            "near_zero_frac": round(sum(1 for v in vals if abs(v) < 1e-6) / len(vals), 4),
            "suggest_band": [round(lo_p, 3), round(hi_p, 3)],
        }
    progress("C 真实语料", 88, "语料体检完成")
    return out


# ---------------------------------------------------------------- D. band 口径

def _old_band(rows, w, h):
    """v1 定义：行墨迹 ≥ 50% 页宽 的最长连续段（保留用于对比）。"""
    thr = max(1, int(0.5 * w))
    best = cur = 0
    for v in rows:
        if v >= thr:
            cur += 1
            best = max(best, cur)
        else:
            cur = 0
    return best / h


def run_band(pdfdir: str, limit: int = 12, dpi: int = 40) -> dict:
    progress("D band 口径", 90, f"在 {limit} 篇真实 PDF 上重算 v1/v2")
    pdfs = sorted(glob.glob(os.path.join(pdfdir, "*.pdf")))[:limit]
    rows_all = []
    tmp = tempfile.mkdtemp(dir=WORK, prefix="band_")
    for i, pdf in enumerate(pdfs, 1):
        imgs, err = visual.render_gray(pdf, tmp, dpi=dpi)
        if err:
            continue
        for img in imgs:
            w, h, data = visual._parse_pgm(img)
            dark = [1 if b < 200 else 0 for b in data]
            rows = [sum(dark[r * w:(r + 1) * w]) for r in range(h)]
            m = visual.page_metrics(img)
            rows_all.append({"old": round(_old_band(rows, w, h), 3),
                             "new": m["band"], "ink": m["ink_ratio"],
                             "pdf": os.path.basename(pdf)})
        progress("D band 口径", 90 + int(6 * i / max(1, len(pdfs))),
                 f"{i}/{len(pdfs)} 篇")
    old = [r["old"] for r in rows_all]
    new = [r["new"] for r in rows_all]
    return {
        "pdfs": len(pdfs), "pages": len(rows_all),
        "old": {"p50": _pct(old, 0.5), "p90": _pct(old, 0.9), "p99": _pct(old, 0.99),
                "max": max(old) if old else None,
                "nonzero_frac": round(sum(1 for v in old if v > 0) / len(old), 4) if old else None},
        "new": {"p50": _pct(new, 0.5), "p90": _pct(new, 0.9), "p99": _pct(new, 0.99),
                "max": max(new) if new else None,
                "nonzero_frac": round(sum(1 for v in new if v > 0) / len(new), 4) if new else None},
        "top_pages": sorted(rows_all, key=lambda r: -r["new"])[:8],
    }


# ---------------------------------------------------------------- 报告

def verdict(sec_synth, sec_log, sec_corpus, sec_band) -> list[dict]:
    rows = []
    for mt, e in sec_synth["error"].items():
        c = (sec_corpus or {}).get("metrics", {}).get(mt, {}) if sec_corpus else {}
        v = "可用"
        why = []
        if not e["pass"]:
            v = "需改口径"
            why.append(f"合成真值误差 {e['max_abs_err']}（>{TOL}）")
        if c and c.get("n"):
            if c["near_zero_frac"] > 0.60:
                v = "暂缓"
                why.append(f"{c['near_zero_frac'] * 100:.0f}% 的页恒为 0，不可辨识")
            elif c["cv"] is not None and c["cv"] < 0.05:
                v = "暂缓"
                why.append(f"变异系数仅 {c['cv']}，几乎不区分页面")
            elif c["in_band_frac"] < 0.30:
                v = "暂缓"
                why.append(f"现带只装下 {c['in_band_frac'] * 100:.0f}% 的正常页，"
                           f"作为双侧软带不成立（建议只留上界做缺陷判据）")
            elif c["in_band_frac"] < 0.85:
                v = "需改口径"
                why.append(f"现带只装下 {c['in_band_frac'] * 100:.0f}% 的正常页，"
                           f"应为 {c['suggest_band']}")
        rows.append({"metric": mt, "verdict": v,
                     "synth_max_err": e["max_abs_err"],
                     "cur_band": c.get("cur_band"), "in_band_frac": c.get("in_band_frac"),
                     "suggest_band": c.get("suggest_band"),
                     "reasons": why or ["合成真值与语料分位均正常"]})
    logpass = sec_log["pass"] if sec_log else None
    rows.append({"metric": "log:overfull/underfull/vbox/floatwarn",
                 "verdict": "可用" if logpass else "需改口径",
                 "synth_max_err": None,
                 "cur_band": None, "in_band_frac": None, "suggest_band": None,
                 "reasons": ["注入样例全部识别"] if logpass else
                            ["注入样例有漏检（见 log.unit）"]})
    return rows


def write_report(data: dict) -> str:
    L = ["# Step 2 检测器体检报告（2026-10-27）", ""]
    L.append("口径：合成图 + 真值比对 / 日志注入 / 真实语料分位。"
             "本节只回答“指标本身能不能用”，不调权重。")
    L.append("")
    s = data.get("synth")
    if s:
        L += ["## 1　合成图注入（测得准不准）", "",
              "| 指标 | 最大绝对误差 | 最差样例 | 结论 |", "|---|---|---|---|"]
        for mt, e in s["error"].items():
            L.append(f"| {mt} | {e['max_abs_err']} | {e['worst_case']} | "
                     f"{'通过' if e['pass'] else '偏差过大'} |")
        L.append("")
    lg = data.get("log")
    if lg:
        L += ["## 2　日志注入（认不认）", "", "| 样例 | 期望 | 实测 | 结论 |", "|---|---|---|---|"]
        for u in lg["unit"]:
            L.append(f"| {u['case']} | {u['want']} | {u['got']} | "
                     f"{'通过' if u['pass'] else '漏检'} |")
        c = lg.get("corpus")
        if c:
            L += ["", f"真实日志 {c['log_lines']} 篇：overfull 原始 {c['overfull_raw']} / 识别 "
                      f"{c['overfull_perceived']}（漏检 {c['overfull_miss_rate'] * 100:.1f}%）；"
                      f"vbox 原始 {c['vbox_raw']} / 识别 {c['vbox_perceived']}"
                      f"（漏检 {c['vbox_miss_rate'] * 100:.1f}%）。"
                      f"其中 `detected at line` 形式 {c['detected_form']} 处、"
                      f"`in alignment` 形式 {c['alignment_form']} 处。"]
        L.append("")
    cc = data.get("corpus")
    if cc:
        L += ["## 3　真实语料体检（能不能区分）", "",
              f"{cc['papers']} 篇 / {cc['pages']} 页。", "",
              "| 指标 | P5 | P50 | P95 | 现带 | 带内 | 恒零 | CV | 建议带 |",
              "|---|---|---|---|---|---|---|---|---|"]
        for mt, c in cc["metrics"].items():
            if not c.get("n"):
                continue
            L.append(f"| {mt} | {c['p5']} | {c['p50']} | {c['p95']} | {c['cur_band']} | "
                     f"{c['in_band_frac'] * 100:.0f}% | {c['near_zero_frac'] * 100:.0f}% | "
                     f"{c['cv']} | {c['suggest_band']} |")
        L.append("")
    bd = data.get("band")
    if bd:
        L += ["## 4　band 口径对比（v1 → v2）", "",
              f"{bd['pdfs']} 篇 / {bd['pages']} 页，40 dpi。", "",
              "| 版本 | P50 | P90 | P99 | 最大 | 非零页占比 |", "|---|---|---|---|---|---|"]
        for k in ("old", "new"):
            v = bd[k]
            L.append(f"| {k} | {v['p50']} | {v['p90']} | {v['p99']} | {v['max']} | "
                     f"{v['nonzero_frac'] * 100:.0f}% |")
        L.append("")
        L.append("v2 非零页应是真有大图/大表的页；v1 只认“行墨迹 ≥ 50% 页宽”，"
                 "40 dpi 下正文行本来就达不到，故几乎全 0。")
        L.append("")
    v = data.get("verdict")
    if v:
        L += ["## 5　结论表", "", "| 指标 | 结论 | 理由 |", "|---|---|---|"]
        for r in v:
            L.append(f"| {r['metric']} | {r['verdict']} | {'；'.join(r['reasons'])} |")
        L.append("")
    os.makedirs(WORK, exist_ok=True)
    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    return OUT_MD


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="all",
                    choices=["all", "synth", "log", "corpus", "band"])
    ap.add_argument("--logdir", default="/mnt/d/texopt-corpus/log")
    ap.add_argument("--rows", default="/mnt/d/texopt-corpus/rows_originals.jsonl")
    ap.add_argument("--pdfdir", default="/mnt/d/texopt-corpus/pdf")
    ap.add_argument("--limit", type=int, default=12)
    a = ap.parse_args()

    data = {}
    if os.path.isfile(OUT_JSON):
        try:
            data = json.load(open(OUT_JSON, encoding="utf-8"))
        except Exception:
            data = {}
    if a.only in ("all", "synth"):
        data["synth"] = run_synth()
    if a.only in ("all", "log"):
        data["log"] = run_log(a.logdir)
    if a.only in ("all", "corpus"):
        data["corpus"] = run_corpus(a.rows)
    if a.only in ("all", "band"):
        data["band"] = run_band(a.pdfdir, a.limit)
    data["verdict"] = verdict(data.get("synth"), data.get("log"),
                              data.get("corpus"), data.get("band"))
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    md = write_report(data)
    progress("完成", 100, f"报告 {md}")
    print(json.dumps(data.get("verdict"), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
