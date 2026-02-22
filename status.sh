#!/bin/bash
# HeyStat Status Script
# Comprehensive status check for all HeyStat services

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║       HeyStat System Status           ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"
echo ""

# Overall status
ISSUES=0

# 1. Colima Status
echo -e "${CYAN}[1] Docker/Colima${NC}"
if colima status >/dev/null 2>&1; then
    COLIMA_INFO=$(colima status 2>&1)
    echo -e "  ${GREEN}✓${NC} Colima: Running"
    
    if docker ps >/dev/null 2>&1; then
        echo -e "  ${GREEN}✓${NC} Docker: Ready"
    else
        echo -e "  ${RED}✗${NC} Docker: Not responding"
        ISSUES=$((ISSUES + 1))
    fi
else
    echo -e "  ${RED}✗${NC} Colima: Not running"
    echo -e "  ${RED}✗${NC} Docker: Unavailable"
    ISSUES=$((ISSUES + 1))
fi
echo ""

# 2. HeyStat Container
echo -e "${CYAN}[2] HeyStat Container${NC}"
if docker ps >/dev/null 2>&1; then
    CONTAINER_STATUS=$(docker ps --filter "name=heystat" --format "{{.Status}}" 2>/dev/null)
    if [ -n "$CONTAINER_STATUS" ]; then
        echo -e "  ${GREEN}✓${NC} Status: $CONTAINER_STATUS"
        
        # Get container stats
        CONTAINER_ID=$(docker ps --filter "name=heystat" --format "{{.ID}}" 2>/dev/null)
        if [ -n "$CONTAINER_ID" ]; then
            STATS=$(docker stats --no-stream --format "table {{.CPUPerc}}\t{{.MemUsage}}" $CONTAINER_ID 2>/dev/null | tail -n 1)
            echo -e "  ${GREEN}ℹ${NC} Resources: $STATS"
        fi
    else
        echo -e "  ${RED}✗${NC} Container not running"
        ISSUES=$((ISSUES + 1))
    fi
else
    echo -e "  ${RED}✗${NC} Cannot check (Docker unavailable)"
    ISSUES=$((ISSUES + 1))
fi
echo ""

# 3. Nginx
echo -e "${CYAN}[3] Nginx (Reverse Proxy)${NC}"
if pgrep -f "nginx" >/dev/null 2>&1; then
    echo -e "  ${GREEN}✓${NC} Nginx: Running"
    
    if lsof -iTCP:8082 -sTCP:LISTEN 2>/dev/null | grep -q -E "nginx|vz.0.virtio"; then
        echo -e "  ${GREEN}✓${NC} Port 8082: Listening"
    else
        echo -e "  ${YELLOW}⚠${NC} Port 8082: Check inconclusive"
    fi
else
    echo -e "  ${RED}✗${NC} Nginx: Not running"
    ISSUES=$((ISSUES + 1))
fi
echo ""

# 4. LaunchDaemons
echo -e "${CYAN}[4] Auto-Start Services${NC}"
if sudo -n true 2>/dev/null; then
    if sudo launchctl list | grep -q "com.heystat.complete"; then
        echo -e "  ${GREEN}✓${NC} HeyStat LaunchDaemon: Loaded"
    else
        echo -e "  ${YELLOW}⚠${NC} HeyStat LaunchDaemon: Not loaded"
    fi
    
    if sudo launchctl list | grep -q "com.cloudflare.cloudflared.heystat"; then
        echo -e "  ${GREEN}✓${NC} Cloudflare Tunnel: Loaded"
    else
        echo -e "  ${YELLOW}⚠${NC} Cloudflare Tunnel: Not loaded"
    fi
else
    echo -e "  ${YELLOW}⚠${NC} Cannot check (requires sudo)"
fi
echo ""

# 5. Network Access
echo -e "${CYAN}[5] Network Access${NC}"

# Local access
LOCAL_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8082 2>/dev/null || echo "000")
if [ "$LOCAL_STATUS" == "302" ] || [ "$LOCAL_STATUS" == "200" ]; then
    echo -e "  ${GREEN}✓${NC} Local (8082): Accessible (HTTP $LOCAL_STATUS)"
elif [ "$LOCAL_STATUS" == "000" ]; then
    echo -e "  ${RED}✗${NC} Local (8082): Connection failed"
    ISSUES=$((ISSUES + 1))
else
    echo -e "  ${YELLOW}⚠${NC} Local (8082): HTTP $LOCAL_STATUS"
fi

# Public access
PUBLIC_STATUS=$(curl -s -o /dev/null -w "%{http_code}" https://heystat.truyenthong.edu.vn 2>/dev/null || echo "000")
if [ "$PUBLIC_STATUS" == "302" ] || [ "$PUBLIC_STATUS" == "200" ]; then
    echo -e "  ${GREEN}✓${NC} Public (HTTPS): Accessible (HTTP $PUBLIC_STATUS)"
elif [ "$PUBLIC_STATUS" == "000" ]; then
    echo -e "  ${RED}✗${NC} Public (HTTPS): Connection failed"
    ISSUES=$((ISSUES + 1))
else
    echo -e "  ${YELLOW}⚠${NC} Public (HTTPS): HTTP $PUBLIC_STATUS"
fi
echo ""

# 6. Recent Logs
echo -e "${CYAN}[6] Recent Activity${NC}"
if [ -f "$SCRIPT_DIR/logs/heystat-complete-startup.log" ]; then
    LAST_START=$(tail -n 20 "$SCRIPT_DIR/logs/heystat-complete-startup.log" | grep "HeyStat Startup Complete" | tail -n 1 | awk '{print $1, $2}')
    if [ -n "$LAST_START" ]; then
        echo -e "  ${GREEN}ℹ${NC} Last startup: $LAST_START"
    fi
fi

if docker ps >/dev/null 2>&1; then
    CONTAINER_ID=$(docker ps --filter "name=heystat" --format "{{.ID}}" 2>/dev/null)
    if [ -n "$CONTAINER_ID" ]; then
        ERROR_COUNT=$(docker logs $CONTAINER_ID 2>&1 | grep -i "error" | wc -l | tr -d ' ')
        if [ "$ERROR_COUNT" -gt 0 ]; then
            echo -e "  ${YELLOW}⚠${NC} Container errors: $ERROR_COUNT (check logs)"
        else
            echo -e "  ${GREEN}ℹ${NC} Container errors: None"
        fi
    fi
fi
echo ""

# Summary
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
if [ $ISSUES -eq 0 ]; then
    echo -e "${GREEN}✓ All systems operational${NC}"
    echo ""
    echo -e "  Local:  ${BLUE}http://localhost:8082${NC}"
    echo -e "  Public: ${BLUE}https://heystat.truyenthong.edu.vn${NC}"
else
    echo -e "${RED}✗ $ISSUES issue(s) detected${NC}"
    echo ""
    echo -e "Run ${YELLOW}./restart.sh${NC} to attempt recovery"
    echo -e "Or ${YELLOW}./stop.sh && ./start.sh${NC} for full restart"
fi
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Quick actions
echo -e "${CYAN}Quick Actions:${NC}"
echo -e "  ${YELLOW}./start.sh${NC}         - Start all services"
echo -e "  ${YELLOW}./stop.sh${NC}          - Stop services (keep Colima)"
echo -e "  ${YELLOW}./stop.sh --full${NC}   - Stop everything including Colima"
echo -e "  ${YELLOW}./restart.sh${NC}       - Quick restart (container + nginx)"
echo -e "  ${YELLOW}./restart.sh --full${NC} - Full restart with Colima"
echo ""

exit $ISSUES
