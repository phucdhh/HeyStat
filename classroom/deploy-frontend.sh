#!/bin/bash
# Deploy classroom frontend: build Vue app và copy vào /var/www/classroom/
# Chạy: bash /root/HeyStat/classroom/deploy-frontend.sh

set -e
FRONTEND_DIR="/root/HeyStat/classroom/frontend"
DEPLOY_DIR="/var/www/classroom"

echo "=== Build classroom frontend ==="
cd "$FRONTEND_DIR"

# Kiểm tra node_modules
if [ ! -d "node_modules" ]; then
    echo "Cài đặt dependencies..."
    npm install
fi

npm run build

echo "=== Deploy sang $DEPLOY_DIR ==="
mkdir -p "$DEPLOY_DIR"
cp -r dist/. "$DEPLOY_DIR/"

echo "=== Reload Nginx ==="
nginx -t && nginx -s reload

echo ""
echo "✓ Classroom frontend đã deploy thành công tại https://heystat.pedu.vn/classroom/"
