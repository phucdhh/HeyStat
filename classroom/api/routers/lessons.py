"""Lessons & Lesson Resources router (Phase 11)."""
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from database import get_db
from models import Class, Lesson, LessonResource, Enrollment, User, UserRole, Role
from auth.deps import get_current_user
from services.embed_validator import is_allowed_embed_url, transform_to_embed_url
from services.markdown import sanitize_md

router = APIRouter(tags=["lessons"])


async def _get_user_roles(db, user_id):
    r = await db.execute(
        select(Role.name).join(UserRole, UserRole.role_id == Role.id).where(UserRole.user_id == user_id)
    )
    return {row for (row,) in r.all()}


async def _class_access(db, class_id, user):
    r = await db.execute(select(Class).where(Class.id == class_id))
    cls = r.scalar_one_or_none()
    if not cls:
        raise HTTPException(404, "Lớp học không tồn tại")
    roles = await _get_user_roles(db, user.id)
    if "admin" in roles or cls.teacher_id == user.id:
        return cls, "teacher"
    er = await db.execute(
        select(Enrollment).where(
            Enrollment.class_id == class_id,
            Enrollment.user_id == user.id,
            Enrollment.status == "active",
        )
    )
    if er.scalar_one_or_none():
        return cls, "student"
    raise HTTPException(403, "Không có quyền truy cập lớp học này")


# ─── schemas ────────────────────────────────────────────────────

class LessonCreate(BaseModel):
    title: str
    content: Optional[str] = None
    sort_order: int = 0


class LessonUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    sort_order: Optional[int] = None
    is_published: Optional[bool] = None


class LessonResponse(BaseModel):
    id: str
    class_id: str
    title: str
    content: Optional[str]
    sort_order: int
    is_published: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ResourceCreate(BaseModel):
    resource_type: str  # 'video'|'pdf'|'link'|'data_file'
    title: Optional[str] = None
    url: Optional[str] = None
    file_id: Optional[uuid.UUID] = None
    sort_order: int = 0


class ResourceUpdate(BaseModel):
    title: Optional[str] = None
    url: Optional[str] = None
    sort_order: Optional[int] = None


class ResourceResponse(BaseModel):
    id: str
    lesson_id: str
    resource_type: str
    title: Optional[str]
    url: Optional[str]
    embed_url: Optional[str] = None
    file_id: Optional[str]
    sort_order: int

    model_config = {"from_attributes": True}


class ReorderRequest(BaseModel):
    order: list[str]  # list of lesson IDs in new order


# ─── Lessons ────────────────────────────────────────────────────

@router.get("/classes/{class_id}/lessons", response_model=list[LessonResponse])
async def list_lessons(
    class_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cls, role = await _class_access(db, class_id, current_user)
    stmt = select(Lesson).where(Lesson.class_id == class_id).order_by(Lesson.sort_order)
    if role == "student":
        stmt = stmt.where(Lesson.is_published == True)
    r = await db.execute(stmt)
    return [
        LessonResponse(id=str(l.id), class_id=str(l.class_id), title=l.title,
                       content=l.content, sort_order=l.sort_order, is_published=l.is_published,
                       created_at=l.created_at)
        for l in r.scalars().all()
    ]


@router.post("/classes/{class_id}/lessons", status_code=201, response_model=LessonResponse)
async def create_lesson(
    class_id: uuid.UUID, body: LessonCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cls, role = await _class_access(db, class_id, current_user)
    if role != "teacher":
        raise HTTPException(403, "Chỉ giáo viên mới tạo bài giảng được")
    lesson = Lesson(
        class_id=class_id, title=body.title, content=sanitize_md(body.content), sort_order=body.sort_order
    )
    db.add(lesson)
    await db.flush()
    return LessonResponse(id=str(lesson.id), class_id=str(lesson.class_id), title=lesson.title,
                          content=lesson.content, sort_order=lesson.sort_order,
                          is_published=lesson.is_published, created_at=lesson.created_at)


@router.get("/classes/{class_id}/lessons/{lesson_id}", response_model=LessonResponse)
async def get_lesson(
    class_id: uuid.UUID, lesson_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cls, role = await _class_access(db, class_id, current_user)
    r = await db.execute(select(Lesson).where(Lesson.id == lesson_id, Lesson.class_id == class_id))
    lesson = r.scalar_one_or_none()
    if not lesson:
        raise HTTPException(404)
    if role == "student" and not lesson.is_published:
        raise HTTPException(404)
    return LessonResponse(id=str(lesson.id), class_id=str(lesson.class_id), title=lesson.title,
                          content=lesson.content, sort_order=lesson.sort_order,
                          is_published=lesson.is_published, created_at=lesson.created_at)


@router.patch("/classes/{class_id}/lessons/{lesson_id}", response_model=LessonResponse)
async def update_lesson(
    class_id: uuid.UUID, lesson_id: uuid.UUID, body: LessonUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cls, role = await _class_access(db, class_id, current_user)
    if role != "teacher":
        raise HTTPException(403)
    r = await db.execute(select(Lesson).where(Lesson.id == lesson_id, Lesson.class_id == class_id))
    lesson = r.scalar_one_or_none()
    if not lesson:
        raise HTTPException(404)
    updates = body.model_dump(exclude_none=True)
    if "content" in updates:
        updates["content"] = sanitize_md(updates["content"])
    for field, val in updates.items():
        setattr(lesson, field, val)
    lesson.updated_at = datetime.now(tz=timezone.utc)
    return LessonResponse(id=str(lesson.id), class_id=str(lesson.class_id), title=lesson.title,
                          content=lesson.content, sort_order=lesson.sort_order,
                          is_published=lesson.is_published, created_at=lesson.created_at)


@router.delete("/classes/{class_id}/lessons/{lesson_id}", status_code=204)
async def delete_lesson(
    class_id: uuid.UUID, lesson_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cls, role = await _class_access(db, class_id, current_user)
    if role != "teacher":
        raise HTTPException(403)
    r = await db.execute(select(Lesson).where(Lesson.id == lesson_id, Lesson.class_id == class_id))
    lesson = r.scalar_one_or_none()
    if not lesson:
        raise HTTPException(404)
    await db.delete(lesson)


@router.patch("/classes/{class_id}/lessons/reorder", status_code=204)
async def reorder_lessons(
    class_id: uuid.UUID, body: ReorderRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cls, role = await _class_access(db, class_id, current_user)
    if role != "teacher":
        raise HTTPException(403)
    for idx, lesson_id in enumerate(body.order):
        r = await db.execute(
            select(Lesson).where(Lesson.id == uuid.UUID(lesson_id), Lesson.class_id == class_id)
        )
        lesson = r.scalar_one_or_none()
        if lesson:
            lesson.sort_order = idx


# ─── Resources ──────────────────────────────────────────────────

@router.post("/classes/{class_id}/lessons/{lesson_id}/resources", status_code=201, response_model=ResourceResponse)
async def add_resource(
    class_id: uuid.UUID, lesson_id: uuid.UUID, body: ResourceCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cls, role = await _class_access(db, class_id, current_user)
    if role != "teacher":
        raise HTTPException(403)
    r = await db.execute(select(Lesson).where(Lesson.id == lesson_id, Lesson.class_id == class_id))
    if not r.scalar_one_or_none():
        raise HTTPException(404, "Bài giảng không tồn tại")

    # Validate embed URL for video/pdf types
    if body.url and body.resource_type in ("video", "pdf"):
        if not is_allowed_embed_url(body.url):
            raise HTTPException(400, "URL không thuộc danh sách domain cho phép nhúng")
    if body.url is None and body.file_id is None:
        raise HTTPException(400, "Phải cung cấp URL hoặc file_id")
    if body.url is not None and body.file_id is not None:
        raise HTTPException(400, "Chỉ cung cấp một trong URL hoặc file_id")

    res = LessonResource(
        lesson_id=lesson_id,
        resource_type=body.resource_type,
        title=body.title,
        url=body.url,
        file_id=body.file_id,
        sort_order=body.sort_order,
    )
    db.add(res)
    await db.flush()
    embed_url = None
    if res.url and body.resource_type in ("video", "pdf"):
        embed_url = transform_to_embed_url(res.url, body.resource_type)
    return ResourceResponse(
        id=str(res.id), lesson_id=str(res.lesson_id), resource_type=res.resource_type,
        title=res.title, url=res.url, embed_url=embed_url,
        file_id=str(res.file_id) if res.file_id else None, sort_order=res.sort_order,
    )


@router.patch("/classes/{class_id}/lessons/{lesson_id}/resources/{resource_id}", response_model=ResourceResponse)
async def update_resource(
    class_id: uuid.UUID, lesson_id: uuid.UUID, resource_id: uuid.UUID, body: ResourceUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cls, role = await _class_access(db, class_id, current_user)
    if role != "teacher":
        raise HTTPException(403)
    r = await db.execute(
        select(LessonResource).where(LessonResource.id == resource_id, LessonResource.lesson_id == lesson_id)
    )
    res = r.scalar_one_or_none()
    if not res:
        raise HTTPException(404)
    if body.url and res.resource_type in ("video", "pdf"):
        if not is_allowed_embed_url(body.url):
            raise HTTPException(400, "URL không thuộc danh sách domain cho phép nhúng")
    for field, val in body.model_dump(exclude_none=True).items():
        setattr(res, field, val)
    embed_url = transform_to_embed_url(res.url, res.resource_type) if res.url and res.resource_type in ("video", "pdf") else None
    return ResourceResponse(
        id=str(res.id), lesson_id=str(res.lesson_id), resource_type=res.resource_type,
        title=res.title, url=res.url, embed_url=embed_url,
        file_id=str(res.file_id) if res.file_id else None, sort_order=res.sort_order,
    )


@router.delete("/classes/{class_id}/lessons/{lesson_id}/resources/{resource_id}", status_code=204)
async def delete_resource(
    class_id: uuid.UUID, lesson_id: uuid.UUID, resource_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cls, role = await _class_access(db, class_id, current_user)
    if role != "teacher":
        raise HTTPException(403)
    r = await db.execute(
        select(LessonResource).where(LessonResource.id == resource_id, LessonResource.lesson_id == lesson_id)
    )
    res = r.scalar_one_or_none()
    if not res:
        raise HTTPException(404)
    await db.delete(res)
