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


def probe(doc_key):
    """一个文档：clean + 逐档退化，每档只编译一次（用 texopt.evalexternal.measure_once）。"""
    from texopt import evalexternal as EE

    tex = DOCS[doc_key]
    drop = SH.gate_drop_dims()
    src = open(tex, encoding="utf-8", errors="replace").read()
    rows = []
    cases = [("clean", None)] + [(f"deg{i+1}", kinds) for i, kinds in enumerate(EE.LADDER)]
    for tag, kinds in cases:
        ov = None if kinds is None else EE.degrade_source(src, kinds)
        m = EE.measure_once(tex, os.path.join(WORK, f"{doc_key}-{tag}"), src_override=ov)
        if not m.get("compile_ok"):
            rows.append({"tag": tag, "error": m.get("error")})
            continue
        rows.append({
            "tag": tag, "kinds": list(kinds or []),
            "n_pages": m.get("n_pages"), "a_profile": m.get("a_profile"),
            "dim_norm": m.get("dim_norm") or {}, "dim_loss": m.get("dim_loss") or {},
            "d2_norm": m.get("d2_norm"), "raw_median": m.get("raw_median") or {},
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
                  f"ws={((r.get('raw_median') or {}).get('whitespace.total_ratio'))}")
            if r.get("dim_norm"):
                for d in dims:
                    v = (r["dim_norm"] or {}).get(d, 0.0)
                    print(f"        {d:32s} {v}")
    with open(os.path.join(WORK, "attr_profile.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"\n写出 {os.path.join(WORK, 'attr_profile.json')}")


if __name__ == "__main__":
    main()
