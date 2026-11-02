"""Classes & Enrollment router."""
import csv
import io
import re
import unicodedata
import uuid
import secrets
import string
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel, Field
from typing import Optional
import bcrypt as _bcrypt_lib

from database import get_db
from models import Assignment, Class, Enrollment, Submission, User, UserRole, Role
from auth.deps import get_current_user, require_teacher, require_admin

router = APIRouter(prefix="/classes", tags=["classes"])


def _hash_key(plain: str) -> str:
    return _bcrypt_lib.hashpw(plain.encode(), _bcrypt_lib.gensalt(rounds=12)).decode()


def _verify_key(plain: str, hashed: str) -> bool:
    return _bcrypt_lib.checkpw(plain.encode(), hashed.encode())


# ─── schemas ────────────────────────────────────────────────────

class ClassCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    max_students: int = 200
    starts_at: datetime
    ends_at: datetime
    enrollment_code: Optional[str] = None


class ClassUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    max_students: Optional[int] = None
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    status: Optional[str] = None


class ClassResponse(BaseModel):
    id: str
    teacher_id: str
    teacher_name: Optional[str] = None
    title: str
    description: Optional[str]
    max_students: int
    starts_at: datetime
    ends_at: datetime
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class EnrollRequest(BaseModel):
    enrollment_key: str


class StudentProgress(BaseModel):
    assignment_id: str
    title: str
    assignment_type: str
    deadline: datetime
    max_score: float
    # graded | submitted | missing | open
    state: str
    submitted_at: Optional[datetime] = None
    score: Optional[float] = None
    mistakes: Optional[int] = None
    synced_at: Optional[datetime] = None  # newest result snapshot not handed in yet

    model_config = {"from_attributes": True}


class StudentResponse(BaseModel):
    id: str
    email: str
    full_name: str
    enrolled_at: datetime
    status: str
    assignments_total: int
    submitted: int
    graded: int
    awaiting_grade: int
    missing: int
    average_score: Optional[float] = None
    score_pct: Optional[float] = None  # awarded / possible across the graded assignments
    last_activity: Optional[datetime] = None
    progress: list[StudentProgress]

    model_config = {"from_attributes": True}


# ─── helpers ────────────────────────────────────────────────────

def _generate_enrollment_key() -> str:
    chars = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(chars) for _ in range(8))


def _normalize_code(raw: Optional[str]) -> Optional[str]:
    """A teacher typing "xtsk 26" means XTSK26, so spaces and dashes carry no meaning."""
    if raw is None:
        return None
    code = re.sub(r"[\s\-_.]", "", raw).upper()
    if not re.fullmatch(r"[A-Z0-9]{4,16}", code):
        raise HTTPException(
            status_code=400,
            detail="Mã lớp phải dài 4–16 ký tự, chỉ gồm chữ Hoa A–Z và số 0–9",
        )
    return code


async def _code_taken(db: AsyncSession, code: str, exclude: Optional[uuid.UUID] = None) -> bool:
    q = select(Class.id).where(Class.enrollment_code == code)
    if exclude:
        q = q.where(Class.id != exclude)
    return (await db.execute(q)).scalar_one_or_none() is not None


async def _new_code(db: AsyncSession) -> str:
    for _ in range(5):
        code = _generate_enrollment_key()
        if not await _code_taken(db, code):
            return code
    raise HTTPException(status_code=500, detail="Không sinh được mã lớp, hãy thử lại")


async def _get_class_or_404(db: AsyncSession, class_id: uuid.UUID) -> Class:
    result = await db.execute(select(Class).where(Class.id == class_id))
    cls = result.scalar_one_or_none()
    if not cls:
        raise HTTPException(status_code=404, detail="Lớp học không tồn tại")
    return cls


async def _require_teacher_owns(db: AsyncSession, cls: Class, user: User) -> None:
    roles = await db.execute(
        select(Role.name).join(UserRole, UserRole.role_id == Role.id).where(UserRole.user_id == user.id)
    )
    role_names = {r for (r,) in roles.all()}
    if "admin" not in role_names and cls.teacher_id != user.id:
        raise HTTPException(status_code=403, detail="Không có quyền thực hiện")


async def _is_enrolled(db: AsyncSession, class_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    r = await db.execute(
        select(Enrollment).where(
            Enrollment.class_id == class_id,
            Enrollment.user_id == user_id,
            Enrollment.status == "active",
        )
    )
    return r.scalar_one_or_none() is not None


async def _get_user_roles_set(db: AsyncSession, user_id: uuid.UUID) -> set[str]:
    r = await db.execute(
        select(Role.name).join(UserRole, UserRole.role_id == Role.id).where(UserRole.user_id == user_id)
    )
    return {row for (row,) in r.all()}


async def _teacher_names(db: AsyncSession, teacher_ids: set[uuid.UUID]) -> dict[uuid.UUID, str]:
    if not teacher_ids:
        return {}
    r = await db.execute(
        select(User.id, func.coalesce(func.nullif(User.full_name, ""), User.email)).where(User.id.in_(teacher_ids))
    )
    return dict(r.all())


# ─── endpoints ──────────────────────────────────────────────────

@router.get("", response_model=list[ClassResponse])
async def list_classes(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    roles = await _get_user_roles_set(db, current_user.id)
    if "admin" in roles:
        result = await db.execute(select(Class))
        classes = result.scalars().all()
    elif "teacher" in roles:
        result = await db.execute(select(Class).where(Class.teacher_id == current_user.id))
        classes = result.scalars().all()
    else:
        # User/Student: return enrolled classes
        result = await db.execute(
            select(Class)
            .join(Enrollment, Enrollment.class_id == Class.id)
            .where(Enrollment.user_id == current_user.id, Enrollment.status == "active")
        )
        classes = result.scalars().all()

    responses = []
    names = await _teacher_names(db, {c.teacher_id for c in classes})
    for c in classes:
        d = ClassResponse(
            id=str(c.id), teacher_id=str(c.teacher_id),
            teacher_name=names.get(c.teacher_id),
            title=c.title,
            description=c.description, max_students=c.max_students,
            starts_at=c.starts_at, ends_at=c.ends_at, status=c.status,
            created_at=c.created_at,
        )
        responses.append(d)
    return responses


@router.post("", status_code=201, response_model=dict)
async def create_class(
    body: ClassCreate,
    current_user: User = Depends(require_teacher()),
    db: AsyncSession = Depends(get_db),
):
    if body.ends_at <= body.starts_at:
        raise HTTPException(status_code=400, detail="ends_at phải sau starts_at")
    code = _normalize_code(body.enrollment_code) or await _new_code(db)
    if await _code_taken(db, code):
        raise HTTPException(status_code=400, detail=f"Mã {code} đã có lớp khác đang dùng")
    cls = Class(
        teacher_id=current_user.id,
        title=body.title,
        description=body.description,
        enrollment_key=_hash_key(code),
        enrollment_code=code,
        max_students=body.max_students,
        starts_at=body.starts_at,
        ends_at=body.ends_at,
        status="active",
    )
    db.add(cls)
    await db.flush()
    return {
        "id": str(cls.id),
        "title": cls.title,
        "enrollment_code": code,
        "status": cls.status,
    }


@router.get("/{class_id}", response_model=ClassResponse)
async def get_class(
    class_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cls = await _get_class_or_404(db, class_id)
    roles = await _get_user_roles_set(db, current_user.id)
    is_teacher_owner = cls.teacher_id == current_user.id
    is_admin = "admin" in roles
    is_enrolled = await _is_enrolled(db, class_id, current_user.id)
    if not (is_teacher_owner or is_admin or is_enrolled):
        raise HTTPException(status_code=403, detail="Không có quyền xem lớp này")
    names = await _teacher_names(db, {cls.teacher_id})
    return ClassResponse(
        id=str(cls.id), teacher_id=str(cls.teacher_id),
        teacher_name=names.get(cls.teacher_id), title=cls.title,
        description=cls.description, max_students=cls.max_students,
        starts_at=cls.starts_at, ends_at=cls.ends_at, status=cls.status,
        created_at=cls.created_at,
    )


@router.patch("/{class_id}", response_model=ClassResponse)
async def update_class(
    class_id: uuid.UUID,
    body: ClassUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cls = await _get_class_or_404(db, class_id)
    await _require_teacher_owns(db, cls, current_user)
    for field, val in body.model_dump(exclude_none=True).items():
        setattr(cls, field, val)
    cls.updated_at = datetime.now(tz=timezone.utc)
    names = await _teacher_names(db, {cls.teacher_id})
    return ClassResponse(
        id=str(cls.id), teacher_id=str(cls.teacher_id),
        teacher_name=names.get(cls.teacher_id), title=cls.title,
        description=cls.description, max_students=cls.max_students,
        starts_at=cls.starts_at, ends_at=cls.ends_at, status=cls.status,
        created_at=cls.created_at,
    )


@router.delete("/{class_id}", status_code=204)
async def delete_class(
    class_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cls = await _get_class_or_404(db, class_id)
    await _require_teacher_owns(db, cls, current_user)
    cls.status = "archived"
    cls.updated_at = datetime.now(tz=timezone.utc)


@router.post("/{class_id}/enroll", status_code=201)
async def enroll(
    class_id: uuid.UUID,
    body: EnrollRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cls = await _get_class_or_404(db, class_id)
    if cls.status != "active":
        raise HTTPException(status_code=400, detail="Lớp học không ở trạng thái active")

    count_result = await db.execute(
        select(func.count(Enrollment.id)).where(Enrollment.class_id == class_id, Enrollment.status == "active")
    )
    count = count_result.scalar()
    if count >= cls.max_students:
        raise HTTPException(status_code=400, detail="Lớp học đã đầy")

    if not _verify_key(_normalize_code(body.enrollment_key), cls.enrollment_key):
        raise HTTPException(status_code=400, detail="Mã lớp không đúng")

    existing = await db.execute(
        select(Enrollment).where(Enrollment.class_id == class_id, Enrollment.user_id == current_user.id)
    )
    enr = existing.scalar_one_or_none()
    if enr:
        if enr.status == "active":
            raise HTTPException(status_code=400, detail="Bạn đã tham gia lớp học này")
        enr.status = "active"
    else:
        db.add(Enrollment(class_id=class_id, user_id=current_user.id))
    return {"detail": "Tham gia lớp học thành công"}


@router.delete("/{class_id}/enroll", status_code=204)
async def leave_class(
    class_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Enrollment).where(
            Enrollment.class_id == class_id,
            Enrollment.user_id == current_user.id,
        )
    )
    enr = result.scalar_one_or_none()
    if not enr:
        raise HTTPException(status_code=404, detail="Bạn không tham gia lớp học này")
    enr.status = "dropped"


def _student_progress(
    assignments: list[Assignment],
    subs: list[Submission],
    enrolled_at: datetime,
    now: datetime,
) -> dict:
    """One student's per-assignment status, plus the roll-ups the tab shows."""
    by_assignment: dict[uuid.UUID, list[Submission]] = {}
    for s in subs:
        by_assignment.setdefault(s.assignment_id, []).append(s)

    items: list[StudentProgress] = []
    for a in sorted(assignments, key=lambda a: a.deadline):
        mine = by_assignment.get(a.id, [])
        final = max((s for s in mine if s.is_final), key=lambda s: s.submitted_at, default=None)
        synced = max((s for s in mine if not s.is_final), key=lambda s: s.submitted_at, default=None)
        if final:
            state = "graded" if final.score is not None else "submitted"
        elif now > a.deadline.replace(tzinfo=timezone.utc):
            state = "missing"
        else:
            state = "open"
        grade = final.auto_grade or {} if final else {}
        items.append(StudentProgress(
            assignment_id=str(a.id), title=a.title, assignment_type=a.assignment_type,
            deadline=a.deadline, max_score=float(a.max_score), state=state,
            submitted_at=final.submitted_at if final else None,
            score=float(final.score) if final and final.score is not None else None,
            mistakes=grade.get("mistake_count") if grade else None,
            synced_at=synced.submitted_at if synced else None,
        ))

    graded = [i for i in items if i.score is not None]
    possible = sum(i.max_score for i in graded)
    activity = [enrolled_at] + [i.submitted_at or i.synced_at for i in items
                                if i.submitted_at or i.synced_at]
    return {
        "assignments_total": len(items),
        "submitted": len([i for i in items if i.state in ("graded", "submitted")]),
        "graded": len(graded),
        "awaiting_grade": len([i for i in items if i.state == "submitted"]),
        "missing": len([i for i in items if i.state == "missing"]),
        "average_score": round(sum(i.score for i in graded) / len(graded), 2) if graded else None,
        "score_pct": round(sum(i.score for i in graded) / possible * 100, 1) if possible else None,
        "last_activity": max(activity),
        "progress": items,
    }


@router.get("/{class_id}/students", response_model=list[StudentResponse])
async def list_students(
    class_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    students, _ = await _roster(db, class_id, current_user)
    return students


async def _roster(
    db: AsyncSession, class_id: uuid.UUID, current_user: User
) -> tuple[list[StudentResponse], list[Assignment]]:
    """The members tab and its CSV export must say the same thing, so they read
    from one place. Also returns the class assignments, for the per-assignment columns."""
    cls = await _get_class_or_404(db, class_id)
    roles = await _get_user_roles_set(db, current_user.id)
    if "admin" not in roles and cls.teacher_id != current_user.id:
        raise HTTPException(status_code=403, detail="Không có quyền xem danh sách sinh viên")

    result = await db.execute(
        select(User, Enrollment.enrolled_at, Enrollment.status)
        .join(Enrollment, Enrollment.user_id == User.id)
        .where(Enrollment.class_id == class_id)
    )
    rows = result.all()
    student_ids = {u.id for u, _, _ in rows}

    assignments = (await db.execute(
        select(Assignment).where(Assignment.class_id == class_id).order_by(Assignment.deadline)
    )).scalars().all()
    submissions = (await db.execute(
        select(Submission).where(
            Submission.assignment_id.in_({a.id for a in assignments} or {uuid.UUID(int=0)}),
            Submission.student_id.in_(student_ids or {uuid.UUID(int=0)}),
        )
    )).scalars().all()

    now = datetime.now(tz=timezone.utc)
    students = [
        StudentResponse(
            id=str(u.id), email=u.email, full_name=u.full_name,
            enrolled_at=ea, status=es,
            **_student_progress(
                assignments,
                [s for s in submissions if s.student_id == u.id],
                ea,
                now,
            ),
        )
        for u, ea, es in rows
    ]
    return students, assignments


# The teacher opens this CSV in Excel and reads it as VN wall-clock time.
VN_TZ = timezone(timedelta(hours=7))


def _ascii_slug(text: str) -> str:
    """Turn a Vietnamese class title into an ASCII, header-safe download name."""
    stripped = "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")
    return re.sub(r"[^A-Za-z0-9]+", "_", stripped).strip("_")


def _fmt_dt(value: Optional[datetime]) -> str:
    if not value:
        return ""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(VN_TZ).strftime("%d/%m/%Y %H:%M")


def _progress_cell(p: StudentProgress) -> str:
    if p.score is not None:
        when = f" (nộp {_fmt_dt(p.submitted_at)})" if p.submitted_at else ""
        return f"đã chấm {p.score}/{p.max_score}{when}"
    if p.state == "submitted":
        return f"đã nộp, chờ chấm ({_fmt_dt(p.submitted_at)})"
    if p.state == "missing":
        return f"chưa nộp – quá hạn ({_fmt_dt(p.deadline)})"
    return "chưa tới hạn"


@router.get("/{class_id}/students/export")
async def export_students(
    class_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    students, assignments = await _roster(db, class_id, current_user)

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        ["Họ tên", "Email", "Ngày tham gia", "Trạng thái", "Số bài", "Đã nộp",
         "Đã chấm", "Chờ chấm", "Nợ bài", "Điểm TB", "% điểm", "Hoạt động cuối"]
        + [a.title for a in assignments]
    )
    for s in students:
        by_assignment = {p.assignment_id: p for p in s.progress}
        writer.writerow(
            [s.full_name, s.email, _fmt_dt(s.enrolled_at), s.status,
             s.assignments_total, s.submitted, s.graded, s.awaiting_grade, s.missing,
             "" if s.average_score is None else s.average_score,
             "" if s.score_pct is None else s.score_pct,
             _fmt_dt(s.last_activity)]
            + [_progress_cell(by_assignment[str(a.id)]) if str(a.id) in by_assignment else "" for a in assignments]
        )

    cls_r = await db.execute(select(Class).where(Class.id == class_id))
    cls = cls_r.scalar_one()
    file_name = f"hoc_vien_{_ascii_slug(cls.title) or str(class_id)}.csv"
    return Response(
        # utf-8-sig prepends the BOM Excel needs to read Vietnamese
        content=buf.getvalue().encode("utf-8-sig"),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{file_name}"'},
    )


@router.delete("/{class_id}/students/{user_id}", status_code=204)
async def remove_student(
    class_id: uuid.UUID,
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cls = await _get_class_or_404(db, class_id)
    await _require_teacher_owns(db, cls, current_user)
    result = await db.execute(
        select(Enrollment).where(Enrollment.class_id == class_id, Enrollment.user_id == user_id)
    )
    enr = result.scalar_one_or_none()
    if not enr:
        raise HTTPException(status_code=404, detail="Sinh viên không tham gia lớp này")
    enr.status = "dropped"


@router.get("/{class_id}/enrollment-code", response_model=dict)
async def read_enrollment_code(
    class_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """The code students type in, for the teacher who owns the class.

    Classes created before enrollment_code existed hold only the bcrypt hash,
    so for those the teacher has to set a code once.
    """
    cls = await _get_class_or_404(db, class_id)
    await _require_teacher_owns(db, cls, current_user)
    return {"enrollment_code": cls.enrollment_code}


class EnrollmentCodeBody(BaseModel):
    enrollment_code: Optional[str] = None


@router.put("/{class_id}/enrollment-code", response_model=dict)
async def set_enrollment_code(
    class_id: uuid.UUID,
    body: EnrollmentCodeBody,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Set the class code, or generate a random one when the body is empty.

    enrollment_key is what a join is checked against and enrollment_code is the
    copy the teacher reads back, so both move together or a student would be
    turned away with the code shown on their teacher's screen."""
    cls = await _get_class_or_404(db, class_id)
    await _require_teacher_owns(db, cls, current_user)
    code = _normalize_code(body.enrollment_code) or await _new_code(db)
    if await _code_taken(db, code, exclude=class_id):
        raise HTTPException(status_code=400, detail=f"Mã {code} đã có lớp khác đang dùng")
    cls.enrollment_code = code
    cls.enrollment_key = _hash_key(code)
    return {"enrollment_code": code}


class JoinRequest(BaseModel):
    enrollment_key: str


@router.post("/join", status_code=201)
async def join_by_key(
    body: JoinRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Join a class using only the enrollment code (no class_id needed)."""
    code = _normalize_code(body.enrollment_key)
    matched = (await db.execute(
        select(Class).where(Class.status == "active", Class.enrollment_code == code)
    )).scalar_one_or_none()

    if matched is None:
        # A class with no readable copy can only be matched against its hash.
        r = await db.execute(select(Class).where(
            Class.status == "active", Class.enrollment_code.is_(None)
        ))
        for cls in r.scalars():
            if cls.enrollment_key and _verify_key(code, cls.enrollment_key):
                matched = cls
                break

    if matched is None:
        raise HTTPException(status_code=400, detail="Mã lớp không đúng hoặc lớp đã đóng")

    class_id = matched.id

    count_result = await db.execute(
        select(func.count(Enrollment.id)).where(
            Enrollment.class_id == class_id, Enrollment.status == "active"
        )
    )
    if (count_result.scalar() or 0) >= matched.max_students:
        raise HTTPException(status_code=400, detail="Lớp học đã đầy")

    existing = await db.execute(
        select(Enrollment).where(
            Enrollment.class_id == class_id,
            Enrollment.user_id == current_user.id,
        )
    )
    enr = existing.scalar_one_or_none()
    if enr:
        if enr.status == "active":
            raise HTTPException(status_code=400, detail="Bạn đã tham gia lớp học này")
        enr.status = "active"
    else:
        db.add(Enrollment(class_id=class_id, user_id=current_user.id))

    return {"detail": "Tham gia lớp học thành công", "class_id": str(class_id), "title": matched.title}

