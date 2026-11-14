#!/bin/bash
# Restart HeyStat services only after they stay unresponsive for several checks.
# A single slow request during a heavy class must not interrupt students.
set -u

STATE_DIR=/run/heystat-watchdog
mkdir -p "$STATE_DIR"
MAX_FAILURES=${MAX_FAILURES:-5}

check_and_restart() {
    name=$1
    url=$2
    container=$3

    if curl -fsS --max-time 8 -H 'Host: heystat.pedu.vn' "$url" -o /dev/null; then
        rm -f "$STATE_DIR/$name.fail"
        return
    fi

    failures=$(cat "$STATE_DIR/$name.fail" 2>/dev/null || echo 0)
    failures=$((failures + 1))
    echo "$failures" > "$STATE_DIR/$name.fail"
    logger -t heystat-watchdog "$container health check failed ($failures/$MAX_FAILURES)"

    if [ "$failures" -ge "$MAX_FAILURES" ]; then
        logger -t heystat-watchdog "restarting $container after $failures failed checks"
        docker restart "$container" >/dev/null 2>&1 || \
            logger -t heystat-watchdog "docker restart $container failed"
        rm -f "$STATE_DIR/$name.fail"
    fi
}

check_and_restart jamovi http://127.0.0.1:42337/version heystat
check_and_restart api http://127.0.0.1:8080/api/v1/health classroom_api_1
