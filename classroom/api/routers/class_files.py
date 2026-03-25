"""Class files router – upload, download, delete."""
import uuid
import os
import aiofiles
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from database import get_db
from models import Class, ClassFile, Enrollment, User, UserRole, Role
from auth.deps import get_current_user
from services.file_validator import validate_file_extension, validate_mime_type
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

    model_config = {"from_attributes": True}


@router.get("/classes/{class_id}/files", response_model=list[FileResponse_])
async def list_files(
    class_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cls = await _get_class_or_404(db, class_id)
    await _check_class_access(db, cls, current_user)
    r = await db.execute(select(ClassFile).where(ClassFile.class_id == class_id))
    files = r.scalars().all()
    return [FileResponse_(id=str(f.id), file_name=f.file_name, file_size=f.file_size,
                          mime_type=f.mime_type, created_at=str(f.created_at)) for f in files]


@router.post("/classes/{class_id}/files", status_code=201)
async def upload_file(
    class_id: uuid.UUID,
    file: UploadFile = File(...),
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
    )
    db.add(cf)
    await db.flush()
    return {"id": str(cf.id), "file_name": cf.file_name, "file_size": cf.file_size}


@router.get("/classes/{class_id}/files/{file_id}/download")
async def download_file(
    class_id: uuid.UUID,
    file_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cls = await _get_class_or_404(db, class_id)
    await _check_class_access(db, cls, current_user)
    r = await db.execute(
        select(ClassFile).where(ClassFile.id == file_id, ClassFile.class_id == class_id)
    )
    cf = r.scalar_one_or_none()
    if not cf:
        raise HTTPException(404, "File không tồn tại")
    full_path = Path(settings.upload_dir) / cf.file_path
    if not full_path.exists():
        raise HTTPException(404, "File không tồn tại trên server")
    return FileResponse(str(full_path), filename=cf.file_name)


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
