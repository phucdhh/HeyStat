"""Each route that hands out exam material rechecks the teacher's lock."""
import asyncio
import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from auth import redis_client
from routers import assignments, class_files, sessions

CID, AID, FID, UID = (uuid.uuid4() for _ in range(4))
USER = SimpleNamespace(id=UID, is_active=True)


def _assignment(**changes):
    fields = dict(id=AID, class_id=CID, is_open=False, file_id=FID, group_size=1,
                  assignment_type="exam")
    return SimpleNamespace(**(fields | changes))


def _file(**changes):
    return SimpleNamespace(**(dict(id=FID, class_id=CID, file_name="de.sav",
                                   file_path="de.sav", file_size=1, mime_type=None,
                                   created_at="2026-11-01", student_access=True) | changes))


class _Db:
    def __init__(self, **results):
        self.results = results

    async def execute(self, statement):
        sql = str(statement).lower()
        for table, result in self.results.items():
            if f"from {table}" in sql:
                items = result if isinstance(result, list) else [result]
                return SimpleNamespace(
                    scalar_one_or_none=lambda: result if not isinstance(result, list) else None,
                    scalars=lambda: SimpleNamespace(all=lambda: items),
                )
        raise AssertionError(f"Unexpected query: {statement}")


@pytest.fixture
def wiring(monkeypatch):
    monkeypatch.setattr(assignments, "_get_class_or_404",
                        lambda *_a, **_k: _async(SimpleNamespace(id=CID)))
    monkeypatch.setattr(assignments, "_get_assignment_or_404",
                        lambda *_a, **_k: _async(_assignment()))
    monkeypatch.setattr(assignments, "_class_access_role", lambda *_a, **_k: _async("student"))
    monkeypatch.setattr(class_files, "_get_class_or_404",
                        lambda *_a, **_k: _async(SimpleNamespace(id=CID)))
    return monkeypatch


async def _async(value):
    return value


def test_a_closed_assignment_cannot_be_downloaded_as_a_dataset(wiring):
    with pytest.raises(HTTPException) as err:
        asyncio.run(assignments.get_assignment_dataset(AID, USER, _Db()))
    assert err.value.status_code == 403


def test_a_closed_assignment_cannot_open_a_workspace(wiring):
    class Db:
        async def execute(self, statement):
            sql = str(statement).lower()
            if "from assignments" in sql:
                return SimpleNamespace(scalar_one_or_none=lambda: _assignment())
            return SimpleNamespace(scalar_one_or_none=lambda: SimpleNamespace(id=1))

    with pytest.raises(HTTPException) as err:
        asyncio.run(sessions.get_session_token(
            sessions.SessionTokenRequest(assignment_id=AID), USER, Db()))
    assert err.value.status_code == 403


def test_a_private_attached_file_is_not_downloadable(wiring):
    async def student_access(*_a, **_k):
        return "student"

    wiring.setattr(class_files, "_check_class_access", student_access)
    with pytest.raises(HTTPException) as err:
        asyncio.run(class_files.download_file(
            CID, FID, USER, _Db(class_files=_file(student_access=False))))
    assert err.value.status_code == 403


def test_unlocking_a_file_used_by_a_closed_exam_is_refused(wiring):
    async def teacher_access(*_a, **_k):
        return "teacher"

    wiring.setattr(class_files, "_check_class_access", teacher_access)
    db = _Db(**{"class_files": _file(), "assignments": [FID]})
    with pytest.raises(HTTPException) as err:
        asyncio.run(class_files.update_file_access(
            CID, FID, class_files.FileAccessUpdate(student_access=True), USER, db))
    assert err.value.status_code == 409


def test_locking_a_file_used_by_an_open_assignment_is_refused(wiring):
    async def teacher_access(*_a, **_k):
        return "teacher"

    wiring.setattr(class_files, "_check_class_access", teacher_access)
    db = _Db(**{"class_files": _file(), "assignments": [FID]})
    with pytest.raises(HTTPException) as err:
        asyncio.run(class_files.update_file_access(
            CID, FID, class_files.FileAccessUpdate(student_access=False), USER, db))
    assert err.value.status_code == 409
    assert "bài đang mở" in err.value.detail


class _Redis:
    def __init__(self):
        self.writes = []

    async def setex(self, key, ttl, value):
        self.writes.append((key, ttl, value))


def test_a_browser_navigation_is_redirected_into_heystat(wiring):
    async def teacher_access(*_a, **_k):
        return "teacher"

    async def session_user(_token):
        return str(UID)

    async def redis():
        return _Redis()

    wiring.setattr(class_files, "_check_class_access", teacher_access)
    wiring.setattr(redis_client, "validate_refresh_token", session_user)
    wiring.setattr(redis_client, "get_redis", redis)
    request = Request({"type": "http", "path": "/", "headers": [
        (b"cookie", b"hs_session=token"),
        (b"host", b"heystat.pedu.vn"),
        (b"x-forwarded-proto", b"https"),
    ]})
    db = _Db(**{"users": USER, "class_files": _file(), "assignments": []})
    response = asyncio.run(class_files.open_file_from_browser(CID, FID, request, db))
    assert response.status_code == 302
    assert response.headers["location"].startswith(
        "/#open?url=https%3A%2F%2Fheystat.pedu.vn%2Fapi%2Fv1%2Ffiles%2Fot%2F")
    assert "title=de.sav" in response.headers["location"]


def test_a_browser_navigation_without_a_session_cookie_is_refused(wiring):
    request = Request({"type": "http", "headers": []})
    with pytest.raises(HTTPException) as err:
        asyncio.run(class_files.open_file_from_browser(
            CID, FID, request, _Db(**{"users": USER, "class_files": _file()})))
    assert err.value.status_code == 401


def test_students_are_not_shown_private_draft_uploads(wiring):
    async def student_access(*_a, **_k):
        return "student"

    wiring.setattr(class_files, "_check_class_access", student_access)
    db = _Db(**{"class_files": [_file(student_access=False), _file(id=uuid.uuid4())],
                "assignments": []})
    listed = asyncio.run(class_files.list_files(CID, USER, db))
    assert [f.id for f in listed] == [str(db.results["class_files"][1].id)]
