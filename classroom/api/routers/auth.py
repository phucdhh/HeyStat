"""Authentication router – register, login, refresh, verify-email, reset-password."""
import uuid
import secrets
from datetime import timedelta, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database import get_db
from models import User, UserRole, Role
from auth.security import hash_password, verify_password, create_access_token, create_refresh_token
from auth.redis_client import store_refresh_token, validate_refresh_token, revoke_refresh_token
from auth.schemas import (
    RegisterRequest, LoginRequest, RefreshRequest,
    ForgotPasswordRequest, ResetPasswordRequest,
    TokenResponse, UserResponse,
    UpdateProfileRequest, ChangePasswordRequest,
)
from auth.deps import get_current_user
import redis.asyncio as aioredis
from auth.redis_client import get_redis
from fastapi import UploadFile, File as FastAPIFile
from pathlib import Path
import aiofiles
from config import get_settings

settings = get_settings()

router = APIRouter(prefix="/auth", tags=["auth"])

VERIFY_TTL = timedelta(hours=24)
RESET_TTL = timedelta(hours=1)
_SESSION_COOKIE = "hs_session"
_SESSION_MAX_AGE = 7 * 24 * 3600  # 7 days – matches refresh token TTL


def _set_session_cookie(response: Response, refresh_token: str) -> None:
    response.set_cookie(
        key=_SESSION_COOKIE,
        value=refresh_token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=_SESSION_MAX_AGE,
        path="/",
    )


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(key=_SESSION_COOKIE, path="/")


async def _get_user_roles(db: AsyncSession, user_id: uuid.UUID) -> list[str]:
    result = await db.execute(
        select(Role.name)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(UserRole.user_id == user_id)
    )
    return [r for (r,) in result.all()]


async def _build_token_response(db: AsyncSession, user: User) -> TokenResponse:
    roles = await _get_user_roles(db, user.id)
    access = create_access_token(str(user.id), roles)
    refresh = create_refresh_token(str(user.id))
    await store_refresh_token(str(user.id), refresh)
    return TokenResponse(access_token=access, refresh_token=refresh)


@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=TokenResponse)
async def register(body: RegisterRequest, response: Response, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email đã được sử dụng")

    # Assign default 'user' role
    result = await db.execute(select(Role).where(Role.name == "user"))
    user_role = result.scalar_one_or_none()

    user = User(
        email=body.email,
        password_hash=hash_password(body.password),
        full_name=body.full_name.strip(),
    )
    db.add(user)
    await db.flush()  # get user.id

    if user_role:
        db.add(UserRole(user_id=user.id, role_id=user_role.id))

    # Queue verification email (simplified: store token in Redis)
    r = await get_redis()
    verify_token = secrets.token_urlsafe(32)
    await r.setex(f"verify:{verify_token}", VERIFY_TTL, str(user.id))

    token_resp = await _build_token_response(db, user)
    _set_session_cookie(response, token_resp.refresh_token)
    return token_resp


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if not user or not user.password_hash or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Email hoặc mật khẩu không đúng")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Tài khoản đã bị vô hiệu hoá")
    token_resp = await _build_token_response(db, user)
    _set_session_cookie(response, token_resp.refresh_token)
    return token_resp


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, response: Response, db: AsyncSession = Depends(get_db)):
    user_id = await validate_refresh_token(body.refresh_token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Refresh token không hợp lệ hoặc đã hết hạn")
    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Người dùng không tồn tại")
    await revoke_refresh_token(body.refresh_token)
    token_resp = await _build_token_response(db, user)
    _set_session_cookie(response, token_resp.refresh_token)
    return token_resp


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(body: RefreshRequest, response: Response):
    await revoke_refresh_token(body.refresh_token)
    _clear_session_cookie(response)


@router.get("/check", status_code=status.HTTP_200_OK)
async def auth_check(request: Request):
    """Lightweight endpoint for Nginx auth_request. Validates hs_session cookie."""
    session = request.cookies.get(_SESSION_COOKIE)
    if not session:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user_id = await validate_refresh_token(session)
    if not user_id:
        raise HTTPException(status_code=401, detail="Session expired")
    return {"ok": True}


@router.post("/verify-email", status_code=status.HTTP_204_NO_CONTENT)
async def verify_email(token: str, db: AsyncSession = Depends(get_db)):
    r = await get_redis()
    user_id = await r.get(f"verify:{token}")
    if not user_id:
        raise HTTPException(status_code=400, detail="Token xác thực không hợp lệ hoặc đã hết hạn")
    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng")
    user.is_verified = True
    await r.delete(f"verify:{token}")


@router.post("/forgot-password", status_code=status.HTTP_204_NO_CONTENT)
async def forgot_password(body: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if user:
        r = await get_redis()
        reset_token = secrets.token_urlsafe(32)
        await r.setex(f"reset:{reset_token}", RESET_TTL, str(user.id))
        # In production, send reset email here


@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT)
async def reset_password(body: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    r = await get_redis()
    user_id = await r.get(f"reset:{body.token}")
    if not user_id:
        raise HTTPException(status_code=400, detail="Token đặt lại mật khẩu không hợp lệ hoặc đã hết hạn")
    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng")
    user.password_hash = hash_password(body.new_password)
    await r.delete(f"reset:{body.token}")


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    roles = await _get_user_roles(db, current_user.id)
    return UserResponse(
        id=str(current_user.id),
        email=current_user.email,
        full_name=current_user.full_name,
        phone=current_user.phone,
        avatar_url=current_user.avatar_url,
        is_verified=current_user.is_verified,
        roles=roles,
    )


@router.patch("/profile", response_model=UserResponse)
async def update_profile(
    body: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if body.full_name is not None:
        current_user.full_name = body.full_name
    if body.phone is not None:
        current_user.phone = body.phone or None
    await db.commit()
    await db.refresh(current_user)
    roles = await _get_user_roles(db, current_user.id)
    return UserResponse(
        id=str(current_user.id),
        email=current_user.email,
        full_name=current_user.full_name,
        phone=current_user.phone,
        avatar_url=current_user.avatar_url,
        is_verified=current_user.is_verified,
        roles=roles,
    )


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    body: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not current_user.password_hash or not verify_password(body.current_password, current_user.password_hash):
        raise HTTPException(status_code=401, detail="Mật khẩu hiện tại không đúng")
    current_user.password_hash = hash_password(body.new_password)
    await db.commit()


@router.post("/avatar", response_model=UserResponse)
async def upload_avatar(
    file: UploadFile = FastAPIFile(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if file.content_type not in ("image/jpeg", "image/png", "image/gif", "image/webp"):
        raise HTTPException(status_code=400, detail="Chỉ chấp nhận ảnh JPEG, PNG, GIF, WebP")
    ext = Path(file.filename).suffix.lower() if file.filename else ".jpg"
    avatar_dir = Path(settings.upload_dir) / "avatars"
    avatar_dir.mkdir(parents=True, exist_ok=True)
    dest = avatar_dir / f"{current_user.id}{ext}"
    async with aiofiles.open(dest, "wb") as f:
        content = await file.read()
        if len(content) > 2 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Ảnh avatar không được vượt quá 2MB")
        await f.write(content)
    current_user.avatar_url = f"/api/v1/auth/avatar/{current_user.id}{ext}"
    await db.commit()
    await db.refresh(current_user)
    roles = await _get_user_roles(db, current_user.id)
    return UserResponse(
        id=str(current_user.id),
        email=current_user.email,
        full_name=current_user.full_name,
        phone=current_user.phone,
        avatar_url=current_user.avatar_url,
        is_verified=current_user.is_verified,
        roles=roles,
    )


@router.get("/avatar/{filename}")
async def serve_avatar(filename: str):
    """Serve uploaded avatar images."""
    avatar_path = Path(settings.upload_dir) / "avatars" / filename
    if not avatar_path.exists() or not avatar_path.is_file():
        raise HTTPException(status_code=404, detail="Avatar không tìm thấy")
    from fastapi.responses import FileResponse as FR
    return FR(str(avatar_path))
