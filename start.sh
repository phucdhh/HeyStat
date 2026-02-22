#!/bin/bash
# HeyStat Start Script
# Starts Colima, waits for Docker, then starts HeyStat container and services

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$SCRIPT_DIR/logs"
LOG_FILE="$LOG_DIR/heystat-startup.log"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Create log directory
mkdir -p "$LOG_DIR"

# Log function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

echo -e "${BLUE}=== Starting HeyStat ===${NC}"
log "========================================="
log "HeyStat Startup"
log "========================================="

# Step 1: Check and start Colima
echo -e "${YELLOW}[1/4]${NC} Checking Colima..."
log "Step 1: Checking Colima status..."

if ! colima status >/dev/null 2>&1; then
    log "Colima is not running. Starting Colima..."
    echo -e "  ${YELLOW}→${NC} Starting Colima (this may take a minute)..."
    
    colima start --cpu 4 --memory 8 --disk 60 --vm-type=vz --mount-type=virtiofs >> "$LOG_FILE" 2>&1
    
    if [ $? -eq 0 ]; then
        log "✓ Colima started successfully"
        echo -e "  ${GREEN}✓${NC} Colima started"
    else
        log "✗ ERROR: Failed to start Colima"
        echo -e "  ${RED}✗${NC} Failed to start Colima"
        exit 1
    fi
else
    log "✓ Colima is already running"
    echo -e "  ${GREEN}✓${NC} Colima is running"
fi

# Step 2: Wait for Docker to be ready
echo -e "${YELLOW}[2/4]${NC} Waiting for Docker..."
log "Step 2: Waiting for Docker to be ready..."

MAX_WAIT=30
COUNT=0

while [ $COUNT -lt $MAX_WAIT ]; do
    if docker ps >/dev/null 2>&1; then
        log "✓ Docker is ready"
        echo -e "  ${GREEN}✓${NC} Docker is ready"
        break
    fi
    sleep 1
    COUNT=$((COUNT + 1))
done

if [ $COUNT -ge $MAX_WAIT ]; then
    log "✗ ERROR: Docker did not become ready in time"
    echo -e "  ${RED}✗${NC} Docker timeout"
    exit 1
fi

# Step 3: Start HeyStat container
echo -e "${YELLOW}[3/4]${NC} Starting HeyStat container..."
log "Step 3: Starting HeyStat container..."

cd "$SCRIPT_DIR"

if docker ps --filter "name=heystat" --format "{{.Names}}" | grep -q "^heystat$"; then
    log "HeyStat container is already running"
    echo -e "  ${GREEN}✓${NC} Container already running"
else
    docker compose up -d >> "$LOG_FILE" 2>&1
    
    if [ $? -eq 0 ]; then
        log "✓ HeyStat container started"
        echo -e "  ${GREEN}✓${NC} Container started"
        sleep 3
    else
        log "✗ ERROR: Failed to start HeyStat container"
        echo -e "  ${RED}✗${NC} Failed to start container"
        exit 1
    fi
fi

# Step 4: Check Nginx
echo -e "${YELLOW}[4/4]${NC} Checking Nginx..."
log "Step 4: Checking Nginx..."

if pgrep -f "nginx" >/dev/null 2>&1; then
    log "✓ Nginx is already running"
    echo -e "  ${GREEN}✓${NC} Nginx is running"
else
    log "Starting Nginx..."
    echo -e "  ${YELLOW}→${NC} Starting Nginx..."
    
    if [ -f "/opt/homebrew/bin/nginx" ]; then
        /opt/homebrew/bin/nginx >> "$LOG_FILE" 2>&1
        
        if [ $? -eq 0 ]; then
            log "✓ Nginx started"
            echo -e "  ${GREEN}✓${NC} Nginx started"
        else
            log "⚠ WARNING: Failed to start Nginx"
            echo -e "  ${YELLOW}⚠${NC} Nginx start failed (may need manual start)"
        fi
    else
        log "⚠ WARNING: Nginx not found"
        echo -e "  ${YELLOW}⚠${NC} Nginx not found"
    fi
fi

echo ""
log "========================================="
log "HeyStat Startup Complete"
log "========================================="

echo -e "${GREEN}✓ HeyStat Started Successfully${NC}"
echo ""
echo -e "  Local:  ${BLUE}http://localhost:8082${NC}"
echo -e "  Public: ${BLUE}https://heystat.truyenthong.edu.vn${NC}"
echo ""
echo -e "Run ${YELLOW}./status.sh${NC} to check system status"
