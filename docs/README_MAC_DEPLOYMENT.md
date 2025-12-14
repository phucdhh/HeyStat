# HeyStat - Triển khai trên Mac Mini M2

HeyStat là một ứng dụng phân tích thống kê mã nguồn mở, fork từ Jamovi 2.7.6. Dự án này được cấu hình để chạy trên Mac Mini M2 và được truy cập qua Cloudflare Tunnel.

## 📋 Yêu cầu hệ thống

- Mac Mini M2 (hoặc Apple Silicon)
- macOS 12.0 trở lên
- Docker Desktop for Mac
- Homebrew
- Nginx (cài qua Homebrew)
- Cloudflared (cài qua Homebrew)

## 🔧 Cài đặt Dependencies

```bash
# Cài đặt Homebrew (nếu chưa có)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Cài đặt các packages cần thiết
brew install nginx
brew install cloudflared
brew install docker

# Khởi động Docker Desktop
open -a Docker
```

## 🚀 Triển khai nhanh

### Bước 1: Setup dự án

```bash
cd /Users/mac/HeyStat

# Chạy script setup (cần sudo)
sudo ./deploy-mac.sh setup
```

Script này sẽ:
- Tạo thư mục logs
- Cấu hình Nginx với HeyStat
- Setup LaunchDaemon
- Build Docker images cho ARM64
- Khởi động HeyStat service

### Bước 2: Setup Cloudflare Tunnel

```bash
# Đăng nhập Cloudflare (chỉ cần làm 1 lần)
cloudflared tunnel login

# Setup tunnel cho HeyStat
./cloudflare-setup.sh setup
```

### Bước 3: Kiểm tra

```bash
# Kiểm tra HeyStat service
sudo ./deploy-mac.sh status

# Kiểm tra Cloudflare tunnel
./cloudflare-setup.sh status

# Xem logs
sudo ./deploy-mac.sh logs
```

## 🌐 Truy cập

- **Local:** http://localhost:8082
- **Public:** https://heystat.truyenthong.edu.vn

## 📁 Cấu trúc dự án

```
/Users/mac/HeyStat/
├── docker-compose.yaml           # Cấu hình Docker (port 42337-42339)
├── heystat-nginx-mac.conf        # Nginx config cho Mac (port 8082)
├── deploy-mac.sh                 # Script quản lý HeyStat
├── cloudflare-setup.sh           # Script setup Cloudflare Tunnel
├── launch-daemons/
│   └── com.heystat.docker.plist  # LaunchDaemon cho Docker
└── logs/
    ├── heystat-docker.log
    ├── cloudflared-heystat.log
    └── ...
```

## 🔌 Ports đã sử dụng

HeyStat đã được cấu hình để tránh xung đột với các dự án khác (HeyTeX, AIThink):

- **42337-42339:** Docker containers (thay vì 41337-41339)
- **8082:** Nginx reverse proxy (thay vì 80)

Các dự án khác đang sử dụng:
- 3000, 5173, 5433-5437: HeyTeX/AIThink
- 5432, 5434: PostgreSQL, MinIO
- 11434: Ollama

## 📝 Quản lý Service

### Các lệnh deploy-mac.sh

```bash
# Setup hoàn chỉnh
sudo ./deploy-mac.sh setup

# Build lại Docker images
sudo ./deploy-mac.sh build

# Khởi động service
sudo ./deploy-mac.sh start

# Dừng service
sudo ./deploy-mac.sh stop

# Khởi động lại
sudo ./deploy-mac.sh restart

# Kiểm tra trạng thái
sudo ./deploy-mac.sh status

# Xem logs realtime
sudo ./deploy-mac.sh logs

# Gỡ cài đặt
sudo ./deploy-mac.sh uninstall
```

### Các lệnh cloudflare-setup.sh

```bash
# Setup hoàn chỉnh
./cloudflare-setup.sh setup

# Chỉ tạo tunnel
./cloudflare-setup.sh create

# Chỉ tạo config
./cloudflare-setup.sh config

# Setup DNS route
./cloudflare-setup.sh dns

# Test tunnel (interactive)
./cloudflare-setup.sh test

# Khởi động/dừng service
./cloudflare-setup.sh start
./cloudflare-setup.sh stop
./cloudflare-setup.sh restart

# Kiểm tra trạng thái
./cloudflare-setup.sh status

# Gỡ cài đặt
./cloudflare-setup.sh uninstall
```

## 🔍 Troubleshooting

### Docker không khởi động

```bash
# Kiểm tra Docker Desktop đã chạy chưa
open -a Docker

# Kiểm tra Docker daemon
docker ps
```

### Nginx lỗi

```bash
# Test cấu hình
nginx -t

# Reload Nginx
brew services restart nginx

# Xem logs
tail -f /opt/homebrew/var/log/nginx/heystat_error.log
```

### Cloudflare Tunnel không kết nối

```bash
# Xem logs
tail -f /Users/mac/HeyStat/logs/cloudflared-heystat.log

# Restart tunnel
./cloudflare-setup.sh restart

# Test tunnel
./cloudflare-setup.sh test
```

### Port conflict

```bash
# Kiểm tra ports đang sử dụng
lsof -iTCP -sTCP:LISTEN -n -P | grep -E '(42337|42338|42339|8082)'

# Nếu có xung đột, sửa trong docker-compose.yaml và heystat-nginx-mac.conf
```

## 🔒 Bảo mật

### Access Key

HeyStat có thể được bảo vệ bằng access key. Trong `docker-compose.yaml`:

```yaml
# Tự động tạo access key (recommended cho production)
JAMOVI_ACCESS_KEY: ''

# Hoặc đặt key cố định
JAMOVI_ACCESS_KEY: 'your-secret-key-here'

# Hoặc tắt hoàn toàn (chỉ cho development)
JAMOVI_DISABLE_ACCESS_KEY: '1'
```

Truy cập với key: `https://heystat.truyenthong.edu.vn/?access_key=your-secret-key-here`

### Multi-origin Security

HeyStat chạy trên 3 origins để tăng bảo mật (như Jamovi):
- Host A: `heystat.truyenthong.edu.vn:42337`
- Host B: `heystat.truyenthong.edu.vn:42337/analyses`
- Host C: `heystat.truyenthong.edu.vn:42337/results`

## 🔄 Cập nhật

### Cập nhật code

```bash
cd /Users/mac/HeyStat
git pull

# Rebuild và restart
sudo ./deploy-mac.sh build
sudo ./deploy-mac.sh restart
```

### Cập nhật config

Sau khi sửa config, restart services:

```bash
# Nếu sửa docker-compose.yaml
sudo ./deploy-mac.sh restart

# Nếu sửa nginx config
sudo nginx -t && brew services restart nginx

# Nếu sửa cloudflare config
./cloudflare-setup.sh restart
```

## 📊 Monitoring

### Logs locations

```bash
# HeyStat Docker logs
/Users/mac/HeyStat/logs/heystat-docker.log
/Users/mac/HeyStat/logs/heystat-docker-error.log

# Cloudflare Tunnel logs
/Users/mac/HeyStat/logs/cloudflared-heystat.log
/Users/mac/HeyStat/logs/cloudflared-heystat-error.log

# Nginx logs
/opt/homebrew/var/log/nginx/heystat_access.log
/opt/homebrew/var/log/nginx/heystat_error.log
```

### Xem logs realtime

```bash
# Docker logs
docker logs -f heystat

# Cloudflare logs
tail -f /Users/mac/HeyStat/logs/cloudflared-heystat.log

# Nginx logs
tail -f /opt/homebrew/var/log/nginx/heystat_access.log
```

## 🎯 So sánh với Ubuntu deployment

| Aspect | Ubuntu (LXC) | Mac Mini M2 |
|--------|-------------|-------------|
| Architecture | linux/amd64 | linux/arm64 |
| Ports | 41337-41339 | 42337-42339 |
| Nginx Port | 80 | 8082 |
| Service Manager | systemd | LaunchDaemon |
| Container Name | jamovi | heystat |
| Domain | jamovi.truyenthong.edu.vn | heystat.truyenthong.edu.vn |

## 📞 Liên hệ và Hỗ trợ

- **Project:** HeyStat (fork from Jamovi)
- **Original:** https://www.jamovi.org
- **License:** AGPL-3.0 (giống Jamovi)

## ⚖️ Giấy phép

HeyStat là fork từ Jamovi và tuân theo cùng giấy phép AGPL-3.0. Bạn có thể:
- Sử dụng miễn phí
- Chỉnh sửa source code
- Phân phối lại
- Sử dụng cho mục đích thương mại

Với điều kiện:
- Phải công khai source code khi phân phối
- Phải giữ nguyên giấy phép AGPL-3.0
- Phải ghi rõ nguồn gốc từ Jamovi

## 🚧 Development

### Build client

```bash
cd client
npm install
npm run build
```

### Development mode với hot reload

```bash
# Enable vite service trong docker-compose.yaml
# Sau đó set environment variable:
JAMOVI_DEV_SERVER: "http://vite:5173"
```

### Run tests

```bash
# Python tests
cd server
python -m pytest tests/

# R tests
cd jmv
Rscript -e "devtools::test()"
```

## 📚 Tài liệu tham khảo

- [Jamovi Documentation](https://www.jamovi.org)
- [Jamovi Developer Hub](https://dev.jamovi.org)
- [Cloudflare Tunnel Docs](https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/)
- [Docker Compose Docs](https://docs.docker.com/compose/)
- [Nginx Reverse Proxy](https://docs.nginx.com/nginx/admin-guide/web-server/reverse-proxy/)

---

**Note:** Đây là dự án development. Để sử dụng production, cần:
1. Đặt access key mạnh trong docker-compose.yaml
2. Cấu hình firewall
3. Enable monitoring và alerting
4. Setup backup tự động
5. Review security settings
