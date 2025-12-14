# HeyStat - Báo cáo Cấu hình cho Mac Mini M2

## Tổng quan

Dự án **HeyStat** là một fork từ **Jamovi 2.7.6** (ứng dụng phân tích thống kê mã nguồn mở) được cấu hình lại để chạy trên Mac Mini M2. Dự án tuân theo giấy phép AGPL-3.0 giống như Jamovi, cho phép chỉnh sửa và phân phối với điều kiện giữ nguyên giấy phép và công khai source code.

### Thông tin dự án
- **Tên:** HeyStat
- **Nền tảng:** Mac Mini M2 (Apple Silicon)
- **Địa chỉ:** `/Users/mac/HeyStat`
- **Domain:** https://heystat.truyenthong.edu.vn
- **Access local:** http://localhost:8082

## Các thay đổi chính

### 1. Docker Configuration (docker-compose.yaml)

#### Thay đổi kiến trúc và ports:
```yaml
# Thay đổi:
platform: linux/arm64           # Thay vì linux/amd64
container_name: heystat          # Thay vì jamovi
ports:
  - '42337:42337'               # Thay vì 41337
  - '42338:42338'               # Thay vì 41338
  - '42339:42339'               # Thay vì 41339
```

#### Thay đổi environment variables:
```yaml
JAMOVI_HOST_A: 'heystat.truyenthong.edu.vn:42337'
JAMOVI_HOST_B: 'heystat.truyenthong.edu.vn:42337/analyses'
JAMOVI_HOST_C: 'heystat.truyenthong.edu.vn:42337/results'
```

**Lý do:** Tránh xung đột với ports của HeyTeX/AIThink đang chạy (41337-41339)

### 2. Nginx Configuration

#### File mới: `heystat-nginx-mac.conf`
- **Port:** 8082 (thay vì 80)
- **Server name:** heystat.truyenthong.edu.vn
- **Proxy pass:** http://127.0.0.1:42337
- **Logs:** `/opt/homebrew/var/log/nginx/heystat_*.log`

**Lý do:** Port 80 yêu cầu quyền root và có thể xung đột với services khác

### 3. LaunchDaemon Service

#### File: `launch-daemons/com.heystat.docker.plist`
- Tự động khởi động Docker container khi boot
- Quản lý bởi launchd (thay vì systemd trên Linux)
- Logs tại: `/Users/mac/HeyStat/logs/`

**Đặc điểm:**
- KeepAlive: Tự động restart nếu crash
- RunAtLoad: Khởi động khi system boot
- WorkingDirectory: `/Users/mac/HeyStat`

### 4. Cloudflare Tunnel Configuration

#### Script: `cloudflare-setup.sh`
Tự động hóa việc:
- Tạo Cloudflare Tunnel
- Cấu hình DNS route
- Setup LaunchDaemon cho tunnel
- Quản lý tunnel service

#### Config file: `~/.cloudflared/config-heystat.yml`
```yaml
ingress:
  - hostname: heystat.truyenthong.edu.vn
    service: http://localhost:8082
    originRequest:
      httpHostHeader: heystat.truyenthong.edu.vn:42337
```

### 5. Deployment Scripts

#### `deploy-mac.sh` - Service Management
Chức năng:
- `setup`: Cài đặt hoàn chỉnh (nginx, docker, build)
- `build`: Build Docker images
- `start/stop/restart`: Quản lý service
- `status`: Kiểm tra trạng thái
- `logs`: Xem logs realtime
- `uninstall`: Gỡ cài đặt

#### `cloudflare-setup.sh` - Tunnel Management
Chức năng:
- `setup`: Cài đặt tunnel hoàn chỉnh
- `create/config/dns`: Từng bước cụ thể
- `test`: Test tunnel trước khi install
- `start/stop/restart`: Quản lý tunnel service
- `status`: Kiểm tra trạng thái và logs

#### `quick-start.sh` - Interactive Setup
- Wizard hướng dẫn từng bước
- Kiểm tra dependencies tự động
- Kiểm tra port conflicts
- Triển khai interactive

## Kiến trúc hệ thống

```
┌─────────────────────────────────────────────────────────────┐
│                        Internet                             │
│                  (HTTPS requests)                           │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌────────────────────────────────────────────────────────────┐
│              Cloudflare Tunnel (cloudflared)               │
│              Port: Dynamic (managed by CF)                 │
│              Service: com.cloudflare.cloudflared.heystat   │
└────────────────────────┬───────────────────────────────────┘
                         │
                         ▼ localhost:8082
┌────────────────────────────────────────────────────────────┐
│                 Nginx Reverse Proxy                        │
│                 Port: 8082                                 │
│                 Config: heystat-nginx-mac.conf             │
└────────────────────────┬───────────────────────────────────┘
                         │
                         ▼ localhost:42337
┌────────────────────────────────────────────────────────────┐
│              Docker Container (HeyStat)                    │
│              Platform: linux/arm64                         │
│              Ports: 42337, 42338, 42339                    │
│              Service: com.heystat.docker                   │
└────────────────────────────────────────────────────────────┘
```

## Cấu trúc thư mục mới

```
/Users/mac/HeyStat/
├── docker-compose.yaml               [MODIFIED] - ARM64, new ports, domain
├── jamovi-nginx.conf                 [ORIGINAL] - Ubuntu config
├── heystat-nginx-mac.conf            [NEW] - Mac specific nginx
├── deploy-mac.sh                     [NEW] - Service management
├── cloudflare-setup.sh               [NEW] - CF tunnel setup
├── quick-start.sh                    [NEW] - Interactive wizard
├── README_MAC_DEPLOYMENT.md          [NEW] - Mac deployment docs
├── CONFIGURATION.md                  [NEW] - Config summary
├── .gitignore                        [MODIFIED] - Added Mac specific
├── launch-daemons/                   [NEW]
│   └── com.heystat.docker.plist      - Docker service
└── logs/                             [NEW] - Auto-created
    ├── heystat-docker.log
    ├── heystat-docker-error.log
    ├── cloudflared-heystat.log
    └── cloudflared-heystat-error.log
```

## Ports mapping

| Service          | Old (Ubuntu) | New (Mac) | Reason                    |
|------------------|--------------|-----------|---------------------------|
| Docker A         | 41337        | 42337     | Avoid conflict            |
| Docker B         | 41338        | 42338     | Avoid conflict            |
| Docker C         | 41339        | 42339     | Avoid conflict            |
| Nginx            | 80           | 8082      | No root, avoid conflict   |
| Cloudflare       | N/A          | Dynamic   | Managed by CF             |

**Ports đang được sử dụng bởi projects khác:**
- 3000, 5173, 5433-5437: HeyTeX/AIThink
- 5432: PostgreSQL
- 8081: Nginx default
- 11434: Ollama

## Hướng dẫn triển khai

### Phương pháp 1: Quick Start (Khuyến nghị cho lần đầu)

```bash
cd /Users/mac/HeyStat
./quick-start.sh
```

Script này sẽ:
1. Kiểm tra dependencies (Docker, Nginx, Cloudflared)
2. Kiểm tra port conflicts
3. Deploy HeyStat
4. Setup Cloudflare Tunnel (optional)
5. Hiển thị trạng thái và cách truy cập

### Phương pháp 2: Manual Setup

```bash
# 1. Deploy HeyStat
sudo ./deploy-mac.sh setup

# 2. Verify local access
curl http://localhost:8082

# 3. Setup Cloudflare (cho public access)
cloudflared tunnel login
./cloudflare-setup.sh setup

# 4. Verify
./cloudflare-setup.sh status
```

## Quản lý hàng ngày

### Khởi động/Dừng services

```bash
# HeyStat
sudo ./deploy-mac.sh start
sudo ./deploy-mac.sh stop
sudo ./deploy-mac.sh restart

# Cloudflare Tunnel
./cloudflare-setup.sh start
./cloudflare-setup.sh stop
./cloudflare-setup.sh restart

# Nginx
brew services restart nginx
```

### Kiểm tra trạng thái

```bash
# Tổng quan
sudo ./deploy-mac.sh status
./cloudflare-setup.sh status

# Chi tiết
docker ps | grep heystat
lsof -iTCP:42337 -sTCP:LISTEN
lsof -iTCP:8082 -sTCP:LISTEN
```

### Xem logs

```bash
# Realtime logs
sudo ./deploy-mac.sh logs

# Specific logs
tail -f logs/heystat-docker.log
tail -f logs/cloudflared-heystat.log
tail -f /opt/homebrew/var/log/nginx/heystat_access.log
```

## Bảo mật

### 1. Access Key (Khuyến nghị cho production)

Sửa trong `docker-compose.yaml`:
```yaml
# Thay vì để trống:
JAMOVI_ACCESS_KEY: ''

# Đặt một key mạnh:
JAMOVI_ACCESS_KEY: 'your-strong-secret-key-here'
```

Truy cập: `https://heystat.truyenthong.edu.vn/?access_key=your-strong-secret-key-here`

### 2. Code Execution

```yaml
JAMOVI_ALLOW_ARBITRARY_CODE: 'false'  # Khuyến nghị: false
```

Chỉ set `true` nếu bạn hiểu rõ rủi ro bảo mật.

### 3. Multi-Origin Security

HeyStat chạy trên 3 origins riêng biệt:
- Host A: Main application
- Host B: Analysis UI (isolated)
- Host C: Results view (isolated)

Điều này ngăn chặn XSS attacks giữa các components.

## Khắc phục sự cố

### 1. Port đã được sử dụng

```bash
# Kiểm tra process đang dùng port
lsof -iTCP:42337 -sTCP:LISTEN

# Dừng process hoặc thay đổi port trong config
```

### 2. Docker không khởi động

```bash
# Khởi động Docker Desktop
open -a Docker

# Kiểm tra
docker ps

# Xem logs
docker logs heystat
```

### 3. Nginx lỗi

```bash
# Test config
nginx -t

# Xem error logs
tail -f /opt/homebrew/var/log/nginx/heystat_error.log

# Restart
brew services restart nginx
```

### 4. Cloudflare Tunnel không kết nối

```bash
# Kiểm tra authentication
cloudflared tunnel list

# Xem logs
tail -f logs/cloudflared-heystat.log

# Test tunnel
./cloudflare-setup.sh test

# Restart
./cloudflare-setup.sh restart
```

### 5. Không truy cập được từ browser

Kiểm tra theo thứ tự:
1. Docker container: `docker ps | grep heystat`
2. Local access: `curl -I http://localhost:42337`
3. Nginx: `curl -I http://localhost:8082`
4. Cloudflare: `curl -I https://heystat.truyenthong.edu.vn`

## Testing

### Local Testing
```bash
# Basic connectivity
curl -I http://localhost:8082

# WebSocket test
curl -I http://localhost:8082 -H "Upgrade: websocket"

# Load interface
open http://localhost:8082
```

### Public Testing
```bash
# HTTPS connectivity
curl -I https://heystat.truyenthong.edu.vn

# Browser test
open https://heystat.truyenthong.edu.vn
```

### Verify correct URLs
```bash
# Check config.js returns correct domains
curl -s https://heystat.truyenthong.edu.vn/config.js

# Expected output:
# window.config = {"client":{"roots":["https://heystat.truyenthong.edu.vn/",...]}
```

## Backup và Restore

### Backup
```bash
cd /Users/mac/HeyStat

# Backup config files
tar -czf ~/heystat-backup-$(date +%Y%m%d).tar.gz \
  docker-compose.yaml \
  heystat-nginx-mac.conf \
  launch-daemons/ \
  README_MAC_DEPLOYMENT.md \
  CONFIGURATION.md

# Backup Cloudflare config
cp -r ~/.cloudflared ~/cloudflared-backup-$(date +%Y%m%d)
```

### Restore
```bash
# Restore files
tar -xzf ~/heystat-backup-YYYYMMDD.tar.gz

# Redeploy
sudo ./deploy-mac.sh setup
./cloudflare-setup.sh setup
```

## Performance

### Docker Resources
Trong Docker Desktop Settings:
- **Memory:** 4GB minimum, 8GB khuyến nghị
- **CPUs:** 2 minimum, 4 khuyến nghị
- **Disk:** 20GB minimum

### Nginx Tuning
Trong `/opt/homebrew/etc/nginx/nginx.conf`:
```nginx
worker_processes  4;          # Theo số CPU cores
worker_connections  1024;     # Tăng nếu cần nhiều connections
```

## Monitoring

### System Monitoring
```bash
# Docker stats
docker stats heystat

# Port monitoring
watch -n 5 'lsof -iTCP -sTCP:LISTEN | grep -E "(42337|8082)"'

# Log monitoring
tail -f logs/*.log /opt/homebrew/var/log/nginx/heystat*.log
```

### Health Checks
```bash
# Create health check script
cat > check-heystat.sh << 'EOF'
#!/bin/bash
echo "Checking HeyStat health..."
curl -sf http://localhost:8082 > /dev/null && echo "✓ Local OK" || echo "✗ Local FAIL"
curl -sf https://heystat.truyenthong.edu.vn > /dev/null && echo "✓ Public OK" || echo "✗ Public FAIL"
docker ps | grep -q heystat && echo "✓ Docker OK" || echo "✗ Docker FAIL"
EOF

chmod +x check-heystat.sh
./check-heystat.sh
```

## Tài liệu tham khảo

### Dự án HeyStat
- [README_MAC_DEPLOYMENT.md](README_MAC_DEPLOYMENT.md) - Chi tiết triển khai
- [CONFIGURATION.md](CONFIGURATION.md) - Tổng hợp cấu hình
- [SETUP_NOTES.md](SETUP_NOTES.md) - Notes từ Ubuntu deployment

### Jamovi (Upstream)
- Website: https://www.jamovi.org
- GitHub: https://github.com/jamovi/jamovi
- Documentation: https://dev.jamovi.org
- Forum: https://forum.jamovi.org

### Technologies
- Docker: https://docs.docker.com
- Nginx: https://nginx.org/en/docs/
- Cloudflare Tunnel: https://developers.cloudflare.com/cloudflare-one/

## License

HeyStat tuân theo giấy phép **AGPL-3.0** (giống Jamovi):
- ✓ Sử dụng miễn phí
- ✓ Chỉnh sửa và phân phối
- ✓ Sử dụng thương mại
- ✗ Phải công khai source code khi phân phối
- ✗ Phải giữ nguyên giấy phép AGPL-3.0
- ✗ Phải ghi rõ nguồn gốc từ Jamovi

## Kết luận

Dự án HeyStat đã được cấu hình thành công cho Mac Mini M2 với:

✅ **Hoàn thành:**
- Docker container chạy trên ARM64 architecture
- Ports đã được thay đổi để tránh xung đột (42337-42339, 8082)
- Nginx reverse proxy cấu hình đúng
- LaunchDaemons setup cho tự động khởi động
- Cloudflare Tunnel script hoàn chỉnh
- Scripts quản lý service đầy đủ
- Documentation chi tiết

🎯 **Sẵn sàng deploy:**
- Chạy `./quick-start.sh` để bắt đầu
- Hoặc manual với `sudo ./deploy-mac.sh setup`
- Truy cập local: http://localhost:8082
- Truy cập public: https://heystat.truyenthong.edu.vn (sau khi setup CF)

⚠️ **Lưu ý:**
- Đây là môi trường development
- Cần đặt JAMOVI_ACCESS_KEY cho production
- Review security settings trước khi public
- Setup monitoring và backup cho production

---

**Báo cáo tạo:** $(date)
**Nền tảng:** Mac Mini M2 (Apple Silicon)
**Vị trí:** /Users/mac/HeyStat
**Phiên bản:** Based on Jamovi 2.7.6
