"""One place that decides what a user is allowed to do inside a class.

Three levels, per the HeyStat role model:

- ``teacher``   — the class owner (``classes.teacher_id``) or a system admin.
                  Full control: settings, datasets, coursework, grading, roster.
- ``assistant`` — an enrolled user the owner appointed. Supports grading and
                  answers questions, but cannot delete the class or edit its
                  settings/coursework.
- ``student``   — an ordinary enrollee: reads lessons, submits work, sees own marks.

Callers compare against these constants rather than re-deriving them, so the
``admin`` escape hatch and the enrollment lookup stay in one file.
"""
import uuid
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Class, Enrollment, Role, User, UserRole

TEACHER = "teacher"
ASSISTANT = "assistant"
STUDENT = "student"

SYSTEM_ROLES = ("admin", "teacher", "user", "moderator")


async def system_roles(db: AsyncSession, user_id: uuid.UUID) -> set[str]:
    r = await db.execute(
        select(Role.name).join(UserRole, UserRole.role_id == Role.id).where(UserRole.user_id == user_id)
    )
    return {row for (row,) in r.all()}


async def enrollment_role(db: AsyncSession, class_id: uuid.UUID, user_id: uuid.UUID) -> Optional[str]:
    r = await db.execute(
        select(Enrollment.role).where(
            Enrollment.class_id == class_id,
            Enrollment.user_id == user_id,
            Enrollment.status == "active",
        )
    )
    return r.scalar_one_or_none()


async def class_role(db: AsyncSession, cls: Class, user: User) -> str:
    """Return the caller's role in this class, or raise 403."""
    if "admin" in await system_roles(db, user.id) or cls.teacher_id == user.id:
        return TEACHER
    role = await enrollment_role(db, cls.id, user.id)
    if role is None:
        raise HTTPException(403, "Không có quyền truy cập lớp học này")
    return role


def can_grade(role: str) -> bool:
    return role in (TEACHER, ASSISTANT)


def can_author(role: str) -> bool:
    """Content and settings: owner/admin only — an assistant never gets these."""
    return role == TEACHER
