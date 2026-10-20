#!/bin/bash
# Script khởi động HeyStat trên heystat.pedu.vn
# Chạy sau khi docker-compose build hoàn thành

set -e

WORKDIR="/root/HeyStat"
cd "$WORKDIR"

echo "=== Khởi động HeyStat ==="

# Kiểm tra image đã được build chưa
if ! docker images -q heystat/heystat:2.7.30 | grep -q .; then
    echo "Image heystat/heystat:2.7.30 chưa được build."
    echo "Chạy: cd $WORKDIR && docker build -f docker/jamovi-Dockerfile -t heystat/heystat:2.7.30 ."
    exit 1
fi

# Dừng container cũ nếu có
docker-compose stop heystat 2>/dev/null || true
docker-compose rm -f heystat 2>/dev/null || true

# Tạo thư mục cần thiết
mkdir -p Documents jamovi-modules

# Khoá không cho R nạp module học viên tự cài (image chỉ có module cài sẵn)
COLLAB_SECRET=$(sed -n 's/^JAMOVI_COLLAB_SECRET=//p' "$WORKDIR/classroom/api/.env" 2>/dev/null | head -1)

# Khởi động container
docker rm -f heystat 2>/dev/null || true
docker run -d \
  --name heystat \
  --restart unless-stopped \
  -p 42337:80 \
  -e JAMOVI_ALLOW_ARBITRARY_CODE=false \
  -e JAMOVI_SUPPRESS_USER_MODULES=1 \
  -e JAMOVI_HOST_A=heystat.pedu.vn \
  -e JAMOVI_HOST_B=heystat.pedu.vn/analyses \
  -e JAMOVI_HOST_C=heystat.pedu.vn/results \
  -e JAMOVI_ACCESS_KEY= \
  ${COLLAB_SECRET:+-e JAMOVI_COLLAB_SECRET="$COLLAB_SECRET"} \
  -v "$WORKDIR/Documents":/root/Documents \
  -v "$WORKDIR/jamovi-modules":/root/.jamovi/modules \
  -v "$WORKDIR/server/jamovi/server/public_roots.py":/usr/lib/jamovi/server/jamovi/server/public_roots.py:ro \
  heystat/heystat:2.7.30 \
  "/usr/bin/python3 -u -m jamovi.server 42337 --if=*"

echo ""
echo "=== Kiểm tra trạng thái ==="
sleep 3
docker ps | grep heystat || echo "Container chưa chạy!"

echo ""
echo "HeyStat đang chạy tại: http://127.0.0.1:42337"
echo "Qua nginx (sau khi DNS xong): https://heystat.pedu.vn"
