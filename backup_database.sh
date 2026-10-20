#!/bin/bash
# Backup du lieu HeyStat tren LXC (192.168.1.223) ve keo ve may cua ban.
# Mac dinh: PostgreSQL (classroom) + Redis + volume uploads.
# Chay tai: < thu muc du an >/backups/db/
#
#   ./backup_database.sh                 # backup du lieu
#   ./backup_database.sh --pg-only       # chi backup PostgreSQL
#   ./backup_database.sh --with-docs     # backup ca Documents/ (du lieu file nguoi dung, co the nang)
#   ./backup_database.sh --keep-days 30  # giu backup trong 30 ngay
#
# San pham:
#   classroom_<timestamp>.sql.gz  -> phuc hoi: gunzip -c file | psql -U heystat -d classroom
#   redis_<timestamp>.rdb
#   uploads_<timestamp>.tar.gz
#   documents_<timestamp>.tar.gz  (chi khi --with-docs)

set -euo pipefail

REMOTE="${HEYSTAT_REMOTE:-root@192.168.1.223}"
REMOTE_DIR="${HEYSTAT_REMOTE_DIR:-/root/HeyStat}"
LOCAL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_DIR="${HEYSTAT_BACKUP_DIR:-$LOCAL_DIR/backups/db}"
KEEP_DAYS="${HEYSTAT_BACKUP_KEEP_DAYS:-14}"

DO_PG=true
DO_REDIS=true
DO_UPLOADS=true
DO_DOCS=false
VERIFY=true

while [ $# -gt 0 ]; do
  case "$1" in
    --pg-only)      DO_PG=true; DO_REDIS=false; DO_UPLOADS=false ;;
    --redis-only)   DO_PG=false; DO_REDIS=true; DO_UPLOADS=false ;;
    --skip-redis)   DO_REDIS=false ;;
    --skip-uploads) DO_UPLOADS=false ;;
    --with-docs)    DO_DOCS=true ;;
    --keep-days)    KEEP_DAYS="$2"; shift ;;
    --no-verify)    VERIFY=false ;;
    -h|--help)      sed -n '1,18p' "$0"; exit 0 ;;
    *) echo "Khong nhan ra tham so: $1"; exit 2 ;;
  esac
  shift
done

STAMP="$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"
echo "=== backup_database: $REMOTE -> $BACKUP_DIR ($STAMP) ==="

# --- 1. tim container Postgres + Redis tren LXC ------------------------------
DB_CID=$(ssh "$REMOTE" 'docker ps --format "{{.Names}}" | grep -E "db" | grep -iE "classroom|postgre" | head -1')
RD_CID=$(ssh "$REMOTE" 'docker ps --format "{{.Names}}" | grep -iE "redis" | head -1')

if [ -z "$DB_CID" ]; then
  echo "!! Khong tim thay container PostgreSQL dang chay tren $REMOTE (bo qua buoc 1)."
else
  echo "-- [1] PostgreSQL: container $DB_CID"
  # Goi pg_dump ngay trong container Postgres de dung dung client va khong can mat khau.
  ssh "$REMOTE" "docker exec '$DB_CID' sh -c 'pg_dump -U \$POSTGRES_USER -d \$POSTGRES_DB'" \
    | gzip -9 > "$BACKUP_DIR/classroom_$STAMP.sql.gz"
  ls -lh "$BACKUP_DIR/classroom_$STAMP.sql.gz"
fi

# --- 2. Redis (dump.rdb cua volume redis_data) -------------------------------
if $DO_REDIS; then
  if [ -z "$RD_CID" ]; then
    echo "!! Khong tim thay container Redis (bo qua buoc 2)."
  else
    echo "-- [2] Redis: container $RD_CID"
    # SAVE in ra "OK" -> phai nap /dev/null, neu khong 3 byte do bi ghi vao dump.rdb.
    ssh "$REMOTE" "RD=\$(docker volume ls -q | grep -E 'classroom.*redis_data' | head -1)
      docker exec '$RD_CID' redis-cli SAVE >/dev/null 2>&1 || true
      for d in /var/lib/docker/volumes/\"\$RD\"/_data /data; do
        [ -f \"\$d/dump.rdb\" ] && cat \"\$d/dump.rdb\" && exit 0
      done
      docker exec '$RD_CID' cat /data/dump.rdb" > "$BACKUP_DIR/redis_$STAMP.rdb"
    if [ "$(head -c 5 "$BACKUP_DIR/redis_$STAMP.rdb" | tr -d '\n')" = "REDIS" ]; then
      ls -lh "$BACKUP_DIR/redis_$STAMP.rdb"
    else
      echo "!! redis_$STAMP.rdb khong dung dinh dang REDIS (bo qua, giu file cu nếu co)"
    fi
  fi
fi

# --- 3. volume uploads (file bai tap / ho so ma API luu) ---------------------
if $DO_UPLOADS; then
  echo "-- [3] uploads volume"
  ssh "$REMOTE" 'UP=$(docker volume ls -q | grep -E "classroom.*uploads" | head -1)
    [ -n "$UP" ] || UP=$(docker volume ls -q | grep uploads | head -1)
    [ -n "$UP" ] || { echo "khong tim thay volume uploads" >&2; exit 0; }
    docker run --rm -v "$UP":/v:ro alpine tar -czf - -C /v .' \
    > "$BACKUP_DIR/uploads_$STAMP.tar.gz"
  [ -s "$BACKUP_DIR/uploads_$STAMP.tar.gz" ] || rm -f "$BACKUP_DIR/uploads_$STAMP.tar.gz"
  ls -lh "$BACKUP_DIR/uploads_$STAMP.tar.gz" 2>/dev/null || echo "   (khong co uploads)"
fi

# --- 4. Documents/ = kho file .omv/.csv cua jamovi ---------------------------
if $DO_DOCS; then
  echo "-- [4] Documents/ tren LXC"
  ssh "$REMOTE" "tar -czf - -C '$REMOTE_DIR' Documents 2>/dev/null" \
    > "$BACKUP_DIR/documents_$STAMP.tar.gz"
  ls -lh "$BACKUP_DIR/documents_$STAMP.tar.gz"
fi

# --- 5. kiem tra + xoa backup cu ---------------------------------------------
if $VERIFY; then
  for f in "$BACKUP_DIR"/*_"$STAMP".sql.gz "$BACKUP_DIR"/*_"$STAMP".tar.gz; do
    [ -e "$f" ] || continue
    if gzip -t "$f" 2>/dev/null; then echo "   OK gzip: $(basename "$f")"; else echo "   !! file hu hong: $f"; fi
  done
  if [ -e "$BACKUP_DIR/classroom_$STAMP.sql.gz" ]; then
    if gunzip -c "$BACKUP_DIR/classroom_$STAMP.sql.gz" 2>/dev/null | head -3 | grep -q 'PostgreSQL database dump'; then
      echo "   OK dump: $(basename "$BACKUP_DIR/classroom_$STAMP.sql.gz") (so bang: $(gunzip -c "$BACKUP_DIR/classroom_$STAMP.sql.gz" | grep -c '^CREATE TABLE'))"
    else
      echo "   !! dump khong phai pg_dump cua PostgreSQL"
    fi
  fi
fi

echo "-- Xoa backup hon $KEEP_DAYS ngay"
find "$BACKUP_DIR" -type f \( -name '*.sql.gz' -o -name '*.rdb' -o -name '*.tar.gz' \) \
  -mtime +"$KEEP_DAYS" -print -delete

echo ""
echo "Xong. Backup hien co:"
ls -lh "$BACKUP_DIR" | tail -8
