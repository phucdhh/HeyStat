# ✅ HeyStat Auto-Start Fix - December 15, 2025

## Vấn đề gặp phải

Sau khi restart Mac Mini, truy cập https://heystat.truyenthong.edu.vn gặp lỗi **502 Bad Gateway**.

### Nguyên nhân:
- Colima (Docker engine) không tự động khởi động sau khi Mac restart
- LaunchDaemon `com.colima.plist` không hoạt động vì:
  - Colima **không thể chạy dưới quyền root**
  - LaunchDaemon chạy dưới quyền system, gây xung đột

## Giải pháp

Thay vì tách riêng LaunchDaemon cho Colima và HeyStat, tạo **một LaunchDaemon duy nhất** quản lý toàn bộ stack:

### Cấu trúc mới:

```
com.heystat.complete (LaunchDaemon)
  ↓
start-heystat-complete.sh
  ↓
  1. Start Colima (nếu chưa chạy)
  2. Đợi Docker ready
  3. Start HeyStat container
```

## Files đã tạo/cập nhật

### 1. Script startup hoàn chỉnh
**File**: [scripts/start-heystat-complete.sh](scripts/start-heystat-complete.sh)

- Khởi động Colima với user `mac`
- Tự động detect đường dẫn Docker binary
- Đợi Docker sẵn sàng (tối đa 60 giây)
- Khởi động HeyStat container
- Log chi tiết vào: `/Users/mac/HeyStat/logs/heystat-complete-startup.log`

### 2. LaunchDaemon mới
**File**: [launch-daemons/com.heystat.complete.plist](launch-daemons/com.heystat.complete.plist)

- Chạy với user `mac` (tránh quyền root)
- `RunAtLoad=true`: Tự động chạy khi boot
- `KeepAlive=false`: Chạy một lần rồi dừng

### 3. Script kiểm tra trạng thái
**File**: [scripts/check-status.sh](scripts/check-status.sh) (đã cập nhật)

- Kiểm tra LaunchDaemon mới
- Hiển thị trạng thái Docker, Nginx, Cloudflare
- Test local và public access

## Cài đặt đã thực hiện

```bash
# 1. Xóa LaunchDaemons cũ
sudo launchctl unload /Library/LaunchDaemons/com.colima.plist 2>/dev/null
sudo launchctl unload /Library/LaunchDaemons/com.heystat.docker.plist 2>/dev/null
sudo rm -f /Library/LaunchDaemons/com.colima.plist
sudo rm -f /Library/LaunchDaemons/com.heystat.docker.plist

# 2. Cài đặt LaunchDaemon mới
sudo cp /Users/mac/HeyStat/launch-daemons/com.heystat.complete.plist /Library/LaunchDaemons/
sudo chown root:wheel /Library/LaunchDaemons/com.heystat.complete.plist
sudo chmod 644 /Library/LaunchDaemons/com.heystat.complete.plist
sudo launchctl load -w /Library/LaunchDaemons/com.heystat.complete.plist
```

## Kiểm tra trạng thái

```bash
# Kiểm tra nhanh
/Users/mac/HeyStat/scripts/check-status.sh

# Xem log startup
tail -f /Users/mac/HeyStat/logs/heystat-complete-startup.log

# Kiểm tra LaunchDaemon
sudo launchctl list | grep heystat
```

## Test auto-start

### Cách 1: Restart Mac
```bash
sudo shutdown -r now
```

### Cách 2: Test script thủ công
```bash
# Dừng Colima
colima stop

# Chạy script
/Users/mac/HeyStat/scripts/start-heystat-complete.sh

# Kiểm tra log
tail -20 /Users/mac/HeyStat/logs/heystat-complete-startup.log
```

## Quản lý LaunchDaemon

### Tạm dừng auto-start
```bash
sudo launchctl unload /Library/LaunchDaemons/com.heystat.complete.plist
```

### Bật lại auto-start
```bash
sudo launchctl load -w /Library/LaunchDaemons/com.heystat.complete.plist
```

### Xem log LaunchDaemon
```bash
tail -f /Users/mac/HeyStat/logs/launchdaemon-complete.log
```

## Trạng thái hiện tại

✅ **Đã fix thành công**:
- LaunchDaemon: `com.heystat.complete` loaded
- Docker/Colima: Running
- HeyStat container: Up
- Public access: https://heystat.truyenthong.edu.vn ✓

⚠️ **Cần test**: Restart Mac Mini để xác nhận auto-start hoạt động

## Lưu ý

1. **Colima phải chạy với user thường** (`mac`), không thể chạy dưới root
2. Script tự động detect Docker binary path (tương thích cả Homebrew và Docker Desktop)
3. Timeout 60 giây để Docker sẵn sàng - có thể tăng nếu Mac khởi động chậm
4. LaunchDaemon chỉ chạy một lần khi boot, không restart tự động nếu service die

## Troubleshooting

### Nếu sau restart HeyStat không chạy:

1. Kiểm tra LaunchDaemon status:
```bash
sudo launchctl list | grep heystat
```

2. Xem log:
```bash
tail -50 /Users/mac/HeyStat/logs/heystat-complete-startup.log
```

3. Kiểm tra Colima:
```bash
colima status
```

4. Khởi động thủ công:
```bash
/Users/mac/HeyStat/scripts/start-heystat-complete.sh
```

### Nếu Nginx không chạy:

```bash
# Kiểm tra process
ps aux | grep nginx

# Khởi động lại
sudo pkill -9 nginx
nginx
```

## Next Steps

- [ ] Test auto-start bằng cách restart Mac Mini
- [ ] Monitor logs trong 24-48 giờ đầu
- [ ] Xem xét thêm health check script chạy định kỳ
