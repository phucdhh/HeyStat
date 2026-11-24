# Tài liệu HeyStat

> **Cập nhật:** 2026-11-25  
> **Nền tảng hiện tại:** jamovi **2.7.30** + Classroom LMS  
> **Production:** Linux LXC (amd64) — https://heystat.pedu.vn

Tài liệu trong thư mục này được chia làm hai nhóm: **đang dùng** và **lịch sử**.
Các tài liệu lịch sử mô tả giai đoạn chạy trên Mac Mini M2 với domain
`heystat.truyenthong.edu.vn`; nội dung có thể không còn khớp với production.

## Đang dùng

| Tài liệu | Nội dung |
|---|---|
| [`../README.md`](../README.md) | Giới thiệu, quick start, kiến trúc và deployment hiện tại |
| [`../classroom/PLAN.md`](../classroom/PLAN.md) | Thiết kế và trạng thái các phase của LMS |
| [`FORK_NOTICE.md`](FORK_NOTICE.md) | Ghi chú fork, phiên bản gốc, license và attribution |
| [`UPSTREAM_SYNC_GUIDE.md`](UPSTREAM_SYNC_GUIDE.md) | Các file đã fork và cách merge jamovi upstream |
| [`CONFIGURATION.md`](CONFIGURATION.md) | Tóm tắt cấu hình (một phần là bối cảnh Mac cũ) |

## Lịch sử (Mac Mini M2 / `heystat.truyenthong.edu.vn`)

Các tài liệu dưới đây được giữ để tra cứu, **không phải hướng dẫn triển khai hiện tại**:

- [`README_MAC_DEPLOYMENT.md`](README_MAC_DEPLOYMENT.md)
- [`AUTOSTART_FIX.md`](AUTOSTART_FIX.md)
- [`LAUNCHDAEMONS_GUIDE.md`](LAUNCHDAEMONS_GUIDE.md)
- [`DEPLOYMENT_REPORT.md`](DEPLOYMENT_REPORT.md)
- [`DEPLOYMENT_SUCCESS.md`](DEPLOYMENT_SUCCESS.md)
- [`BRANDING_PLAN.md`](BRANDING_PLAN.md)
- [`BRANDING_SUMMARY.md`](BRANDING_SUMMARY.md)
- [`SETUP_NOTES.md`](SETUP_NOTES.md)
- [`SCRIPTS_GUIDE.md`](SCRIPTS_GUIDE.md)
- [`JAMOVI_MERGE_ANALYSIS.md`](JAMOVI_MERGE_ANALYSIS.md)

## Triển khai hiện tại (tóm tắt)

```
Cloudflare → Nginx :80
  ├── /                → trang chủ tĩnh
  ├── /help            → hướng dẫn đọc kết quả
  ├── /classroom/      → Vue SPA (LMS)
  ├── /api/            → FastAPI :8080
  └── /app, /<id>/...  → jamovi Tornado :42337
```

- HeyStat/jamovi: `docker compose --profile main up`
- Classroom LMS: `classroom/docker-compose.yml` (API, PostgreSQL, Redis, worker, scheduler)
- Build/deploy frontend + API: `./rebuild.sh`
- Đồng bộ lên LXC: `./sync2LXC.sh --apply` (hoặc `--build`)

Xem [`../README.md`](../README.md) để biết chi tiết.
