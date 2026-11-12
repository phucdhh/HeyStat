"""The browser keeps its refresh token in the hs_session cookie, not in JS."""
import asyncio
import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from starlette.requests import Request
from starlette.responses import Response

from auth.schemas import RefreshRequest, TokenResponse
from routers import auth

UID = uuid.uuid4()


def _request(cookie: str | None) -> Request:
    headers = [(b"cookie", f"hs_session={cookie}".encode())] if cookie else []
    return Request({"type": "http", "headers": headers})


class _Db:
    async def execute(self, _statement):
        return SimpleNamespace(
            scalar_one_or_none=lambda: SimpleNamespace(id=UID, is_active=True))


@pytest.fixture
def refresh_wiring(monkeypatch):
    seen = {"validated": [], "revoked": []}

    async def validate(token):
        seen["validated"].append(token)
        return str(UID)

    async def revoke(token):
        seen["revoked"].append(token)

    async def build(_db, _user):
        return TokenResponse(access_token="new-access", refresh_token="new-refresh")

    monkeypatch.setattr(auth, "validate_refresh_token", validate)
    monkeypatch.setattr(auth, "revoke_refresh_token", revoke)
    monkeypatch.setattr(auth, "_build_token_response", build)
    return seen


def _refresh(request, body=None):
    return asyncio.run(auth.refresh(request, Response(), body, _Db()))


def test_an_empty_json_body_falls_back_to_the_session_cookie(refresh_wiring):
    """axios posts {} with credentials; requiring the token in JSON returned 422,
    and the client then logged the user out in the middle of their work."""
    result = _refresh(_request("cookie-token"), RefreshRequest())
    assert result.access_token == "new-access"
    assert refresh_wiring["validated"] == ["cookie-token"]
    assert refresh_wiring["revoked"] == ["cookie-token"]


def test_an_explicit_body_token_still_works_for_api_clients(refresh_wiring):
    result = _refresh(_request("cookie-token"), RefreshRequest(refresh_token="body-token"))
    assert result.access_token == "new-access"
    assert refresh_wiring["validated"] == ["body-token"]


def test_no_cookie_and_no_body_is_unauthorised(refresh_wiring):
    with pytest.raises(HTTPException) as err:
        _refresh(_request(None), RefreshRequest())
    assert err.value.status_code == 401


def test_the_http_route_accepts_an_empty_json_body(refresh_wiring):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from database import get_db

    async def db_override():
        yield _Db()

    app = FastAPI()
    app.include_router(auth.router, prefix="/api/v1")
    app.dependency_overrides[get_db] = db_override
    client = TestClient(app)
    response = client.post("/api/v1/auth/refresh", json={},
                           cookies={"hs_session": "cookie-token"})
    assert response.status_code == 200
    assert response.json()["access_token"] == "new-access"
    assert "hs_session=new-refresh" in response.headers["set-cookie"]
