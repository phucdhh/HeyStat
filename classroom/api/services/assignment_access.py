from fastapi import HTTPException
from sqlalchemy import select

from models import Assignment


def require_assignment_open(assignment):
    if not assignment.is_open:
        raise HTTPException(403, "Giáo viên chưa mở bài này cho học viên")


async def closed_file_ids(db, class_id):
    result = await db.execute(
        select(Assignment.file_id).where(
            Assignment.class_id == class_id,
            Assignment.is_open.is_(False),
            Assignment.file_id.isnot(None),
        )
    )
    return set(result.scalars().all())


async def open_file_ids(db, class_id):
    result = await db.execute(
        select(Assignment.file_id).where(
            Assignment.class_id == class_id,
            Assignment.is_open.is_(True),
            Assignment.file_id.isnot(None),
        )
    )
    return set(result.scalars().all())


async def require_file_open(db, file):
    if not file.student_access or file.id in await closed_file_ids(db, file.class_id):
        raise HTTPException(403, "Tệp đang khoá. Hãy chờ giáo viên cho phép mở.")
