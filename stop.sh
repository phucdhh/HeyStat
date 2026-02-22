#!/bin/bash
# HeyStat Stop Script
# Stops HeyStat container, Nginx, and optionally Colima

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$SCRIPT_DIR/logs"
LOG_FILE="$LOG_DIR/heystat-shutdown.log"

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

echo -e "${BLUE}=== Stopping HeyStat ===${NC}"
log "========================================="
log "HeyStat Shutdown"
log "========================================="

# Parse options
STOP_COLIMA=false
if [ "$1" == "--full" ] || [ "$1" == "-f" ]; then
    STOP_COLIMA=true
fi

# Step 1: Stop HeyStat container
echo -e "${YELLOW}[1/3]${NC} Stopping HeyStat container..."
log "Step 1: Stopping HeyStat container..."

cd "$SCRIPT_DIR"

if docker ps >/dev/null 2>&1; then
    if docker ps --filter "name=heystat" --format "{{.Names}}" | grep -q "^heystat$"; then
        docker compose down >> "$LOG_FILE" 2>&1
        
        if [ $? -eq 0 ]; then
            log "✓ HeyStat container stopped"
            echo -e "  ${GREEN}✓${NC} Container stopped"
        else
            log "✗ ERROR: Failed to stop HeyStat container"
            echo -e "  ${RED}✗${NC} Failed to stop container"
        fi
    else
        log "HeyStat container is not running"
        echo -e "  ${YELLOW}ℹ${NC} Container not running"
    fi
else
    log "Docker is not available"
    echo -e "  ${YELLOW}ℹ${NC} Docker not available"
fi

# Step 2: Stop Nginx
echo -e "${YELLOW}[2/3]${NC} Stopping Nginx..."
log "Step 2: Stopping Nginx..."

if pgrep -f "nginx" >/dev/null 2>&1; then
    if [ -f "/opt/homebrew/bin/nginx" ]; then
        /opt/homebrew/bin/nginx -s quit >> "$LOG_FILE" 2>&1
        sleep 1
        
        if ! pgrep -f "nginx" >/dev/null 2>&1; then
            log "✓ Nginx stopped"
            echo -e "  ${GREEN}✓${NC} Nginx stopped"
        else
            log "⚠ Nginx still running, force killing..."
            pkill -9 nginx 2>/dev/null || true
            echo -e "  ${YELLOW}⚠${NC} Nginx force stopped"
        fi
    else
        log "⚠ Nginx executable not found, killing process..."
        pkill -9 nginx 2>/dev/null || true
        echo -e "  ${YELLOW}⚠${NC} Nginx force stopped"
    fi
else
    log "Nginx is not running"
    echo -e "  ${YELLOW}ℹ${NC} Nginx not running"
fi

# Step 3: Optionally stop Colima
echo -e "${YELLOW}[3/3]${NC} Colima..."
log "Step 3: Checking Colima..."

if [ "$STOP_COLIMA" = true ]; then
    if colima status >/dev/null 2>&1; then
        log "Stopping Colima..."
        echo -e "  ${YELLOW}→${NC} Stopping Colima..."
        
        colima stop >> "$LOG_FILE" 2>&1
        
        if [ $? -eq 0 ]; then
            log "✓ Colima stopped"
            echo -e "  ${GREEN}✓${NC} Colima stopped"
        else
            log "✗ ERROR: Failed to stop Colima"
            echo -e "  ${RED}✗${NC} Failed to stop Colima"
        fi
    else
        log "Colima is not running"
        echo -e "  ${YELLOW}ℹ${NC} Colima not running"
    fi
else
    log "Leaving Colima running (use --full to stop Colima)"
    echo -e "  ${YELLOW}ℹ${NC} Colima left running (use ${YELLOW}--full${NC} to stop)"
fi

echo ""
log "========================================="
log "HeyStat Shutdown Complete"
log "========================================="

echo -e "${GREEN}✓ HeyStat Stopped${NC}"
echo ""
if [ "$STOP_COLIMA" = false ]; then
    echo -e "Note: Colima is still running. Use ${YELLOW}./stop.sh --full${NC} to stop everything."
fi
