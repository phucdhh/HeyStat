"""Two approval gates the role model depends on.

An admin unlocks course creation (so a fresh account cannot spam classes on a
server with fixed Jamovi capacity), and a teacher appoints assistants inside a
single class (so a TA grades without ever owning the course).
"""
import asyncio
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from models import Enrollment, Notification, TeacherRequest, UserRole
from routers import classes, teacher_requests
from tests.test_course_roles import FakeDb

UID = uuid.uuid4()          # the class owner / the reviewing admin
APPLICANT = uuid.uuid4()
APPLICANT_EMAIL = "sv@hstats-test.example.com"
CID = uuid.uuid4()
NOW = datetime.now(tz=timezone.utc)

TEACHER_ROLE = SimpleNamespace(id=2, name="teacher")


class _Session(FakeDb):
    """FakeDb plus the write side of an AsyncSession."""

    def __init__(self, **rows):
        super().__init__(**rows)
        self.added = []

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        for obj in self.added:
            if isinstance(obj, (Enrollment, Notification, TeacherRequest)) and obj.id is None:
                obj.id = uuid.uuid4()
            if isinstance(obj, Enrollment) and obj.enrolled_at is None:
                obj.enrolled_at = NOW


def _user(user_id=APPLICANT, email=APPLICANT_EMAIL, full_name="Trần A"):
    return SimpleNamespace(id=user_id, email=email, full_name=full_name, is_active=True)


def _cls():
    """The owning teacher is UID, so an appointment made by UID is the owner speaking."""
    return SimpleNamespace(id=CID, teacher_id=UID, title="Thống kê 2026")


def _request(status="pending", **changes):
    fields = dict(
        id=uuid.uuid4(), user_id=APPLICANT, status=status, institution="Trường ĐH Y",
        reason="Giảng viên thống kê, cần mở lớp thực hành", review_note=None,
        created_at=NOW, reviewed_at=None,
    )
    return SimpleNamespace(**(fields | changes))


def _body(**kwargs):
    return teacher_requests.TeacherRequestCreate(**({"reason": "cần mở lớp thực hành"} | kwargs))


def _assistant_db(**rows):
    """Every class endpoint reads the class row before it looks at anyone."""
    return _Session(classes=[(_cls(),)], **rows)


async def _owner_only(*_args):
    return None


async def _never_owner(*_args):
    raise HTTPException(403, "Không có quyền thực hiện")


# ─── asking for the teacher role ────────────────────────────────

def test_a_teacher_does_not_have_to_ask():
    db = _Session(roles=[("teacher",)])
    with pytest.raises(HTTPException) as err:
        asyncio.run(teacher_requests.submit_request(_body(), _user(), db))
    assert err.value.status_code == 400


def test_a_second_request_reuses_the_pending_one():
    pending = _request()
    db = _Session(roles=[("user",)], teacher_requests=[(pending,), (pending,)])
    out = asyncio.run(teacher_requests.submit_request(_body(), _user(), db))
    assert out.id == str(pending.id)
    assert not any(isinstance(o, TeacherRequest) for o in db.added)


def test_a_first_request_is_recorded_as_pending():
    db = _Session(roles=[("user",)], teacher_requests=[])
    out = asyncio.run(teacher_requests.submit_request(
        _body(institution="Trường ĐH Y"), _user(), db))
    created = [o for o in db.added if isinstance(o, TeacherRequest)][0]
    assert out.status == created.status == "pending"
    assert created.user_id == APPLICANT
    assert created.institution == "Trường ĐH Y"


# ─── the admin decision ─────────────────────────────────────────

def test_approving_grants_the_role_and_tells_the_applicant():
    req = _request()
    db = _Session(
        teacher_requests=[(req, _user())], roles=[(TEACHER_ROLE,)],
        user_roles=[], notifications=[],
    )
    out = asyncio.run(teacher_requests.approve_request(
        req.id, teacher_requests.ReviewRequest(note="Duyệt"), _user(UID), db))
    assert out.status == "approved"
    assert req.reviewed_by == UID
    assert any(
        isinstance(o, UserRole) and o.role_id == 2 and o.user_id == APPLICANT and o.granted_by == UID
        for o in db.added
    )
    assert any(isinstance(o, Notification) and o.type == "teacher_request.approved" for o in db.added)


def test_an_already_granted_account_is_not_granted_twice():
    req = _request()
    granted = SimpleNamespace(user_id=APPLICANT, role_id=2)
    db = _Session(
        teacher_requests=[(req, _user())], roles=[(TEACHER_ROLE,)],
        user_roles=[(granted,)], notifications=[],
    )
    asyncio.run(teacher_requests.approve_request(
        req.id, teacher_requests.ReviewRequest(), _user(UID), db))
    assert not any(isinstance(o, UserRole) for o in db.added)


def test_rejecting_records_the_reason():
    req = _request()
    db = _Session(teacher_requests=[(req, _user())], user_roles=[], notifications=[])
    out = asyncio.run(teacher_requests.reject_request(
        req.id, teacher_requests.ReviewRequest(note="Thiếu thông tin"), _user(UID), db))
    assert out.status == "rejected"
    assert out.review_note == "Thiếu thông tin"
    assert req.reviewed_at is not None
    assert any(isinstance(o, Notification) and o.type == "teacher_request.rejected" for o in db.added)


def test_a_decided_request_cannot_be_decided_again():
    req = _request(status="approved")
    db = _Session(teacher_requests=[(req, _user())])
    with pytest.raises(HTTPException) as err:
        asyncio.run(teacher_requests.approve_request(
            req.id, teacher_requests.ReviewRequest(), _user(UID), db))
    assert err.value.status_code == 400


def test_an_unknown_request_is_not_decided():
    db = _Session(teacher_requests=[])
    with pytest.raises(HTTPException) as err:
        asyncio.run(teacher_requests.approve_request(
            uuid.uuid4(), teacher_requests.ReviewRequest(), _user(UID), db))
    assert err.value.status_code == 404


# ─── assistants inside one class ────────────────────────────────

def test_a_ta_is_upgraded_in_place(monkeypatch):
    monkeypatch.setattr(classes, "_require_teacher_owns", _owner_only)
    enrollment = Enrollment(id=uuid.uuid4(), class_id=CID, user_id=APPLICANT,
                            role="student", status="active", enrolled_at=NOW)
    db = _assistant_db(users=[(_user(),)], enrollments=[(enrollment,)])
    out = asyncio.run(classes.add_assistant(
        CID, classes.AssistantCreate(email=APPLICANT_EMAIL), _user(UID), db))
    assert enrollment.role == "assistant"
    assert out.id == str(APPLICANT)


def test_a_ta_who_is_not_in_the_class_yet_is_enrolled_as_assistant(monkeypatch):
    monkeypatch.setattr(classes, "_require_teacher_owns", _owner_only)
    db = _assistant_db(users=[(_user(),)], enrollments=[])
    asyncio.run(classes.add_assistant(
        CID, classes.AssistantCreate(email=APPLICANT_EMAIL), _user(UID), db))
    created = [o for o in db.added if isinstance(o, Enrollment)][0]
    assert created.role == "assistant"
    assert created.user_id == APPLICANT


def test_an_unknown_account_cannot_be_appointed(monkeypatch):
    monkeypatch.setattr(classes, "_require_teacher_owns", _owner_only)
    db = _assistant_db(users=[], enrollments=[])
    with pytest.raises(HTTPException) as err:
        asyncio.run(classes.add_assistant(
            CID, classes.AssistantCreate(email="ghost@example.com"), _user(UID), db))
    assert err.value.status_code == 404


def test_the_owning_teacher_is_never_an_assistant_of_their_own_class(monkeypatch):
    monkeypatch.setattr(classes, "_require_teacher_owns", _owner_only)
    owner = _user(UID, email="thay@hstats-test.example.com")
    db = _assistant_db(users=[(owner,)], enrollments=[])
    with pytest.raises(HTTPException) as err:
        asyncio.run(classes.add_assistant(
            CID, classes.AssistantCreate(email=owner.email), _user(UID), db))
    assert err.value.status_code == 400


def test_removing_an_assistant_keeps_them_in_the_roster(monkeypatch):
    monkeypatch.setattr(classes, "_require_teacher_owns", _owner_only)
    ta = Enrollment(id=uuid.uuid4(), class_id=CID, user_id=APPLICANT,
                    role="assistant", status="active", enrolled_at=NOW)

    class _NoDelete(_Session):
        async def delete(self, obj):
            raise AssertionError("a downgraded assistant must not be deleted")

    db = _NoDelete(classes=[(_cls(),)], enrollments=[(ta,)])
    asyncio.run(classes.remove_assistant(CID, APPLICANT, _user(UID), db))
    assert ta.role == "student"
    assert ta.status == "active"


def test_removing_someone_who_is_not_an_assistant_is_a_404(monkeypatch):
    monkeypatch.setattr(classes, "_require_teacher_owns", _owner_only)
    db = _assistant_db(enrollments=[])
    with pytest.raises(HTTPException) as err:
        asyncio.run(classes.remove_assistant(CID, APPLICANT, _user(UID), db))
    assert err.value.status_code == 404


def test_only_the_owner_appoints(monkeypatch):
    """The shared ownership guard still runs, so a student cannot promote themselves."""
    monkeypatch.setattr(classes, "_require_teacher_owns", _never_owner)
    db = _assistant_db(users=[(_user(),)], enrollments=[])
    with pytest.raises(HTTPException) as err:
        asyncio.run(classes.add_assistant(
            CID, classes.AssistantCreate(email=APPLICANT_EMAIL), _user(APPLICANT), db))
    assert err.value.status_code == 403
