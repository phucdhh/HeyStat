"""Classes & Enrollment router."""
import uuid
import secrets
import string
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel, Field
from typing import Optional
import bcrypt as _bcrypt_lib

from database import get_db
from models import Class, Enrollment, User, UserRole, Role
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
    title: str
    description: Optional[str]
    max_students: int
    starts_at: datetime
    ends_at: datetime
    status: str
    created_at: datetime
    enrollment_key: Optional[str] = None  # only for teacher/admin

    model_config = {"from_attributes": True}


class EnrollRequest(BaseModel):
    enrollment_key: str


class StudentResponse(BaseModel):
    id: str
    email: str
    full_name: str
    enrolled_at: datetime
    status: str

    model_config = {"from_attributes": True}


# ─── helpers ────────────────────────────────────────────────────

def _generate_enrollment_key() -> str:
    chars = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(chars) for _ in range(8))


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
    for c in classes:
        d = ClassResponse(
            id=str(c.id), teacher_id=str(c.teacher_id), title=c.title,
            description=c.description, max_students=c.max_students,
            starts_at=c.starts_at, ends_at=c.ends_at, status=c.status,
            created_at=c.created_at,
        )
        if "admin" in roles or c.teacher_id == current_user.id:
            d.enrollment_key = None  # raw key not stored; teacher sees it only after creation
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
    plain_key = _generate_enrollment_key()
    hashed_key = _hash_key(plain_key)
    cls = Class(
        teacher_id=current_user.id,
        title=body.title,
        description=body.description,
        enrollment_key=hashed_key,
        max_students=body.max_students,
        starts_at=body.starts_at,
        ends_at=body.ends_at,
        status="draft",
    )
    db.add(cls)
    await db.flush()
    return {
        "id": str(cls.id),
        "title": cls.title,
        "enrollment_key": plain_key,  # shown once
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
    return ClassResponse(
        id=str(cls.id), teacher_id=str(cls.teacher_id), title=cls.title,
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
    return ClassResponse(
        id=str(cls.id), teacher_id=str(cls.teacher_id), title=cls.title,
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

    if not _verify_key(body.enrollment_key, cls.enrollment_key):
        raise HTTPException(status_code=400, detail="Enrollment key không đúng")

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


@router.get("/{class_id}/students", response_model=list[StudentResponse])
async def list_students(
    class_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
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
    return [
        StudentResponse(
            id=str(u.id), email=u.email, full_name=u.full_name,
            enrolled_at=ea, status=es,
        )
        for u, ea, es in rows
    ]


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


@router.post("/{class_id}/regenerate-key", response_model=dict)
async def regenerate_key(
    class_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cls = await _get_class_or_404(db, class_id)
    await _require_teacher_owns(db, cls, current_user)
    plain_key = _generate_enrollment_key()
    cls.enrollment_key = _hash_key(plain_key)
    return {"enrollment_key": plain_key}
