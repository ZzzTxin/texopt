#!/usr/bin/env bash
# install_templates.sh —— 把数据集生成的会议模板安装进 texopt 的 templates/ 目录，
# 使 `python3 optimize.py --template <id>` 可以直接使用（requirements 模块对接）。
#
# 默认是 **预览**（--dry-run 等价）；加 --apply 才真正写入。
# 已存在且内容不同的文件不会被覆盖，除非加 --force。
#
# 用法:
#   tools/install_templates.sh                 # 预览
#   tools/install_templates.sh --apply         # 安装（不覆盖已存在的不同文件）
#   tools/install_templates.sh --apply --force # 强制覆盖
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$ROOT/texopt-templates"
DEST="${TEXOPT_TEMPLATES_DIR:-$(cd "$ROOT/../.." && pwd)/templates}"

MODE="dry-run"
FORCE=0
for a in "$@"; do
  case "$a" in
    --apply) MODE="apply" ;;
    --force) FORCE=1 ;;
    -h|--help) sed -n '2,14p' "$0"; exit 0 ;;
  esac
done

[ -d "$SRC" ] || { echo "找不到 $SRC：先运行 python3 tools/build_dataset.py" >&2; exit 1; }
mkdir -p "$DEST"

echo "源:   $SRC"
echo "目标: $DEST"
echo "模式: $MODE"
echo
n_new=0; n_same=0; n_diff=0
for f in "$SRC"/*.json; do
  b="$(basename "$f")"
  if [ ! -e "$DEST/$b" ]; then
    echo "  新增  $b"; n_new=$((n_new+1))
    [ "$MODE" = "apply" ] && cp -f "$f" "$DEST/$b"
  elif cmp -s "$f" "$DEST/$b"; then
    echo "  相同  $b"; n_same=$((n_same+1))
  else
    if [ "$FORCE" = "1" ]; then
      echo "  覆盖  $b"; n_diff=$((n_diff+1))
      [ "$MODE" = "apply" ] && cp -f "$f" "$DEST/$b"
    else
      echo "  已存在且不同，跳过（--force 可覆盖）: $b"; n_diff=$((n_diff+1))
    fi
  fi
done
echo
echo "新增 $n_new / 相同 $n_same / 冲突 $n_diff"
[ "$MODE" = "dry-run" ] && echo "（预览模式；确认后加 --apply）"
