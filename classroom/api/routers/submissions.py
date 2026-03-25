"""Submissions router – nộp bài, nộp lại, chấm điểm."""
import uuid
import aiofiles
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel

from database import get_db
from models import Assignment, Submission, Enrollment, Class, User, UserRole, Role
from auth.deps import get_current_user
from config import get_settings
from services.file_validator import validate_file_extension, validate_mime_type

settings = get_settings()
router = APIRouter(tags=["submissions"])


async def _get_user_roles(db, user_id):
    r = await db.execute(
        select(Role.name).join(UserRole, UserRole.role_id == Role.id).where(UserRole.user_id == user_id)
    )
    return {row for (row,) in r.all()}


async def _get_assignment_or_404(db, assignment_id):
    r = await db.execute(select(Assignment).where(Assignment.id == assignment_id))
    a = r.scalar_one_or_none()
    if not a:
        raise HTTPException(404, "Bài tập không tồn tại")
    return a


async def _is_enrolled(db, class_id, user_id):
    r = await db.execute(
        select(Enrollment).where(
            Enrollment.class_id == class_id,
            Enrollment.user_id == user_id,
            Enrollment.status == "active",
        )
    )
    return r.scalar_one_or_none() is not None


class GradeRequest(BaseModel):
    score: float
    feedback: Optional[str] = None


class SubmissionResponse(BaseModel):
    id: str
    assignment_id: str
    student_id: str
    submitted_at: datetime
    is_final: bool
    score: Optional[float]
    feedback: Optional[str]
    file_path: Optional[str]

    model_config = {"from_attributes": True}


async def _create_submission(
    assignment_id: uuid.UUID,
    current_user: User,
    db: AsyncSession,
    file: Optional[UploadFile] = None,
    is_final: bool = True,
) -> SubmissionResponse:
    a = await _get_assignment_or_404(db, assignment_id)
    if not await _is_enrolled(db, a.class_id, current_user.id):
        raise HTTPException(403, "Bạn chưa tham gia lớp học này")

    # Deadline check (server-side)
    now = datetime.now(tz=timezone.utc)
    if is_final and now > a.deadline.replace(tzinfo=timezone.utc):
        raise HTTPException(403, "Đã quá hạn nộp bài")

    # Resubmit check
    if is_final and not a.allow_resubmit:
        existing_final = await db.execute(
            select(Submission).where(
                Submission.assignment_id == assignment_id,
                Submission.student_id == current_user.id,
                Submission.is_final == True,
            )
        )
        if existing_final.scalar_one_or_none():
            raise HTTPException(400, "Bài tập này không cho phép nộp lại")

    file_path: Optional[str] = None
    if file:
        if not validate_file_extension(file.filename or ""):
            raise HTTPException(400, "Định dạng file không được hỗ trợ")
        max_bytes = settings.max_file_size_mb * 1024 * 1024
        data = await file.read(max_bytes + 1)
        if len(data) > max_bytes:
            raise HTTPException(400, f"File vượt quá {settings.max_file_size_mb}MB")

        dest_dir = Path(settings.upload_dir) / "submissions" / str(assignment_id) / str(current_user.id)
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / f"{uuid.uuid4()}.omv"
        async with aiofiles.open(dest, "wb") as fp:
            await fp.write(data)
        file_path = str(dest.relative_to(settings.upload_dir))

    # Demote previous final
    if is_final:
        prev_finals = await db.execute(
            select(Submission).where(
                Submission.assignment_id == assignment_id,
                Submission.student_id == current_user.id,
                Submission.is_final == True,
            )
        )
        for s in prev_finals.scalars().all():
            s.is_final = False

    sub = Submission(
        assignment_id=assignment_id,
        student_id=current_user.id,
        file_path=file_path,
        is_final=is_final,
    )
    db.add(sub)
    await db.flush()
    return SubmissionResponse(
        id=str(sub.id), assignment_id=str(sub.assignment_id),
        student_id=str(sub.student_id), submitted_at=sub.submitted_at,
        is_final=sub.is_final, score=None, feedback=None, file_path=file_path,
    )


@router.post("/assignments/{assignment_id}/submissions", status_code=201, response_model=SubmissionResponse)
async def submit(
    assignment_id: uuid.UUID,
    file: Optional[UploadFile] = File(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await _create_submission(assignment_id, current_user, db, file, is_final=True)


@router.get("/assignments/{assignment_id}/submissions/my", response_model=list[SubmissionResponse])
async def my_submissions(
    assignment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    r = await db.execute(
        select(Submission).where(
            Submission.assignment_id == assignment_id,
            Submission.student_id == current_user.id,
        ).order_by(Submission.submitted_at.desc())
    )
    subs = r.scalars().all()
    return [
        SubmissionResponse(
            id=str(s.id), assignment_id=str(s.assignment_id),
            student_id=str(s.student_id), submitted_at=s.submitted_at,
            is_final=s.is_final, score=float(s.score) if s.score is not None else None,
            feedback=s.feedback, file_path=s.file_path,
        )
        for s in subs
    ]


@router.get("/assignments/{assignment_id}/submissions", response_model=list[SubmissionResponse])
async def all_submissions(
    assignment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    a = await _get_assignment_or_404(db, assignment_id)
    cls_r = await db.execute(select(Class).where(Class.id == a.class_id))
    cls = cls_r.scalar_one_or_none()
    roles = await _get_user_roles(db, current_user.id)
    if "admin" not in roles and cls.teacher_id != current_user.id:
        raise HTTPException(403, "Chỉ giáo viên mới xem được tất cả bài nộp")
    r = await db.execute(
        select(Submission).where(
            Submission.assignment_id == assignment_id,
            Submission.is_final == True,
        )
    )
    subs = r.scalars().all()
    return [
        SubmissionResponse(
            id=str(s.id), assignment_id=str(s.assignment_id),
            student_id=str(s.student_id), submitted_at=s.submitted_at,
            is_final=s.is_final, score=float(s.score) if s.score is not None else None,
            feedback=s.feedback, file_path=s.file_path,
        )
        for s in subs
    ]


@router.get("/assignments/{assignment_id}/submissions/{submission_id}", response_model=SubmissionResponse)
async def get_submission(
    assignment_id: uuid.UUID, submission_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    r = await db.execute(
        select(Submission).where(
            Submission.id == submission_id,
            Submission.assignment_id == assignment_id,
        )
    )
    sub = r.scalar_one_or_none()
    if not sub:
        raise HTTPException(404, "Bài nộp không tồn tại")
    roles = await _get_user_roles(db, current_user.id)
    a = await _get_assignment_or_404(db, assignment_id)
    cls_r = await db.execute(select(Class).where(Class.id == a.class_id))
    cls = cls_r.scalar_one()
    is_teacher = "admin" in roles or cls.teacher_id == current_user.id
    if not is_teacher and sub.student_id != current_user.id:
        raise HTTPException(403, "Không có quyền xem bài nộp này")
    return SubmissionResponse(
        id=str(sub.id), assignment_id=str(sub.assignment_id),
        student_id=str(sub.student_id), submitted_at=sub.submitted_at,
        is_final=sub.is_final, score=float(sub.score) if sub.score is not None else None,
        feedback=sub.feedback, file_path=sub.file_path,
    )


@router.post("/assignments/{assignment_id}/submissions/{submission_id}/grade")
async def grade_submission(
    assignment_id: uuid.UUID, submission_id: uuid.UUID,
    body: GradeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    a = await _get_assignment_or_404(db, assignment_id)
    cls_r = await db.execute(select(Class).where(Class.id == a.class_id))
    cls = cls_r.scalar_one()
    roles = await _get_user_roles(db, current_user.id)
    if "admin" not in roles and cls.teacher_id != current_user.id:
        raise HTTPException(403, "Không có quyền chấm điểm")
    r = await db.execute(
        select(Submission).where(Submission.id == submission_id, Submission.assignment_id == assignment_id)
    )
    sub = r.scalar_one_or_none()
    if not sub:
        raise HTTPException(404, "Bài nộp không tồn tại")
    sub.score = body.score
    sub.feedback = body.feedback
    sub.graded_by = current_user.id
    sub.graded_at = datetime.now(tz=timezone.utc)
    # Send notification (async task in production)
    return {"detail": "Chấm điểm thành công", "score": body.score}


@router.post("/assignments/{assignment_id}/submissions/{submission_id}/share")
async def share_submission(
    assignment_id: uuid.UUID, submission_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    a = await _get_assignment_or_404(db, assignment_id)
    if not a.allow_sharing:
        raise HTTPException(403, "Bài tập này không cho phép chia sẻ bài nộp")
    r = await db.execute(
        select(Submission).where(
            Submission.id == submission_id,
            Submission.student_id == current_user.id,
        )
    )
    sub = r.scalar_one_or_none()
    if not sub:
        raise HTTPException(404, "Bài nộp không tồn tại hoặc không phải của bạn")

    import secrets as _secrets
    from models import FileShare
    token = _secrets.token_hex(32)
    share = FileShare(
        file_id=submission_id,
        file_type="submission",
        shared_by=current_user.id,
        share_token=token,
        permission="view",
    )
    db.add(share)
    await db.flush()
    return {"share_url": f"/shared/{token}", "token": token}
