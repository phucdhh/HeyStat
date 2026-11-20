"""What a Moderator may and may not touch.

The role exists to keep public share links clean, so its surface is only the
share table: no account, role or server setting is reachable from it.
"""
import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException

from auth.deps import require_moderator
from models import FileShare
from routers import moderation
from tests.test_course_roles import FakeDb

NOW = datetime.now(tz=timezone.utc)


def _share(token, views=3, expires_at=None):
    return SimpleNamespace(
        id=uuid.uuid4(), share_token=token, file_type="user_file", file_id=uuid.uuid4(),
        shared_by=uuid.uuid4(), view_count=views, created_at=NOW - timedelta(days=1),
        expires_at=expires_at,
    )


def _row(token, **kwargs):
    return (_share(token, **kwargs),
            SimpleNamespace(file_name=f"{token}.omv"),
            SimpleNamespace(id=uuid.uuid4(), email="minh@x.vn", full_name="Phúc"))


# ─── the queue ──────────────────────────────────────────────────

def test_live_links_are_listed_with_their_owner():
    live = _row("aaaa")
    db = FakeDb(file_shares=[live])
    out = asyncio.run(moderation.list_shared_links(db=db))
    assert out[0].share_token == "aaaa"
    assert out[0].file_name == "aaaa.omv"
    assert out[0].owner_email == "minh@x.vn"


def test_an_expired_link_is_no_longer_reviewable():
    rows = [
        _row("live", expires_at=NOW + timedelta(days=7)),
        _row("gone", expires_at=NOW - timedelta(days=1)),
        _row("forever"),
    ]
    db = FakeDb(file_shares=rows)
    out = asyncio.run(moderation.list_shared_links(db=db))
    assert [s.share_token for s in out] == ["live", "forever"]


def test_take_down_removes_the_link():
    deleted = []

    class _Db(FakeDb):
        async def delete(self, obj):
            deleted.append(obj)

    share = _share("bad")
    db = _Db(file_shares=[(share,)])
    asyncio.run(moderation.take_down_shared_link(share.id, db=db))
    assert deleted == [share]


def test_an_already_gone_link_still_leaves_nothing_behind():
    deleted = []

    class _Db(FakeDb):
        async def delete(self, obj):
            deleted.append(obj)

    asyncio.run(moderation.take_down_shared_link(uuid.uuid4(), db=_Db(file_shares=[])))
    assert deleted == []


# ─── the size of the role ───────────────────────────────────────

def _role_names(guard):
    """The tuple require_roles() closed over, i.e. the roles that pass the gate."""
    for cell in guard.__closure__ or ():
        if isinstance(cell.cell_contents, tuple):
            return cell.cell_contents
    raise AssertionError("no role list captured")


def test_both_routes_are_guarded_by_the_moderator_gate():
    app = FastAPI()
    app.include_router(moderation.router, prefix="/api/v1")
    assert {route.path for route in app.routes if hasattr(route, "dependant")} == {
        "/api/v1/moderation/shares", "/api/v1/moderation/shares/{share_id}",
    }
    for route in moderation.router.routes:
        assert _role_names(route.dependant.dependencies[0].call) == ("admin", "moderator")


def test_a_moderator_passes_and_a_teacher_does_not():
    gate = require_moderator()
    user = SimpleNamespace(id=uuid.uuid4())

    async def _go(role):
        return await gate(user, FakeDb(roles=[(role,)]))

    assert asyncio.run(_go("moderator")).id == user.id
    assert asyncio.run(_go("admin")).id == user.id
    for role in ("user", "teacher", "student"):
        with pytest.raises(HTTPException) as err:
            asyncio.run(_go(role))
        assert err.value.status_code == 403
