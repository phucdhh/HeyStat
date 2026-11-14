#!/bin/bash
# Clear leftover jamovi sessions outside class hours. Session timeouts handle
# normal tab closes; this restart also releases anything stuck in memory.
set -u

logger -t heystat-cleanup "nightly jamovi restart"
docker restart heystat >/dev/null 2>&1 || \
    logger -t heystat-cleanup "docker restart heystat failed"

sleep 10
docker exec heystat sh -c \
    "find /tmp -mindepth 1 -maxdepth 1 -type d -name 'tmp*' -mmin +60 -exec rm -rf {} +" \
    >/dev/null 2>&1 || true
