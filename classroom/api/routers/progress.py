"""Progress dashboard, grade export, notifications, admin routers."""
import uuid
import csv
import io
import re
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel, EmailStr

from database import get_db
from models import (
    User, UserRole, Role, Class, Enrollment, Assignment, Submission, Notification,
    SystemSetting,
)
from auth.deps import get_current_user
from auth.security import hash_password

router = APIRouter(tags=["progress-admin"])


async def _get_user_roles(db, user_id):
    r = await db.execute(
        select(Role.name).join(UserRole, UserRole.role_id == Role.id).where(UserRole.user_id == user_id)
    )
    return {row for (row,) in r.all()}


# ─── progress dashboard ──────────────────────────────────────────

@router.get("/classes/{class_id}/progress")
async def class_progress(
    class_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cls_r = await db.execute(select(Class).where(Class.id == class_id))
    cls = cls_r.scalar_one_or_none()
    if not cls:
        raise HTTPException(404, "Lớp học không tồn tại")
    roles = await _get_user_roles(db, current_user.id)
    if "admin" not in roles and cls.teacher_id != current_user.id:
        raise HTTPException(403, "Không có quyền xem tiến độ")

    # Students
    students_r = await db.execute(
        select(User, Enrollment.enrolled_at)
        .join(Enrollment, Enrollment.user_id == User.id)
        .where(Enrollment.class_id == class_id, Enrollment.status == "active")
    )
    students = students_r.all()
    total_students = len(students)

    # Assignments
    asgn_r = await db.execute(select(Assignment).where(Assignment.class_id == class_id))
    assignments = asgn_r.scalars().all()
    total_assignments = len(assignments)

    per_assignment = []
    for a in assignments:
        subs = await db.execute(
            select(Submission).where(Submission.assignment_id == a.id, Submission.is_final == True)
        )
        final_subs = subs.scalars().all()
        submitted = len(final_subs)
        graded = sum(1 for s in final_subs if s.score is not None)
        scores = [float(s.score) for s in final_subs if s.score is not None]
        per_assignment.append({
            "assignment_id": str(a.id),
            "title": a.title,
            "deadline": a.deadline.isoformat(),
            "submitted": submitted,
            "not_submitted": total_students - submitted,
            "graded": graded,
            "average_score": round(sum(scores) / len(scores), 2) if scores else None,
        })

    # Per-student breakdown
    student_rows = []
    for user, _ in students:
        sub_status = []
        for a in assignments:
            s_r = await db.execute(
                select(Submission).where(
                    Submission.assignment_id == a.id,
                    Submission.student_id == user.id,
                    Submission.is_final == True,
                )
            )
            final_sub = s_r.scalar_one_or_none()
            if final_sub:
                status = "graded" if final_sub.score is not None else "submitted"
                sub_status.append({"assignment_id": str(a.id), "status": status, "score": float(final_sub.score) if final_sub.score else None})
            else:
                sub_status.append({"assignment_id": str(a.id), "status": "not_submitted", "score": None})
        student_rows.append({
            "user_id": str(user.id),
            "full_name": user.full_name,
            "submissions": sub_status,
        })

    return {
        "total_students": total_students,
        "total_assignments": total_assignments,
        "per_assignment": per_assignment,
        "students": student_rows,
    }


@router.get("/classes/{class_id}/grades/export")
async def export_grades(
    class_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cls_r = await db.execute(select(Class).where(Class.id == class_id))
    cls = cls_r.scalar_one_or_none()
    if not cls:
        raise HTTPException(404)
    roles = await _get_user_roles(db, current_user.id)
    if "admin" not in roles and cls.teacher_id != current_user.id:
        raise HTTPException(403)

    students_r = await db.execute(
        select(User).join(Enrollment, Enrollment.user_id == User.id)
        .where(Enrollment.class_id == class_id, Enrollment.status == "active")
    )
    students = students_r.scalars().all()

    asgn_r = await db.execute(select(Assignment).where(Assignment.class_id == class_id))
    assignments = asgn_r.scalars().all()

    buf = io.StringIO()
    buf.write("\ufeff")  # UTF-8 BOM for Excel
    writer = csv.writer(buf)
    headers = ["Họ tên", "Email"] + [a.title for a in assignments] + ["Tổng điểm TB"]
    writer.writerow(headers)

    for user in students:
        scores = []
        for a in assignments:
            s_r = await db.execute(
                select(Submission).where(
                    Submission.assignment_id == a.id,
                    Submission.student_id == user.id,
                    Submission.is_final == True,
                )
            )
            sub = s_r.scalar_one_or_none()
            scores.append(float(sub.score) if sub and sub.score is not None else "")
        avg = sum(s for s in scores if isinstance(s, float)) / max(sum(1 for s in scores if isinstance(s, float)), 1)
        writer.writerow([user.full_name, user.email] + scores + [round(avg, 2)])

    content = buf.getvalue()
    return Response(
        content=content.encode("utf-8-sig"),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=grades_{class_id}.csv"},
    )


# ─── notifications ───────────────────────────────────────────────

notif_router = APIRouter(prefix="/notifications", tags=["notifications"])


class NotifResponse(BaseModel):
    id: str
    type: str
    title: str
    body: Optional[str]
    is_read: bool
    created_at: datetime

    model_config = {"from_attributes": True}


@notif_router.get("", response_model=list[NotifResponse])
async def list_notifications(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    r = await db.execute(
        select(Notification)
        .where(Notification.user_id == current_user.id)
        .order_by(Notification.created_at.desc())
        .limit(50)
    )
    notifs = r.scalars().all()
    return [
        NotifResponse(id=str(n.id), type=n.type, title=n.title, body=n.body,
                      is_read=n.is_read, created_at=n.created_at)
        for n in notifs
    ]


@notif_router.patch("/{notif_id}/read", status_code=204)
async def mark_read(
    notif_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    r = await db.execute(
        select(Notification).where(Notification.id == notif_id, Notification.user_id == current_user.id)
    )
    n = r.scalar_one_or_none()
    if not n:
        raise HTTPException(404)
    n.is_read = True


@notif_router.patch("/read-all", status_code=204)
async def mark_all_read(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    r = await db.execute(
        select(Notification).where(Notification.user_id == current_user.id, Notification.is_read == False)
    )
    for n in r.scalars().all():
        n.is_read = True


# ─── admin ───────────────────────────────────────────────────────

admin_router = APIRouter(prefix="/admin", tags=["admin"])


@admin_router.get("/users")
async def list_users(
    page: int = 1, size: int = 20,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    roles = await _get_user_roles(db, current_user.id)
    if "admin" not in roles:
        raise HTTPException(403)
    offset = (page - 1) * size
    r = await db.execute(select(User).offset(offset).limit(size))
    users = r.scalars().all()
    total_r = await db.execute(select(func.count(User.id)))
    total = total_r.scalar()
    # Include roles for each user
    items = []
    for u in users:
        u_roles = await _get_user_roles(db, u.id)
        items.append({
            "id": str(u.id),
            "email": u.email,
            "full_name": u.full_name,
            "is_active": u.is_active,
            "is_verified": u.is_verified,
            "roles": list(u_roles),
            "avatar_url": u.avatar_url,
        })
    return {"items": items, "total": total, "page": page}


@admin_router.patch("/users/{user_id}")
async def update_user(
    user_id: uuid.UUID,
    is_active: Optional[bool] = None,
    full_name: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    roles = await _get_user_roles(db, current_user.id)
    if "admin" not in roles:
        raise HTTPException(403)
    r = await db.execute(select(User).where(User.id == user_id))
    user = r.scalar_one_or_none()
    if not user:
        raise HTTPException(404)
    if is_active is not None:
        user.is_active = is_active
    if full_name is not None:
        user.full_name = full_name
    return {"id": str(user.id), "is_active": user.is_active}


@admin_router.post("/users/{user_id}/roles/{role_name}")
async def grant_role(
    user_id: uuid.UUID, role_name: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    roles = await _get_user_roles(db, current_user.id)
    if "admin" not in roles:
        raise HTTPException(403)
    role_r = await db.execute(select(Role).where(Role.name == role_name))
    role = role_r.scalar_one_or_none()
    if not role:
        raise HTTPException(400, f"Vai trò '{role_name}' không tồn tại")
    user_r = await db.execute(select(User).where(User.id == user_id))
    if not user_r.scalar_one_or_none():
        raise HTTPException(404)
    # Check not already assigned
    existing = await db.execute(
        select(UserRole).where(UserRole.user_id == user_id, UserRole.role_id == role.id)
    )
    if not existing.scalar_one_or_none():
        db.add(UserRole(user_id=user_id, role_id=role.id, granted_by=current_user.id))
    return {"detail": f"Đã cấp vai trò {role_name}"}


@admin_router.delete("/users/{user_id}/roles/{role_name}", status_code=204)
async def revoke_role(
    user_id: uuid.UUID, role_name: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    roles = await _get_user_roles(db, current_user.id)
    if "admin" not in roles:
        raise HTTPException(403)
    role_r = await db.execute(select(Role).where(Role.name == role_name))
    role = role_r.scalar_one_or_none()
    if not role:
        raise HTTPException(400)
    r = await db.execute(select(UserRole).where(UserRole.user_id == user_id, UserRole.role_id == role.id))
    ur = r.scalar_one_or_none()
    if ur:
        await db.delete(ur)


@admin_router.get("/stats")
async def system_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    roles = await _get_user_roles(db, current_user.id)
    if "admin" not in roles:
        raise HTTPException(403)
    users_count = (await db.execute(select(func.count(User.id)))).scalar()
    classes_count = (await db.execute(select(func.count(Class.id)))).scalar()
    subs_count = (await db.execute(select(func.count(Submission.id)))).scalar()
    return {"total_users": users_count, "total_classes": classes_count, "total_submissions": subs_count}


@admin_router.get("/settings")
async def get_settings_api(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    roles = await _get_user_roles(db, current_user.id)
    if "admin" not in roles:
        raise HTTPException(403)
    r = await db.execute(select(SystemSetting))
    return [{"key": s.key, "value": s.value} for s in r.scalars().all()]


@admin_router.put("/settings")
async def update_settings_api(
    updates: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    roles = await _get_user_roles(db, current_user.id)
    if "admin" not in roles:
        raise HTTPException(403)
    for key, value in updates.items():
        r = await db.execute(select(SystemSetting).where(SystemSetting.key == key))
        setting = r.scalar_one_or_none()
        if setting:
            setting.value = str(value)
            setting.updated_by = current_user.id
            setting.updated_at = datetime.now(tz=timezone.utc)
        else:
            db.add(SystemSetting(key=key, value=str(value), updated_by=current_user.id))
    return {"detail": "Cài đặt đã được lưu"}


class CreateUserRequest(BaseModel):
    email: EmailStr
    full_name: str
    password: str
    roles: list[str] = ["user"]


@admin_router.post("/users", status_code=201)
async def create_user(
    body: CreateUserRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    admin_roles = await _get_user_roles(db, current_user.id)
    if "admin" not in admin_roles:
        raise HTTPException(403)
    # Validate password
    if len(body.password) < 8 or not re.search(r'[A-Za-z]', body.password) or not re.search(r'[0-9]', body.password):
        raise HTTPException(400, detail="Mật khẩu phải có ít nhất 8 ký tự, gồm chữ và số")
    # Check email uniqueness
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(400, detail="Email đã được sử dụng")
    new_user = User(
        email=body.email,
        full_name=body.full_name.strip(),
        password_hash=hash_password(body.password),
        is_active=True,
        is_verified=True,
    )
    db.add(new_user)
    await db.flush()
    for role_name in body.roles:
        role_r = await db.execute(select(Role).where(Role.name == role_name))
        role = role_r.scalar_one_or_none()
        if role:
            db.add(UserRole(user_id=new_user.id, role_id=role.id, granted_by=current_user.id))
    await db.commit()
    return {
        "id": str(new_user.id),
        "email": new_user.email,
        "full_name": new_user.full_name,
        "roles": body.roles,
    }
