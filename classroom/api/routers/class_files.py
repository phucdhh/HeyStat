"""Class files router – upload, download, delete."""
import uuid
import os
import secrets
import aiofiles
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from database import get_db
from models import Class, ClassFile, Enrollment, User, UserRole, Role
from auth.deps import get_current_user
from services.file_validator import validate_file_extension, validate_mime_type
from services.assignment_access import closed_file_ids, require_file_open
from config import get_settings

settings = get_settings()
router = APIRouter(tags=["class-files"])


async def _get_user_roles_set(db: AsyncSession, user_id: uuid.UUID) -> set[str]:
    from sqlalchemy import select
    r = await db.execute(
        select(Role.name).join(UserRole, UserRole.role_id == Role.id).where(UserRole.user_id == user_id)
    )
    return {row for (row,) in r.all()}


async def _get_class_or_404(db, class_id):
    r = await db.execute(select(Class).where(Class.id == class_id))
    cls = r.scalar_one_or_none()
    if not cls:
        raise HTTPException(404, "Lớp học không tồn tại")
    return cls


async def _check_class_access(db, cls, user):
    roles = await _get_user_roles_set(db, user.id)
    if "admin" in roles or cls.teacher_id == user.id:
        return "teacher"
    r = await db.execute(
        select(Enrollment).where(
            Enrollment.class_id == cls.id,
            Enrollment.user_id == user.id,
            Enrollment.status == "active",
        )
    )
    if r.scalar_one_or_none():
        return "student"
    raise HTTPException(403, "Không có quyền truy cập lớp học này")


class FileResponse_(BaseModel):
    id: str
    file_name: str
    file_size: Optional[int]
    mime_type: Optional[str]
    created_at: str
    student_access: bool
    is_locked: bool

    model_config = {"from_attributes": True}


@router.get("/classes/{class_id}/files", response_model=list[FileResponse_])
async def list_files(
    class_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cls = await _get_class_or_404(db, class_id)
    access = await _check_class_access(db, cls, current_user)
    r = await db.execute(select(ClassFile).where(ClassFile.class_id == class_id))
    files = r.scalars().all()
    if access != "teacher":
        # Draft exam uploads are not even named to students until the teacher opens one.
        files = [f for f in files if f.student_access]
    closed = await closed_file_ids(db, class_id)
    return [FileResponse_(id=str(f.id), file_name=f.file_name, file_size=f.file_size,
                          mime_type=f.mime_type, created_at=str(f.created_at),
                          student_access=f.student_access,
                          is_locked=not f.student_access or f.id in closed) for f in files]


@router.post("/classes/{class_id}/files", status_code=201)
async def upload_file(
    class_id: uuid.UUID,
    file: UploadFile = File(...),
    student_access: bool = Form(True),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cls = await _get_class_or_404(db, class_id)
    roles = await _get_user_roles_set(db, current_user.id)
    if "admin" not in roles and cls.teacher_id != current_user.id:
        raise HTTPException(403, "Chỉ giáo viên mới có thể upload file")

    if not validate_file_extension(file.filename or ""):
        raise HTTPException(400, "Định dạng file không được hỗ trợ")

    # Read and validate
    max_bytes = settings.max_file_size_mb * 1024 * 1024
    data = await file.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise HTTPException(400, f"File vượt quá giới hạn {settings.max_file_size_mb}MB")
    if not validate_mime_type(data):
        raise HTTPException(400, "Loại file không hợp lệ")

    # Save to disk
    dest_dir = Path(settings.upload_dir) / "class" / str(class_id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    safe_name = Path(file.filename or "upload").name
    dest_path = dest_dir / f"{uuid.uuid4()}_{safe_name}"
    async with aiofiles.open(dest_path, "wb") as fp:
        await fp.write(data)

    cf = ClassFile(
        class_id=class_id,
        uploaded_by=current_user.id,
        file_name=safe_name,
        file_path=str(dest_path.relative_to(settings.upload_dir)),
        file_size=len(data),
        mime_type=file.content_type,
        student_access=student_access,
    )
    db.add(cf)
    await db.flush()
    return {"id": str(cf.id), "file_name": cf.file_name, "file_size": cf.file_size,
            "student_access": cf.student_access, "is_locked": not cf.student_access}


class FileAccessUpdate(BaseModel):
    student_access: bool


@router.patch("/classes/{class_id}/files/{file_id}")
async def update_file_access(
    class_id: uuid.UUID,
    file_id: uuid.UUID,
    body: FileAccessUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cls = await _get_class_or_404(db, class_id)
    if await _check_class_access(db, cls, current_user) != "teacher":
        raise HTTPException(403, "Chỉ giáo viên mới được mở hoặc khoá tệp")
    result = await db.execute(select(ClassFile).where(ClassFile.id == file_id, ClassFile.class_id == class_id))
    cf = result.scalar_one_or_none()
    if cf is None:
        raise HTTPException(404, "Tệp không tồn tại")
    closed = await closed_file_ids(db, class_id)
    if body.student_access and cf.id in closed:
        raise HTTPException(409, "Tệp thuộc bài đang khoá. Hãy mở bài trước khi mở tệp.")
    cf.student_access = body.student_access
    return {"student_access": cf.student_access, "is_locked": not cf.student_access or cf.id in closed}


@router.get("/classes/{class_id}/files/{file_id}/download")
async def download_file(
    class_id: uuid.UUID,
    file_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cls = await _get_class_or_404(db, class_id)
    access = await _check_class_access(db, cls, current_user)
    r = await db.execute(
        select(ClassFile).where(ClassFile.id == file_id, ClassFile.class_id == class_id)
    )
    cf = r.scalar_one_or_none()
    if not cf:
        raise HTTPException(404, "File không tồn tại")
    if access != "teacher":
        await require_file_open(db, cf)
    full_path = Path(settings.upload_dir) / cf.file_path
    if not full_path.exists():
        raise HTTPException(404, "File không tồn tại trên server")
    return FileResponse(str(full_path), filename=cf.file_name, headers={"Cache-Control": "no-store"})


@router.get("/classes/{class_id}/files/{file_id}/omv-schema")
async def preview_file_schema(
    class_id: uuid.UUID,
    file_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """The analyses/tables a ``.omv`` already contains, before it is an assignment.

    Teachers build an assignment around a solved example file, so the check
    pickers must work while the assignment does not exist yet. Same payload as
    ``/assignments/{id}/grading-schema``.
    """
    cls = await _get_class_or_404(db, class_id)
    roles = await _get_user_roles_set(db, current_user.id)
    if "admin" not in roles and cls.teacher_id != current_user.id:
        raise HTTPException(403, "Chỉ giáo viên mới đọc được cấu trúc tệp")
    r = await db.execute(
        select(ClassFile).where(ClassFile.id == file_id, ClassFile.class_id == class_id)
    )
    cf = r.scalar_one_or_none()
    if not cf:
        raise HTTPException(404, "Tệp không tồn tại")

    from services.omv_reader import grading_schema, parse_omv

    # A .sav/.csv/.xlsx dataset opens fine in jamovi but holds no analyses — only a
    # saved jamovi workbook does. Answering empty lets the form fall back to typing
    # the names in; 422 would read as "your data file is broken", which it is not.
    if Path(cf.file_name).suffix.lower() != ".omv":
        return {"file_name": cf.file_name, "analyses": []}

    full_path = Path(settings.upload_dir) / cf.file_path
    if not full_path.is_file():
        raise HTTPException(404, "Tệp không tồn tại trên server")
    try:
        doc = parse_omv(full_path.read_bytes())
    except Exception as exc:
        raise HTTPException(422, f"Không đọc được bảng kết quả từ file này: {exc}")

    return {"file_name": cf.file_name, "analyses": grading_schema(doc)}


@router.delete("/classes/{class_id}/files/{file_id}", status_code=204)
async def delete_file(
    class_id: uuid.UUID,
    file_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cls = await _get_class_or_404(db, class_id)
    roles = await _get_user_roles_set(db, current_user.id)
    if "admin" not in roles and cls.teacher_id != current_user.id:
        raise HTTPException(403, "Không có quyền xoá file")
    r = await db.execute(
        select(ClassFile).where(ClassFile.id == file_id, ClassFile.class_id == class_id)
    )
    cf = r.scalar_one_or_none()
    if not cf:
        raise HTTPException(404, "File không tồn tại")
    full_path = Path(settings.upload_dir) / cf.file_path
    if full_path.exists():
        full_path.unlink(missing_ok=True)
    await db.delete(cf)


@router.post("/classes/{class_id}/files/{file_id}/open-url", status_code=201)
async def get_file_open_url(
    class_id: uuid.UUID,
    file_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return a short-lived one-time URL so Jamovi can fetch the file without JWT."""
    cls = await _get_class_or_404(db, class_id)
    access = await _check_class_access(db, cls, current_user)
    r = await db.execute(
        select(ClassFile).where(ClassFile.id == file_id, ClassFile.class_id == class_id)
    )
    cf = r.scalar_one_or_none()
    if not cf:
        raise HTTPException(404, "File không tồn tại")

    if access != "teacher":
        await require_file_open(db, cf)
    from auth.redis_client import get_redis
    token = secrets.token_hex(24)
    r_client = await get_redis()
    await r_client.setex(f"file_ot_access:{token}", 300, f"{cf.id}|{current_user.id}")
    return {"token": token, "filename": cf.file_name}


@router.get("/files/ot/{token}")
async def one_time_download(
    token: str,
    db: AsyncSession = Depends(get_db),
):
    """No-auth one-time download – Jamovi fetches from this URL to open the file."""
    from auth.redis_client import get_redis
    r_client = await get_redis()
    token_data = await r_client.getdel(f"file_ot_access:{token}")
    if not token_data:
        raise HTTPException(404, "Token không hợp lệ hoặc đã hết hạn")
    try:
        parts = (token_data if isinstance(token_data, str) else token_data.decode()).split("|")
        file_id, user_id = (uuid.UUID(part) for part in parts)
    except (ValueError, UnicodeDecodeError):
        raise HTTPException(404, "Token không hợp lệ")
    r = await db.execute(select(ClassFile).where(ClassFile.id == file_id))
    cf = r.scalar_one_or_none()
    if not cf:
        raise HTTPException(404, "File không tồn tại")
    r = await db.execute(select(User).where(User.id == user_id, User.is_active.is_(True)))
    user = r.scalar_one_or_none()
    if user is None:
        raise HTTPException(403, "Tài khoản không còn quyền truy cập")
    cls = await _get_class_or_404(db, cf.class_id)
    if await _check_class_access(db, cls, user) != "teacher":
        await require_file_open(db, cf)
    full_path = Path(settings.upload_dir) / cf.file_path
    if not full_path.is_file():
        raise HTTPException(404, "File không tồn tại trên server")
    return FileResponse(str(full_path), filename=cf.file_name, headers={"Cache-Control": "no-store"})
