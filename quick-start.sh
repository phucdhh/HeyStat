#!/bin/bash
# HeyStat Quick Start Guide
# Hướng dẫn nhanh để triển khai HeyStat trên Mac Mini M2

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

clear

cat << "EOF"
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║   ██╗  ██╗███████╗██╗   ██╗███████╗████████╗ █████╗ ████████╗║
║   ██║  ██║██╔════╝╚██╗ ██╔╝██╔════╝╚══██╔══╝██╔══██╗╚══██╔══╝║
║   ███████║█████╗   ╚████╔╝ ███████╗   ██║   ███████║   ██║   ║
║   ██╔══██║██╔══╝    ╚██╔╝  ╚════██║   ██║   ██╔══██║   ██║   ║
║   ██║  ██║███████╗   ██║   ███████║   ██║   ██║  ██║   ██║   ║
║   ╚═╝  ╚═╝╚══════╝   ╚═╝   ╚══════╝   ╚═╝   ╚═╝  ╚═╝   ╚═╝   ║
║                                                               ║
║              Mac Mini M2 Deployment Quick Start               ║
║                  Fork from Jamovi 2.7.6                       ║
╚═══════════════════════════════════════════════════════════════╝
EOF

echo ""
echo -e "${GREEN}Chào mừng đến với HeyStat Setup!${NC}"
echo ""
echo "Hướng dẫn này sẽ giúp bạn triển khai HeyStat trên Mac Mini M2"
echo ""

# Check if running as root for system setup
if [ "$EUID" -eq 0 ]; then 
    echo -e "${YELLOW}Warning: Đang chạy với quyền root${NC}"
fi

echo -e "${BLUE}════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}Bước 1: Kiểm tra Dependencies${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════${NC}"
echo ""

# Check Docker
echo -n "Kiểm tra Docker... "
if command -v docker &> /dev/null; then
    echo -e "${GREEN}✓ Đã cài đặt${NC} ($(docker --version))"
else
    echo -e "${YELLOW}✗ Chưa cài đặt${NC}"
    echo "  → Cài đặt: brew install docker"
    echo "  → Hoặc tải Docker Desktop: https://www.docker.com/products/docker-desktop"
fi

# Check Nginx
echo -n "Kiểm tra Nginx... "
if command -v nginx &> /dev/null; then
    echo -e "${GREEN}✓ Đã cài đặt${NC} ($(nginx -v 2>&1))"
else
    echo -e "${YELLOW}✗ Chưa cài đặt${NC}"
    echo "  → Cài đặt: brew install nginx"
fi

# Check Cloudflared
echo -n "Kiểm tra Cloudflared... "
if command -v cloudflared &> /dev/null; then
    echo -e "${GREEN}✓ Đã cài đặt${NC} ($(cloudflared --version 2>&1 | head -1))"
else
    echo -e "${YELLOW}✗ Chưa cài đặt${NC}"
    echo "  → Cài đặt: brew install cloudflared"
fi

echo ""
echo -e "${BLUE}════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}Bước 2: Cài đặt Dependencies (nếu cần)${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════${NC}"
echo ""
echo "Nếu bạn chưa cài đặt các dependencies trên, chạy:"
echo ""
echo "  brew install nginx cloudflared docker"
echo "  open -a Docker  # Khởi động Docker Desktop"
echo ""

read -p "Bạn đã cài đặt đủ dependencies? (y/N) " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Vui lòng cài đặt dependencies trước khi tiếp tục"
    exit 1
fi

echo ""
echo -e "${BLUE}════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}Bước 3: Kiểm tra Ports${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════${NC}"
echo ""
echo "HeyStat sẽ sử dụng các ports sau:"
echo "  • 42337-42339: Docker containers"
echo "  • 8082: Nginx reverse proxy"
echo ""
echo "Kiểm tra xem các ports này có bị sử dụng không..."
echo ""

PORTS_IN_USE=0
for port in 42337 42338 42339 8082; do
    if lsof -iTCP:$port -sTCP:LISTEN &> /dev/null; then
        echo -e "${YELLOW}✗ Port $port đang được sử dụng${NC}"
        lsof -iTCP:$port -sTCP:LISTEN | grep LISTEN
        PORTS_IN_USE=1
    else
        echo -e "${GREEN}✓ Port $port trống${NC}"
    fi
done

if [ $PORTS_IN_USE -eq 1 ]; then
    echo ""
    echo -e "${YELLOW}Cảnh báo: Một số ports đang được sử dụng${NC}"
    echo "Bạn có thể:"
    echo "  1. Dừng các services đang sử dụng ports này"
    echo "  2. Sửa ports trong docker-compose.yaml và heystat-nginx-mac.conf"
    echo ""
    read -p "Tiếp tục? (y/N) " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo ""
echo -e "${BLUE}════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}Bước 4: Deploy HeyStat${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════${NC}"
echo ""
echo "Sẵn sàng triển khai HeyStat!"
echo ""
echo "Các bước sẽ thực hiện:"
echo "  1. Tạo thư mục logs"
echo "  2. Cấu hình Nginx"
echo "  3. Setup LaunchDaemon"
echo "  4. Build Docker images (có thể mất vài phút)"
echo "  5. Khởi động HeyStat service"
echo ""

read -p "Bắt đầu deploy? (y/N) " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Deploy bị hủy"
    exit 1
fi

echo ""
echo -e "${GREEN}Đang deploy HeyStat...${NC}"
echo ""

# Run deploy script
sudo ./deploy-mac.sh setup

echo ""
echo -e "${BLUE}════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}Bước 5: Setup Cloudflare Tunnel${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════${NC}"
echo ""
echo "Để truy cập HeyStat từ internet qua https://heystat.truyenthong.edu.vn,"
echo "bạn cần cấu hình Cloudflare Tunnel."
echo ""

read -p "Setup Cloudflare Tunnel ngay bây giờ? (y/N) " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    echo "Đầu tiên, đăng nhập Cloudflare (mở trình duyệt):"
    cloudflared tunnel login
    
    echo ""
    echo "Bây giờ setup tunnel..."
    ./cloudflare-setup.sh setup
else
    echo ""
    echo "Bạn có thể setup Cloudflare Tunnel sau bằng lệnh:"
    echo "  cloudflared tunnel login"
    echo "  ./cloudflare-setup.sh setup"
fi

echo ""
echo -e "${BLUE}════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✓ Hoàn thành!${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════${NC}"
echo ""
echo "HeyStat đã được triển khai thành công!"
echo ""
echo -e "${GREEN}Truy cập:${NC}"
echo "  • Local:  http://localhost:8082"
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "  • Public: https://heystat.truyenthong.edu.vn"
fi
echo ""
echo -e "${GREEN}Các lệnh hữu ích:${NC}"
echo "  • Kiểm tra trạng thái: sudo ./deploy-mac.sh status"
echo "  • Xem logs:            sudo ./deploy-mac.sh logs"
echo "  • Dừng service:        sudo ./deploy-mac.sh stop"
echo "  • Khởi động lại:       sudo ./deploy-mac.sh restart"
echo ""
echo "  • CF tunnel status:    ./cloudflare-setup.sh status"
echo "  • CF tunnel logs:      tail -f logs/cloudflared-heystat.log"
echo ""
echo -e "${GREEN}Tài liệu:${NC}"
echo "  • Chi tiết: README_MAC_DEPLOYMENT.md"
echo "  • Jamovi docs: https://www.jamovi.org"
echo ""
echo -e "${YELLOW}Lưu ý:${NC}"
echo "  • Đây là môi trường development"
echo "  • Để production, cần đặt JAMOVI_ACCESS_KEY trong docker-compose.yaml"
echo "  • Xem thêm security settings trong README_MAC_DEPLOYMENT.md"
echo ""
echo "Chúc bạn làm việc vui vẻ với HeyStat! 🎉"
echo ""
