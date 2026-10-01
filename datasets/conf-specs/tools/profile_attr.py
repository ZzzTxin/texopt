# -*- coding: utf-8 -*-
"""阶段 8 · E1 归因：A_profile 对源码级退化为什么不敏感？（只编译一次，不跑闭环）

对每个退化档：**只编译一次**（不跑闭环），提取矢量层指标，用与影子完全相同的
口径（aesthetic.evaluate_doc + gate_drop_dims + 已启用权重）算 dim_norm_top，
即 A_profile 的分量分解。对照 clean（原始源码）看每一维怎么动。

用法：
    python3 tools/profile_attr.py demo neurips issues

对每个退化档只**编译一次**（原始源码 → 退化源码），再走与影子完全相同的口径
（extract + evaluate_doc + 门槛剔除 + 已启用权重），把 A_profile 拆到每一维。
产出：workbench-eval/profile_attr/attr_profile.json
"""
import json
import os
import shutil
import sys

ROOT = "/mnt/d/桌面/texopt"
sys.path.insert(0, ROOT)

from texopt import aesthetic as AE            # noqa: E402
from texopt import engine                     # noqa: E402
from texopt import evalexternal as EE         # noqa: E402
from texopt import extract as EX              # noqa: E402
from texopt import shadow as SH               # noqa: E402

DOCS = {
    "demo": os.path.join(ROOT, "examples", "demo.tex"),
    "issues": os.path.join(ROOT, "examples", "issues.tex"),
    "neurips": os.path.join(ROOT, "examples", "NeurlPS examples", "main.tex"),
}
WORK = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "workbench-eval", "profile_attr")


def build_and_compile(tag, tex_path, src_override):
    """把文档目录拷进工作区（带图/.sty/.bbl），写入（可能退化过的）源码，编译一次。"""
    out = os.path.join(WORK, tag)
    if os.path.isdir(out):
        shutil.rmtree(out, ignore_errors=True)
    os.makedirs(out, exist_ok=True)
    srcdir = os.path.dirname(tex_path)
    for name in os.listdir(srcdir):
        if name in ("workbench", "__pycache__"):
            continue
        s, d = os.path.join(srcdir, name), os.path.join(out, name)
        if os.path.isdir(s):
            shutil.copytree(s, d, dirs_exist_ok=True)
        else:
            shutil.copy2(s, d)
    main = os.path.join(out, os.path.basename(tex_path))
    if src_override is not None:
        with open(main, "w", encoding="utf-8") as f:
            f.write(src_override)
    res = engine.compile_tex(main, passes=2, timeout=180)
    return out, res


def probe(doc_key):
    tex = DOCS[doc_key]
    prof = SH.load_profile()
    drop = SH.gate_drop_dims()
    src = open(tex, encoding="utf-8", errors="replace").read()
    rows = []
    cases = [("clean", None)] + [(f"deg{i+1}", kinds) for i, kinds in enumerate(EE.LADDER)]
    for tag, kinds in cases:
        ov = None if kinds is None else EE.degrade_source(src, kinds)
        out, res = build_and_compile(f"{doc_key}-{tag}", tex, ov)
        pdf = getattr(res, "pdf_path", None)
        if not pdf or not os.path.isfile(pdf):
            rows.append({"tag": tag, "error": f"编译失败: {getattr(res, 'first_error', res)}"})
            continue
        doc = EX.extract_pdf(pdf)
        rep = AE.evaluate_doc(doc, prof, lambda_=0.0, drop_dims=drop)
        paper = rep.get("paper") or {}
        ws = [p.get("whitespace", {}).get("total_ratio") for p in doc.get("pages", [])]
        rows.append({
            "tag": tag, "kinds": list(kinds or []),
            "n_pages": rep.get("n_pages"),
            "a_profile": paper.get("a_profile"),
            "dim_norm": paper.get("dim_norm_top") or {},
            "dim_loss": paper.get("dim_loss_top") or {},
            "d2_norm": paper.get("norm_d2_top"),
            "n_anom": paper.get("n_anomalous_pages"),
            "ws_total_median": sorted(x for x in ws if x is not None)[len(ws) // 2] if ws else None,
        })
    return {"doc": doc_key, "tex": tex, "dropped_dims": drop, "rows": rows}


def main():
    keys = sys.argv[1:] or ["demo"]
    os.makedirs(WORK, exist_ok=True)
    out = [probe(k) for k in keys]
    # 控制台表格
    for blk in out:
        print(f"\n===== {blk['doc']}（剔除维 {blk['dropped_dims']}）")
        dims = sorted({d for r in blk["rows"] for d in (r.get("dim_norm") or {})})
        for r in blk["rows"]:
            print(f"  {r.get('tag'):6s} pages={r.get('n_pages')} "
                  f"A_profile={r.get('a_profile')} d2_norm={r.get('d2_norm')} "
                  f"ws={r.get('ws_total_median')}")
            if r.get("dim_norm"):
                for d in dims:
                    v = (r["dim_norm"] or {}).get(d, 0.0)
                    print(f"        {d:32s} {v}")
    with open(os.path.join(WORK, "attr_profile.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"\n写出 {os.path.join(WORK, 'attr_profile.json')}")


if __name__ == "__main__":
    main()
