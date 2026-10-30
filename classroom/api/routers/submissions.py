"""Submissions router – nộp bài, nộp lại, chấm điểm."""
import io
import json
import uuid
import aiofiles
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel

from database import get_db
from models import Assignment, Submission, Enrollment, Class, Notification, User, UserRole, Role
from auth.deps import get_current_user
from config import get_settings
from services.auto_grader import auto_grade
from services.file_validator import validate_file_extension, validate_mime_type
from services.omv_reader import parse_omv

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


class OutputsRequest(BaseModel):
    selected: list[int]


class SubmissionResponse(BaseModel):
    id: str
    assignment_id: str
    student_id: str
    student_name: Optional[str] = None
    submitted_at: datetime
    is_final: bool
    score: Optional[float]
    feedback: Optional[str]
    file_path: Optional[str]
    answers: Optional[dict] = None
    auto_grade: Optional[dict] = None
    outputs: Optional[list] = None

    model_config = {"from_attributes": True}


def _without_marks(payload: SubmissionResponse) -> SubmissionResponse:
    """A student sees when they handed in, never the mark or the pass/fail detail.

    The teacher publishes điểm outside the app, so the numbers stay in the teacher
    and admin views only.
    """
    payload.score = None
    payload.feedback = None
    payload.auto_grade = None
    return payload


def _parse_json_field(raw: Optional[str], field: str) -> Optional[Any]:
    if raw in (None, ""):
        return None
    try:
        parsed = json.loads(raw)
    except ValueError:
        raise HTTPException(400, f"Trường {field} không phải JSON hợp lệ")
    if not isinstance(parsed, (dict, list)):
        raise HTTPException(400, f"Trường {field} phải là JSON object hoặc array")
    return parsed


_MAX_REPORT_CHARS = 4_000_000


def _read_outputs(data: bytes, report_html: Optional[str] = None) -> Optional[dict]:
    """Parse an uploaded .omv, or None when it is not a readable jamovi file.

    The results jamovi computed live inside the file itself, so a submission is
    gradeable from what arrived on disk.  ``report_html`` — the markup the
    student's browser rendered — is only a fallback for a document saved before
    any analysis ran, and it is never stored or displayed.
    """
    try:
        return parse_omv(data, html=report_html or None)
    except Exception:
        return None


def _table_rows(doc: dict) -> list[dict]:
    return [
        {"index": i, "analysis": t["analysis"], "title": t["title"],
         "columns": t["columns"], "rows": t["rows"], "notes": t.get("notes") or []}
        for i, t in enumerate(doc["tables"])
    ]


def _snapshot_payload(doc: dict, selected: Optional[list[int]]) -> dict:
    tables = _table_rows(doc)
    if selected is not None:
        keep = set(selected)
        tables = [t for t in tables if t["index"] in keep]
    return {
        "tables": tables,
        "modules": doc["modules"],
        "images": doc["images"],
        "synced_at": datetime.now(tz=timezone.utc).isoformat(),
    }


async def _create_submission(
    assignment_id: uuid.UUID,
    current_user: User,
    db: AsyncSession,
    file: Optional[UploadFile] = None,
    is_final: bool = True,
    answers: Optional[dict] = None,
    selected: Optional[list[int]] = None,
    report: Optional[str] = None,
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
    doc: Optional[dict] = None
    data: Optional[bytes] = None
    if report is not None and len(report) > _MAX_REPORT_CHARS:
        raise HTTPException(400, "Báo cáo kết quả vượt quá kích thước cho phép")
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
        doc = _read_outputs(data, report)

    tables = _table_rows(doc) if doc else []
    snapshot = _snapshot_payload(doc, selected) if doc else None

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
        session_snapshot=snapshot,
        answers=answers,
        is_final=is_final,
    )
    db.add(sub)

    grade: Optional[dict] = None
    if is_final and data is not None:
        grade = auto_grade(a, doc, answers)
        if grade:
            sub.score = grade["score"]
            sub.feedback = grade["feedback"]
            sub.auto_grade = grade
            sub.graded_at = now

    await db.flush()

    if is_final:
        await _notify(db, current_user.id, "submission.received",
                      "Đã nhận bài nộp",
                      f"Bài «{a.title}» đã được nộp thành công.")

    return _without_marks(SubmissionResponse(
        id=str(sub.id), assignment_id=str(sub.assignment_id),
        student_id=str(sub.student_id), submitted_at=sub.submitted_at,
        is_final=sub.is_final, score=float(sub.score) if sub.score is not None else None,
        feedback=sub.feedback, file_path=file_path,
        answers=answers, auto_grade=grade, outputs=tables or None,
    ))


async def _notify(db: AsyncSession, user_id: uuid.UUID, type_: str, title: str,
                  body: str, metadata: Optional[dict] = None) -> None:
    db.add(Notification(user_id=user_id, type=type_, title=title, body=body, metadata_=metadata))
    await db.flush()


def _doc_of_submission(sub: Submission) -> Optional[dict]:
    """Re-read a stored submission's .omv, or None when it is gone or unreadable."""
    if not sub.file_path:
        return None
    path = Path(settings.upload_dir) / sub.file_path
    if not path.is_file():
        return None
    return _read_outputs(path.read_bytes())


def _refresh_snapshot(sub: Submission, doc: dict) -> None:
    """Rebuild the evidence tables from the file, keeping what the student ticked.

    Older submissions were snapshotted from a browser report that rounded every
    number, or held nothing at all because the file could not be read then; their
    unticked evidence is restored by showing every table the file now yields.
    """
    old = sub.session_snapshot or {}
    fresh = _snapshot_payload(doc, None)
    chosen = {(t.get("analysis"), t.get("title")) for t in old.get("tables", [])}
    if chosen:
        fresh["tables"] = [t for t in fresh["tables"] if (t["analysis"], t["title"]) in chosen]
    sub.session_snapshot = fresh


def regrade_submission(assignment: Assignment, sub: Submission, doc: Optional[dict]) -> Optional[dict]:
    """Update one submission from its parsed file.

    Returns the new grade, or None when the submission must keep what it has:
    a teacher scored it by hand, the file cannot be read, or the assignment simply
    has no automatic criteria.
    """
    if sub.graded_by is not None or doc is None:
        return None
    _refresh_snapshot(sub, doc)
    grade = auto_grade(assignment, doc, sub.answers)
    if grade is None:
        return None
    sub.score = grade["score"]
    sub.feedback = grade["feedback"]
    sub.auto_grade = grade
    sub.graded_at = datetime.now(tz=timezone.utc)
    return grade


async def regrade_assignment(db: AsyncSession, assignment: Assignment) -> dict:
    """Re-run automatic grading over an assignment's final submissions.

    Called when the teacher edits the criteria, so a mark follows the rules that
    were actually in force, and from the admin endpoint to backfill submissions
    saved before the .omv could be read.
    """
    rows = await db.execute(
        select(Submission).where(
            Submission.assignment_id == assignment.id,
            Submission.is_final == True,
        )
    )
    regraded = skipped = unreadable = 0
    for sub in rows.scalars().all():
        if sub.graded_by is not None:
            skipped += 1
            continue
        doc = _doc_of_submission(sub)
        if doc is None:
            unreadable += 1
            continue
        if regrade_submission(assignment, sub, doc) is None:
            continue
        regraded += 1
    return {"regraded": regraded, "manual": skipped, "unreadable": unreadable}


@router.post("/assignments/{assignment_id}/submissions", status_code=201, response_model=SubmissionResponse)
async def submit(
    assignment_id: uuid.UUID,
    file: Optional[UploadFile] = File(None),
    answers: Optional[str] = Form(None),
    selected: Optional[str] = Form(None),
    report: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await _create_submission(
        assignment_id, current_user, db, file, is_final=True,
        answers=_parse_json_field(answers, "answers"),
        selected=_parse_json_field(selected, "selected"),
        report=report,
    )


@router.patch("/assignments/{assignment_id}/submissions/{submission_id}/outputs",
              response_model=SubmissionResponse)
async def choose_outputs(
    assignment_id: uuid.UUID, submission_id: uuid.UUID,
    body: OutputsRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Keep only the tables the student ticks as the evidence of their work."""
    r = await db.execute(
        select(Submission).where(
            Submission.id == submission_id,
            Submission.assignment_id == assignment_id,
            Submission.student_id == current_user.id,
        )
    )
    sub = r.scalar_one_or_none()
    if not sub:
        raise HTTPException(404, "Bài nộp không tồn tại")
    snapshot = sub.session_snapshot or {}
    all_tables = snapshot.get("tables", [])
    keep = set(body.selected)
    snapshot["tables"] = [t for t in all_tables if t.get("index") in keep]
    snapshot["available"] = all_tables
    sub.session_snapshot = snapshot
    await db.flush()
    return _without_marks(SubmissionResponse(
        id=str(sub.id), assignment_id=str(sub.assignment_id),
        student_id=str(sub.student_id), submitted_at=sub.submitted_at,
        is_final=sub.is_final, score=float(sub.score) if sub.score is not None else None,
        feedback=sub.feedback, file_path=sub.file_path,
        answers=sub.answers, auto_grade=sub.auto_grade,
        outputs=snapshot["tables"],
    ))


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
        _without_marks(SubmissionResponse(
            id=str(s.id), assignment_id=str(s.assignment_id),
            student_id=str(s.student_id), submitted_at=s.submitted_at,
            is_final=s.is_final, score=float(s.score) if s.score is not None else None,
            feedback=s.feedback, file_path=s.file_path,
            answers=s.answers, auto_grade=s.auto_grade,
        ))
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
    # Join with User to get student name
    from sqlalchemy import outerjoin
    stmt = (
        select(Submission, User.full_name, User.email)
        .outerjoin(User, User.id == Submission.student_id)
        .where(Submission.assignment_id == assignment_id, Submission.is_final == True)
    )
    rows = (await db.execute(stmt)).all()
    return [
        SubmissionResponse(
            id=str(s.id), assignment_id=str(s.assignment_id),
            student_id=str(s.student_id),
            student_name=full_name or email,
            submitted_at=s.submitted_at,
            is_final=s.is_final, score=float(s.score) if s.score is not None else None,
            feedback=s.feedback, file_path=s.file_path,
        )
        for s, full_name, email in rows
    ]


@router.post("/assignments/{assignment_id}/submissions/regrade")
async def regrade_submissions(
    assignment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Re-grade every submission against the criteria as they stand now."""
    a = await _get_assignment_or_404(db, assignment_id)
    cls_r = await db.execute(select(Class).where(Class.id == a.class_id))
    cls = cls_r.scalar_one_or_none()
    roles = await _get_user_roles(db, current_user.id)
    if "admin" not in roles and (not cls or cls.teacher_id != current_user.id):
        raise HTTPException(403, "Chỉ giáo viên mới chấm lại bài")
    return await regrade_assignment(db, a)


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
    payload = SubmissionResponse(
        id=str(sub.id), assignment_id=str(sub.assignment_id),
        student_id=str(sub.student_id), submitted_at=sub.submitted_at,
        is_final=sub.is_final, score=float(sub.score) if sub.score is not None else None,
        feedback=sub.feedback, file_path=sub.file_path,
        answers=sub.answers, auto_grade=sub.auto_grade,
        outputs=(sub.session_snapshot or {}).get("tables") or None,
    )
    return payload if is_teacher else _without_marks(payload)


@router.get("/submissions/{submission_id}/download")
async def download_submission(
    submission_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Hand the .omv a student submitted back to them or to their teacher."""
    r = await db.execute(select(Submission).where(Submission.id == submission_id))
    sub = r.scalar_one_or_none()
    if not sub:
        raise HTTPException(404, "Bài nộp không tồn tại")
    a = await _get_assignment_or_404(db, sub.assignment_id)
    cls_r = await db.execute(select(Class).where(Class.id == a.class_id))
    cls = cls_r.scalar_one()
    roles = await _get_user_roles(db, current_user.id)
    is_teacher = "admin" in roles or cls.teacher_id == current_user.id
    if not is_teacher and sub.student_id != current_user.id:
        raise HTTPException(403, "Không có quyền tải bài nộp này")
    if not sub.file_path:
        raise HTTPException(404, "Bài nộp không kèm file")
    path = Path(settings.upload_dir) / sub.file_path
    if not path.is_file():
        raise HTTPException(404, "File không tồn tại trên server")

    # Stored under a random uuid, so name it after the student for whoever downloads it
    ur = await db.execute(select(User.full_name).where(User.id == sub.student_id))
    student = ur.scalar_one_or_none() or str(sub.student_id)[:8]
    filename = f"{a.title} - {student}{path.suffix}"
    return FileResponse(str(path), filename=filename, media_type="application/octet-stream")


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
    await _notify(
        db, sub.student_id, "submission.graded",
        f"Giáo viên đã chấm bài «{a.title}»",
        "Kết quả do giáo viên công bố.",
        {"submission_id": str(sub.id)},
    )
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


class SubmitFromFileRequest(BaseModel):
    user_file_id: str


@router.post("/assignments/{assignment_id}/submissions/from_file", status_code=201, response_model=SubmissionResponse)
async def submit_from_file(
    assignment_id: uuid.UUID,
    body: SubmitFromFileRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Submit by referencing a file already in 'Tệp của tôi'.

    The file is copied into the submission folder so later edits to the student's
    own copy cannot rewrite the evidence they handed in.
    """
    from models import UserFile
    file_id = uuid.UUID(body.user_file_id)
    uf_r = await db.execute(select(UserFile).where(UserFile.id == file_id, UserFile.user_id == current_user.id))
    uf = uf_r.scalar_one_or_none()
    if not uf:
        raise HTTPException(404, "Không tìm thấy file trong Tệp của tôi")

    full_path = Path(settings.upload_dir) / uf.file_path
    if not full_path.exists():
        raise HTTPException(404, "File không tồn tại trên server")

    upload = UploadFile(filename=uf.file_name, file=io.BytesIO(full_path.read_bytes()))
    return await _create_submission(assignment_id, current_user, db, upload, is_final=True)
