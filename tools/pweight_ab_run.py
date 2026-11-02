#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P 权重回填 A/B：同一批靶稿分别在**旧权重**与**现行权重**下跑完整闭环。

用法：
    python3 tools/pweight_ab_run.py old   <tex> [optimize.py 参数…]   # 用旧权重
    python3 tools/pweight_ab_run.py cur   <tex> [optimize.py 参数…]   # 用现行权重

旧权重从 metrics/p_weight_tradeoff_round1_20261102.json 的 diffs.old 还原
（stage 11 的 human×corpus 值），只需覆盖被重标的 7 个键。
"""
import json
import os
import runpy
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from texopt import score  # noqa: E402

mode = sys.argv[1]
del sys.argv[1]

if mode == "old":
    f = os.path.join(ROOT, "metrics", "p_weight_tradeoff_round1_20261102.json")
    d = json.load(open(f, encoding="utf-8"))
    for it in d["diffs"]:
        if it.get("old") is not None:
            score.PAGE_DEFECT_WEIGHT[it["key"]] = it["old"]

sys.argv[0] = "optimize.py"
runpy.run_path(os.path.join(ROOT, "optimize.py"), run_name="__main__")
