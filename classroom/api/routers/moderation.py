"""Content moderation for what the platform publishes publicly.

A Moderator is a community role: it reviews links that share files outside a
class and takes down the ones that abuse the platform. There is deliberately no
route here that touches server configuration, accounts or roles — those stay
with an Admin.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.deps import require_moderator
from database import get_db
from models import FileShare, User, UserFile

router = APIRouter(prefix="/moderation", tags=["moderation"])


class SharedLinkResponse(BaseModel):
    id: str
    share_token: str
    file_name: str
    owner_id: str
    owner_name: Optional[str] = None
    owner_email: str
    view_count: int
    created_at: datetime
    expires_at: Optional[datetime] = None


@router.get("/shares", response_model=list[SharedLinkResponse])
async def list_shared_links(
    _moderator: User = Depends(require_moderator()),
    db: AsyncSession = Depends(get_db),
):
    """Every live public link to a personal file, most-viewed first."""
    now = datetime.now(tz=timezone.utc)
    rows = (await db.execute(
        select(FileShare, UserFile, User)
        .join(UserFile, UserFile.id == FileShare.file_id)
        .join(User, User.id == FileShare.shared_by)
        .where(FileShare.file_type == "user_file")
        .order_by(FileShare.view_count.desc(), FileShare.created_at.desc())
        .limit(200)
    )).all()
    return [
        SharedLinkResponse(
            id=str(share.id),
            share_token=share.share_token,
            file_name=uf.file_name,
            owner_id=str(user.id),
            owner_name=user.full_name or None,
            owner_email=user.email,
            view_count=share.view_count,
            created_at=share.created_at,
            expires_at=share.expires_at,
        )
        for share, uf, user in rows
        if share.expires_at is None or share.expires_at > now
    ]


@router.delete("/shares/{share_id}", status_code=204)
async def take_down_shared_link(
    share_id: uuid.UUID,
    _moderator: User = Depends(require_moderator()),
    db: AsyncSession = Depends(get_db),
):
    share = (await db.execute(select(FileShare).where(FileShare.id == share_id))).scalar_one_or_none()
    if share:
        await db.delete(share)
