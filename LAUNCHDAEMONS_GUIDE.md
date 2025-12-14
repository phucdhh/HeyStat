# HeyStat LaunchDaemons - Auto-Start Configuration

## Overview

HeyStat đã được cấu hình để tự động khởi động khi Mac Mini restart thông qua macOS LaunchDaemons.

## LaunchDaemons đã cài đặt

### 1. Colima (Docker Engine)
- **File:** `/Library/LaunchDaemons/com.colima.plist`
- **Mô tả:** Khởi động Colima để cung cấp Docker runtime
- **Chạy trước:** HeyStat (dependency)

### 2. HeyStat Container
- **File:** `/Library/LaunchDaemons/com.heystat.docker.plist`
- **Mô tả:** Khởi động HeyStat container thông qua script
- **Script:** `/Users/mac/HeyStat/scripts/start-heystat.sh`
- **Chạy sau:** Colima (đợi Docker ready)

### 3. Cloudflare Tunnel
- **File:** `/Library/LaunchDaemons/com.cloudflare.cloudflared.heystat.plist`
- **Mô tả:** Cloudflare Tunnel cho public access
- **Độc lập:** Không phụ thuộc vào HeyStat

## Startup Sequence

```
Mac Mini Boot
    ↓
[1] Colima LaunchDaemon starts
    ↓ (wait for Docker ready)
[2] HeyStat Script starts
    - Waits up to 60s for Docker
    - Starts HeyStat container
    ↓
[3] Cloudflare Tunnel (independent)
    ↓
✅ All services running
```

## Management Commands

### Kiểm tra trạng thái

```bash
# Liệt kê tất cả LaunchDaemons liên quan
sudo launchctl list | grep -E "(colima|heystat|cloudflare)"

# Kiểm tra HeyStat container
docker ps --filter "name=heystat"

# Xem logs startup
tail -f /Users/mac/HeyStat/logs/heystat-startup.log
tail -f /Users/mac/HeyStat/logs/colima.log
```

### Start/Stop Services

```bash
# Stop HeyStat
sudo launchctl unload /Library/LaunchDaemons/com.heystat.docker.plist

# Start HeyStat
sudo launchctl load -w /Library/LaunchDaemons/com.heystat.docker.plist

# Stop Colima
sudo launchctl unload /Library/LaunchDaemons/com.colima.plist
colima stop

# Start Colima
sudo launchctl load -w /Library/LaunchDaemons/com.colima.plist
```

### Restart Services

```bash
# Restart HeyStat only
sudo launchctl unload /Library/LaunchDaemons/com.heystat.docker.plist
sleep 2
sudo launchctl load -w /Library/LaunchDaemons/com.heystat.docker.plist

# Restart everything (Colima + HeyStat)
sudo launchctl unload /Library/LaunchDaemons/com.heystat.docker.plist
sudo launchctl unload /Library/LaunchDaemons/com.colima.plist
colima stop
sleep 5
sudo launchctl load -w /Library/LaunchDaemons/com.colima.plist
sleep 10
sudo launchctl load -w /Library/LaunchDaemons/com.heystat.docker.plist
```

### Disable Auto-Start

```bash
# Disable HeyStat auto-start
sudo launchctl unload -w /Library/LaunchDaemons/com.heystat.docker.plist

# Disable Colima auto-start
sudo launchctl unload -w /Library/LaunchDaemons/com.colima.plist

# Disable Cloudflare Tunnel auto-start
sudo launchctl unload -w /Library/LaunchDaemons/com.cloudflare.cloudflared.heystat.plist
```

### Re-enable Auto-Start

```bash
# Enable HeyStat auto-start
sudo launchctl load -w /Library/LaunchDaemons/com.heystat.docker.plist

# Enable Colima auto-start
sudo launchctl load -w /Library/LaunchDaemons/com.colima.plist

# Enable Cloudflare Tunnel auto-start
sudo launchctl load -w /Library/LaunchDaemons/com.cloudflare.cloudflared.heystat.plist
```

## Logs

### Log Locations

```bash
# HeyStat startup log
/Users/mac/HeyStat/logs/heystat-startup.log

# Colima logs
/Users/mac/HeyStat/logs/colima.log
/Users/mac/HeyStat/logs/colima-error.log

# HeyStat Docker logs
/Users/mac/HeyStat/logs/heystat-docker.log
/Users/mac/HeyStat/logs/heystat-docker-error.log

# Cloudflare Tunnel logs
/Users/mac/HeyStat/logs/cloudflared-heystat.log
/Users/mac/HeyStat/logs/cloudflared-heystat-error.log
```

### View Logs

```bash
# Real-time HeyStat startup
tail -f /Users/mac/HeyStat/logs/heystat-startup.log

# Real-time Docker logs
docker logs -f heystat

# Real-time Cloudflare logs
tail -f /Users/mac/HeyStat/logs/cloudflared-heystat.log

# View all logs at once
tail -f /Users/mac/HeyStat/logs/*.log
```

## Testing Auto-Start

### Method 1: Restart Services

```bash
# 1. Stop all services
sudo launchctl unload /Library/LaunchDaemons/com.heystat.docker.plist
sudo launchctl unload /Library/LaunchDaemons/com.colima.plist
docker compose down
colima stop

# 2. Wait a moment
sleep 5

# 3. Load LaunchDaemons (simulates boot)
sudo launchctl load -w /Library/LaunchDaemons/com.colima.plist
sleep 10  # Wait for Colima
sudo launchctl load -w /Library/LaunchDaemons/com.heystat.docker.plist

# 4. Check status (wait 15 seconds)
sleep 15
docker ps --filter "name=heystat"
curl -I http://localhost:8082
```

### Method 2: Full System Restart (Recommended)

```bash
# Restart Mac Mini
sudo reboot

# After boot, SSH back in and check:
docker ps --filter "name=heystat"
curl -I http://localhost:8082
curl -I https://heystat.truyenthong.edu.vn
```

## Troubleshooting

### HeyStat không khởi động sau restart

1. **Kiểm tra Colima:**
   ```bash
   colima status
   docker ps
   ```

2. **Xem logs:**
   ```bash
   tail -50 /Users/mac/HeyStat/logs/heystat-startup.log
   tail -50 /Users/mac/HeyStat/logs/colima-error.log
   ```

3. **Kiểm tra LaunchDaemon:**
   ```bash
   sudo launchctl list | grep heystat
   sudo launchctl list | grep colima
   ```

4. **Reload manually:**
   ```bash
   sudo launchctl unload /Library/LaunchDaemons/com.colima.plist
   sudo launchctl load -w /Library/LaunchDaemons/com.colima.plist
   sleep 10
   sudo launchctl unload /Library/LaunchDaemons/com.heystat.docker.plist
   sudo launchctl load -w /Library/LaunchDaemons/com.heystat.docker.plist
   ```

### Colima không khởi động

```bash
# Check if Colima is installed
which colima

# Try starting manually
colima start

# Check logs
tail -50 /Users/mac/HeyStat/logs/colima-error.log

# Reset Colima
colima delete
colima start --arch aarch64 --cpu 4 --memory 8
```

### Container khởi động nhưng không accessible

1. **Kiểm tra Nginx:**
   ```bash
   sudo nginx -t
   lsof -iTCP:8082 -sTCP:LISTEN
   ```

2. **Restart Nginx:**
   ```bash
   sudo nginx -s reload
   ```

3. **Kiểm tra Cloudflare Tunnel:**
   ```bash
   ./cloudflare-setup.sh status
   ```

## File Locations

### LaunchDaemon Files

```
/Library/LaunchDaemons/
├── com.colima.plist                              # Colima auto-start
├── com.heystat.docker.plist                      # HeyStat auto-start
└── com.cloudflare.cloudflared.heystat.plist      # Cloudflare Tunnel
```

### Source Files

```
/Users/mac/HeyStat/
├── launch-daemons/
│   ├── com.colima.plist                    # Source
│   └── com.heystat.docker.plist            # Source
└── scripts/
    └── start-heystat.sh                    # Startup script
```

## Updating LaunchDaemons

Nếu bạn sửa file plist:

```bash
# 1. Edit source file
vi /Users/mac/HeyStat/launch-daemons/com.heystat.docker.plist

# 2. Unload current daemon
sudo launchctl unload /Library/LaunchDaemons/com.heystat.docker.plist

# 3. Copy updated file
sudo cp /Users/mac/HeyStat/launch-daemons/com.heystat.docker.plist /Library/LaunchDaemons/

# 4. Set permissions
sudo chown root:wheel /Library/LaunchDaemons/com.heystat.docker.plist
sudo chmod 644 /Library/LaunchDaemons/com.heystat.docker.plist

# 5. Reload
sudo launchctl load -w /Library/LaunchDaemons/com.heystat.docker.plist
```

## Best Practices

1. **Always check logs** after restart:
   ```bash
   tail -100 /Users/mac/HeyStat/logs/heystat-startup.log
   ```

2. **Wait for services** to fully start (30-60 seconds after boot)

3. **Monitor resource usage:**
   ```bash
   docker stats heystat
   ```

4. **Regular backups** of configuration:
   ```bash
   tar -czf ~/heystat-launchdaemons-$(date +%Y%m%d).tar.gz \
     /Library/LaunchDaemons/com.*.plist \
     /Users/mac/HeyStat/launch-daemons/ \
     /Users/mac/HeyStat/scripts/
   ```

5. **Test after updates:**
   - After macOS updates
   - After Homebrew updates
   - After Docker/Colima updates

## Security Notes

- LaunchDaemons chạy với quyền root
- Scripts được gọi từ LaunchDaemons cần có permissions đúng
- Logs có thể chứa thông tin nhạy cảm, hạn chế truy cập

## Status Check Script

Quick check script:

```bash
#!/bin/bash
echo "=== HeyStat Auto-Start Status ==="
echo ""
echo "LaunchDaemons:"
sudo launchctl list | grep -E "(colima|heystat|cloudflare)" || echo "  None loaded"
echo ""
echo "Docker/Colima:"
docker ps --filter "name=heystat" --format "  {{.Names}}: {{.Status}}" || echo "  Not running"
echo ""
echo "Nginx:"
lsof -iTCP:8082 -sTCP:LISTEN | grep nginx && echo "  ✓ Listening" || echo "  ✗ Not listening"
echo ""
echo "Public Access:"
curl -s -I https://heystat.truyenthong.edu.vn | head -1 || echo "  ✗ Not accessible"
echo ""
```

Save as `/Users/mac/HeyStat/scripts/check-status.sh` and run:
```bash
chmod +x /Users/mac/HeyStat/scripts/check-status.sh
./scripts/check-status.sh
```

## Summary

✅ **Configured:**
- Colima auto-starts at boot
- HeyStat waits for Docker and auto-starts
- Cloudflare Tunnel auto-starts independently
- All logs captured for debugging

✅ **Tested:**
- Services start in correct order
- HeyStat accessible after boot
- Logs show successful startup

✅ **Management:**
- Easy start/stop/restart commands
- Comprehensive logging
- Troubleshooting guide included

---

**Last Updated:** December 15, 2025
**Status:** ✅ Production Ready
