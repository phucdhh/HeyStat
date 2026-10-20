"""My Files + File Sharing router (Phase 8-9)."""
import uuid
import secrets
import aiofiles
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Response
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel

from database import get_db
from models import UserFile, FileShare, Submission, User, UserRole, Role
from auth.deps import get_current_user
from services.file_validator import validate_file_extension, validate_mime_type
from auth.redis_client import get_redis
from config import get_settings

settings = get_settings()
router = APIRouter(prefix="/files", tags=["my-files"])
shared_router = APIRouter(tags=["sharing"])


# ─── schemas ────────────────────────────────────────────────────

class FileResponse_(BaseModel):
    id: str
    file_name: str
    file_size: Optional[int]
    description: Optional[str]
    is_public: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class FileUpdate(BaseModel):
    file_name: Optional[str] = None
    description: Optional[str] = None
    is_public: Optional[bool] = None


class ShareRequest(BaseModel):
    expires_at: Optional[datetime] = None


class ShareResponse(BaseModel):
    share_url: str
    token: str
    expires_at: Optional[datetime]


# ─── helpers ────────────────────────────────────────────────────

async def _get_user_roles(db, user_id):
    r = await db.execute(
        select(Role.name).join(UserRole, UserRole.role_id == Role.id).where(UserRole.user_id == user_id)
    )
    return {row for (row,) in r.all()}


async def _check_user_quota(db: AsyncSession, user_id: uuid.UUID) -> None:
    count_r = await db.execute(select(func.count(UserFile.id)).where(UserFile.user_id == user_id))
    count = count_r.scalar()
    if count >= settings.max_user_files:
        raise HTTPException(400, f"Đã đạt giới hạn {settings.max_user_files} file")

    size_r = await db.execute(select(func.sum(UserFile.file_size)).where(UserFile.user_id == user_id))
    total_size = size_r.scalar() or 0
    max_bytes = settings.max_user_storage_mb * 1024 * 1024
    if total_size >= max_bytes:
        raise HTTPException(400, f"Đã hết dung lượng lưu trữ ({settings.max_user_storage_mb}MB)")


# ─── My Files CRUD ──────────────────────────────────────────────

@router.get("", response_model=list[FileResponse_])
async def list_my_files(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    r = await db.execute(
        select(UserFile).where(UserFile.user_id == current_user.id).order_by(UserFile.created_at.desc())
    )
    files = r.scalars().all()
    return [
        FileResponse_(id=str(f.id), file_name=f.file_name, file_size=f.file_size,
                      description=f.description, is_public=f.is_public, created_at=f.created_at)
        for f in files
    ]


@router.post("", status_code=201, response_model=FileResponse_)
async def upload_my_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _check_user_quota(db, current_user.id)

    if not validate_file_extension(file.filename or ""):
        raise HTTPException(400, "Định dạng file không được hỗ trợ")

    max_bytes = settings.max_file_size_mb * 1024 * 1024
    data = await file.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise HTTPException(400, f"File vượt quá giới hạn {settings.max_file_size_mb}MB")
    if not validate_mime_type(data):
        raise HTTPException(400, "Loại file không hợp lệ")

    dest_dir = Path(settings.upload_dir) / "myfiles" / str(current_user.id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    safe_name = Path(file.filename or "upload").name
    dest = dest_dir / f"{uuid.uuid4()}_{safe_name}"
    async with aiofiles.open(dest, "wb") as fp:
        await fp.write(data)

    uf = UserFile(
        user_id=current_user.id,
        file_name=safe_name,
        file_path=str(dest.relative_to(settings.upload_dir)),
        file_size=len(data),
    )
    db.add(uf)
    await db.flush()
    return FileResponse_(id=str(uf.id), file_name=uf.file_name, file_size=uf.file_size,
                         description=None, is_public=False, created_at=uf.created_at)


@router.get("/{file_id}", response_model=FileResponse_)
async def get_my_file(
    file_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    r = await db.execute(select(UserFile).where(UserFile.id == file_id, UserFile.user_id == current_user.id))
    uf = r.scalar_one_or_none()
    if not uf:
        raise HTTPException(404, "File không tồn tại")
    return FileResponse_(id=str(uf.id), file_name=uf.file_name, file_size=uf.file_size,
                         description=uf.description, is_public=uf.is_public, created_at=uf.created_at)


@router.patch("/{file_id}", response_model=FileResponse_)
async def update_my_file(
    file_id: uuid.UUID, body: FileUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    r = await db.execute(select(UserFile).where(UserFile.id == file_id, UserFile.user_id == current_user.id))
    uf = r.scalar_one_or_none()
    if not uf:
        raise HTTPException(404, "File không tồn tại")
    for field, val in body.model_dump(exclude_none=True).items():
        setattr(uf, field, val)
    uf.updated_at = datetime.now(tz=timezone.utc)
    return FileResponse_(id=str(uf.id), file_name=uf.file_name, file_size=uf.file_size,
                         description=uf.description, is_public=uf.is_public, created_at=uf.created_at)


@router.delete("/{file_id}", status_code=204)
async def delete_my_file(
    file_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    r = await db.execute(select(UserFile).where(UserFile.id == file_id, UserFile.user_id == current_user.id))
    uf = r.scalar_one_or_none()
    if not uf:
        raise HTTPException(404)
    # Delete physical file
    full_path = Path(settings.upload_dir) / uf.file_path
    full_path.unlink(missing_ok=True)
    await db.delete(uf)


@router.put("/{file_id}", response_model=FileResponse_)
async def replace_my_file(
    file_id: uuid.UUID,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Replace the content of an existing file (overwrite)."""
    r = await db.execute(select(UserFile).where(UserFile.id == file_id, UserFile.user_id == current_user.id))
    uf = r.scalar_one_or_none()
    if not uf:
        raise HTTPException(404, "File không tồn tại")

    if not validate_file_extension(file.filename or uf.file_name):
        raise HTTPException(400, "Định dạng file không được hỗ trợ")

    max_bytes = settings.max_file_size_mb * 1024 * 1024
    data = await file.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise HTTPException(400, f"File vượt quá giới hạn {settings.max_file_size_mb}MB")
    if not validate_mime_type(data):
        raise HTTPException(400, "Loại file không hợp lệ")

    full_path = Path(settings.upload_dir) / uf.file_path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    async with aiofiles.open(full_path, "wb") as fp:
        await fp.write(data)

    uf.file_size = len(data)
    uf.updated_at = datetime.now(tz=timezone.utc)
    return FileResponse_(id=str(uf.id), file_name=uf.file_name, file_size=uf.file_size,
                         description=uf.description, is_public=uf.is_public, created_at=uf.created_at)


@router.get("/{file_id}/open")
async def open_my_file(
    file_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the raw .omv file so the browser can POST it to Jamovi's /open endpoint."""
    r = await db.execute(select(UserFile).where(UserFile.id == file_id, UserFile.user_id == current_user.id))
    uf = r.scalar_one_or_none()
    if not uf:
        raise HTTPException(404)
    full_path = Path(settings.upload_dir) / uf.file_path
    if not full_path.exists():
        raise HTTPException(404, "File không tồn tại trên server")
    return FileResponse(
        path=str(full_path),
        filename=uf.file_name,
        media_type="application/octet-stream",
    )


# ─── Sharing ────────────────────────────────────────────────────

@router.post("/{file_id}/share", response_model=ShareResponse)
async def create_share(
    file_id: uuid.UUID,
    body: ShareRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    r = await db.execute(select(UserFile).where(UserFile.id == file_id, UserFile.user_id == current_user.id))
    uf = r.scalar_one_or_none()
    if not uf:
        raise HTTPException(404)
    token = secrets.token_hex(32)
    share = FileShare(
        file_id=file_id,
        file_type="user_file",
        shared_by=current_user.id,
        share_token=token,
        permission="view",
        expires_at=body.expires_at,
    )
    db.add(share)
    await db.flush()
    return ShareResponse(share_url=f"/shared/{token}", token=token, expires_at=body.expires_at)


@router.delete("/{file_id}/share", status_code=204)
async def revoke_share(
    file_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    r = await db.execute(
        select(FileShare).where(
            FileShare.file_id == file_id,
            FileShare.shared_by == current_user.id,
            FileShare.file_type == "user_file",
        )
    )
    share = r.scalar_one_or_none()
    if share:
        await db.delete(share)


# ─── Public shared view ──────────────────────────────────────────

@shared_router.get("/shared/{token}")
async def view_shared(
    token: str,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    r = await db.execute(select(FileShare).where(FileShare.share_token == token))
    share = r.scalar_one_or_none()
    if not share:
        raise HTTPException(404, "Link chia sẻ không tồn tại hoặc đã bị thu hồi")
    now = datetime.now(tz=timezone.utc)
    if share.expires_at and now > share.expires_at.replace(tzinfo=timezone.utc):
        raise HTTPException(410, "Link chia sẻ đã hết hạn")

    # Increment view count
    share.view_count += 1

    # Find the file
    if share.file_type == "user_file":
        fr = await db.execute(select(UserFile).where(UserFile.id == share.file_id))
        uf = fr.scalar_one_or_none()
        if not uf:
            raise HTTPException(404)
        file_name = uf.file_name
        size_bytes: int | None = uf.file_size
    else:
        # submission
        sr = await db.execute(select(Submission).where(Submission.id == share.file_id))
        sub = sr.scalar_one_or_none()
        if not sub or not sub.file_path:
            raise HTTPException(404)
        file_name = "submission.omv"
        size_bytes = None

    # Get owner name and file size
    owner_r = await db.execute(select(User).where(User.id == share.shared_by))
    owner = owner_r.scalar_one_or_none()
    owner_name = owner.full_name if owner else ""

    size_bytes = uf.file_size if share.file_type == "user_file" else None  # type: ignore[name-defined]

    # Issue a temporary shared-viewer session cookie so nginx auth_request passes
    # for subsequent Jamovi requests (/open, /{session_id}/...)
    r_client = await get_redis()
    session_key = secrets.token_hex(32)
    ttl = 7200  # 2 hours
    if share.expires_at:
        remaining = int(
            (share.expires_at.replace(tzinfo=timezone.utc) - datetime.now(tz=timezone.utc))
            .total_seconds()
        )
        ttl = max(300, min(ttl, remaining))
    await r_client.setex(f"shared_session:{session_key}", ttl, "1")
    response.set_cookie(
        key="hs_shared_session",
        value=session_key,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=ttl,
        path="/",
    )

    return {
        "file_name": file_name,
        "owner_username": owner_name,
        "size_bytes": size_bytes,
        "expires_at": share.expires_at.isoformat() if share.expires_at else None,
    }


@shared_router.get("/shared/{token}/file")
async def download_shared_file(
    token: str,
    db: AsyncSession = Depends(get_db),
):
    """Return the raw file bytes for a shared link (no auth required)."""
    r = await db.execute(select(FileShare).where(FileShare.share_token == token))
    share = r.scalar_one_or_none()
    if not share:
        raise HTTPException(404, "Link chia sẻ không tồn tại hoặc đã bị thu hồi")
    now = datetime.now(tz=timezone.utc)
    if share.expires_at and now > share.expires_at.replace(tzinfo=timezone.utc):
        raise HTTPException(410, "Link chia sẻ đã hết hạn")

    if share.file_type == "user_file":
        fr = await db.execute(select(UserFile).where(UserFile.id == share.file_id))
        uf = fr.scalar_one_or_none()
        if not uf:
            raise HTTPException(404)
        file_path = uf.file_path
        file_name = uf.file_name
    else:
        sr = await db.execute(select(Submission).where(Submission.id == share.file_id))
        sub = sr.scalar_one_or_none()
        if not sub or not sub.file_path:
            raise HTTPException(404)
        file_path = sub.file_path
        file_name = "submission.omv"

    full_path = Path(settings.upload_dir) / file_path
    if not full_path.exists():
        raise HTTPException(404, "File không tồn tại trên server")

    return FileResponse(
        path=str(full_path),
        filename=file_name,
        media_type="application/octet-stream",
    )
