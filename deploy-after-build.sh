#!/bin/bash
# Kiểm tra build xong chưa rồi restart HeyStat
# Chạy: bash /root/HeyStat/deploy-after-build.sh

set -e
WORKDIR="/root/HeyStat"
LOG="/tmp/heystat_build3.log"

echo "=== Kiểm tra build ==="
if ! tail -3 "$LOG" | grep -q "Successfully built\|Successfully tagged"; then
    echo "Build chưa xong. Xem log: tail -f $LOG"
    echo "Bước hiện tại: $(grep 'Step' $LOG | tail -1)"
    exit 1
fi

echo "Build hoàn thành!"

echo "=== Restart HeyStat ==="
docker rm -f heystat 2>/dev/null || true
docker run -d \
  --name heystat \
  --restart unless-stopped \
  -p 42337:80 \
  -e JAMOVI_ALLOW_ARBITRARY_CODE=false \
  -e JAMOVI_HOST_A=heystat.pedu.vn \
  -e JAMOVI_HOST_B=heystat.pedu.vn/analyses \
  -e JAMOVI_HOST_C=heystat.pedu.vn/results \
  -e JAMOVI_ACCESS_KEY= \
  -v "$WORKDIR/Documents":/root/Documents \
  -v "$WORKDIR/jamovi-modules":/root/.jamovi/modules \
  -v "$WORKDIR/server/jamovi/server/public_roots.py":/usr/lib/jamovi/server/jamovi/server/public_roots.py:ro \
  heystat/heystat:2.7.6 \
  "/usr/bin/python3 -u -m jamovi.server 42337 --if=*"

sleep 4
docker ps | grep heystat
echo ""
echo "Test: $(curl -s -o /dev/null -w '%{http_code}' https://heystat.pedu.vn/)"
echo "HeyStat v2.7.16 đang chạy tại https://heystat.pedu.vn"
