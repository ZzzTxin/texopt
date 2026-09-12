#!/usr/bin/env bash
# bootstrap_py.sh —— 为 PDF 量化工具准备纯 Python 依赖（本机无 pip 的环境）
#
# 本机 python3.13 无 pip/ensurepip，因此这里直接从 PyPI 下载 wheel 解包到
# TEXOPT_TOOLS 目录（默认 ~/.local/lib/texopt-tools），用 PYTHONPATH 引入。
# 依赖：pdfminer.six（版面分析，字形级几何）、charset-normalizer（pdfminer 依赖）、
#       pypdf（页数等元信息，pdfminer 的备用）
#
# cryptography：pdfminer.six 在**模块导入期**就 import 它（即便我们只读未加密 PDF）。
#   由于本机无法编译/安装真正的 cryptography，这里放一个 **shim**：
#   只提供 pdfminer 需要的符号名，一旦真的被调用（加密 PDF）就显式报错。
#   这不是“绕过安全机制”，而是让工具在无 pip 环境下可用；加密 PDF 会被明确拒绝。
#
# 用法: bash tools/bootstrap_py.sh
set -euo pipefail
T="${TEXOPT_TOOLS:-$HOME/.local/lib/texopt-tools}"
mkdir -p "$T"

pip_dl() {  # $1=包名  $2=文件名筛选表达式
  local pkg="$1" filt="${2:-py3-none-any}"
  local url
  url=$(curl -sSL --max-time 30 "https://pypi.org/pypi/$pkg/json" | python3 -c "
import json,sys
d=json.load(sys.stdin)
want=sys.argv[1]
for f in d['urls']:
    if f['packagetype']!='bdist_wheel': continue
    if want in f['filename']: print(f['url']); break
" "$filt")
  [ -n "$url" ] || { echo "找不到 $pkg ($filt) 的 wheel" >&2; return 1; }
  echo "下载 $url"
  ( cd "$T" && curl -sSL --max-time 180 -O "$url" )
}

if python3 -c "import sys;sys.path.insert(0,'$T');import pdfminer,pypdf" 2>/dev/null; then
  echo "依赖已就绪: $T"
  exit 0
fi

pip_dl pdfminer.six py3-none-any
pip_dl pypdf py3-none-any
pip_dl charset-normalizer manylinux
python3 - "$T" <<'PY'
import sys, glob, zipfile, os
t = sys.argv[1]
for w in glob.glob(os.path.join(t, "*.whl")):
    if "cryptography" in w:
        continue
    zipfile.ZipFile(w).extractall(t)
    print("解包", os.path.basename(w))
PY

# cryptography shim（仅让 import 通过；加密 PDF 会显式报错）
mkdir -p "$T/cryptography/hazmat/backends" "$T/cryptography/hazmat/primitives/ciphers"
cat > "$T/cryptography/__init__.py" <<'EOF'
"""SHIM：仅供 pdfminer.six 的模块级 import 通过；本工具不处理加密 PDF。"""
__shim__ = True

def _missing(*a, **k):
    raise RuntimeError("cryptography 为 shim，未实现：本工具不支持加密 PDF")
EOF
: > "$T/cryptography/hazmat/__init__.py"
: > "$T/cryptography/hazmat/primitives/__init__.py"
cat > "$T/cryptography/hazmat/backends/__init__.py" <<'EOF'
def default_backend(*a, **k):
    from cryptography import _missing
    return _missing()
EOF
cat > "$T/cryptography/hazmat/primitives/ciphers/__init__.py" <<'EOF'
from cryptography import _missing

def Cipher(*a, **k):
    return _missing()

class _NS:
    def __getattr__(self, name):
        return _missing()

algorithms = _NS()
modes = _NS()
EOF
cat > "$T/cryptography/exceptions.py" <<'EOF'
class UnsupportedAlgorithm(Exception):
    pass
EOF

python3 -c "import sys;sys.path.insert(0,'$T');import pdfminer,pypdf;print('OK: pdfminer + pypdf 就绪 ->', '$T')"
