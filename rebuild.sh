#!/bin/bash
# Rebuild toàn bộ HeyStat Classroom: frontend Vue + API Docker
# Chạy: bash /root/HeyStat/rebuild.sh
#
# Options:
#   --frontend-only   Chỉ build và deploy frontend
#   --api-only        Chỉ rebuild các container API (Docker)
#   --no-cache        Rebuild Docker images từ đầu (không dùng cache)

set -e

WORKDIR="/root/HeyStat"
CLASSROOM_DIR="$WORKDIR/classroom"
FRONTEND_DIR="$CLASSROOM_DIR/frontend"
DEPLOY_DIR="/var/www/classroom"

FRONTEND_ONLY=false
API_ONLY=false
NO_CACHE=""

for arg in "$@"; do
  case "$arg" in
    --frontend-only) FRONTEND_ONLY=true ;;
    --api-only)      API_ONLY=true ;;
    --no-cache)      NO_CACHE="--no-cache" ;;
  esac
done

# ─── Frontend ────────────────────────────────────────────────────────────────

build_frontend() {
  echo ""
  echo "=== [1/2] Build classroom frontend ==="
  cd "$FRONTEND_DIR"

  if [ ! -d "node_modules" ]; then
    echo "Cài đặt npm dependencies..."
    npm install
  fi

  npm run build

  echo "--- Deploy sang $DEPLOY_DIR ---"
  mkdir -p "$DEPLOY_DIR"
  cp -r dist/. "$DEPLOY_DIR/"

  echo "--- Reload Nginx ---"
  nginx -t && nginx -s reload

  echo "✓ Frontend đã deploy tại https://heystat.pedu.vn/classroom/"
}

# ─── API (Docker Compose) ────────────────────────────────────────────────────

rebuild_api() {
  echo ""
  echo "=== [2/2] Rebuild classroom API (Docker) ==="
  cd "$CLASSROOM_DIR"

  docker-compose build $NO_CACHE api worker scheduler

  echo "--- Restart services ---"
  docker-compose stop api worker scheduler
  docker-compose rm -f api worker scheduler
  docker-compose up -d api worker scheduler

  echo "--- Chờ API khởi động ---"
  sleep 5

  STATUS=$(docker-compose ps 2>/dev/null || echo "(không lấy được trạng thái)")
  echo "$STATUS"

  HTTP=$(curl -s -o /dev/null -w '%{http_code}' https://heystat.pedu.vn/classroom/api/v1/health 2>/dev/null || echo "???")
  echo "Health check API: HTTP $HTTP"
  echo "✓ API đã rebuild và restart thành công"
}

# ─── Main ────────────────────────────────────────────────────────────────────

echo "========================================="
echo " HeyStat Classroom Rebuild"
echo " $(date '+%Y-%m-%d %H:%M:%S')"
echo "========================================="

if $FRONTEND_ONLY; then
  build_frontend
elif $API_ONLY; then
  rebuild_api
else
  build_frontend
  rebuild_api
fi

echo ""
echo "========================================="
echo " Xong! https://heystat.pedu.vn/classroom/"
echo "========================================="
