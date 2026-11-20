"""Requests to unlock the teacher role, and the admin queue that approves them.

Any registered account may read courses and hand in work, but only a teacher may
create a class. Creation rights are therefore not self-service: the request
lands in a queue and an admin grants the role, which keeps a throwaway account
from spamming courses on a server with a fixed jamovi capacity.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.deps import get_current_user, require_admin
from database import get_db
from models import Role, TeacherRequest, User, UserRole
from routers.submissions import _notify

router = APIRouter(prefix="/teacher-requests", tags=["teacher-requests"])


class TeacherRequestCreate(BaseModel):
    institution: Optional[str] = Field(None, max_length=255)
    reason: str = Field(..., min_length=10, max_length=2000)


class ReviewRequest(BaseModel):
    note: Optional[str] = Field(None, max_length=1000)


class TeacherRequestResponse(BaseModel):
    id: str
    status: str
    institution: Optional[str] = None
    reason: Optional[str] = None
    review_note: Optional[str] = None
    created_at: datetime
    reviewed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class AdminTeacherRequestResponse(TeacherRequestResponse):
    user_id: str
    email: str
    full_name: str


def _as_response(req: TeacherRequest) -> TeacherRequestResponse:
    return TeacherRequestResponse(
        id=str(req.id), status=req.status, institution=req.institution, reason=req.reason,
        review_note=req.review_note, created_at=req.created_at, reviewed_at=req.reviewed_at,
    )


@router.post("", status_code=201, response_model=TeacherRequestResponse)
async def submit_request(
    body: TeacherRequestCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    roles = (await db.execute(
        select(Role.name)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(UserRole.user_id == current_user.id)
    )).scalars().all()
    if "teacher" in roles or "admin" in roles:
        raise HTTPException(400, detail="Tài khoản của bạn đã có quyền tạo lớp học")

    existing = (await db.execute(
        select(TeacherRequest).where(
            TeacherRequest.user_id == current_user.id, TeacherRequest.status == "pending"
        )
    )).scalar_one_or_none()
    if existing:
        return _as_response(existing)

    req = TeacherRequest(
        user_id=current_user.id,
        status="pending",
        institution=(body.institution or "").strip() or None,
        reason=body.reason.strip(),
        # created_at is a server default: set it here because the response below
        # reads it, and an async session cannot lazy-load a column after flush.
        created_at=datetime.now(tz=timezone.utc),
    )
    db.add(req)
    await db.flush()
    return _as_response(req)


@router.get("/mine", response_model=list[TeacherRequestResponse])
async def my_requests(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rows = (await db.execute(
        select(TeacherRequest)
        .where(TeacherRequest.user_id == current_user.id)
        .order_by(TeacherRequest.created_at.desc())
    )).scalars().all()
    return [_as_response(r) for r in rows]


@router.get("/pending", response_model=list[AdminTeacherRequestResponse])
async def pending_requests(
    _admin: User = Depends(require_admin()),
    db: AsyncSession = Depends(get_db),
):
    rows = (await db.execute(
        select(TeacherRequest, User)
        .join(User, User.id == TeacherRequest.user_id)
        .where(TeacherRequest.status == "pending")
        .order_by(TeacherRequest.created_at)
    )).all()
    return [
        AdminTeacherRequestResponse(
            id=str(req.id), status=req.status, institution=req.institution, reason=req.reason,
            review_note=req.review_note, created_at=req.created_at, reviewed_at=req.reviewed_at,
            user_id=str(user.id), email=user.email, full_name=user.full_name,
        )
        for req, user in rows
    ]


async def _load_for_review(db: AsyncSession, request_id: uuid.UUID) -> tuple[TeacherRequest, User]:
    row = (await db.execute(
        select(TeacherRequest, User).join(User, User.id == TeacherRequest.user_id)
        .where(TeacherRequest.id == request_id)
    )).first()
    if row is None:
        raise HTTPException(404, detail="Yêu cầu không tồn tại")
    req, user = row
    if req.status != "pending":
        raise HTTPException(400, detail="Yêu cầu này đã được xử lý")
    return req, user


@router.post("/{request_id}/approve", response_model=TeacherRequestResponse)
async def approve_request(
    request_id: uuid.UUID,
    body: ReviewRequest,
    admin: User = Depends(require_admin()),
    db: AsyncSession = Depends(get_db),
):
    req, user = await _load_for_review(db, request_id)
    role = (await db.execute(select(Role).where(Role.name == "teacher"))).scalar_one_or_none()
    if role is None:
        raise HTTPException(500, detail="Vai trò giảng viên chưa được tạo trong hệ thống")
    already = (await db.execute(
        select(UserRole).where(UserRole.user_id == user.id, UserRole.role_id == role.id)
    )).scalar_one_or_none()
    if not already:
        db.add(UserRole(user_id=user.id, role_id=role.id, granted_by=admin.id))

    req.status = "approved"
    req.reviewed_by = admin.id
    req.review_note = body.note
    req.reviewed_at = datetime.now(tz=timezone.utc)
    await _notify(
        db, user.id, "teacher_request.approved",
        "Đã duyệt quyền tạo lớp học",
        "Bạn có thể tạo lớp và giao bài trên HeyStat.",
        {"request_id": str(req.id)},
    )
    return _as_response(req)


@router.post("/{request_id}/reject", response_model=TeacherRequestResponse)
async def reject_request(
    request_id: uuid.UUID,
    body: ReviewRequest,
    admin: User = Depends(require_admin()),
    db: AsyncSession = Depends(get_db),
):
    req, user = await _load_for_review(db, request_id)
    req.status = "rejected"
    req.reviewed_by = admin.id
    req.review_note = body.note
    req.reviewed_at = datetime.now(tz=timezone.utc)
    await _notify(
        db, user.id, "teacher_request.rejected",
        "Yêu cầu mở quyền tạo lớp chưa được duyệt",
        body.note or "Hãy liên hệ quản trị viên nếu cần làm rõ.",
        {"request_id": str(req.id)},
    )
    return _as_response(req)
