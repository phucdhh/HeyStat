"""Public catalogue for the HeyStat home page.

A visitor who has not logged in is a Guest, and the role model lets a Guest read
the course list and the platform counters — nothing else. So these endpoints
publish the class title, the teacher's display name and aggregate counts, and
never an email, an enrollment code or anything about an individual student.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.redis_client import validate_refresh_token
from database import get_db
from models import Assignment, Class, Enrollment, Lesson, Role, Submission, User, UserRole

router = APIRouter(prefix="/public", tags=["public"])


class PublicClass(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    teacher_name: Optional[str] = None
    student_count: int = 0
    assignment_count: int = 0
    lesson_count: int = 0
    starts_at: datetime
    ends_at: datetime


class PublicStats(BaseModel):
    total_users: int
    total_teachers: int
    active_classes: int
    final_submissions: int
    lessons: int


class VisitorState(BaseModel):
    """Who the home page is talking to. A Guest is simply someone with no session."""

    logged_in: bool
    full_name: Optional[str] = None
    roles: list[str] = []


@router.get("/whoami", response_model=VisitorState)
async def whoami(request: Request, db: AsyncSession = Depends(get_db)):
    """Read-only session probe for the static home page.

    The landing page must offer "Vào Jamovi" to someone already signed in and
    "Đăng nhập" to a Guest, without rotating their refresh token the way
    /auth/refresh would.
    """
    token = request.cookies.get("hs_session")
    user_id = await validate_refresh_token(token) if token else None
    if not user_id:
        return VisitorState(logged_in=False)
    user = (await db.execute(
        select(User).where(User.id == uuid.UUID(user_id), User.is_active.is_(True))
    )).scalar_one_or_none()
    if user is None:
        return VisitorState(logged_in=False)
    roles = (await db.execute(
        select(Role.name)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(UserRole.user_id == user.id)
    )).scalars().all()
    return VisitorState(logged_in=True, full_name=user.full_name, roles=sorted(set(roles)))


@router.get("/stats", response_model=PublicStats)
async def public_stats(db: AsyncSession = Depends(get_db)):
    now = datetime.now(tz=timezone.utc)
    return PublicStats(
        total_users=(await db.execute(
            select(func.count(User.id)).where(User.is_active.is_(True))
        )).scalar() or 0,
        total_teachers=(await db.execute(
            select(func.count(UserRole.user_id))
            .join(Role, Role.id == UserRole.role_id)
            .where(Role.name.in_(("teacher", "admin")))
        )).scalar() or 0,
        active_classes=(await db.execute(
            select(func.count(Class.id)).where(Class.status == "active", Class.ends_at >= now)
        )).scalar() or 0,
        final_submissions=(await db.execute(
            select(func.count(Submission.id)).where(Submission.is_final.is_(True))
        )).scalar() or 0,
        lessons=(await db.execute(
            select(func.count(Lesson.id)).where(Lesson.is_published.is_(True))
        )).scalar() or 0,
    )


@router.get("/classes", response_model=list[PublicClass])
async def public_classes(
    limit: int = 24,
    db: AsyncSession = Depends(get_db),
):
    """Courses running right now, newest first."""
    now = datetime.now(tz=timezone.utc)
    classes = (await db.execute(
        select(Class)
        .where(Class.status == "active", Class.ends_at >= now)
        .order_by(Class.starts_at.desc())
        .limit(max(1, min(limit, 100)))
    )).scalars().all()
    if not classes:
        return []

    class_ids = {c.id for c in classes}
    teacher_names = dict((await db.execute(
        select(User.id, func.coalesce(func.nullif(User.full_name, ""), User.email))
        .where(User.id.in_({c.teacher_id for c in classes}))
    )).all())

    async def _count_by_class(model) -> dict[uuid.UUID, int]:
        rows = (await db.execute(
            select(model.class_id, func.count())
            .where(model.class_id.in_(class_ids))
            .group_by(model.class_id)
        )).all()
        return {cid: count for cid, count in rows}

    students = (await db.execute(
        select(Enrollment.class_id, func.count())
        .where(Enrollment.class_id.in_(class_ids), Enrollment.status == "active",
               Enrollment.role == "student")
        .group_by(Enrollment.class_id)
    )).all()
    student_counts = {cid: n for cid, n in students}
    assignment_counts = await _count_by_class(Assignment)
    lesson_counts = await _count_by_class(Lesson)

    return [
        PublicClass(
            id=str(c.id),
            title=c.title,
            description=(c.description or "").strip() or None,
            teacher_name=teacher_names.get(c.teacher_id),
            student_count=student_counts.get(c.id, 0),
            assignment_count=assignment_counts.get(c.id, 0),
            lesson_count=lesson_counts.get(c.id, 0),
            starts_at=c.starts_at,
            ends_at=c.ends_at,
        )
        for c in classes
    ]
