"""The nginx gate in front of HeyStat asks /auth/check whether a request may pass.

The gate exists so a Guest cannot start a Jamovi session, but an assignment
iframe carries its own one-off ``session=`` token in the URL — a private window
has no cookie, and the student must still get in.
"""
import asyncio
import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from routers import auth as auth_router

UID = uuid.uuid4()
TOKEN = "a" * 64


class _Redis:
    def __init__(self, keys):
        self.keys = set(keys)

    async def get(self, key):
        return "value" if key in self.keys else None


def _request(cookies=(), headers=()):
    items = [(k.lower().encode(), v.encode()) for k, v in headers]
    if cookies:
        items.insert(0, (b"cookie", "; ".join(f"{k}={v}" for k, v in cookies).encode()))
    return Request({"type": "http", "method": "GET", "path": "/check", "headers": items})


@pytest.fixture
def redis_with_session_tokens(monkeypatch):
    async def known(token):
        return str(UID) if token == "good-refresh" else None

    async def redis():
        return _Redis([f"session:{TOKEN}", "shared_session:good-shared"])

    monkeypatch.setattr(auth_router, "validate_refresh_token", known)
    monkeypatch.setattr(auth_router, "get_redis", redis)


def test_a_guest_with_nothing_to_show_is_refused(redis_with_session_tokens):
    with pytest.raises(HTTPException) as err:
        asyncio.run(auth_router.auth_check(_request()))
    assert err.value.status_code == 401


def test_a_logged_in_cookie_still_opens_the_gate(redis_with_session_tokens):
    assert asyncio.run(auth_router.auth_check(_request([("hs_session", "good-refresh")]))) == {"ok": True}


def test_a_shared_viewer_cookie_opens_the_gate(redis_with_session_tokens):
    assert asyncio.run(
        auth_router.auth_check(_request([("hs_shared_session", "good-shared")]))
    ) == {"ok": True}


def test_a_classroom_session_token_in_the_url_opens_the_gate(redis_with_session_tokens):
    """This is the /app?... request an assignment iframe makes."""
    request = _request(headers=[("X-Original-URI", f"/app?session={TOKEN}&path=classroom/c/u&mode=observe")])
    assert asyncio.run(auth_router.auth_check(request)) == {"ok": True}


def test_a_forged_session_token_does_not(redis_with_session_tokens):
    request = _request(headers=[("X-Original-URI", f"/app?session={'0' * 64}&path=classroom/c/u")])
    with pytest.raises(HTTPException) as err:
        asyncio.run(auth_router.auth_check(request))
    assert err.value.status_code == 401


def test_a_session_token_outside_the_query_string_is_ignored(redis_with_session_tokens):
    """The check reads the query, not any substring that happens to say session=."""
    request = _request(headers=[("X-Original-URI", "/notsessionpath?other=1")])
    with pytest.raises(HTTPException):
        asyncio.run(auth_router.auth_check(request))
