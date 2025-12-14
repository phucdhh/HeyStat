#!/bin/bash
# HeyStat Startup Script with Colima Wait
# This script waits for Colima to be ready before starting HeyStat

set -e

LOG_FILE="/Users/mac/HeyStat/logs/heystat-startup.log"
MAX_WAIT=60  # Wait up to 60 seconds

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "========================================="
log "HeyStat Startup Script Started"
log "========================================="

# Wait for Colima to be ready
log "Waiting for Colima to be ready..."
COUNTER=0
while [ $COUNTER -lt $MAX_WAIT ]; do
    if docker ps &>/dev/null; then
        log "✓ Colima is ready!"
        break
    fi
    log "Waiting for Docker... ($COUNTER/$MAX_WAIT)"
    sleep 2
    COUNTER=$((COUNTER + 2))
done

# Check if Docker is available
if ! docker ps &>/dev/null; then
    log "✗ ERROR: Docker is not available after $MAX_WAIT seconds"
    exit 1
fi

# Change to project directory
cd /Users/mac/HeyStat || exit 1
log "Changed to /Users/mac/HeyStat"

# Start HeyStat with docker compose
log "Starting HeyStat container..."
/opt/homebrew/bin/docker compose up -d 2>&1 | tee -a "$LOG_FILE"

if [ $? -eq 0 ]; then
    log "✓ HeyStat started successfully!"
    log "Container status:"
    docker ps --filter "name=heystat" | tee -a "$LOG_FILE"
else
    log "✗ ERROR: Failed to start HeyStat"
    exit 1
fi

log "========================================="
log "HeyStat Startup Complete"
log "========================================="
