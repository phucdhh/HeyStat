"""Sessions router – issue Jamovi session tokens for students."""
import uuid
import secrets
import hmac
import hashlib
import os
import time
from pathlib import Path
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from database import get_db
from models import Assignment, Enrollment, AssignmentGroup, AssignmentGroupMember, Class, User, UserRole, Role
from auth.deps import get_current_user
from auth.redis_client import get_redis
from config import get_settings

settings = get_settings()
router = APIRouter(prefix="/sessions", tags=["sessions"])
SESSION_TOKEN_TTL = timedelta(hours=8)


def _make_collab_token(collab_role: str, ttl_seconds: int = 28800) -> str:
    """Create a signed collab token that clientconnection.py can verify without Redis.

    Format: ``{role}.{expiry_unix}.{hmac_hex}``
    Token is signed with JAMOVI_COLLAB_SECRET (env var shared with HeyStat container).
    """
    secret = settings.jamovi_collab_secret
    if not secret:
        return ''
    expiry = int(time.time()) + ttl_seconds
    payload = f'{collab_role}:{expiry}'
    sig = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f'{collab_role}.{expiry}.{sig}'


async def _get_user_roles(db, user_id):
    r = await db.execute(
        select(Role.name).join(UserRole, UserRole.role_id == Role.id).where(UserRole.user_id == user_id)
    )
    return {row for (row,) in r.all()}


class SessionTokenRequest(BaseModel):
    assignment_id: uuid.UUID


class SessionTokenResponse(BaseModel):
    embed_url: str
    session_token: str
    collab_role: str  # 'writer' | 'observer'


@router.post("/token", response_model=SessionTokenResponse)
async def get_session_token(
    body: SessionTokenRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Provide a session token for the student to embed HeyStat for an assignment."""
    # Fetch assignment
    r = await db.execute(select(Assignment).where(Assignment.id == body.assignment_id))
    assignment = r.scalar_one_or_none()
    if not assignment:
        raise HTTPException(404, "Bài tập không tồn tại")

    # Verify enrollment
    enr = await db.execute(
        select(Enrollment).where(
            Enrollment.class_id == assignment.class_id,
            Enrollment.user_id == current_user.id,
            Enrollment.status == "active",
        )
    )
    if not enr.scalar_one_or_none():
        raise HTTPException(403, "Bạn chưa tham gia lớp học này")

    collab_role = "writer"
    session_path: str

    if assignment.group_size > 1 and assignment.assignment_type != "exam":
        # Find the group this student belongs to
        gm = await db.execute(
            select(AssignmentGroup)
            .join(AssignmentGroupMember, AssignmentGroupMember.group_id == AssignmentGroup.id)
            .where(
                AssignmentGroup.assignment_id == body.assignment_id,
                AssignmentGroupMember.user_id == current_user.id,
            )
        )
        group = gm.scalar_one_or_none()
        if not group:
            raise HTTPException(400, "Bạn chưa tham gia nhóm nào cho bài tập này")
        session_path = group.session_path or f"classroom/{assignment.class_id}/group_{group.id}"
        if group.leader_id != current_user.id:
            collab_role = "observer"
    else:
        session_path = f"classroom/{assignment.class_id}/{current_user.id}"

    # Create session directory
    full_session_dir = Path(settings.jamovi_data_root) / session_path
    full_session_dir.mkdir(parents=True, exist_ok=True)

    # Store token in Redis
    r_client = await get_redis()
    session_token = secrets.token_hex(32)
    token_data = f"{current_user.id}|{session_path}|{collab_role}"
    await r_client.setex(f"session:{session_token}", SESSION_TOKEN_TTL, token_data)

    embed_url = f"/?session={session_token}&path={session_path}"
    collab_param = _make_collab_token(collab_role)
    if collab_param:
        embed_url += f"&collab_token={collab_param}"
    return SessionTokenResponse(
        embed_url=embed_url,
        session_token=session_token,
        collab_role=collab_role,
    )


@router.delete("/token", status_code=204)
async def revoke_session_token(
    token: str,
    current_user: User = Depends(get_current_user),
):
    r_client = await get_redis()
    await r_client.delete(f"session:{token}")


@router.post("/snapshot", status_code=201)
async def save_snapshot(
    assignment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Draft-save endpoint: client calls this with the .omv blob to create a draft submission."""
    from routers.submissions import _create_submission
    return await _create_submission(assignment_id, current_user, db, is_final=False)


@router.get("/observe/{session_id}", response_model=SessionTokenResponse)
async def observe_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Teacher gets read-only observer URL for a student's live session."""
    roles = await _get_user_roles(db, current_user.id)
    if "admin" not in roles and "teacher" not in roles:
        raise HTTPException(403, "Chỉ giáo viên mới quan sát được session")

    r_client = await get_redis()
    token_data = await r_client.get(f"session:{session_id}")
    if not token_data:
        raise HTTPException(404, "Session không tồn tại hoặc đã hết hạn")

    parts = token_data.split("|")
    session_path = parts[1] if len(parts) >= 2 else ""

    # Block observation for exam sessions
    # exam check: look at assignment — if path contains known pattern this can be enhanced
    # For now: issue observer token
    obs_token = secrets.token_hex(32)
    await r_client.setex(
        f"session:{obs_token}",
        SESSION_TOKEN_TTL,
        f"{current_user.id}|{session_path}|observer",
    )
    return SessionTokenResponse(
        embed_url=f"/?session={obs_token}&path={session_path}&mode=observe",
        session_token=obs_token,
        collab_role="observer",
    )
