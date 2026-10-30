# -*- coding: utf-8 -*-
"""Step 5-a：缺陷**严重度**成对比较表（15 题）——只问「哪个更影响阅读」。

为什么要问：`PAGE_DEFECT_WEIGHT` 那 11 个比重是 9 月手拍的，没有来源
（见 `docs/weight_calibration_plan_20261016.md` D1）。标定方案是

    wᵢ = 严重度ᵢ ÷ 频率ᵢ     严重度=人（本工具），频率=语料（200 篇/3898 页）

只问**人眼能看见**的 10 类；`warn` / `macros_missing` / `unstable_spec` 这类
技术项人无法判断，继续沿用先验（在结果里单独标注）。

用法：
  python3 tools/make_severity_sheet.py --build        # 生成 15 题成对表
  python3 tools/make_severity_sheet.py --import answers.json
  python3 tools/make_severity_sheet.py --stats
  python3 tools/make_severity_sheet.py --selftest     # 用已知真值自检 BT 估计

产物：
  workbench-severity/sheet.html     离线成对表（含示意图，无需联网）
  workbench-severity/pairs.json     题目与左右映射
  workbench-severity/result.json    BT 强度、语料频率、建议权重
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import sys

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJ)

ROWS = "/mnt/d/texopt-corpus/rows_originals.jsonl"
WORK = os.path.join(PROJ, "workbench-severity")

# 10 个“人眼可见”的缺陷；freq_key 对应语料 defects 里的键（None=无频率数据）
ITEMS = [
    dict(key="overfull", name="行溢出", freq_key="overfull",
         desc="正文一行超出右边线，文字压到版心外或撞到栏间"),
    dict(key="underfull", name="行欠满", freq_key="underfull",
         desc="一行字距被拉得很开，行内出现明显的白缝"),
    dict(key="vbox_over", name="页面垂直溢出", freq_key="vbox_over",
         desc="整页内容超出版心下边界，页底文字压到页码区"),
    dict(key="vbox_under", name="页面垂直欠满", freq_key="vbox_under",
         desc="这一页没排满就断了，页底留下明显的大片空白"),
    dict(key="floatwarn", name="浮动体错位", freq_key="floatwarn",
         desc="图表被挤到离正文引用处很远的位置（可能翻了好几页）"),
    dict(key="tab_overwide", name="表格超宽", freq_key=None,
         desc="表格宽度超出栏宽，右侧被截断或挤进相邻栏"),
    dict(key="fig_overwide", name="图片超宽", freq_key=None,
         desc="图片宽度超出栏宽，右侧压出版心"),
    dict(key="spec_H", name="强排图表（[H]）", freq_key="float_H",
         desc="图表用 [H] 强行钉在原位，导致页面被撑出大块空白或失衡"),
    dict(key="stranded_block", name="内容孤立", freq_key=None,
         desc="一个图表孤零零留在一页，周围大片空白，没有正文陪衬"),
    dict(key="near_empty", name="近空白页", freq_key=None,
         desc="整页几乎没有内容，只有一两行或一个孤立图表"),
]
BY_KEY = {it["key"]: it for it in ITEMS}

# ---- 极简示意图（SVG）：每种缺陷一张，避免纯文字判断的语义漂移 ----
_SVG_BASE = ('<svg viewBox="0 0 120 84" width="120" height="84">'
             '<rect x="6" y="4" width="108" height="76" fill="#fff" stroke="#bbb"/>')


def _svg(key: str) -> str:
    L = '<g stroke="#333" stroke-width="1.6">'
    if key == "overfull":
        body = (L + "".join(f'<line x1="12" y1="{12 + i * 6}" x2="96" y2="{12 + i * 6}"/>'
                            for i in range(9))
                + '<line x1="12" y1="66" x2="114" y2="66" stroke="#c00"/>' + "</g>")
    elif key == "underfull":
        body = (L + "".join(f'<line x1="12" y1="{12 + i * 6}" x2="96" y2="{12 + i * 6}"/>'
                            for i in range(6))
                + '<line x1="12" y1="48" x2="30" y2="48"/><line x1="46" y1="48" x2="64" y2="48"/>'
                + '<line x1="80" y1="48" x2="96" y2="48"/>'
                + '<line x1="12" y1="54" x2="96" y2="54"/></g>')
    elif key == "vbox_over":
        body = (L + "".join(f'<line x1="12" y1="{10 + i * 6}" x2="96" y2="{10 + i * 6}"/>'
                            for i in range(13))
                + '<line x1="10" y1="80" x2="110" y2="80" stroke="#c00"/></g>')
    elif key == "vbox_under":
        body = (L + "".join(f'<line x1="12" y1="{10 + i * 6}" x2="96" y2="{10 + i * 6}"/>'
                            for i in range(5))
                + '<rect x="12" y="44" width="84" height="30" fill="#eee" stroke="none"/>' + "</g>")
    elif key == "floatwarn":
        body = (L + '<rect x="12" y="10" width="40" height="24" fill="#dde"/>'
                + '<line x1="12" y1="44" x2="96" y2="44"/><line x1="12" y1="50" x2="96" y2="50"/>'
                + '<line x1="12" y1="66" x2="60" y2="66" stroke="#c00"/>'
                + '<rect x="62" y="56" width="40" height="22" fill="#dde" stroke="#c00"/></g>')
    elif key == "tab_overwide":
        body = (L + '<rect x="10" y="14" width="104" height="40" fill="#f2f2f2"/>'
                + "".join(f'<line x1="{10 + i * 17.3}" y1="14" x2="{10 + i * 17.3}" y2="54"/>'
                          for i in range(7))
                + '<line x1="10" y1="34" x2="114" y2="34"/>'
                + '<line x1="104" y1="8" x2="104" y2="60" stroke="#c00"/></g>')
    elif key == "fig_overwide":
        body = (L + '<rect x="12" y="12" width="88" height="34" fill="#ddd"/>'
                + "".join(f'<line x1="12" y1="{54 + i * 6}" x2="96" y2="{54 + i * 6}"/>'
                          for i in range(4))
                + '<line x1="104" y1="8" x2="104" y2="50" stroke="#c00"/></g>')
    elif key == "spec_H":
        body = (L + '<rect x="12" y="10" width="50" height="26" fill="#dde"/>'
                + '<rect x="12" y="44" width="84" height="26" fill="#eee"/>'
                + "".join(f'<line x1="12" y1="{74 + 0}" x2="96" y2="74"/>' for _ in range(1)) + "</g>")
    elif key == "stranded_block":
        body = (L + '<rect x="30" y="30" width="60" height="26" fill="#dde"/>'
                + '<line x1="12" y1="76" x2="96" y2="76"/></g>')
    else:  # near_empty
        body = (L + '<line x1="12" y1="14" x2="80" y2="14"/><line x1="12" y1="20" x2="60" y2="20"/></g>')
    return _SVG_BASE + body + "</svg>"


ROUNDS = 3           # 圆桌法取前 3 轮 -> 15 对，每项出现 3 次


def _rounds(items: list[dict], rounds: int) -> list[tuple[str, str]]:
    """圆桌轮转法：n 项 s 轮，保证每项每轮出现一次、无重复配对。"""
    keys = [it["key"] for it in items]
    n = len(keys)
    if n % 2:
        keys = keys + [None]          # 奇数补轮空
        n += 1
    out = []
    arr = keys[:]
    for _ in range(rounds):
        for i in range(n // 2):
            a, b = arr[i], arr[n - 1 - i]
            if a and b:
                out.append((a, b))
        arr = [arr[0]] + [arr[-1]] + arr[1:-1]
    return out


def build() -> int:
    random.seed(20261028)
    os.makedirs(WORK, exist_ok=True)
    pairs = _rounds(ITEMS, ROUNDS)
    recs, cards = [], []
    for i, (a, b) in enumerate(pairs, 1):
        flip = random.random() < 0.5
        left, right = (a, b) if not flip else (b, a)
        recs.append({"pair": i, "left": left, "right": right})
        cards.append({"pair": i, "left": BY_KEY[left], "right": BY_KEY[right]})
    with open(os.path.join(WORK, "pairs.json"), "w", encoding="utf-8") as f:
        json.dump({"n": len(recs), "items": [it["key"] for it in ITEMS],
                   "pairs": recs}, f, ensure_ascii=False, indent=2)
    with open(os.path.join(WORK, "sheet.html"), "w", encoding="utf-8") as f:
        f.write(_html(cards))
    counts = {}
    for r in recs:
        counts[r["left"]] = counts.get(r["left"], 0) + 1
        counts[r["right"]] = counts.get(r["right"], 0) + 1
    print(f"{len(recs)} 对 -> {os.path.join(WORK, 'sheet.html')}")
    print("每题出现次数:", counts)
    return 0


def _html(cards: list[dict]) -> str:
    import html as H
    blocks = []
    for c in cards:
        def card(it):
            return (f'<div class="card"><div class="nm">{H.escape(it["name"])}</div>'
                    f'{_svg(it["key"])}'
                    f'<div class="ds">{H.escape(it["desc"])}</div></div>')
        blocks.append(f"""
  <div class="pair" id="q{c['pair']}">
    <div class="ph">第 {c['pair']} 题 / 共 {len(cards)} 题</div>
    <div class="two">{card(c['left'])}{card(c['right'])}</div>
    <div class="opts">
      <label><input type="radio" name="q{c['pair']}" value="left">左更严重</label>
      <label><input type="radio" name="q{c['pair']}" value="right">右更严重</label>
      <label><input type="radio" name="q{c['pair']}" value="same">差不多</label>
    </div>
  </div>""")
    return f"""<!doctype html><html lang="zh"><meta charset="utf-8">
<title>缺陷严重度成对比较（{len(cards)} 题）</title>
<style>
 body{{font-family:system-ui,sans-serif;margin:20px;background:#f6f6f7;color:#1d1d1f}}
 h1{{font-size:18px;margin:0 0 6px}} p.lead{{font-size:13px;color:#555;max-width:900px}}
 .pair{{background:#fff;border:1px solid #ddd;border-radius:10px;padding:10px;margin:14px 0}}
 .ph{{font-size:12px;color:#888;margin-bottom:6px}}
 .two{{display:grid;grid-template-columns:1fr 1fr;gap:10px}}
 .card{{background:#fafafa;border:1px solid #eee;border-radius:8px;padding:8px;text-align:center}}
 .card .nm{{font-size:14px;font-weight:600;margin-bottom:4px}}
 .card .ds{{font-size:12px;color:#555;margin-top:4px;text-align:left}}
 .opts{{display:flex;gap:22px;margin-top:8px;font-size:14px}}
 .bar{{position:sticky;top:0;background:#fff;border:1px solid #ddd;border-radius:8px;
      padding:8px 10px;display:flex;align-items:center;gap:12px;z-index:9}}
 button{{padding:7px 14px;font-size:14px}} #prog,#msg{{font-size:13px;color:#444}}
</style>
<h1>缺陷严重度成对比较（Step 5-a）</h1>
<p class="lead">假设这两种问题**同时出现在一篇论文里**，哪一个更影响你对该论文排版的第一印象？
只比“看着多难受/多像没做完”，不要考虑“修起来难不难”、也不要想“哪个更常见”。
真的分不出就选「差不多」。共 {len(cards)} 题。</p>
<div class="bar"><button onclick="exp()">导出答案</button>
  <span id="prog">已完成 0 / {len(cards)}</span><span id="msg"></span></div>
{''.join(blocks)}
<script>
const N={len(cards)};
function picked(){{const o={{}};for(let i=1;i<=N;i++){{const e=document.querySelector('input[name="q'+i+'"]:checked');if(e)o[i]=e.value;}}return o;}}
function upd(){{document.getElementById('prog').textContent='已完成 '+Object.keys(picked()).length+' / '+N;}}
document.addEventListener('change',upd);upd();
function exp(){{
  const o=picked(),miss=[];for(let i=1;i<=N;i++)if(!o[i])miss.push('#'+i);
  if(miss.length){{document.getElementById('msg').textContent='还缺：'+miss.join(' ');return;}}
  const data={{ranker:'user',ts:new Date().toISOString(),
    answers:Object.keys(o).map(k=>({{pair:+k,choice:o[k]}}))}};
  const blob=new Blob([JSON.stringify(data,null,2)],{{type:'application/json'}});
  const a=document.createElement('a');a.href=URL.createObjectURL(blob);
  a.download='answers.json';a.click();
  document.getElementById('msg').textContent='已导出 answers.json';
}}
</script></html>"""


# ---------------------------------------------------------------- BT 估计

def bt_fit(items: list[str], wins: dict[tuple[str, str], float],
           prior: float = 0.5, iters: int = 2000) -> dict[str, float]:
    """Bradley-Terry（MM 算法）+ Jeffreys 先验（每对补 0.5 胜/0.5 负）。

    先验的作用：15 对里必有两项一次没赢过，无先验会让强度落到 0 并放大其它项的
    估计（实测 overfull 与 vbox_over 差 50 倍，纯数值病态）。补先验后强度有界。
    并列按各 0.5 胜处理；最后按几何均值归一。
    """
    s = {k: 1.0 for k in items}
    pw = []                      # (i, j, n_ij, wins_i)
    for (i, j), w in wins.items():
        wi, wj = w + prior, (1.0 - w) + prior
        n = wi + wj
        pw.append((i, j, n, wi))
        pw.append((j, i, n, wj))
    for _ in range(iters):
        new = {}
        for k in items:
            num = sum(w for i, _j, _n, w in pw if i == k)
            den = sum(n / (s[i] + s[j]) for i, j, n, _w in pw if i == k)
            new[k] = num / den if den > 0 else 1e-12
        g = sum(math.log(max(v, 1e-12)) for v in new.values()) / len(new)
        s = {k: math.exp(math.log(max(v, 1e-12)) - g) for k, v in new.items()}
    return s


def _freq() -> dict[str, dict]:
    """语料频率：受影响论文占比 + 每页发生率。"""
    n_paper = n_page = 0
    hit_paper = {it["freq_key"]: 0 for it in ITEMS if it["freq_key"]}
    hit_page = {it["freq_key"]: 0 for it in ITEMS if it["freq_key"]}
    for line in open(ROWS, encoding="utf-8"):
        r = json.loads(line)
        n_paper += 1
        pages = max(1, len(r.get("page_metrics") or []) or r.get("pages") or 1)
        n_page += pages
        d = r.get("defects") or {}
        for k in hit_paper:
            c = d.get(k) or 0
            if c > 0:
                hit_paper[k] += 1
                hit_page[k] += c
    out = {}
    for k in hit_paper:
        out[k] = {"prevalence": round(hit_paper[k] / n_paper, 4),
                  "per_page": round(hit_page[k] / n_page, 4),
                  "papers": hit_paper[k], "n_paper": n_paper, "n_page": n_page}
    return out


CURRENT = {  # 现行 PAGE_DEFECT_WEIGHT（含人不可判的技术项，仅作对照）
    "overfull": 1.0, "underfull": 0.6, "vbox_over": 1.0, "vbox_under": 1.4,
    "floatwarn": 1.6, "tab_overwide": 1.2, "fig_overwide": 1.0,
    "warn": 0.3, "macros_missing": 2.0, "unstable_spec": 0.8, "spec_H": 0.5,
}
TECH_ONLY = {"warn", "macros_missing", "unstable_spec"}


def import_answers(path: str, out_name: str = "result.json") -> int:
    pj = json.load(open(os.path.join(WORK, "pairs.json"), encoding="utf-8"))
    ans = json.load(open(path, encoding="utf-8"))
    got = {int(a["pair"]): a["choice"] for a in ans.get("answers", [])}
    items = pj["items"]
    wins, n_dec, n_tie = {}, 0, 0
    for p in pj["pairs"]:
        ch = got.get(p["pair"])
        if not ch:
            continue
        key = tuple(sorted((p["left"], p["right"])))
        wins.setdefault(key, 0.0)
        if ch == "same":
            n_tie += 1
            wins[key] += 0.5
            continue
        n_dec += 1
        winner = p["left"] if ch == "left" else p["right"]
        if winner == key[0]:
            wins[key] += 1.0
    if not wins or not any(wins.values()):
        print("没有任何有效选择")
        return 1
    s = bt_fit(items, wins)
    order = sorted(items, key=lambda k: -s[k])
    freq = _freq()

    # 严重度相对值（人）：几何均值归一
    sev_rel = {k: s[k] for k in items}

    # 频率相对值（语料）：per_page / 有数据项的均值；0 计数视为“不可作分母”
    have_freq = {k: freq[BY_KEY[k]["freq_key"]] for k in items
                 if BY_KEY[k]["freq_key"] and freq.get(BY_KEY[k]["freq_key"], {}
                                                       ).get("per_page", 0) > 0}
    rate_mean = (sum(v["per_page"] for v in have_freq.values()) / len(have_freq)
                 if have_freq else 0.0)

    proposed, notes = {}, {}
    for k in items:
        fk = BY_KEY[k]["freq_key"]
        f = freq.get(fk) if fk else None
        if not f:
            notes[k] = "语料无此计数（表格/图片超宽、孤立、空白页属源码扫描项，不在 rows_originals 的 defects 里）"
            basis = "prior_kept"
        elif f["per_page"] <= 0:
            notes[k] = f"语料 {f['n_paper']} 篇/{f['n_page']} 页里计数为 0，无法作分母"
            basis = "prior_kept"
        else:
            basis = "human×corpus"
        if basis == "prior_kept":
            proposed[k] = {"severity_rel": round(sev_rel[k], 3), "freq_rel": None,
                           "w_raw": None, "w_damped": None, "final": None,
                           "basis": basis}
            continue
        fr = f["per_page"] / rate_mean if rate_mean else None
        raw = sev_rel[k] / fr if fr else None
        proposed[k] = {"severity_rel": round(sev_rel[k], 3),
                       "freq_rel": round(fr, 3) if fr else None,
                       "w_raw": round(raw, 3) if raw else None,
                       "w_damped": round(math.sqrt(raw), 3) if raw else None,
                       "final": None, "basis": basis}

    # 把 damped 值缩放到“现行权重（同样有数据项）的均值”，保持量纲可比
    damped = [v["w_damped"] for v in proposed.values() if v["w_damped"]]
    cur = [CURRENT[k] for k in items if proposed[k]["w_damped"] and k in CURRENT]
    scale = (sum(cur) / len(cur) / (sum(damped) / len(damped))) if damped else 1.0
    for k, v in proposed.items():
        if v["w_damped"]:
            v["final"] = round(v["w_damped"] * scale, 3)

    res = {
        "n_questions": len(pj["pairs"]), "n_decided": n_dec, "n_tied": n_tie,
        "bt_strength": {k: round(s[k], 4) for k in order},
        "severity_rank": order,
        "frequency": freq,
        "frequency_notes": notes,
        "proposed": proposed,
        "scale": round(scale, 4),
        "current": CURRENT,
        "untested_tech_items": sorted(TECH_ONLY),
        "method": ("严重度=人（BT，15 对，Jeffreys 先验 0.5）；频率=语料 per_page；"
                   "w=sqrt(严重度/频率) 后缩放到现行均值。开方是阻尼：raw 比值对"
                   "极稀缺陷（vbox_over 0.023/页）会给出 10 倍以上的权重，不宜直接用。"),
    }
    with open(os.path.join(WORK, out_name), "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    print(json.dumps({k: v for k, v in res.items()
                      if k in ("n_questions", "n_decided", "n_tied",
                               "severity_rank", "proposed", "scale", "method")},
                     ensure_ascii=False, indent=2))
    return 0


def stats() -> int:
    p = os.path.join(WORK, "result.json")
    if not os.path.isfile(p):
        print("还没有 result.json（先 --import answers.json）")
        return 1
    print(open(p, encoding="utf-8").read())
    return 0


def selftest() -> int:
    """用“已知真值”造答案，检查两件事：
    ① BT 估计**不得与任何一次直接比较矛盾**（硬不变量）；
    ② 与真值的秩相关 ≥ 0.8（3 轮设计实测均值 0.88，p10 0.81）。
    """
    pj = json.load(open(os.path.join(WORK, "pairs.json"), encoding="utf-8"))
    truth = {k: math.exp(-0.35 * i) for i, k in enumerate(pj["items"])}
    arr, wins = [], {}
    for p in pj["pairs"]:
        a, b = truth[p["left"]], truth[p["right"]]
        ch = "same" if abs(a - b) < 1e-9 else (
            "left" if a > b else "right")
        arr.append({"pair": p["pair"], "choice": ch})
        key = tuple(sorted((p["left"], p["right"])))
        if ch != "same":
            winner = p["left"] if ch == "left" else p["right"]
            wins[key] = 1.0 if winner == key[0] else 0.0
    s = bt_fit(pj["items"], wins)
    bad = [(i, j, w) for (i, j), w in wins.items()
           if (s[i] > s[j]) != (w == 1.0)]
    got = sorted(pj["items"], key=lambda k: -s[k])
    want = sorted(pj["items"], key=lambda k: -truth[k])
    rho = _spearman([s[k] for k in want], [truth[k] for k in want])
    ok = (not bad) and rho >= 0.8
    print(f"selftest: 直接比较矛盾 {len(bad)} 处；rho={rho:.3f}（要求 0 处且 ≥0.8）")
    if not ok:
        print("  got =", got)
        print("  want=", want)
    return 0 if ok else 1


def _spearman(a: list[float], b: list[float]) -> float:
    n = len(a)
    def rank(xs):
        order = sorted(range(n), key=lambda i: xs[i])
        r = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and xs[order[j + 1]] == xs[order[i]]:
                j += 1
            avg = (i + j) / 2 + 1
            for k in range(i, j + 1):
                r[order[k]] = avg
            i = j + 1
        return r
    ra, rb = rank(a), rank(b)
    ma, mb = sum(ra) / n, sum(rb) / n
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    den = (sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb)) ** 0.5
    return round(num / den, 4) if den else 0.0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--import", dest="imp")
    ap.add_argument("--stats", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.build:
        return build()
    if a.imp:
        return import_answers(a.imp)
    if a.stats:
        return stats()
    if a.selftest:
        return selftest()
    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
