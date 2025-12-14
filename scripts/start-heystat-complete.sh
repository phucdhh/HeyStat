#!/bin/bash
# Complete HeyStat Auto-Start Script
# Starts Colima, waits for Docker, then starts HeyStat container

LOG_DIR="/Users/mac/HeyStat/logs"
LOG_FILE="$LOG_DIR/heystat-complete-startup.log"

# Create log directory
mkdir -p "$LOG_DIR"

# Log function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "========================================="
log "HeyStat Complete Auto-Start"
log "========================================="

# Step 1: Check and start Colima
log "Step 1: Checking Colima status..."
if ! /opt/homebrew/bin/colima status >/dev/null 2>&1; then
    log "Colima is not running. Starting Colima..."
    /opt/homebrew/bin/colima start --arch aarch64 --cpu 4 --memory 8 --disk 50 >> "$LOG_FILE" 2>&1
    
    if [ $? -eq 0 ]; then
        log "✓ Colima started successfully"
    else
        log "✗ ERROR: Failed to start Colima"
        exit 1
    fi
else
    log "✓ Colima is already running"
fi

# Step 2: Wait for Docker to be ready
log "Step 2: Waiting for Docker to be ready..."
MAX_WAIT=60
COUNT=0

# Find docker binary
DOCKER_BIN=$(which docker 2>/dev/null || echo "/opt/homebrew/bin/docker")

while [ $COUNT -lt $MAX_WAIT ]; do
    if $DOCKER_BIN ps >/dev/null 2>&1; then
        log "✓ Docker is ready"
        break
    fi
    sleep 1
    COUNT=$((COUNT + 1))
    
    if [ $((COUNT % 10)) -eq 0 ]; then
        log "Waiting for Docker... ($COUNT/$MAX_WAIT)"
    fi
done

if [ $COUNT -ge $MAX_WAIT ]; then
    log "✗ ERROR: Docker is not available after $MAX_WAIT seconds"
    exit 1
fi

# Step 3: Start HeyStat container
log "Step 3: Starting HeyStat container..."
cd /Users/mac/HeyStat

# Check if container exists and is running
if $DOCKER_BIN ps --format "{{.Names}}" 2>/dev/null | grep -q "^heystat$"; then
    log "✓ HeyStat container is already running"
    exit 0
fi

# Start container
$DOCKER_BIN compose up -d >> "$LOG_FILE" 2>&1

if [ $? -eq 0 ]; then
    log "✓ HeyStat container started successfully"
else
    log "✗ ERROR: Failed to start HeyStat container"
    exit 1
fi

log "========================================="
log "HeyStat Complete Startup Finished"
log "========================================="

exit 0
