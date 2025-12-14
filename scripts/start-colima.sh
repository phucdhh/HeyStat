#!/bin/bash
# Colima Auto-Start Script for LaunchDaemon
# This script ensures Colima starts properly with correct configuration

LOG_DIR="/Users/mac/HeyStat/logs"
LOG_FILE="$LOG_DIR/colima-autostart.log"

# Create log directory
mkdir -p "$LOG_DIR"

# Log function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "========================================="
log "Starting Colima Auto-Start"
log "========================================="

# Check if Colima is already running
if /opt/homebrew/bin/colima status >/dev/null 2>&1; then
    log "✓ Colima is already running"
    exit 0
fi

log "Starting Colima with configuration..."

# Start Colima in background
/opt/homebrew/bin/colima start \
    --arch aarch64 \
    --cpu 4 \
    --memory 8 \
    --disk 50 \
    >> "$LOG_FILE" 2>&1

if [ $? -eq 0 ]; then
    log "✓ Colima started successfully"
    
    # Wait for Docker to be ready
    log "Waiting for Docker to be ready..."
    for i in {1..30}; do
        if /usr/local/bin/docker ps >/dev/null 2>&1; then
            log "✓ Docker is ready"
            exit 0
        fi
        sleep 1
    done
    
    log "⚠ Docker took longer than expected to be ready, but Colima started"
    exit 0
else
    log "✗ Failed to start Colima"
    exit 1
fi
