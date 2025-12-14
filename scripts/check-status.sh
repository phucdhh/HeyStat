#!/bin/bash
# Quick Status Check for HeyStat Auto-Start Services

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== HeyStat Auto-Start Status ===${NC}"
echo ""

# Check LaunchDaemons
echo -e "${YELLOW}LaunchDaemons:${NC}"
if sudo launchctl list | grep -q "com.heystat.complete"; then
    echo -e "  ${GREEN}✓${NC} HeyStat Complete LaunchDaemon loaded"
else
    echo -e "  ${RED}✗${NC} HeyStat Complete LaunchDaemon NOT loaded"
fi

if sudo launchctl list | grep -q "com.cloudflare.cloudflared.heystat"; then
    echo -e "  ${GREEN}✓${NC} Cloudflare Tunnel LaunchDaemon loaded"
else
    echo -e "  ${RED}✗${NC} Cloudflare Tunnel LaunchDaemon NOT loaded"
fi

echo ""

# Check Docker/Colima
echo -e "${YELLOW}Docker/Colima:${NC}"
if docker ps &>/dev/null; then
    echo -e "  ${GREEN}✓${NC} Docker is running"
    CONTAINER_STATUS=$(docker ps --filter "name=heystat" --format "{{.Status}}" 2>/dev/null)
    if [ -n "$CONTAINER_STATUS" ]; then
        echo -e "  ${GREEN}✓${NC} HeyStat container: $CONTAINER_STATUS"
    else
        echo -e "  ${RED}✗${NC} HeyStat container NOT running"
    fi
else
    echo -e "  ${RED}✗${NC} Docker is NOT running"
fi

echo ""

# Check Nginx
echo -e "${YELLOW}Nginx (port 8082):${NC}"
if lsof -iTCP:8082 -sTCP:LISTEN 2>/dev/null | grep -q nginx; then
    echo -e "  ${GREEN}✓${NC} Nginx is listening on port 8082"
else
    echo -e "  ${RED}✗${NC} Nginx is NOT listening on port 8082"
fi

echo ""

# Check Local Access
echo -e "${YELLOW}Local Access:${NC}"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8082 2>/dev/null)
if [ "$HTTP_CODE" = "302" ] || [ "$HTTP_CODE" = "200" ]; then
    echo -e "  ${GREEN}✓${NC} http://localhost:8082 is accessible (HTTP $HTTP_CODE)"
else
    echo -e "  ${RED}✗${NC} http://localhost:8082 is NOT accessible (HTTP $HTTP_CODE)"
fi

echo ""

# Check Public Access
echo -e "${YELLOW}Public Access:${NC}"
HTTPS_CODE=$(curl -s -o /dev/null -w "%{http_code}" https://heystat.truyenthong.edu.vn 2>/dev/null)
if [ "$HTTPS_CODE" = "302" ] || [ "$HTTPS_CODE" = "200" ]; then
    echo -e "  ${GREEN}✓${NC} https://heystat.truyenthong.edu.vn is accessible (HTTP $HTTPS_CODE)"
else
    echo -e "  ${RED}✗${NC} https://heystat.truyenthong.edu.vn is NOT accessible (HTTP $HTTPS_CODE)"
fi

echo ""

# Check Recent Logs
echo -e "${YELLOW}Recent Logs (last 3 lines):${NC}"
if [ -f /Users/mac/HeyStat/logs/heystat-startup.log ]; then
    echo -e "${BLUE}HeyStat Startup:${NC}"
    tail -3 /Users/mac/HeyStat/logs/heystat-startup.log | sed 's/^/  /'
else
    echo -e "  ${YELLOW}⚠${NC} No startup log found"
fi

echo ""
echo -e "${BLUE}=================================${NC}"

# Overall status
if docker ps --filter "name=heystat" --format "{{.Status}}" 2>/dev/null | grep -q "Up"; then
    if [ "$HTTPS_CODE" = "302" ] || [ "$HTTPS_CODE" = "200" ]; then
        echo -e "${GREEN}✓ All services are running properly${NC}"
        exit 0
    else
        echo -e "${YELLOW}⚠ HeyStat is running but not publicly accessible${NC}"
        exit 1
    fi
else
    echo -e "${RED}✗ HeyStat is NOT running${NC}"
    exit 1
fi
