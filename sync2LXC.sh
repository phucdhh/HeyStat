#!/bin/bash
# Dong bo ma nguon HeyStat tu iMac -> LXC (noi app dang chay that).
# Mac dinh: CHI gui (khong xoa file tren LXC) + in ra danh sach thay doi.
#
#   ./sync2LXC.sh                   # dry-run: xem se gui/xoa gi
#   ./sync2LXC.sh --apply           # dong bo that
#   ./sync2LXC.sh --apply --delete  # dong bo + xoa file thua tren LXC (van giu du lieu)
#   ./sync2LXC.sh --build           # sync + rebuild & restart HeyStat tren LXC
#   ./sync2LXC.sh --no-code         # chi gui classroom/
#
# Du lieu cua nguoi dung (Documents/, backups/, dump.rdb, jamovi-modules/)
# luon duoc loai khoi rsync va khong bao bi lenh xoá theo.

set -euo pipefail

REMOTE="${HEYSTAT_REMOTE:-root@192.168.1.223}"
REMOTE_DIR="${HEYSTAT_REMOTE_DIR:-/root/HeyStat}"
LOCAL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

APPLY=false
DELETE=false
BUILD=false
CODE_ONLY=false
EXCLUDES=()

while [ $# -gt 0 ]; do
  case "$1" in
    --apply|-y)    APPLY=true ;;
    --dry-run)     APPLY=false ;;
    --delete)      DELETE=true ;;
    --build)       BUILD=true; APPLY=true ;;
    --no-code)     CODE_ONLY=true ;;
    -e|--exclude)  EXCLUDES+=("$2"); shift ;;
    -h|--help)     sed -n '1,13p' "$0"; exit 0 ;;
    *) echo "Khong nhan ra tham so: $1"; exit 2 ;;
  esac
  shift
done

PROTECTED=(
  .git/
  Documents/
  backups/
  logs/
  dump.rdb
  jamovi-modules/
  chrome-test/
  .venv/
  .pytest_cache/
  node_modules/
  '**/dist/'
  '**/__pycache__/'
  '*.pyc' '*.o' '*.so'
  '.DS_Store' '*.log'
  '.env'
)

if $CODE_ONLY; then
  INCLUDES=(classroom/)
else
  INCLUDES=(.)
fi

ARGS=(-avz --human-readable --itemize-changes --no-perms --no-owner --no-group)
$APPLY || ARGS+=(--dry-run)
# --delete nhung KHONG dung --delete-excluded: tuyon do se xoa Documents/, backups/,
# jamovi-modules/ tren LXC (file bi exclude o phia nhan bi xoá khi --delete chay).
if $DELETE && ! $CODE_ONLY; then ARGS+=(--delete); fi
for p in "${PROTECTED[@]}"; do ARGS+=(--exclude "$p"); done
for p in ${EXCLUDES[@]+"${EXCLUDES[@]}"}; do ARGS+=(--exclude "$p"); done

echo "=== sync2LXC: $LOCAL_DIR -> $REMOTE:$REMOTE_DIR ==="
$APPLY || echo "(dry-run - them --apply de dong bo that)"
if $DELETE; then echo "!! --delete: file thua tren LXC se bi xoa (du lieu da duoc bao ve)"; fi

ssh -o ConnectTimeout=10 "$REMOTE" "mkdir -p '$REMOTE_DIR'"
for item in "${INCLUDES[@]}"; do
  # duong dan KHONG duoc co '/' o cuoi: rsync src/ -> dst/ chi noi dung cua src
  # vao dst (se ra dst/api, dst/frontend thay vi dst/classroom/api)
  src="$LOCAL_DIR/${item%/}"
  [ -e "$src" ] || { echo "!! Khong co '$src', bo qua"; continue; }
  [ -d "$src" ] && src="$src/"
  rsync "${ARGS[@]}" "$src" "$REMOTE:$REMOTE_DIR/${item%/}/"
done

if $BUILD; then
  echo "=== rebuild + restart tren LXC ==="
  ssh "$REMOTE" "cd '$REMOTE_DIR' && bash rebuild.sh"
  ssh "$REMOTE" "cd '$REMOTE_DIR' && bash start-heystat-linux.sh"
fi

echo ""
if $APPLY; then
  echo "OK. Kiem tra: ssh $REMOTE 'docker ps | grep -E \"heystat|classroom\"'"
else
  echo "-> Dry-run. Chay './sync2LXC.sh --apply' de dong bo."
fi
