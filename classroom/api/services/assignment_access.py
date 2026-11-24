from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import and_, func, not_, or_, select

from models import Assignment


def _as_utc(value):
    """SQLite returns naive datetimes even for DateTime(timezone=True)."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def assignment_started(assignment):
    """False while a scheduled start time is still in the future."""
    start = getattr(assignment, 'start_at', None)
    return start is None or _as_utc(start) <= datetime.now(tz=timezone.utc)


def assignment_visible(assignment):
    """Students see the brief/files only once opened *and* started."""
    return bool(assignment.is_open) and assignment_started(assignment)


def require_assignment_open(assignment):
    if not assignment.is_open:
        raise HTTPException(403, "Giáo viên chưa mở bài này cho học viên")
    if not assignment_started(assignment):
        raise HTTPException(403, "Chưa đến giờ bắt đầu của bài tập")


def _start_reached():
    """SQL condition matching assignment_started() for file access queries."""
    return or_(Assignment.start_at.is_(None), Assignment.start_at <= func.now())


async def closed_file_ids(db, class_id):
    result = await db.execute(
        select(Assignment.file_id).where(
            Assignment.class_id == class_id,
            or_(Assignment.is_open.is_(False), not_(_start_reached())),
            Assignment.file_id.isnot(None),
        )
    )
    return set(result.scalars().all())


async def open_file_ids(db, class_id):
    result = await db.execute(
        select(Assignment.file_id).where(
            Assignment.class_id == class_id,
            and_(Assignment.is_open.is_(True), _start_reached()),
            Assignment.file_id.isnot(None),
        )
    )
    return set(result.scalars().all())


async def require_file_open(db, file):
    if not file.student_access or file.id in await closed_file_ids(db, file.class_id):
        raise HTTPException(403, "Tệp đang khoá. Hãy chờ giáo viên cho phép mở.")
