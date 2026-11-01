"""以指定 ρ 跑 optimize.py（不改源码）：供 tools/rho_ab_compare.py 调用。

用法： python3 tools/rho_ab_run.py <rho> <tex> [optimize.py 的其它参数…]
"""
import os
import runpy
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from texopt import score  # noqa: E402

score.W_PAGE_DEFECT = float(sys.argv[1])
del sys.argv[1]
sys.argv[0] = "optimize.py"
runpy.run_path(os.path.join(ROOT, "optimize.py"), run_name="__main__")
