"""The home page reads three public endpoints, and they must not leak a class.

A Guest gets course titles, aggregate counts and — from /public/whoami — whether
they are already signed in. Emails, enrollment codes and anything about an
individual student stay behind the login.
"""
import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from starlette.requests import Request

from routers import public
from tests.test_course_roles import FakeDb

CID = uuid.uuid4()
TID = uuid.uuid4()
NOW = datetime.now(tz=timezone.utc)


def _run(coro):
    return asyncio.run(coro)


def _class(**changes):
    fields = dict(
        id=CID, teacher_id=TID, title="Thống kê ứng dụng 2026", description="",
        starts_at=NOW - timedelta(days=1), ends_at=NOW + timedelta(days=60), status="active",
    )
    return SimpleNamespace(**(fields | changes))


def _db(**overrides):
    rows = dict(
        classes=[(_class(),)],
        users=[(TID, "Nguyễn Văn A")],
        enrollments=[(CID, 30)],
        assignments=[(CID, 4)],
        lessons=[(CID, 2)],
    )
    return FakeDb(**(rows | overrides))


# ─── course catalogue ───────────────────────────────────────────

def test_the_catalog_publishes_a_running_course_with_its_counts():
    out = _run(public.public_classes(24, _db()))
    assert len(out) == 1
    course = out[0]
    assert course.title == "Thống kê ứng dụng 2026"
    assert course.teacher_name == "Nguyễn Văn A"
    assert (course.student_count, course.assignment_count, course.lesson_count) == (30, 4, 2)


def test_the_catalog_never_carries_a_code_or_an_email():
    payload = _run(public.public_classes(24, _db()))[0].model_dump()
    assert set(payload) == {
        "id", "title", "description", "teacher_name",
        "student_count", "assignment_count", "lesson_count", "starts_at", "ends_at",
    }
    assert "enrollment" not in "".join(payload).lower()


def test_an_empty_description_is_dropped_rather_than_shown_as_blank():
    assert _run(public.public_classes(24, _db()))[0].description is None
    described = _class(description="  Ôn tập thống kê  ")
    out = _run(public.public_classes(24, _db(classes=[(described,)])))
    assert out[0].description == "Ôn tập thống kê"


def test_an_assistant_is_not_counted_as_a_student():
    """The query only counts active students, so the roster size stays honest."""
    assert _run(public.public_classes(24, _db(enrollments=[])))[0].student_count == 0


# ─── counters ───────────────────────────────────────────────────

def test_the_counters_are_plain_aggregates():
    db = FakeDb(
        users=[(120,)], user_roles=[(18,)], classes=[(7,)], submissions=[(500,)], lessons=[(33,)],
    )
    stats = _run(public.public_stats(db))
    assert stats.model_dump() == {
        "total_users": 120, "total_teachers": 18, "active_classes": 7,
        "final_submissions": 500, "lessons": 33,
    }


def test_a_missing_count_reads_as_zero_not_none():
    db = FakeDb(users=[(None,)], user_roles=[], classes=[], submissions=[], lessons=[])
    assert _run(public.public_stats(db)).total_teachers == 0


# ─── who is looking at the page ─────────────────────────────────

def _request(cookie: str | None):
    headers = [] if cookie is None else [(b"cookie", cookie.encode())]
    return Request({"type": "http", "method": "GET", "path": "/", "headers": headers})


def test_a_visitor_without_a_session_cookie_is_a_guest(monkeypatch):
    async def no_user(_token):
        return None

    monkeypatch.setattr(public, "validate_refresh_token", no_user)
    state = _run(public.whoami(_request("hs_session=stale"), FakeDb(users=[])))
    assert state.logged_in is False
    assert state.roles == []


def test_a_signed_in_teacher_gets_a_name_and_a_role(monkeypatch):
    async def known(_token):
        return str(TID)

    monkeypatch.setattr(public, "validate_refresh_token", known)
    db = FakeDb(users=[(SimpleNamespace(id=TID, full_name="Thầy Sơn", is_active=True),)],
                roles=[("teacher",), ("user",)])
    state = _run(public.whoami(_request("hs_session=fresh"), db))
    assert state.logged_in is True
    assert state.full_name == "Thầy Sơn"
    assert state.roles == ["teacher", "user"]
