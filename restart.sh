#!/bin/bash
# HeyStat Restart Script
# Restarts HeyStat services

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}=== Restarting HeyStat ===${NC}"
echo ""

# Parse options
RESTART_MODE="quick"
if [ "$1" == "--full" ] || [ "$1" == "-f" ]; then
    RESTART_MODE="full"
fi

if [ "$RESTART_MODE" == "full" ]; then
    echo -e "${YELLOW}Full restart (including Colima)...${NC}"
    echo ""
    
    # Stop everything including Colima
    "$SCRIPT_DIR/stop.sh" --full
    
    echo ""
    echo -e "${YELLOW}Waiting 3 seconds...${NC}"
    sleep 3
    echo ""
    
    # Start everything
    "$SCRIPT_DIR/start.sh"
else
    echo -e "${YELLOW}Quick restart (Docker container and Nginx only)...${NC}"
    echo ""
    
    # Quick restart: just container and nginx
    cd "$SCRIPT_DIR"
    
    echo -e "${YELLOW}[1/2]${NC} Restarting container..."
    docker compose restart
    
    echo -e "${YELLOW}[2/2]${NC} Reloading Nginx..."
    if [ -f "/opt/homebrew/bin/nginx" ]; then
        if pgrep -f "nginx" >/dev/null 2>&1; then
            /opt/homebrew/bin/nginx -s reload 2>/dev/null || echo "  (reload failed, nginx may not be running)"
        else
            /opt/homebrew/bin/nginx 2>/dev/null || echo "  (nginx start failed)"
        fi
    fi
    
    echo ""
    echo -e "${GREEN}✓ HeyStat Restarted${NC}"
    echo ""
    echo -e "Use ${YELLOW}./restart.sh --full${NC} for full restart with Colima"
fi

echo ""
echo -e "Run ${YELLOW}./status.sh${NC} to verify services"
