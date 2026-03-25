# HeyStat – Classroom LMS Plan

> **Phiên bản:** 1.1.0  
> **Cập nhật:** 2026-03  
> **Nền tảng:** HeyStat (fork of Jamovi 2.7) – Web-based Statistical Analysis  
> **Mục tiêu:** Bổ sung hệ thống lớp học (LMS) vào HeyStat để hỗ trợ giảng dạy thống kê trực tuyến

> **Ghi chú kiến trúc quan trọng (đã rà soát codebase thực tế):**  
> - HeyStat server là **Tornado + Python** (không phải FastAPI). LMS API sẽ là service **FastAPI riêng** chạy cạnh, không sửa Tornado.  
> - Frontend HeyStat dùng **Vue 3 + TypeScript + Vite** (không phải React). LMS frontend dùng Vue 3 để đồng nhất stack.  
> - Jamovi giao tiếp qua **WebSocket + Protobuf** (nanomsg). LMS không can thiệp vào protocol này.  
> - `session.py` của Jamovi đã có khái niệm `Session` (per-path, per-id). Mỗi user classroom sẽ sử dụng một session path riêng biệt thay vì chạy nhiều instance.  
> - File storage hiện tại dùng **local filesystem** (`./Documents` mount vào container). MinIO có thể dùng cho phase sau; phase đầu dùng local volume.  
> - `JAMOVI_ALLOW_ARBITRARY_CODE: 'false'` — bắt buộc giữ nguyên, không bao giờ bật R/Python tùy ý.  
> - Toàn bộ code LMS nằm trong `classroom/` để không ảnh hưởng đến upstream Jamovi.

---

## Mục lục

1. [Tổng quan hệ thống](#1-tổng-quan-hệ-thống)
2. [Kiến trúc hệ thống](#2-kiến-trúc-hệ-thống)
3. [Vai trò & Quyền hạn (RBAC)](#3-vai-trò--quyền-hạn-rbac)
4. [Data Model](#4-data-model)
5. [API Endpoints](#5-api-endpoints)
6. [Luồng nghiệp vụ chính (User Flows)](#6-luồng-nghiệp-vụ-chính-user-flows)
7. [Đặc tả tính năng chi tiết](#7-đặc-tả-tính-năng-chi-tiết)
8. [Bảo mật & Xác thực](#8-bảo-mật--xác-thực)
9. [Quản lý Jamovi Session (Multi-user)](#9-quản-lý-jamovi-session-multi-user)
10. [Thông báo (Notification)](#10-thông-báo-notification)
11. [Tech Stack gợi ý](#11-tech-stack-gợi-ý)
12. [Giai đoạn phát triển](#12-giai-đoạn-phát-triển)
13. [Monorepo với classroom/ tách biệt rõ ràng](#13-monorepo-với-classroom-tách-biệt-rõ-ràng)
14. [My Files – Lưu trữ cá nhân](#14-my-files--lưu-trữ-cá-nhân)
15. [Chia sẻ file phân tích](#15-chia-sẻ-file-phân-tích)
16. [Cộng tác biên tập (Collaboration)](#16-cộng-tác-biên-tập-collaboration)
17. [Tài liệu bài giảng (Lesson)](#17-tài-liệu-bài-giảng-lesson)
18. [Quiz lý thuyết (MCQ + Auto-grade)](#18-quiz-lý-thuyết-mcq--auto-grade)

---

## 1. Tổng quan hệ thống

HeyStat Classroom bổ sung một lớp LMS lên nền tảng phân tích thống kê HeyStat, cho phép giảng viên tạo lớp học, giao bài tập phân tích dữ liệu, và theo dõi / chấm điểm bài làm của sinh viên — tất cả diễn ra trong cùng một giao diện web.

### Nguyên tắc thiết kế

- **Stateless API:** Backend RESTful + JWT, tách biệt hoàn toàn với frontend.
- **Multi-tenancy nhẹ:** Mỗi lớp học là một không gian độc lập; dữ liệu sinh viên không lộ chéo.
- **Session isolation:** Mỗi sinh viên có một HeyStat session riêng, sandbox hoá hoàn toàn.
- **Role-based access control (RBAC):** Mọi endpoint đều kiểm tra quyền trước khi xử lý.
- **Deadline enforcement phía server:** Client không được tin tưởng để kiểm soát thời hạn.
- **Assignment type governs permissions:** `exam` tắt toàn bộ chia sẻ và cộng tác; `group` bật cộng tác trong nhóm; `homework` cho phép chia sẻ tuỳ chọn.
- **My Files:** Mọi User đã đăng nhập có không gian lưu trữ `.omv` cá nhân, tách biệt khỏi classroom.

---

## 2. Kiến trúc hệ thống

```
┌──────────────────────────────────────────────────────────┐
│                        Browser                           │
│          HeyStat UI (Vue 3 + TypeScript + Vite)          │
│   ┌─────────────┐   ┌──────────────┐   ┌─────────────┐   │
│   │  Auth Pages │   │  LMS Module  │   │  Analysis   │   │
│   │ (login/reg) │   │(class/assign)│   │ (Jamovi UI) │   │
│   └─────────────┘   └──────────────┘   └─────────────┘   │
│        classroom/frontend/              client/ (giữ nguyên)
└────────────────────────┬─────────────────────────────────┘
                         │ HTTPS
              ┌──────────▼──────────┐
              │    Nginx Reverse    │
              │       Proxy (80)    │
              └──┬──────────────┬───┘
       /api/*    │              │  /*
    ┌────────────▼───┐    ┌─────▼───────────────────┐
    │  LMS API       │    │   HeyStat (Jamovi)      │
    │  (FastAPI)     │    │   Tornado, port 42337   │
    │  Port: 8080    │    │   WebSocket + Protobuf  │
    │  classroom/api │    │   Session per user path │
    └────────┬───────┘    └─────────────────────────┘
             │
    ┌────────▼──────────────────────────┐
    │          Database Layer           │
    │  PostgreSQL 15+  (relational)     │
    │  Redis 7+        (cache, rate)    │
    │  Local Volume    (file storage,   │
    │   phase 1; MinIO optional later)  │
    └───────────────────────────────────┘
```

### 2.1 Nguyên tắc tích hợp với HeyStat/Jamovi hiện có

- **Không sửa Tornado server:** LMS API là service FastAPI riêng biệt, Nginx phân luồng theo path.
- **Không sửa protobuf/WebSocket:** Giao tiếp Jamovi vẫn giữ nguyên hoàn toàn.
- **Session isolation qua path:** Jamovi's `Session` class tạo instance dựa trên `data_path + session_id`. Mỗi user classroom được cấp một `session_id` riêng → files/data độc lập trên filesystem.
- **LMS chỉ embed Jamovi UI trong iframe** với session token riêng. LMS không intercept WebSocket.

---

## 3. Vai trò & Quyền hạn (RBAC)

Hệ thống có 5 vai trò, được lưu trong bảng `roles` và gán cho user qua `user_roles`.

### 3.1 Bảng quyền tổng hợp

| Quyền | Guest | User | Student | Teacher | Admin |
|---|:---:|:---:|:---:|:---:|:---:|
| Truy cập giao diện HeyStat | ✅ | ✅ | ✅ | ✅ | ✅ |
| Nhập dữ liệu thủ công | ✅ | ✅ | ✅ | ✅ | ✅ |
| Chạy phân tích thống kê | ❌ | ✅ | ✅ | ✅ | ✅ |
| Lưu / tải kết quả phân tích | ❌ | ✅ | ✅ | ✅ | ✅ |
| **My Files** – lưu .omv cá nhân | ❌ | ✅ | ✅ | ✅ | ✅ |
| **Chia sẻ** file cá nhân (link) | ❌ | ✅ | ✅* | ✅ | ✅ |
| Tham gia lớp học (enroll) | ❌ | ✅ | ✅ | — | — |
| Làm & nộp bài tập | ❌ | ❌ | ✅ | — | — |
| **Cộng tác** (group assignment) | ❌ | ❌ | ✅* | — | — |
| Xem điểm & nhận xét của mình | ❌ | ❌ | ✅ | — | — |
| Tạo & quản lý lớp học | ❌ | ❌ | ❌ | ✅ | ✅ |
| Upload file dữ liệu cho lớp | ❌ | ❌ | ❌ | ✅ | ✅ |
| Tạo & quản lý bài giảng (Lesson) | ❌ | ❌ | ❌ | ✅ | ✅ |
| Tạo & quản lý Quiz MCQ | ❌ | ❌ | ❌ | ✅ | ✅ |
| Làm quiz & xem kết quả | ❌ | ❌ | ✅ | — | — |
| Giao bài tập (chọn loại) | ❌ | ❌ | ❌ | ✅ | ✅ |
| Xem & chấm bài sinh viên | ❌ | ❌ | ❌ | ✅ | ✅ |
| **Quan sát** live session student | ❌ | ❌ | ❌ | ✅ | ✅ |
| Export điểm | ❌ | ❌ | ❌ | ✅ | ✅ |
| Quản lý toàn bộ user | ❌ | ❌ | ❌ | ❌ | ✅ |
| Quản lý toàn bộ lớp học | ❌ | ❌ | ❌ | ❌ | ✅ |
| Cấu hình hệ thống | ❌ | ❌ | ❌ | ❌ | ✅ |

*✅\* = chỉ khi `assignment_type ≠ 'exam'`

### 3.2 Định nghĩa vai trò

**Guest**
- Người dùng chưa đăng nhập.
- Có thể nhập dữ liệu thủ công để xem giao diện, nhưng không thể chạy phân tích, không lưu được gì.
- Không thể tham gia lớp học.

**User**
- Đã đăng ký tài khoản.
- Sử dụng HeyStat đầy đủ: phân tích, lưu, xuất kết quả.
- Có thể nhập Enrollment Key để gia nhập một lớp học → tự động nâng lên vai trò **Student** trong lớp đó.
- Một User có thể đồng thời là Student của nhiều lớp khác nhau.

**Student** *(scoped role – chỉ có hiệu lực trong phạm vi một lớp cụ thể)*
- Phát sinh từ việc User nhập đúng Enrollment Key.
- Có quyền truy cập dữ liệu và bài tập của lớp đó.
- Nộp bài, xem lại bài đã nộp, xem điểm.
- Không thể xem bài làm của Student khác trong cùng lớp.

**Teacher**
- Được Admin cấp role.
- Tạo và quản lý lớp học.
- Không thể chỉnh sửa dữ liệu của Student.
- Một Teacher có thể sở hữu nhiều lớp học.

**Admin**
- Quản lý toàn hệ thống.
- Cấp / thu hồi role Teacher.
- Xem và can thiệp vào bất kỳ lớp học nào.
- Truy cập dashboard thống kê hệ thống.

---

## 4. Data Model

### 4.1 Sơ đồ quan hệ (ERD rút gọn)

```
users ──< enrollments >── classes ──< assignments
  │                          │              │
  │                          │              ├──< submissions
  │                          │              └──< assignment_groups >──< users
  │                          ├──< class_files
  │                          ├──< lessons ──< lesson_resources
  │                          └──< quizzes ──< quiz_questions
  │                                               └──< quiz_attempts ──< question_answers
  ├──< user_roles
  │      └── roles
  ├──< user_files ──< file_shares
  └──< notifications
```

### 4.2 Định nghĩa bảng

#### `users`
```sql
CREATE TABLE users (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email         VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255),                    -- NULL nếu dùng OAuth
    full_name     VARCHAR(255) NOT NULL,
    avatar_url    VARCHAR(500),
    provider      VARCHAR(50) DEFAULT 'local',     -- 'local' | 'google' | 'microsoft'
    provider_id   VARCHAR(255),                    -- OAuth external ID
    is_active     BOOLEAN DEFAULT TRUE,
    is_verified   BOOLEAN DEFAULT FALSE,           -- xác thực email
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    updated_at    TIMESTAMPTZ DEFAULT NOW()
);
```

#### `roles`
```sql
CREATE TABLE roles (
    id   SMALLINT PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL   -- 'admin' | 'teacher' | 'user'
    -- NOTE: 'student' là scoped role trong enrollments, không lưu ở đây
);
```

#### `user_roles`
```sql
CREATE TABLE user_roles (
    user_id    UUID REFERENCES users(id) ON DELETE CASCADE,
    role_id    SMALLINT REFERENCES roles(id),
    granted_by UUID REFERENCES users(id),
    granted_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (user_id, role_id)
);
```

#### `classes`
```sql
CREATE TABLE classes (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    teacher_id       UUID REFERENCES users(id) ON DELETE RESTRICT,
    title            VARCHAR(255) NOT NULL,
    description      TEXT,
    enrollment_key   VARCHAR(100) NOT NULL,         -- bcrypt hash
    max_students     INT DEFAULT 200,
    starts_at        TIMESTAMPTZ NOT NULL,
    ends_at          TIMESTAMPTZ NOT NULL,
    status           VARCHAR(20) DEFAULT 'draft',   -- 'draft'|'active'|'closed'|'archived'
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    updated_at       TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT chk_dates CHECK (ends_at > starts_at)
);
```

#### `enrollments`
```sql
CREATE TABLE enrollments (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    class_id     UUID REFERENCES classes(id) ON DELETE CASCADE,
    user_id      UUID REFERENCES users(id) ON DELETE CASCADE,
    enrolled_at  TIMESTAMPTZ DEFAULT NOW(),
    status       VARCHAR(20) DEFAULT 'active',      -- 'active' | 'dropped'
    UNIQUE (class_id, user_id)
);
```

#### `class_files`
```sql
CREATE TABLE class_files (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    class_id     UUID REFERENCES classes(id) ON DELETE CASCADE,
    uploaded_by  UUID REFERENCES users(id),
    file_name    VARCHAR(255) NOT NULL,
    file_path    VARCHAR(500) NOT NULL,             -- đường dẫn tương đối trong volume
    file_size    BIGINT,
    mime_type    VARCHAR(100),
    created_at   TIMESTAMPTZ DEFAULT NOW()
);
```

#### `assignments`
```sql
CREATE TABLE assignments (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    class_id        UUID REFERENCES classes(id) ON DELETE CASCADE,
    title           VARCHAR(255) NOT NULL,
    description     TEXT NOT NULL,                   -- yêu cầu / đề bài (Markdown)
    file_id         UUID REFERENCES class_files(id), -- file dữ liệu đính kèm (tuỳ chọn)
    assignment_type VARCHAR(20) DEFAULT 'homework',  -- 'homework' | 'exam' | 'group'
    max_score       NUMERIC(5,2) DEFAULT 10.00,
    deadline        TIMESTAMPTZ NOT NULL,
    allow_resubmit  BOOLEAN DEFAULT TRUE,            -- tự động FALSE với exam
    group_size      SMALLINT DEFAULT 1,              -- 1 = cá nhân; >1 = nhóm
    allow_sharing   BOOLEAN DEFAULT FALSE,           -- FALSE với exam; Teacher chọn với homework
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT chk_exam_no_sharing CHECK (
        NOT (assignment_type = 'exam' AND allow_sharing = TRUE)
    ),
    CONSTRAINT chk_exam_no_resubmit CHECK (
        NOT (assignment_type = 'exam' AND allow_resubmit = TRUE)
    )
);
```

#### `assignment_groups`
```sql
CREATE TABLE assignment_groups (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    assignment_id UUID REFERENCES assignments(id) ON DELETE CASCADE,
    group_name    VARCHAR(100),
    session_path  VARCHAR(500),   -- đường dẫn session dùng chung cho cả nhóm
    leader_id     UUID REFERENCES users(id),  -- người có quyền edit (có thể chuyển nhượng)
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE assignment_group_members (
    group_id   UUID REFERENCES assignment_groups(id) ON DELETE CASCADE,
    user_id    UUID REFERENCES users(id) ON DELETE CASCADE,
    joined_at  TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (group_id, user_id)
);
```

#### `submissions`
```sql
CREATE TABLE submissions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    assignment_id   UUID REFERENCES assignments(id) ON DELETE CASCADE,
    student_id      UUID REFERENCES users(id) ON DELETE CASCADE,
    session_snapshot JSONB,                          -- HTML output từ Jamovi (tuỳ chọn)
    file_path       VARCHAR(500),                   -- đường dẫn file .omv trong volume
    submitted_at    TIMESTAMPTZ DEFAULT NOW(),
    is_final        BOOLEAN DEFAULT FALSE,           -- TRUE = bài nộp cuối
    score           NUMERIC(5,2),                   -- NULL = chưa chấm
    feedback        TEXT,
    graded_by       UUID REFERENCES users(id),
    graded_at       TIMESTAMPTZ
);
-- Một student có thể nộp nhiều lần; chỉ 1 bản is_final = TRUE tại một thời điểm
```

#### `notifications`
```sql
CREATE TABLE notifications (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      UUID REFERENCES users(id) ON DELETE CASCADE,
    type         VARCHAR(50) NOT NULL,               -- xem mục 10
    title        VARCHAR(255) NOT NULL,
    body         TEXT,
    metadata     JSONB,                              -- { class_id, assignment_id, ... }
    is_read      BOOLEAN DEFAULT FALSE,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);
```

#### `system_settings`
```sql
CREATE TABLE system_settings (
    key   VARCHAR(100) PRIMARY KEY,
    value TEXT,
    updated_by UUID REFERENCES users(id),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
-- Ví dụ keys: 'smtp_host', 'max_file_size_mb', 'allowed_file_types', 'maintenance_mode'
```

#### `lessons`
```sql
CREATE TABLE lessons (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    class_id     UUID REFERENCES classes(id) ON DELETE CASCADE,
    title        VARCHAR(255) NOT NULL,
    content      TEXT,                              -- nội dung Markdown (text, heading, v.v.)
    sort_order   SMALLINT DEFAULT 0,               -- thứ tự hiển thị trong lớp
    is_published BOOLEAN DEFAULT FALSE,
    created_at   TIMESTAMPTZ DEFAULT NOW(),
    updated_at   TIMESTAMPTZ DEFAULT NOW()
);
```

#### `lesson_resources`
```sql
CREATE TABLE lesson_resources (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lesson_id    UUID REFERENCES lessons(id) ON DELETE CASCADE,
    resource_type VARCHAR(20) NOT NULL,             -- 'video' | 'pdf' | 'link' | 'data_file'
    title        VARCHAR(255),
    url          VARCHAR(1000),                    -- URL bên ngoài (YouTube, Drive, v.v.)
    file_id      UUID REFERENCES class_files(id),  -- hoặc file dữ liệu đã upload
    sort_order   SMALLINT DEFAULT 0,
    created_at   TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT chk_resource_source CHECK (
        (url IS NOT NULL AND file_id IS NULL)
        OR (url IS NULL AND file_id IS NOT NULL)
    )
);
-- KHÔNG lưu video/PDF trên server; chỉ lưu URL embed
-- Các URL được whitelist (YouTube, Google Drive, Loom, v.v.) trước khi lưu
```

#### `quizzes`
```sql
CREATE TABLE quizzes (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    class_id        UUID REFERENCES classes(id) ON DELETE CASCADE,
    lesson_id       UUID REFERENCES lessons(id),   -- NULL = quiz độc lập (không gắn bài giảng)
    title           VARCHAR(255) NOT NULL,
    description     TEXT,
    time_limit_min  SMALLINT,                      -- NULL = không giới hạn thời gian
    max_attempts    SMALLINT DEFAULT 1,            -- số lần làm tối đa; NULL = không giới hạn
    shuffle_questions BOOLEAN DEFAULT FALSE,
    shuffle_choices   BOOLEAN DEFAULT FALSE,
    show_result_after VARCHAR(20) DEFAULT 'submit', -- 'submit' | 'deadline' | 'never'
    deadline        TIMESTAMPTZ,
    is_published    BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);
```

#### `quiz_questions`
```sql
CREATE TABLE quiz_questions (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    quiz_id       UUID REFERENCES quizzes(id) ON DELETE CASCADE,
    question_text TEXT NOT NULL,                   -- Markdown (hỗ trợ ký hiệu thống kê)
    question_type VARCHAR(20) DEFAULT 'mcq',       -- 'mcq' | 'multi' | 'truefalse'
    choices       JSONB NOT NULL,
    -- [{ "id": "a", "text": "...", "is_correct": true }, ...]
    explanation   TEXT,                            -- giải thích đáp án đúng (hiện sau khi làm)
    points        NUMERIC(4,2) DEFAULT 1.00,
    sort_order    SMALLINT DEFAULT 0
);
```

#### `quiz_attempts`
```sql
CREATE TABLE quiz_attempts (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    quiz_id       UUID REFERENCES quizzes(id) ON DELETE CASCADE,
    student_id    UUID REFERENCES users(id) ON DELETE CASCADE,
    started_at    TIMESTAMPTZ DEFAULT NOW(),
    submitted_at  TIMESTAMPTZ,                     -- NULL = đang làm
    score         NUMERIC(5,2),                    -- tính sau khi submit
    max_score     NUMERIC(5,2),
    attempt_no    SMALLINT DEFAULT 1
);
```

#### `question_answers`
```sql
CREATE TABLE question_answers (
    attempt_id    UUID REFERENCES quiz_attempts(id) ON DELETE CASCADE,
    question_id   UUID REFERENCES quiz_questions(id) ON DELETE CASCADE,
    chosen_ids    JSONB,                           -- ["a"] hoặc ["a", "c"] với multi
    is_correct    BOOLEAN,
    PRIMARY KEY (attempt_id, question_id)
);
```

#### `user_files`
```sql
CREATE TABLE user_files (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID REFERENCES users(id) ON DELETE CASCADE,
    file_name   VARCHAR(255) NOT NULL,
    file_path   VARCHAR(500) NOT NULL,      -- volume path: myfiles/{user_id}/
    file_size   BIGINT,
    description TEXT,
    is_public   BOOLEAN DEFAULT FALSE,      -- TRUE = bất kỳ ai có link đều xem được
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);
```

#### `file_shares`
```sql
CREATE TABLE file_shares (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    file_id     UUID NOT NULL,              -- tham chiếu tới user_files.id
    file_type   VARCHAR(20) DEFAULT 'user_file', -- 'user_file' | 'submission'
    shared_by   UUID REFERENCES users(id) ON DELETE CASCADE,
    share_token VARCHAR(64) UNIQUE NOT NULL, -- random hex an toàn (secrets.token_hex(32))
    permission  VARCHAR(10) DEFAULT 'view', -- 'view' | 'edit' (edit ở Phase 9)
    expires_at  TIMESTAMPTZ,               -- NULL = không hết hạn
    view_count  INT DEFAULT 0,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
-- URL: https://heystat.pedu.vn/shared/{share_token}
-- LMS kiểm tra expires_at → mở Jamovi iframe load file ở chế độ read-only (hoặc edit)
```

---

## 5. API Endpoints

Base URL: `/api/v1`  
Tất cả request (trừ `/auth/*`) cần header `Authorization: Bearer <access_token>`.

### 5.1 Authentication

| Method | Endpoint | Role | Mô tả |
|---|---|---|---|
| POST | `/auth/register` | Public | Đăng ký tài khoản |
| POST | `/auth/login` | Public | Đăng nhập → trả JWT |
| POST | `/auth/logout` | User+ | Huỷ refresh token |
| POST | `/auth/refresh` | User+ | Làm mới access token |
| POST | `/auth/verify-email` | Public | Xác thực email qua token |
| POST | `/auth/forgot-password` | Public | Gửi email reset |
| POST | `/auth/reset-password` | Public | Đặt lại mật khẩu |
| GET  | `/auth/me` | User+ | Thông tin user hiện tại |
| POST | `/auth/oauth/{provider}` | Public | OAuth callback (Google, Microsoft) |

### 5.2 User Management (Admin)

| Method | Endpoint | Role | Mô tả |
|---|---|---|---|
| GET    | `/admin/users` | Admin | Danh sách user (có phân trang, filter) |
| GET    | `/admin/users/{id}` | Admin | Chi tiết user |
| PATCH  | `/admin/users/{id}` | Admin | Cập nhật user |
| DELETE | `/admin/users/{id}` | Admin | Vô hiệu hoá user |
| POST   | `/admin/users/{id}/roles` | Admin | Cấp role |
| DELETE | `/admin/users/{id}/roles/{role}` | Admin | Thu hồi role |
| GET    | `/admin/stats` | Admin | Thống kê hệ thống |
| GET/PUT| `/admin/settings` | Admin | Xem / sửa cấu hình hệ thống |

### 5.3 Classes

| Method | Endpoint | Role | Mô tả |
|---|---|---|---|
| GET    | `/classes` | Teacher/Admin | Danh sách lớp của tôi / tất cả |
| POST   | `/classes` | Teacher | Tạo lớp học mới |
| GET    | `/classes/{id}` | Teacher/Student/Admin | Chi tiết lớp |
| PATCH  | `/classes/{id}` | Teacher(owner)/Admin | Cập nhật lớp |
| DELETE | `/classes/{id}` | Teacher(owner)/Admin | Xoá / archive lớp |
| POST   | `/classes/{id}/enroll` | User | Tham gia lớp bằng enrollment key |
| DELETE | `/classes/{id}/enroll` | Student | Rời lớp |
| GET    | `/classes/{id}/students` | Teacher/Admin | Danh sách sinh viên |
| DELETE | `/classes/{id}/students/{userId}` | Teacher/Admin | Xoá sinh viên khỏi lớp |
| POST   | `/classes/{id}/regenerate-key` | Teacher(owner) | Tạo lại enrollment key |

### 5.4 Class Files

| Method | Endpoint | Role | Mô tả |
|---|---|---|---|
| GET    | `/classes/{id}/files` | Teacher/Student | Danh sách file |
| POST   | `/classes/{id}/files` | Teacher | Upload file mới |
| GET    | `/classes/{id}/files/{fileId}/download` | Teacher/Student | Tải file |
| DELETE | `/classes/{id}/files/{fileId}` | Teacher(owner) | Xoá file |

### 5.5 Assignments

| Method | Endpoint | Role | Mô tả |
|---|---|---|---|
| GET    | `/classes/{id}/assignments` | Teacher/Student | Danh sách bài tập |
| POST   | `/classes/{id}/assignments` | Teacher | Tạo bài tập mới (chọn type + allow_sharing) |
| GET    | `/classes/{id}/assignments/{aId}` | Teacher/Student | Chi tiết bài tập |
| PATCH  | `/classes/{id}/assignments/{aId}` | Teacher(owner) | Cập nhật bài tập |
| DELETE | `/classes/{id}/assignments/{aId}` | Teacher(owner) | Xoá bài tập |
| GET    | `/classes/{id}/assignments/{aId}/groups` | Teacher/Student | Danh sách nhóm |
| POST   | `/classes/{id}/assignments/{aId}/groups` | Student | Tạo nhóm / tham gia nhóm |
| PATCH  | `/assignments/{aId}/groups/{gId}/leader` | Student(leader) | Chuyển quyền leader |

### 5.6 Submissions

| Method | Endpoint | Role | Mô tả |
|---|---|---|---|
| GET    | `/assignments/{aId}/submissions` | Teacher/Admin | Tất cả bài nộp của 1 bài tập |
| POST   | `/assignments/{aId}/submissions` | Student | Nộp bài (tạo / nộp lại) |
| GET    | `/assignments/{aId}/submissions/my` | Student | Bài nộp của tôi |
| GET    | `/assignments/{aId}/submissions/{sId}` | Teacher/Student(own) | Chi tiết 1 bài nộp |
| POST   | `/assignments/{aId}/submissions/{sId}/grade` | Teacher | Chấm điểm + nhận xét |
| GET    | `/classes/{id}/progress` | Teacher | Tiến độ tổng hợp toàn lớp |
| GET    | `/classes/{id}/grades/export` | Teacher | Export điểm (CSV/XLSX) |

### 5.7 Notifications

| Method | Endpoint | Role | Mô tả |
|---|---|---|---|
| GET    | `/notifications` | User+ | Danh sách thông báo của tôi |
| PATCH  | `/notifications/{id}/read` | User+ | Đánh dấu đã đọc |
| PATCH  | `/notifications/read-all` | User+ | Đánh dấu tất cả đã đọc |

### 5.8 Jamovi Session Token

| Method | Endpoint | Role | Mô tả |
|---|---|---|---|
| POST   | `/sessions/token` | Student | Lấy session token cho (assignment_id) → trả URL embed Jamovi |
| DELETE | `/sessions/token` | Student | Hủy session token (logout khỏi editor) |
| POST   | `/sessions/snapshot` | Student | Lưu nháp: upload .omv blob → lưu draft submission |
| GET    | `/sessions/observe/{sessionId}` | Teacher | URL embed read-only để quan sát live session student |

### 5.9 My Files

| Method | Endpoint | Role | Mô tả |
|---|---|---|---|
| GET    | `/files` | User+ | Danh sách file cá nhân |
| POST   | `/files` | User+ | Upload file .omv mới |
| GET    | `/files/{id}` | User+(owner) | Thông tin file |
| PATCH  | `/files/{id}` | User+(owner) | Đổi tên / mô tả |
| DELETE | `/files/{id}` | User+(owner) | Xoá file |
| GET    | `/files/{id}/open` | User+(owner) | Lấy URL embed Jamovi để mở file |

### 5.10 Sharing

| Method | Endpoint | Role | Mô tả |
|---|---|---|---|
| POST   | `/files/{id}/share` | User+(owner) | Tạo share link (tuỳ chọn expires_at) |
| DELETE | `/files/{id}/share` | User+(owner) | Thu hồi share link |
| GET    | `/shared/{token}` | Public | Mở file được chia sẻ → embed Jamovi read-only |
| POST   | `/assignments/{aId}/submissions/{sId}/share` | Student | Chia sẻ bài nộp (chỉ khi `allow_sharing=true`) |

### 5.11 Lessons

| Method | Endpoint | Role | Mô tả |
|---|---|---|---|
| GET    | `/classes/{id}/lessons` | Teacher/Student | Danh sách bài giảng (Student chỉ thấy published) |
| POST   | `/classes/{id}/lessons` | Teacher | Tạo bài giảng mới |
| GET    | `/classes/{id}/lessons/{lId}` | Teacher/Student | Chi tiết + danh sách resources |
| PATCH  | `/classes/{id}/lessons/{lId}` | Teacher(owner) | Cập nhật nội dung / publish |
| DELETE | `/classes/{id}/lessons/{lId}` | Teacher(owner) | Xoá bài giảng |
| POST   | `/classes/{id}/lessons/{lId}/resources` | Teacher | Thêm resource (URL hoặc file_id) |
| PATCH  | `/classes/{id}/lessons/{lId}/resources/{rId}` | Teacher(owner) | Cập nhật resource |
| DELETE | `/classes/{id}/lessons/{lId}/resources/{rId}` | Teacher(owner) | Xoá resource |
| PATCH  | `/classes/{id}/lessons/reorder` | Teacher(owner) | Sắp xếp lại thứ tự bài giảng |

### 5.12 Quizzes

| Method | Endpoint | Role | Mô tả |
|---|---|---|---|
| GET    | `/classes/{id}/quizzes` | Teacher/Student | Danh sách quiz |
| POST   | `/classes/{id}/quizzes` | Teacher | Tạo quiz mới |
| GET    | `/classes/{id}/quizzes/{qId}` | Teacher/Student | Chi tiết quiz |
| PATCH  | `/classes/{id}/quizzes/{qId}` | Teacher(owner) | Cập nhật quiz / publish |
| DELETE | `/classes/{id}/quizzes/{qId}` | Teacher(owner) | Xoá quiz |
| POST   | `/classes/{id}/quizzes/{qId}/questions` | Teacher | Thêm câu hỏi |
| PATCH  | `/quizzes/{qId}/questions/{queId}` | Teacher(owner) | Sửa câu hỏi |
| DELETE | `/quizzes/{qId}/questions/{queId}` | Teacher(owner) | Xoá câu hỏi |
| PATCH  | `/quizzes/{qId}/questions/reorder` | Teacher(owner) | Sắp xếp lại câu hỏi |
| POST   | `/quizzes/{qId}/attempts` | Student | Bắt đầu lượt làm quiz |
| PATCH  | `/quizzes/{qId}/attempts/{aId}/submit` | Student | Nộp bài quiz → auto-grade |
| GET    | `/quizzes/{qId}/attempts/my` | Student | Lịch sử làm quiz của tôi |
| GET    | `/quizzes/{qId}/attempts` | Teacher | Tất cả lượt làm (thống kê) |
| GET    | `/quizzes/{qId}/stats` | Teacher | Thống kê từng câu: tỷ lệ đúng, phân bố chọn đáp án |

---

## 6. Luồng nghiệp vụ chính (User Flows)

### 6.1 Đăng ký & Đăng nhập

```
[Guest] → Đăng ký (email + password) → Trở thành [User] → Đăng nhập → JWT
       → Redirect đến Dashboard

Có điều kiện thì làm:
[Guest] → "Đăng nhập với Google" → OAuth2 callback
       → Tự động tạo tài khoản nếu chưa có → JWT → Dashboard
```

### 6.2 Teacher tạo lớp học

```
[Teacher] → Tạo lớp (tiêu đề, mô tả, ngày bắt đầu/kết thúc)
          → Hệ thống generate Enrollment Key (random string, hash bcrypt lưu DB)
          → Upload file dữ liệu (CSV/Excel/SPSS/SAS)
          → Tạo Assignment (đề bài Markdown + chọn file đính kèm + deadline)
          → Chia sẻ link lớp + Enrollment Key cho sinh viên
          → Theo dõi dashboard tiến độ
```

### 6.3 Student tham gia và làm bài

```
[User] → Nhập Enrollment Key → Server verify (bcrypt compare)
       → Tạo bản ghi enrollments → User trở thành [Student] của lớp
       → Vào trang lớp học → Xem danh sách Assignment
       → Chọn Assignment → Đọc đề + tải file dữ liệu
       → Mở HeyStat editor → Phân tích dữ liệu trong session riêng
       → Lưu nháp (POST /sessions/snapshot) bất kỳ lúc nào
       → Nộp bài (POST /submissions) trước deadline
       → Nếu allow_resubmit = TRUE và chưa quá deadline → nộp lại được
       → Sau khi giáo viên chấm → nhận Notification → xem điểm + nhận xét
```

### 6.4 Teacher theo dõi & chấm bài

```
[Teacher] → Vào lớp học → Tab "Tiến độ"
          → Xem bảng: [Tên sinh viên | Đã nộp | Điểm | Trạng thái]
          → Click vào bài nộp → Xem snapshot kết quả Jamovi
          → Nhập điểm + nhận xét → Submit
          → Hệ thống gửi Notification cho Student
          → Export điểm toàn lớp → CSV/XLSX

Quan sát live (tuỳ chọn):
          → Teacher click "Quan sát" → LMS cấp URL observe embed read-only
          → Teacher xem Jamovi của Student trong thời gian thực (không can thiệp)
```

### 6.5 User lưu file cá nhân (My Files)

```
[User] → Từ Jamovi editor → "Lưu vào My Files" → upload .omv
       → Trang My Files: danh sách file, đổi tên, mô tả, xoá
       → Mở lại: click → LMS cấp session embed → Jamovi load file
```

### 6.6 Chia sẻ file

```
[User/Student] → My Files → chọn file → "Tạo link chia sẻ"
              → Có thể đặt thời hạn (7 ngày, 30 ngày, vĩnh viễn)
              → Copy link dạng /shared/{token}
              → Người nhận mở link → LMS kiểm tra token + expires_at
              → Nếu hợp lệ → mở Jamovi iframe load file ở chế độ read-only

Từ bài nộp (chỉ khi assignment.allow_sharing = TRUE):
[Student] → Submissions → "Chia sẻ bài này" → tạo share link bài nộp
```

### 6.7 Cộng tác nhóm (Group Assignment)

```
[Teacher] → Tạo assignment với type = 'group', group_size = 3
[Student A] → Vào assignment → "Tạo nhóm" → đặt tên → nhận group_id
[Student B, C] → "Tham gia nhóm" → nhập group_id hoặc chọn từ danh sách
           → Nhóm được cấp 1 session_path chung

Khi làm bài:
[Leader (A)] → mở editor → có quyền edit → thay đổi lan rộng đến B, C
[B, C] → mở editor → observer mode (xem live, không edit)
[A] → có thể "Chuyển quyền leader cho B" → B trở thành writer, A thành observer
[Nhóm] → Leader nộp bài → submission ghi nhận leader_id; tất cả thành viên được chấm điểm chung
```

---

## 7. Đặc tả tính năng chi tiết

### 7.1 Enrollment Key

- Khi tạo lớp, server tự sinh key dạng: `[A-Z0-9]{8}` (ví dụ: `STAT2025`)
- Teacher xem key dạng plain text, có thể copy hoặc regenerate
- Server lưu dạng **bcrypt hash** trong cột `enrollment_key`
- Khi User nhập key: so sánh `bcrypt.compare(inputKey, hash)`
- Một key chỉ hợp lệ khi lớp ở trạng thái `active` và chưa đầy `max_students`

### 7.2 Deadline Enforcement

- Tất cả kiểm tra deadline thực hiện **phía server**, không tin client
- Khi `POST /submissions`: server kiểm tra `NOW() < assignment.deadline`
- Nếu quá hạn → trả `403 Forbidden` với message rõ ràng
- Khi lớp kết thúc (`NOW() > class.ends_at`): tự động cập nhật `status = 'closed'` bằng cron job; Student không thể nộp thêm vào bất kỳ assignment nào trong lớp

### 7.3 File Upload

- Giới hạn kích thước file: cấu hình qua `system_settings.max_file_size_mb` (default: 50MB)
- Định dạng cho phép: CSV, XLSX, XLS, SAV (SPSS), SAS7BDAT, ODS, OMV (Jamovi)
- **Phase 1 – Local volume:** lưu vào `classroom/uploads/{class_id}/` trên filesystem (Docker volume)
- **Phase 2 – MinIO (tuỳ chọn):** nếu cần scale hoặc nhiều server, migrate sang MinIO/S3
- Download URL: LMS API cấp signed token (JWT ngắn hạn) thay vì S3 pre-sign; Nginx phục vụ file tĩnh qua `X-Accel-Redirect` sau khi FastAPI xác thực quyền
- Validate MIME type bằng magic bytes (python-magic), không chỉ dựa vào extension

### 7.4 Submission Versioning

- Mỗi lần nộp tạo một bản ghi `submissions` mới (`is_final = FALSE` cho các bản nộp trước)
- Bản nộp cuối nhất có `is_final = TRUE`
- Logic: khi Student nộp lại, set `is_final = FALSE` cho bản cũ → insert bản mới với `is_final = TRUE`
- Teacher luôn xem bản `is_final = TRUE`; các bản cũ vẫn được lưu để audit

### 7.5 Progress Dashboard (Teacher)

Endpoint `GET /classes/{id}/progress` trả về:
```json
{
  "total_students": 35,
  "total_assignments": 3,
  "per_assignment": [
    {
      "assignment_id": "...",
      "title": "Bài 1 – Thống kê mô tả",
      "deadline": "2025-06-15T23:59:00Z",
      "submitted": 28,
      "not_submitted": 7,
      "graded": 20,
      "average_score": 7.85
    }
  ],
  "students": [
    {
      "user_id": "...",
      "full_name": "Nguyễn Văn A",
      "submissions": [
        { "assignment_id": "...", "status": "graded", "score": 8.5 },
        { "assignment_id": "...", "status": "submitted" },
        { "assignment_id": "...", "status": "not_submitted" }
      ]
    }
  ]
}
```

### 7.6 Export Điểm

- Format: CSV và XLSX
- Cột: `Họ tên | Email | [Tên bài 1] | [Tên bài 2] | ... | Tổng điểm TB`
- Encoding: UTF-8 với BOM (để mở đúng tiếng Việt trong Excel)

### 7.7 My Files

- Mỗi User có quota lưu trữ cá nhân: mặc định 500MB, cấu hình qua `system_settings`
- Volume path: `uploads/myfiles/{user_id}/`
- Định dạng: `.omv` chủ yếu; cho phép thêm CSV, XLSX để tiện tải về
- Khi User mở Jamovi và bấm "Save" từ giao diện chính → LMS intercept → lưu vào My Files nếu User đã đăng nhập
- Giới hạn số file: cấu hình qua `system_settings.max_user_files` (default: 100)

### 7.8 Chia sẻ file phân tích

- Share token là **`secrets.token_hex(32)`** (64 ký tự hex) — không thể đoán, không encode thông tin
- Link: `https://heystat.pedu.vn/shared/{token}` — Vue Router bắt, gọi `/api/v1/shared/{token}`
- LMS kiểm tra: token hợp lệ + chưa `expires_at` → cấp session embed Jamovi **read-only**
- Chế độ read-only thực hiện bằng cách: LMS không cấp access_key đầy đủ cho session embed shared — Jamovi `permissions` mode `cloud` với `open.upload = FALSE`, `save.local = FALSE`
- `view_count` tăng mỗi lần mở (cho chủ sở hữu xem thống kê)
- Chủ sở hữu có thể thu hồi link bất kỳ lúc nào → xoá bản ghi `file_shares`
- **Ràng buộc bài kiểm tra:** Endpoint `POST /assignments/{aId}/submissions/{sId}/share` kiểm tra `assignment.allow_sharing = TRUE` trước khi tạo; nếu `FALSE` → trả `403`

### 7.9 Cộng tác biên tập (Collaboration)

#### Phân tích kỹ thuật

Jamovi `instance.py` dùng `self._coms = None` — một WebSocket client duy nhất per instance. `clientconnection.py` gọi `instance.set_coms(self)` mỗi khi message đến → ghi đè connection cũ.

Để hỗ trợ **một writer + N observers**, cần một thay đổi có chủ đích vào `server/jamovi/server/instance.py`:

```python
# Thay self._coms = None bằng:
self._coms = None           # writer (một người duy nhất)
self._observer_coms = []    # danh sách observer connections

def set_coms(self, coms, role='writer'):
    if role == 'writer':
        self._coms = coms
    else:
        if coms not in self._observer_coms:
            self._observer_coms.append(coms)

def broadcast(self, message):
    """Gửi kết quả đến writer + tất cả observers"""
    if self._coms:
        self._coms.send(message)
    for obs in list(self._observer_coms):
        try:
            obs.send(message)
        except Exception:
            self._observer_coms.remove(obs)
```

Đây là thay đổi **có chủ đích rời khỏi upstream** Jamovi, cần document rõ trong `classroom/PLAN.md` và comment trong code.

#### Cơ chế hoạt động

| Loại | session_path | Quyền WebSocket |
|---|---|---|
| `homework` cá nhân | `classroom/{class_id}/{user_id}/` | writer duy nhất |
| `exam` | `classroom/{class_id}/{user_id}/` | writer duy nhất; sharing/observe bị khoá |
| `group` | `classroom/{class_id}/group_{group_id}/` | leader = writer; thành viên khác = observer |
| Teacher observe | bất kỳ session path hợp lệ | observer (không edit) |

#### Luồng kỹ thuật group session

1. Nhóm được tạo → LMS tạo `assignment_groups.session_path = classroom/{class_id}/group_{group_id}/`
2. Leader mở editor → LMS cấp token với `role=writer` cho session_path đó
3. Observer (thành viên khác) mở editor → LMS cấp token với `role=observer`
4. Khi leader thực hiện phân tích → Jamovi gọi `broadcast()` → observers nhận kết quả real-time
5. Observer không gửi được message edit (LMS validate role trong token; Tornado `clientconnection.py` kiểm tra trước khi forward)
6. Chuyển quyền leader: LMS cập nhật `assignment_groups.leader_id` → leader cũ reconnect với role observer, leader mới reconnect với role writer

#### Giới hạn kỳ thi (Exam mode)

Khi `assignment_type = 'exam'`:
- `GET /sessions/observe/{sessionId}` → `403` (Teacher không quan sát được, tránh lộ đề)
- `POST .../share` → `403`
- `allow_resubmit = FALSE` được enforce ở DB constraint
- Không có group collaboration

### 6.8 Teacher tạo bài giảng

```
[Teacher] → Quản lý lớp → Tab "Bài giảng" → "Tạo bài giảng mới"
         → Nhập tiêu đề + nội dung Markdown
         → "Thêm tài nguyên" → chọn loại:
            - Video   → dán URL (YouTube / Loom / Google Drive)
            - PDF     → dán URL (Google Drive / OneDrive viewer link)
            - Link    → bất kỳ URL nào (Wikipedia, trang thống kê, v.v.)
            - Dataset → chọn file đã upload trong class_files
         → Sắp xếp thứ tự resource bằng drag & drop
         → "Lưu bản nháp" hoặc "Xuất bản" (sinh viên mới nhìn thấy)
         → Sắp xếp các bài giảng trong lớp bằng drag & drop
```

### 6.9 Student xem bài giảng và làm quiz

```
[Student] → Vào lớp học → Tab "Bài giảng"
         → Danh sách bài giảng đã xuất bản
         → Mở bài giảng → Đọc nội dung Markdown
         → Xem tài nguyên:
            - Video   → iframe embed YouTube/Loom (re-scaled, responsive)
            - PDF     → iframe Google Drive viewer
            - Link    → mở tab mới
            - Dataset → nút "Tải về" hoặc "Mở trong HeyStat"
         → "Làm quiz đi kèm" (nếu bài giảng có quiz gắn kết)

[Student] → Tab "Quiz" hoặc liên kết từ bài giảng
         → Xem thông tin: số câu, thời gian, số lần được làm
         → "Bắt đầu" → timer bắt đầu (đếm ngược nếu có time_limit)
         → Làm từng câu (MCQ / Đúng–Sai / Chọn nhiều)
         → "Nộp"
            → Server auto-grade (so choices với is_correct trong quiz_questions)
            → Hiển thị điểm + giải thích (tùy show_result_after)
```

### 7.10 Bài giảng & Tài nguyên nhúng

- **Không lưu video/PDF trên server** — chỉ lưu URL trong `lesson_resources.url`
- URL được kiểm tra **whitelist domain** trước khi lưu để tránh SSRF và nhúng nội dung độc hại:
  ```python
  ALLOWED_EMBED_DOMAINS = {
      'youtube.com', 'youtu.be',
      'drive.google.com', 'docs.google.com',
      'loom.com',
      'onedrive.live.com', '1drv.ms',
      'vimeo.com',
  }
  # Link thông thường (resource_type='link') không cần whitelist — mở tab mới, không embed
  ```
- **Iframe sandbox:** video/PDF embed dùng `sandbox="allow-scripts allow-same-origin"` — không cho popup, không truy cập cookie HeyStat
- **PDF:** sử dụng Google Drive viewer `https://drive.google.com/viewerng/viewer?embedded=true&url=...` hoặc OneDrive embed — không cần plugin PDF
- **Content-Security-Policy:** cập nhật nginx CSP để cho phép `frame-src` về các domain whitelist, không mở rộng toàn bộ

### 7.11 Quiz MCQ & Auto-grade

- **Câu hỏi lưu trong `questions.choices` JSONB** — server là nguồn sự thật về `is_correct`, client không bao giờ nhận field `is_correct` trước khi nộp bài
- **Auto-grade phía server:** khi `POST /quizzes/{qId}/attempts/{aId}/submit`, server:
  1. Kiểm tra `submitted_at IS NULL` (chưa nộp) và deadline chưa qua
  2. Với mỗi câu `mcq`/`truefalse`: `is_correct = (chosen_ids == correct_ids)`
  3. Với `multi` (chọn nhiều): `is_correct = (set(chosen_ids) == set(correct_ids))`
  4. `score = SUM(q.points WHERE is_correct) / SUM(q.points) * quiz.max_score`
  5. Lưu kết quả vào `quiz_attempts.score` và `question_answers`
- **Time limit enforcement phía server:** khi submit, kiểm tra `NOW() <= started_at + interval '{time_limit_min} minutes'`; nếu quá → submit vẫn được nhận nhưng đánh dấu `late_submit = TRUE`
- **Hiển thị kết quả** theo `show_result_after`:
  - `'submit'`: hiển thị ngay sau khi nộp (điểm + giải thích từng câu nếu `explanation` có)
  - `'deadline'`: chỉ hiển thị sau khi deadline qua
  - `'never'`: chỉ Teacher thấy
- **Thống kê Teacher** (`GET /quizzes/{qId}/stats`): tỷ lệ chọn từng đáp án per câu — giúp phát hiện câu hỏi bị hiểu sai
- Câu hỏi viết bằng **Markdown** → hỗ trợ ký hiệu thống kê (LaTeX inline: `$\bar{x}$`, `$H_0$`)

---

## 8. Bảo mật & Xác thực

### 8.1 JWT Strategy

- **Access token:** hết hạn sau 15 phút, payload chứa `{ sub: userId, roles: [...] }`
- **Refresh token:** hết hạn sau 7 ngày, lưu trong `httpOnly` cookie hoặc Redis
- Rotation: mỗi lần refresh → cấp refresh token mới, huỷ token cũ (token rotation)

### 8.2 Password

- Hash bằng **bcrypt**, cost factor 12
- Tối thiểu 8 ký tự, phải có chữ + số

### 8.3 Bảo vệ endpoint

- Mọi endpoint `/api/v1/*` (trừ `/auth/*`) yêu cầu `Authorization: Bearer <token>`
- Middleware kiểm tra: JWT hợp lệ → user tồn tại & `is_active` → role phù hợp → scoped check (ví dụ: Student chỉ được vào lớp mình đã enroll)

### 8.4 Rate Limiting

| Endpoint | Giới hạn |
|---|---|
| `POST /auth/login` | 10 requests / phút / IP |
| `POST /auth/register` | 5 requests / phút / IP |
| `POST /auth/forgot-password` | 3 requests / phút / email |
| `POST /classes/{id}/enroll` | 5 requests / phút / user |
| API chung | 200 requests / phút / user |

### 8.5 CORS

- Chỉ chấp nhận origin từ domain HeyStat chính thức
- `credentials: true` để gửi cookie refresh token

### 8.6 Input Validation

- Validate toàn bộ input với schema (Pydantic/Zod)
- Sanitize Markdown trong `assignment.description` trước khi render (tránh XSS)
- File upload: kiểm tra MIME type thực sự (magic bytes), không chỉ extension

---

## 9. Quản lý HeyStat Session (Multi-user)

Đây là thách thức kỹ thuật quan trọng nhất khi sử dụng Jamovi trong môi trường multi-user.

### 9.1 Vấn đề thực tế

Jamovi gốc thiết kế cho single-user. Tuy nhiên, codebase **đã có cơ chế `Session` class** (`server/jamovi/server/session.py`) quản lý nhiều instance qua `data_path + session_id`. HeyStat đang chạy single instance Tornado, nhưng Tornado là async nên có thể phục vụ nhiều WebSocket client đồng thời.

**Giới hạn thực tế:** Một container HeyStat hiện tại phục vụ nhiều session trong cùng một process. Mỗi "session" tương ứng với một thư mục riêng trên filesystem. Với lớp học đông sinh viên, bottleneck là CPU của engine R/engine Python, không phải Tornado.

### 9.2 Chiến lược Session cho Classroom

```
LMS API (FastAPI)
├── Khi student mở editor cho một assignment:
│   1. LMS tạo/kiểm tra session_token riêng cho (user_id, assignment_id)
│   2. LMS cấp một URL embed: https://heystat.pedu.vn/?session={token}
│      (HeyStat nhận token → bind vào session path /data/{token}/)
│   3. Student làm việc trong iframe embed với session path riêng
│   4. Không có student nào share session path với nhau
│
├── Session path naming:
│   - homework/exam: /root/Documents/classroom/{class_id}/{user_id}/
│   - group:         /root/Documents/classroom/{class_id}/group_{group_id}/
│   - my files:      /root/Documents/myfiles/{user_id}/
│   - shared (read): /root/Documents/shared_readonly/{token}/  ← copy tạm
│
└── Cleanup: LMS cron job xóa session path sau khi lớp closed + 30 ngày
```

**Lưu ý:** Không cần xây "Session Pool" phức tạp — Jamovi Tornado đã xử lý async multi-session. Cần kiểm tra giới hạn `max_students` thực tế bằng load test.

### 9.3 Snapshot để nộp bài

- Jamovi không có built-in "export to JSON" API. Snapshot được thực hiện bằng cách:
  1. Student bấm "Nộp bài" trong LMS UI
  2. LMS UI gọi Jamovi's **save as .omv** (đã có trong client) → blob → upload lên LMS API
  3. LMS API lưu file `.omv` vào `submissions.file_path` (local volume hoặc MinIO)
  4. Teacher xem bài: download `.omv` hoặc LMS mở iframe Jamovi load `.omv` đó ở chế độ read-only

- `session_snapshot` (JSONB) dùng để lưu HTML output từ kết quả phân tích (nếu Jamovi export HTML được), không bắt buộc ở phase 1.

### 9.4 Isolation

- Session path per-user: `/root/Documents/classroom/{class_id}/{user_id}/`
- Jamovi server nhận `session_id` từ LMS token; không student nào biết session_id của nhau
- LMS API validate token trước khi cấp URL embed (kiểm tra enrollment + deadline)
- Group session: tất cả thành viên nhóm dùng chung `session_id` group, nhưng role (writer/observer) được kiểm soát ở lớp LMS
- Shared read-only: LMS tạo bản sao file vào thư mục tạm riêng biệt cho session embed; không dùng session path gốc của chủ sở hữu
- `JAMOVI_ALLOW_ARBITRARY_CODE: 'false'` — **không bao giờ thay đổi**

---

## 10. Thông báo (Notification)

### 10.1 Các loại thông báo

| `type` | Khi nào trigger | Gửi cho |
|---|---|---|
| `class.enrolled` | Student vào lớp thành công | Student |
| `assignment.created` | Teacher tạo bài tập mới | Tất cả Student trong lớp |
| `assignment.deadline_reminder` | 24h trước deadline (cron job) | Student chưa nộp |
| `submission.received` | Student nộp bài | Teacher |
| `submission.graded` | Teacher chấm xong | Student |
| `class.closing_soon` | 48h trước khi lớp đóng (cron job) | Tất cả Student |
| `class.closed` | Lớp chuyển sang `closed` | Tất cả Student |
| `system.announcement` | Admin gửi thông báo hệ thống | Tất cả user |

### 10.2 Cơ chế gửi

- **In-app:** Lưu vào bảng `notifications`, hiển thị qua polling hoặc WebSocket
- **Email:** Gửi qua SMTP (cấu hình trong `system_settings`); có thể dùng queue (Redis BullMQ / Celery)
- User có thể tắt email notification trong hồ sơ cá nhân

---

## 11. Tech Stack gợi ý

### Backend LMS API (`classroom/api/`)
- **Python 3.11+ + FastAPI** — cùng ecosystem Python với HeyStat server; async-native
- **SQLAlchemy 2.0** + **Alembic** — ORM + migration
- **PostgreSQL 15+** — relational data
- **Redis 7+** — rate limiting, session token cache, job queue
- **Celery + Redis** — background jobs: cron notifications, export grades
- **Local volume** (phase 1) → **MinIO** (phase 2 nếu cần scale)
- **Pydantic v2** — validation
- **python-multipart** — file upload
- **python-jose** hoặc **PyJWT** — JWT

### Frontend LMS (`classroom/frontend/`)
- **Vue 3 + TypeScript + Vite** — đồng nhất với stack của `client/` (HeyStat đã dùng Vue 3)
- **Pinia** — global state (auth, notifications)
- **TanStack Query (Vue Query)** — data fetching + cache
- **Vue Router** — routing
- **vue-markdown-render** hoặc **marked** — render đề bài Markdown
- **Naive UI** hoặc **Element Plus** — UI components (phù hợp Vue 3)
- **Axios** — HTTP client
- Tích hợp vào nginx như một SPA riêng tại path `/classroom/`

### DevOps
- **Docker Compose** — `classroom/docker-compose.yml` cho local dev (API + PostgreSQL + Redis)
- **Nginx** — thêm `location /api/` và `location /classroom/` vào config đang có
- Giữ nguyên `docker-compose.yaml` gốc của HeyStat; thêm `docker-compose.full.yml` tổng hợp

---

## 12. Giai đoạn phát triển

> Ước lượng thời gian là tham khảo, phụ thuộc vào số người phát triển.

### Phase 1 – Authentication & User ✅ HOÀN THÀNH
- [x] Schema DB: `users`, `roles`, `user_roles` + Alembic migration
- [x] API: `/api/v1/auth/*` (register, login, refresh, verify-email, reset-password)
- [x] JWT middleware (access 15 phút, refresh 7 ngày, rotation)
- [x] Admin: quản lý user, cấp role Teacher
- [x] Frontend Vue 3: trang đăng nhập, đăng ký, dashboard cơ bản tại `/classroom/`
- [x] Nginx config: thêm `location /api/` → FastAPI:8080; `location /classroom/` → Vue SPA

### Phase 2 – Classes & Enrollment ✅ HOÀN THÀNH
- [x] Schema DB: `classes`, `enrollments`
- [x] API: `/api/v1/classes/*`, enrollment flow với enrollment key
- [x] Enrollment Key generation (random `[A-Z0-9]{8}`) & bcrypt hash verification
- [x] Cron job: tự động đóng lớp khi quá `ends_at`
- [x] Frontend: trang tạo lớp, trang sinh viên nhập key, trang lớp học

### Phase 3 – Files & Assignments ✅ HOÀN THÀNH
- [x] Schema DB: `class_files`, `assignments`
- [x] API: `/api/v1/classes/{id}/files/*`, `/api/v1/classes/{id}/assignments/*`
- [x] File upload lên local volume; validate MIME type bằng magic bytes; pre-sign download URL via signed token (không dùng S3 pre-sign ở phase này)
- [x] Frontend: upload file, soạn đề bài Markdown, trang bài tập

### Phase 4 – Session Token & Submissions ✅ HOÀN THÀNH
- [x] Schema DB: `submissions`
- [x] LMS cấp session token cho (user_id, assignment_id) → URL embed Jamovi
- [x] Jamovi session path isolation: `Documents/classroom/{class_id}/{user_id}/`
- [x] Student làm bài trong iframe; bấm "Nộp bài" → LMS UI trigger save `.omv` → upload
- [x] API: `/api/v1/assignments/{id}/submissions/*` — nộp bài, nộp lại, versioning
- [x] Server kiểm tra deadline trước khi cho phép submit (không tin client)
- [x] Frontend: embed Jamovi iframe, nút nộp bài, lịch sử nộp bài

### Phase 5 – Grading & Progress ✅ HOÀN THÀNH
- [x] API: grading endpoint, progress dashboard, export grades (CSV UTF-8 BOM)
- [x] Teacher xem bài: download `.omv` hoặc embed Jamovi load `.omv` read-only
- [x] Frontend: dashboard tiến độ teacher, trang điểm cho student

### Phase 6 – Notifications ✅ HOÀN THÀNH
- [x] Schema DB: `notifications`
- [x] In-app notification (polling 30s hoặc WebSocket nếu cần real-time)
- [x] Email queue (Celery + Redis + SMTP)
- [x] Cron jobs: deadline reminder (24h trước), class closing reminder (48h trước)
- [x] Frontend: bell icon, notification list, badge count

### Phase 7 – Hardening & Admin ✅ HOÀN THÀNH
- [x] Rate limiting (slowapi hoặc Redis-based middleware)
- [x] Input sanitization toàn bộ; Markdown sanitize (bleach/nh3) trước khi render
- [x] Admin dashboard: thống kê user/lớp/bài, cấu hình hệ thống
- [-] Load test: kiểm tra Jamovi Tornado xử lý bao nhiêu session đồng thời *(bỏ qua – không phải code)*
- [x] Auto-generated API docs (FastAPI OpenAPI/Swagger)
- [x] Dockerfile cho `classroom/api/`; tích hợp vào `docker-compose.full.yml`

### Phase 8 – My Files ✅ HOÀN THÀNH
- [x] Schema DB: `user_files`
- [x] Volume path: `uploads/myfiles/{user_id}/`
- [x] API: `/api/v1/files/*` (CRUD + open embed)
- [x] Quota check: `system_settings.max_user_files`, `max_user_storage_mb`
- [x] Frontend: trang My Files (danh sách, upload, mở, đổi tên, xoá)
- [x] Tích hợp vào navigation chính của LMS frontend

### Phase 9 – Sharing ✅ HOÀN THÀNH
- [x] Schema DB: `file_shares`
- [x] API: `/api/v1/files/{id}/share`, `/api/v1/shared/{token}`
- [x] Share token generation: `secrets.token_hex(32)`
- [x] Shared view: LMS load file vào session path read-only riêng biệt (bản sao tạm)
- [x] Enforce `allow_sharing` check cho bài nộp
- [x] Frontend: dialog tạo link (chọn thời hạn), copy link, thu hồi link
- [x] Trang `/shared/{token}`: hiển thị thông tin file + embed Jamovi read-only

### Phase 10 – Collaboration ✅ HOÀN THÀNH
- [x] **Fork divergence có chủ đích:** Sửa `server/jamovi/server/instance.py` để hỗ trợ `writer + N observers`
- [x] LMS token mang thêm trường `collab_role: 'writer' | 'observer'`
- [x] `clientconnection.py` kiểm tra role trong token trước khi cho phép ghi
- [x] Schema DB: `assignment_groups`, `assignment_group_members`
- [x] API: group endpoints (`/classes/{id}/assignments/{aId}/groups/*`, leader transfer)
- [x] Teacher observe endpoint: `/api/v1/sessions/observe/{sessionId}` (observer token)
- [x] Frontend: giao diện tạo/tham gia nhóm, badge "Writer/Observer" trong editor, nút "Chuyển quyền"
- [x] **Không áp dụng cho `exam`**: kiểm tra server-side, trả `403` nếu cố tình gọi collaboration API trên exam assignment

### Phase 11 – Lessons & Tài nguyên nhúng ⚠️ XONG
- [x] Schema DB: `lessons`, `lesson_resources` (chạy Alembic migration)
- [x] URL whitelist validation: module `classroom/api/services/embed_validator.py` kiểm tra domain trước khi lưu
- [x] API 5.11: CRUD lessons, CRUD resources, `PATCH /lessons/{id}/reorder` (sort_order), `PUT /lessons/{id}/publish`
- [x] Nginx CSP: cập nhật `frame-src` cho phép domain whitelist (YouTube, Drive, Loom, Vimeo, OneDrive)
- [x] Frontend: trang bài giảng với danh sách lesson + iframe embed; Teacher có drag-and-drop reorder và nút Publish/Draft
- [x] Markdown renderer với KaTeX inline cho ký hiệu thống kê ($H_0$, $\bar{x}$, v.v.)

### Phase 12 – Quiz MCQ & Auto-grade ⚠️ XONG
- [x] Schema DB: `quizzes`, `quiz_questions`, `quiz_attempts`, `question_answers` (chạy Alembic migration)
- [x] Auto-grade engine: `classroom/api/services/quiz_grader.py` — so sánh `chosen_ids` vs `is_correct` phía server
- [x] Time limit enforcement: kiểm tra `submitted_at - started_at ≤ time_limit_min * 60s` khi submit
- [x] API 5.12: CRUD quiz, CRUD questions, `POST /attempts`, `POST /attempts/{id}/submit`, `GET /quizzes/{id}/stats`
- [x] Client KHÔNG nhận field `is_correct` từ server trước khi submit (loại bỏ khỏi response schema)
- [x] Frontend Teacher: quiz builder với Markdown + KaTeX preview cho câu hỏi và đáp án
- [x] Frontend Student: countdown timer, nộp bài khi hết giờ tự động (JS + server enforce)
- [x] Hiển thị kết quả theo `show_result_after` (submit / deadline / never)

---
## 13. Monorepo với classroom/ tách biệt rõ ràng

```
HeyStat/                        ← repo chính (fork Jamovi)
│
├── client/                     ← Jamovi frontend Vue 3 (upstream, không sửa)
├── server/                     ← Jamovi Tornado server (upstream, không sửa)
├── engine/                     ← Jamovi engine (upstream, không sửa)
├── jmv/, jmvcore/, plots/      ← R packages (upstream, không sửa)
├── docker-compose.yaml         ← compose gốc HeyStat (giữ nguyên)
├── heystat-nginx-linux.conf    ← nginx config gốc (thêm location mới, không xóa cũ)
│
├── classroom/                  ← 🆕 TẤT CẢ code LMS
│   ├── PLAN.md
│   ├── api/                    ← FastAPI backend (LMS)
│   │   ├── models/             ← SQLAlchemy models
│   │   ├── routers/            ← API routes (auth, classes, assignments, ...)
│   │   ├── services/           ← business logic
│   │   ├── middleware/         ← JWT auth, rate limiting
│   │   ├── migrations/         ← Alembic DB migrations
│   │   ├── main.py
│   │   └── requirements.txt
│   ├── frontend/               ← Vue 3 SPA cho LMS (served at /classroom/)
│   │   ├── src/
│   │   │   ├── pages/
│   │   │   ├── components/
│   │   │   ├── stores/         ← Pinia stores
│   │   │   └── router/
│   │   ├── vite.config.ts
│   │   └── package.json
│   ├── tests/                  ← pytest tests cho API
│   ├── docker-compose.yml      ← local dev: FastAPI + PostgreSQL + Redis
│   ├── Dockerfile              ← cho classroom/api/
│   └── README.md
│
└── docker-compose.full.yml     ← 🆕 compose tổng hợp HeyStat + LMS
```

### Nginx: thêm vào `heystat-nginx-linux.conf`

```nginx
# LMS API
location /api/ {
    proxy_pass http://127.0.0.1:8080;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}

# LMS Frontend SPA
location /classroom/ {
    root /var/www/lms;
    try_files $uri $uri/ /classroom/index.html;
}
```

### Sync upstream từ Jamovi vào HeyStat

```bash
git remote add upstream https://github.com/jamovi/jamovi
git fetch upstream
git merge upstream/main
# classroom/ không bị ảnh hưởng vì không có trong upstream
# LƯU Ý: server/jamovi/server/instance.py đã được fork (Phase 10) → cần resolve conflict thủ công
```

---

## 14. My Files – Lưu trữ cá nhân

Tính năng bổ sung giúp HeyStat ngang bằng với cloud.jamovi.org về lưu trữ file cá nhân.

### Tóm tắt
- Mỗi User đăng nhập có không gian lưu `.omv` riêng tại `uploads/myfiles/{user_id}/`
- Tách biệt hoàn toàn khỏi classroom; không ảnh hưởng đến bài tập hay điểm số
- Quota mặc định: 500MB/user, 100 file (cấu hình qua `system_settings`)
- Tích hợp: từ Jamovi editor → nút "My Files" (trên ribbon LMS) → lưu, mở file cá nhân

### Volume layout
```
uploads/
├── class/        ← class_files (do Teacher upload)
│   └── {class_id}/
├── submissions/  ← bài nộp của Student (.omv)
│   └── {assignment_id}/{user_id}/
├── myfiles/      ← My Files cá nhân
│   └── {user_id}/
└── shared_tmp/   ← bản sao tạm cho session chia sẻ read-only (tự dọn sau 1h)
    └── {share_token}/
```

---

## 15. Chia sẻ file phân tích

### Cách hoạt động
1. Chủ sở hữu tạo link từ My Files → `POST /api/v1/files/{id}/share` → nhận URL
2. Người nhận mở `/shared/{token}` → LMS kiểm tra token + expiry + ownership
3. LMS copy file vào `shared_tmp/{token}/` → cấp session embed Jamovi **read-only**
4. Jamovi chạy ở `mode=cloud` với permissions: `save.local=false`, `open.upload=false`
5. Người nhận chỉ xem và tương tác với phân tích, không lưu được

### Quy tắc với bài tập
| `assignment_type` | `allow_sharing` | Hành vi |
|---|---|---|
| `exam` | luôn `FALSE` (DB constraint) | Mọi attempt share → `403` |
| `homework` | Teacher chọn | Nếu `TRUE`: student chia sẻ bài nộp được |
| `group` | Teacher chọn | Nếu `TRUE`: leader chia sẻ bài nộp của nhóm được |

---

## 16. Cộng tác biên tập (Collaboration)

### Tóm tắt kỹ thuật
- Yêu cầu **1 thay đổi có chủ đích** vào `server/jamovi/server/instance.py` (upstream file)
- Thay đổi: hỗ trợ `_coms` (writer) + `_observer_coms[]` (N observers) thay vì chỉ `_coms`
- Mọi kết quả phân tích (`_on_results`) được **broadcast** đến tất cả coms
- Writer là người duy nhất có thể gửi yêu cầu edit; observer chỉ nhận kết quả
- Khi upstream Jamovi cập nhật `instance.py`: merge thủ công, ưu tiên giữ logic broadcast

### Giới hạn exam
Khi `assignment_type = 'exam'`, server từ chối **tất cả** các hành động collaboration và sharing:
- Không cấp observer token cho Teacher
- Không tạo group cho exam assignment
- Không tạo share link cho submission

### So sánh với cloud.jamovi.org
| Tính năng | cloud.jamovi.org | HeyStat Classroom |
|---|:---:|:---:|
| My Files | ✅ | ✅ Phase 8 |
| Share link (read-only) | ✅ | ✅ Phase 9 |
| Real-time collaboration | ❌ | ✅ Phase 10 (group assignment) |
| Observer mode (teacher) | ❌ | ✅ Phase 10 |
| Exam lockdown | ❌ | ✅ (DB constraints + server enforcement) |
| Bài giảng + nhúng link | ❌ | ✅ Phase 11 |
| Quiz MCQ auto-grade | ❌ | ✅ Phase 12 |

---

## 17. Bài giảng & Tài nguyên nhúng (Lessons)

### Chính sách lưu trữ
HeyStat Classroom **không lưu video, PDF hay bất kỳ media nào trên server**. Tất cả tài nguyên bài giảng được lưu dưới dạng URL trong cột `lesson_resources.url`. Điều này:
- Giảm dung lượng server và băng thông
- Tránh vấn đề bản quyền khi host video giảng dạy
- Tận dụng hạ tầng CDN của YouTube/Google Drive

### Whitelist domain hợp lệ

| Dịch vụ | Pattern URL hợp lệ | Cách nhúng |
|---|---|---|
| YouTube | `youtube.com/watch?v=`, `youtu.be/` | `https://www.youtube.com/embed/{video_id}` |
| Google Drive | `drive.google.com/file/d/{id}/` | `https://drive.google.com/file/d/{id}/preview` |
| Google Docs / Slides | `docs.google.com/` | `{url}?embedded=true` |
| OneDrive | `onedrive.live.com`, `1drv.ms` | embed URL từ "Share → Embed" |
| Loom | `loom.com/share/` | `https://www.loom.com/embed/{id}` |
| Vimeo | `vimeo.com/{id}` | `https://player.vimeo.com/video/{id}` |
| Link thông thường | bất kỳ URL hợp lệ | Mở tab mới — không nhúng iframe |

### Bảo mật iframe
```nginx
# Thêm vào nginx config (Content-Security-Policy)
frame-src 'self' https://www.youtube.com https://drive.google.com
          https://docs.google.com https://onedrive.live.com
          https://www.loom.com https://player.vimeo.com;
```

Tất cả iframe dùng thuộc tính:
```html
<iframe sandbox="allow-scripts allow-same-origin allow-presentation"
        referrerpolicy="strict-origin-when-cross-origin" ...>
```

### Trạng thái bài giảng
- `is_published = FALSE` (draft): chỉ Teacher thấy — Student nhận `404` nếu gọi trực tiếp
- `is_published = TRUE`: Student trong class thấy; không public ra ngoài
- `sort_order`: Teacher kéo thả (drag-and-drop) để sắp xếp; `PATCH /lessons/{lessonId}/reorder` nhận `{ order: [id1, id2, ...] }`

---

## 18. Quiz MCQ & Auto-grade

### Loại câu hỏi

| `question_type` | Mô tả | Auto-grade |
|---|---|---|
| `mcq` | Chọn 1 đáp án đúng | ✅ Exact match `chosen_ids == [correct_id]` |
| `multi` | Chọn nhiều đáp án | ✅ Set match: `set(chosen) == set(correct)` |
| `truefalse` | Đúng / Sai | ✅ Boolean: `chosen == [correct]` |

> Partial credit cho `multi` **không** được áp dụng — tránh phức tạp hóa và tranh cãi.

### Luồng làm bài

```
Student                         Server
  │                               │
  ├─ POST /attempts ──────────────> Tạo attempt, ghi started_at
  │<─ {attempt_id, started_at} ───┤
  │                               │
  │  ... làm bài (frontend đếm giờ)
  │                               │
  ├─ POST /attempts/{id}/submit ──> 1. Kiểm tra chưa nộp (submitted_at IS NULL)
  │  { answers: [{qId, chosen}] } │ 2. Kiểm tra time_limit nếu có
  │                               │ 3. Tính điểm (quiz_grader.py)
  │                               │ 4. Lưu score, submitted_at
  │<─ { score, show_result } ─────┤
```

### Bảo mật câu hỏi
- `GET /quizzes/{id}/questions` **không trả về** field `is_correct`, `explanation` cho Student trước khi nộp
- Response schema Student dùng `QuestionPublicSchema` (loại bỏ 2 field trên)
- Response schema Teacher dùng `QuestionFullSchema` (đầy đủ)
- Kiểm tra ownership trong middleware: chỉ Teacher của class mới gọi được `QuestionFullSchema`

### Time limit
- `time_limit_min = NULL`: không giới hạn thời gian
- `time_limit_min > 0`: server enforce tại submit — nếu `NOW() > started_at + interval`, vẫn nhận bài nhưng ghi `late_submit = TRUE` trong `quiz_attempts`
- Frontend JS đếm ngược và tự động submit khi về 0 (defense-in-depth)

### Thống kê Teacher
`GET /quizzes/{qId}/stats` trả về:
```json
{
  "total_attempts": 42,
  "per_question": [
    {
      "question_id": 1,
      "choices": [
        { "choice_id": "a", "text": "Mean", "selected_pct": 0.12, "is_correct": false },
        { "choice_id": "b", "text": "Median", "selected_pct": 0.71, "is_correct": true },
        { "choice_id": "c", "text": "Mode", "selected_pct": 0.17, "is_correct": false }
      ]
    }
  ]
}
```
Dùng để phát hiện câu hỏi bị hiểu sai (nhiều Student chọn distractors cụ thể).

---

*Tài liệu này là living document – cập nhật khi có thay đổi yêu cầu.*