#!/usr/bin/env bash
# fetch_source.sh —— 抓取官方来源并落盘归档（去重、记录 http 状态与 sha256）
#
# 用法:
#   ./fetch_source.sh <src-id> <url> [ext]
#     src-id : src-<conf>-<edition|name>-<kind>，例如 src-neurips-2025-cfp
#     ext    : html | pdf | sty | txt  （缺省按 URL 后缀/Content-Type 猜）
#
# 产物:
#   sources/raw/<src-id>.<ext>    原始文件（归档，可复现）
#   sources/raw/<src-id>.txt      纯文本抽取（html/pdf 时生成；便于引用校验）
#   sources/fetch_log.jsonl       每次抓取追加一行（含 sha256/http 状态/时间）
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RAW="$ROOT/sources/raw"
LOG="$ROOT/sources/fetch_log.jsonl"
mkdir -p "$RAW"

SRC_ID="${1:?用法: fetch_source.sh <src-id> <url|本地文件> [ext]}"
URL="${2:?缺少 url 或本地文件路径}"
EXT="${3:-}"

# 支持本地文件（例如从官方 zip 里解出来的 .sty/.cls）
if [ -f "$URL" ] || [[ "$URL" == file://* ]]; then
  SRC="${URL#file://}"
  [ -z "$EXT" ] && EXT="${SRC##*.}"
  OUT="$RAW/$SRC_ID.$EXT"
  cp -f "$SRC" "$OUT"
  SHA=$(sha256sum "$OUT" | awk '{print $1}')
  python3 "$ROOT/tools/totext.py" "$OUT" > "$RAW/$SRC_ID.txt" 2>/dev/null || rm -f "$RAW/$SRC_ID.txt"
  python3 - "$LOG" "$SRC_ID" "$URL" "$EXT" "$OUT" "$SHA" "local" <<'PY'
import json, sys, datetime, os
log, sid, url, ext, out, sha, status = sys.argv[1:8]
rec = {"src_id": sid, "url": url, "ext": ext,
       "raw_file": os.path.relpath(out, os.path.dirname(os.path.dirname(os.path.abspath(log)))),
       "sha256": sha, "bytes": os.path.getsize(out), "http_status": status,
       "fetched_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds")}
open(log, "a", encoding="utf-8").write(json.dumps(rec, ensure_ascii=False) + "\n")
print(f"OK(local) {sid} sha256={sha[:16]}… -> {rec['raw_file']}")
PY
  exit 0
fi

if [ -z "$EXT" ]; then
  case "${URL%%\?*}" in
    *.pdf) EXT=pdf ;;
    *.sty|*.cls|*.bst|*.tex) EXT=sty ;;
    *.txt) EXT=txt ;;
    *) EXT=html ;;
  esac
fi

OUT="$RAW/$SRC_ID.$EXT"
UA='Mozilla/5.0 (X11; Linux x86_64) texopt-dataset/1.0 (+academic layout research)'

# 已归档则跳过下载（可用 --force 覆盖），仍写日志
if [ -s "$OUT" ] && [ "${3:-}${FORCE:-}" != "--force" ]; then
  STATUS="cached"
else
  CODE=$(curl -sSL --compressed --max-time 60 -A "$UA" -w '%{http_code}' -o "$OUT" "$URL" 2>/dev/null || echo 000)
  STATUS="$CODE"
  [ "$STATUS" = "000" ] && rm -f "$OUT"
fi

if [ ! -s "$OUT" ]; then
  echo "FETCH_FAILED $SRC_ID $URL" >&2
  exit 1
fi

SHA=$(sha256sum "$OUT" | awk '{print $1}')
SIZE=$(stat -c %s "$OUT")

# 文本抽取：便于按原文摘录校验 quote
TXT="$RAW/$SRC_ID.txt"
if [ "$EXT" != "txt" ]; then
  python3 "$ROOT/tools/totext.py" "$OUT" > "$TXT" 2>/dev/null || true
  [ -s "$TXT" ] || rm -f "$TXT"
fi

python3 - "$LOG" "$SRC_ID" "$URL" "$EXT" "$OUT" "$SHA" "$SIZE" "$STATUS" <<'PY'
import json, sys, datetime, os
log, sid, url, ext, out, sha, size, status = sys.argv[1:9]
rec = {
    "src_id": sid, "url": url, "ext": ext,
    "raw_file": os.path.relpath(out, os.path.dirname(os.path.dirname(os.path.abspath(log)))),
    "sha256": sha, "bytes": int(size), "http_status": status,
    "fetched_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
}
with open(log, "a", encoding="utf-8") as fh:
    fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
print(f"OK {sid} http={status} sha256={sha[:16]}… -> {rec['raw_file']}")
PY
