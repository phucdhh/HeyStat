# HeyStat Management Scripts

Tập hợp scripts quản lý HeyStat ở thư mục gốc dự án.

## Scripts Chính

### 🚀 start.sh
Khởi động toàn bộ HeyStat stack (Colima → Docker → Container → Nginx)

```bash
./start.sh
```

**Các bước thực hiện:**
1. Kiểm tra và start Colima (nếu chưa chạy)
2. Đợi Docker sẵn sàng
3. Start HeyStat container
4. Kiểm tra/start Nginx

**Log:** `logs/heystat-startup.log`

---

### 🛑 stop.sh
Dừng HeyStat services

```bash
# Dừng container + nginx (giữ Colima chạy)
./stop.sh

# Dừng tất cả bao gồm Colima
./stop.sh --full
```

**Các bước thực hiện:**
1. Stop HeyStat container
2. Stop Nginx
3. (Optional) Stop Colima nếu dùng `--full`

**Log:** `logs/heystat-shutdown.log`

---

### 🔄 restart.sh
Khởi động lại HeyStat

```bash
# Quick restart (chỉ container + nginx)
./restart.sh

# Full restart (bao gồm Colima)
./restart.sh --full
```

**Quick restart:**
- Restart Docker container
- Reload Nginx config
- Nhanh (< 5 giây)

**Full restart:**
- Stop everything → Start from scratch
- Chậm hơn (~20-30 giây)
- Dùng khi có vấn đề nghiêm trọng

---

### 📊 status.sh
Kiểm tra trạng thái toàn bộ hệ thống

```bash
./status.sh
```

**Kiểm tra:**
1. ✓ Docker/Colima status
2. ✓ HeyStat container (status, resources)
3. ✓ Nginx (process, port 8082)
4. ✓ Auto-start LaunchDaemons
5. ✓ Network access (local + public)
6. ✓ Recent activity & errors

**Exit codes:**
- `0` = All OK
- `>0` = Number of issues detected

---

## Ví dụ Sử dụng

### Khởi động lần đầu
```bash
./start.sh
./status.sh
```

### Restart khi có lỗi
```bash
# Thử quick restart trước
./restart.sh

# Nếu vẫn lỗi, full restart
./restart.sh --full

# Kiểm tra kết quả
./status.sh
```

### Tắt máy / bảo trì
```bash
# Tắt tất cả
./stop.sh --full

# Hoặc chỉ tắt HeyStat (giữ Colima cho dự án khác)
./stop.sh
```

### Sau khi Mac restart
```bash
# LaunchDaemon sẽ tự động start
# Hoặc start thủ công:
./start.sh
./status.sh
```

---

## Troubleshooting

### Container không start
```bash
# Check logs
docker logs heystat

# Full restart
./stop.sh --full
./start.sh
```

### Nginx lỗi
```bash
# Check nginx logs
tail -f /opt/homebrew/var/log/nginx/heystat_error.log

# Restart nginx
sudo pkill nginx
/opt/homebrew/bin/nginx
```

### Colima VM corrupt
```bash
# Delete và recreate
colima delete -f
./start.sh
```

### Permission denied
```bash
# Fix log permissions
sudo chown -R $USER logs/
sudo chmod -R 755 logs/

# Fix nginx logs
sudo chown -R $USER /opt/homebrew/var/log/nginx/
```

---

## Auto-Start Configuration

HeyStat tự động khởi động qua LaunchDaemon:

**File:** `launch-daemons/com.heystat.complete.plist`

**Script:** `scripts/start-heystat-complete.sh`

**Check status:**
```bash
sudo launchctl list | grep heystat
```

**Reload:**
```bash
sudo launchctl unload /Library/LaunchDaemons/com.heystat.complete.plist
sudo launchctl load /Library/LaunchDaemons/com.heystat.complete.plist
```

---

## Files & Directories

```
/Users/mac/HeyStat/
├── start.sh              # Start script
├── stop.sh               # Stop script  
├── restart.sh            # Restart script
├── status.sh             # Status check
├── docker-compose.yaml   # Container config
├── heystat-nginx-mac.conf # Nginx config
├── logs/                 # Log files
│   ├── heystat-startup.log
│   ├── heystat-shutdown.log
│   └── heystat-complete-startup.log
├── scripts/              # Helper scripts
│   ├── start-heystat-complete.sh  # LaunchDaemon script
│   ├── setup-colima-agent.sh
│   └── setup-launchagent.sh
└── launch-daemons/       # LaunchDaemon configs
    └── com.heystat.complete.plist
```

---

## Environment

- **Platform:** Mac Mini M2 (Apple Silicon)
- **Docker:** Colima 0.9.1
- **Nginx:** 1.29.x (Homebrew)
- **Container:** HeyStat v2.7.14
- **Ports:**
  - 42337-42339: HeyStat container
  - 8082: Nginx local
  - 443: Public via Cloudflare Tunnel

---

## Quick Reference

| Task | Command |
|------|---------|
| Start | `./start.sh` |
| Stop | `./stop.sh` |
| Stop all | `./stop.sh --full` |
| Restart | `./restart.sh` |
| Full restart | `./restart.sh --full` |
| Check status | `./status.sh` |
| View logs | `tail -f logs/heystat-startup.log` |
| Container logs | `docker logs -f heystat` |
| Nginx logs | `tail -f /opt/homebrew/var/log/nginx/heystat_error.log` |

---

**URL:**
- Local: http://localhost:8082
- Public: https://heystat.truyenthong.edu.vn
