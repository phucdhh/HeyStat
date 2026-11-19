"""Presence router – who is in a class right now, and who is in the editor.

The two signals are kept apart on purpose: a tab left open on a class page means
the student walked in, while a tab holding a loaded jamovi session means they are
actually working. Everything lives in Redis – the API runs two workers, so an
in-process dict would split one class in half – and a claim is keyed per browser
tab so a student with two tabs still counts as one person.
"""
import re
import time
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.deps import get_current_user
from auth.redis_client import get_redis, validate_refresh_token
from database import get_db
from models import Class, Enrollment, Role, User, UserRole

router = APIRouter(tags=["presence"])

# The browser beats every 30s. Safari throttles timers in a background tab, so the
# window is wider than the interval: a beat older than this means the tab is gone.
ONLINE_WINDOW = 90
# How long a tab's claim survives without a leave beacon, in case the beacon is lost.
TAB_TTL = 120

_SESSION_COOKIE = "hs_session"
_TAB_RE = re.compile(r"[A-Za-z0-9_-]{8,64}")


class BeatRequest(BaseModel):
    class_id: uuid.UUID
    tab_id: str
    editing: bool = False


class StudentPresence(BaseModel):
    user_id: str
    online: bool
    editing: bool
    seen_seconds_ago: Optional[int] = None


class PresenceResponse(BaseModel):
    enrolled_total: int
    online_total: int
    editing_total: int
    window_seconds: int = ONLINE_WINDOW
    students: list[StudentPresence]


def _online_key(class_id) -> str:
    return f"presence:online:{class_id}"


def _editing_key(class_id) -> str:
    return f"presence:editing:{class_id}"


def _tab_key(tab_id: str) -> str:
    return f"presence:tab:{tab_id}"


def _member(tab_id: str, user_id) -> str:
    return f"{tab_id}:{user_id}"


async def record_beat(r, class_id, user_id, tab_id: str, editing: bool, now: float) -> None:
    member = _member(tab_id, user_id)
    for key, wanted in ((_online_key(class_id), True), (_editing_key(class_id), editing)):
        if wanted:
            await r.zadd(key, {member: now})
        else:
            await r.zrem(key, member)
        # Idle classes drop out on their own; every beat refreshes the hour.
        await r.expire(key, ONLINE_WINDOW * 20)
    await r.setex(_tab_key(tab_id), TAB_TTL, f"{class_id}|{user_id}")


async def read_claims(r, class_id, now: float) -> dict[str, tuple[bool, float]]:
    """user id -> (editing, newest beat). Anything past the window is forgotten."""
    cutoff = now - ONLINE_WINDOW
    found: dict[str, tuple[bool, float]] = {}
    for key, is_editing in ((_online_key(class_id), False), (_editing_key(class_id), True)):
        entries = await r.zrangebyscore(key, min=cutoff, max=now, withscores=True)
        await r.zremrangebyscore(key, min=0, max=cutoff)
        for member, score in entries:
            _, _, user_id = member.partition(":")
            if not user_id:
                continue
            was_editing, best = found.get(user_id, (False, 0.0))
            found[user_id] = (was_editing or is_editing, max(best, score))
    return found


async def _class_or_404(db: AsyncSession, class_id: uuid.UUID) -> Class:
    result = await db.execute(select(Class).where(Class.id == class_id))
    cls = result.scalar_one_or_none()
    if cls is None:
        raise HTTPException(404, "Lớp học không tồn tại")
    return cls


async def _roles(db: AsyncSession, user_id: uuid.UUID) -> set[str]:
    result = await db.execute(
        select(Role.name).join(UserRole, UserRole.role_id == Role.id).where(UserRole.user_id == user_id)
    )
    return {row for (row,) in result.all()}


async def _may_report(db: AsyncSession, class_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    """Only members – and the teacher running the class – may claim a seat in it."""
    hit = await db.execute(
        select(Enrollment.id).where(
            Enrollment.class_id == class_id,
            Enrollment.user_id == user_id,
            Enrollment.status == "active",
        )
    )
    if hit.scalar_one_or_none() is not None:
        return True
    return (await _class_or_404(db, class_id)).teacher_id == user_id


@router.post("/presence/beat", status_code=204)
async def beat(
    body: BeatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not _TAB_RE.fullmatch(body.tab_id):
        raise HTTPException(400, "Mã tab không hợp lệ")
    if not await _may_report(db, body.class_id, current_user.id):
        raise HTTPException(403, "Bạn không thuộc lớp học này")
    r = await get_redis()
    await record_beat(r, body.class_id, current_user.id, body.tab_id, body.editing, time.time())


@router.post("/presence/leave", status_code=204)
async def leave(
    request: Request,
    tab: str = Query(..., max_length=64),
):
    """Called by navigator.sendBeacon when a tab closes. A beacon cannot set an
    Authorization header, so this route reads the HttpOnly session cookie instead."""
    if not _TAB_RE.fullmatch(tab):
        raise HTTPException(400, "Mã tab không hợp lệ")
    token = request.cookies.get(_SESSION_COOKIE)
    user_id = await validate_refresh_token(token) if token else None
    if not user_id:
        raise HTTPException(401, "Phiên đăng nhập đã hết hạn")

    r = await get_redis()
    claim = await r.get(_tab_key(tab))
    if claim:
        class_id, _, owner = claim.partition("|")
        if owner == user_id:
            member = _member(tab, user_id)
            await r.zrem(_online_key(class_id), member)
            await r.zrem(_editing_key(class_id), member)
        await r.delete(_tab_key(tab))


@router.get("/classes/{class_id}/presence", response_model=PresenceResponse)
async def class_presence(
    class_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cls = await _class_or_404(db, class_id)
    roles = await _roles(db, current_user.id)
    if "admin" not in roles and cls.teacher_id != current_user.id:
        raise HTTPException(403, "Chỉ giáo viên của lớp mới xem được trạng thái vào học")

    roster = (await db.execute(
        select(Enrollment.user_id).where(
            Enrollment.class_id == class_id, Enrollment.status == "active"
        )
    )).scalars().all()

    r = await get_redis()
    now = time.time()
    found = await read_claims(r, class_id, now)

    students = []
    for uid in roster:
        hit = found.get(str(uid))
        students.append(StudentPresence(
            user_id=str(uid),
            online=hit is not None,
            editing=bool(hit and hit[0]),
            seen_seconds_ago=int(now - hit[1]) if hit else None,
        ))
    return PresenceResponse(
        enrolled_total=len(roster),
        online_total=sum(1 for s in students if s.online),
        editing_total=sum(1 for s in students if s.editing),
        students=students,
    )
