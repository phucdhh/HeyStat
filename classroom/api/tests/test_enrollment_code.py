"""A class code the teacher can read back has to be the code that gets a student in.

``enrollment_key`` is a bcrypt hash and nothing can reverse it, so the readable
copy lives next to it in ``enrollment_code``. Every test here is about the two
agreeing, because a teacher who shows a student a code that no longer opens the
class is worse off than a teacher who never saw one at all.
"""
import asyncio
import uuid
from types import SimpleNamespace

import pytest

from routers import classes
from routers.classes import (
    EnrollmentCodeBody, JoinRequest, _normalize_code, join_by_key,
    read_enrollment_code, set_enrollment_code,
)


def _res(value=None, many=()):
    return SimpleNamespace(
        scalar_one_or_none=lambda: value,
        scalar=lambda: value,
        scalars=lambda: list(many),
    )


class _Db:
    """Answers each select the route makes, in the order the test scripts it."""

    def __init__(self, *results):
        self._results = list(results)
        self.added = []

    async def execute(self, statement):
        assert self._results, "the route asked the database more than the test scripted"
        return self._results.pop(0)

    def add(self, obj):
        self.added.append(obj)


def _class(**kw):
    base = dict(id=uuid.uuid4(), teacher_id=uuid.uuid4(), title="Thống kê 2026",
                enrollment_code=None, enrollment_key=None, max_students=50)
    base.update(kw)
    return SimpleNamespace(**base)


def _user():
    return SimpleNamespace(id=uuid.uuid4())


@pytest.fixture
def owning(monkeypatch):
    """The two code routes start by loading the class and checking who owns it."""
    cls = _class()

    async def load(_db, class_id):
        return cls

    async def owns(_db, _cls, _user):
        return None

    monkeypatch.setattr(classes, "_get_class_or_404", load)
    monkeypatch.setattr(classes, "_require_teacher_owns", owns)
    return cls


def test_a_teacher_typing_the_code_in_lowercase_means_the_same_code():
    assert _normalize_code("xtsk 26") == "XTSK26"
    assert _normalize_code("ab3x-9k2w") == "AB3X9K2W"
    assert _normalize_code(None) is None


@pytest.mark.parametrize("bad", ["abc", "XTSK@26", "abcdefghijklmnopqrstu"])
def test_a_code_nobody_could_read_aloud_is_refused(bad):
    with pytest.raises(classes.HTTPException) as e:
        _normalize_code(bad)
    assert e.value.status_code == 400
    assert "chữ Hoa" in e.value.detail


def test_setting_a_code_moves_the_hash_with_it(owning):
    out = asyncio.run(set_enrollment_code(
        owning.id, EnrollmentCodeBody(enrollment_code="xtsk 26"), _user(), _Db(_res(None))))

    assert out == {"enrollment_code": "XTSK26"}
    assert owning.enrollment_code == "XTSK26"
    assert classes._verify_key("XTSK26", owning.enrollment_key)


def test_an_empty_body_hands_back_a_random_code(owning):
    # the random path asks twice: once per candidate, once for the settled code
    out = asyncio.run(set_enrollment_code(
        owning.id, EnrollmentCodeBody(), _user(), _Db(_res(None), _res(None))))

    code = out["enrollment_code"]
    assert _normalize_code(code) == code
    assert classes._verify_key(code, owning.enrollment_key)


def test_a_code_another_class_holds_is_refused(owning):
    with pytest.raises(classes.HTTPException) as e:
        asyncio.run(set_enrollment_code(
            owning.id, EnrollmentCodeBody(enrollment_code="XTSK26"),
            _user(), _Db(_res(uuid.uuid4()))))

    assert "đã có lớp khác đang dùng" in e.value.detail
    assert owning.enrollment_code is None, "a refused code must not half-write itself"


def test_a_student_joins_on_the_code_the_teacher_wrote_down(owning):
    owning.enrollment_code = "XTSK26"
    owning.enrollment_key = classes._hash_key("XTSK26")
    db = _Db(_res(owning), _res(3), _res(None))

    out = asyncio.run(join_by_key(JoinRequest(enrollment_key="xtsk 26"), _user(), db))

    assert out["class_id"] == str(owning.id)
    assert len(db.added) == 1


def test_a_class_with_only_a_hash_is_still_joinable():
    """Classes predating enrollment_code hold nothing readable, so the hash still
    has to answer or their students would be locked out by the upgrade."""
    legacy = _class(enrollment_key=classes._hash_key("LEGACY77"))
    db = _Db(_res(None), _res(many=[legacy]), _res(0), _res(None))

    out = asyncio.run(join_by_key(JoinRequest(enrollment_key="LEGACY77"), _user(), db))

    assert out["class_id"] == str(legacy.id)


def test_a_wrong_code_still_turns_the_student_away():
    with pytest.raises(classes.HTTPException) as e:
        asyncio.run(join_by_key(
            JoinRequest(enrollment_key="NOPE1234"), _user(), _Db(_res(None), _res())))

    assert e.value.status_code == 400


def test_the_teacher_reads_the_code_but_no_route_answers_with_the_hash(owning):
    owning.enrollment_code = "XTSK26"
    owning.enrollment_key = "$2b$12$not.a.real.hash"

    assert asyncio.run(read_enrollment_code(owning.id, _user(), _Db())) == {
        "enrollment_code": "XTSK26"
    }
    # /classes and /classes/{id} are answered from ClassResponse to any logged-in
    # user, so neither may carry a field that would hand out a way into a class.
    assert "enrollment_key" not in classes.ClassResponse.model_fields
    assert "enrollment_code" not in classes.ClassResponse.model_fields


def test_the_code_routes_replaced_the_regenerate_route():
    methods = {(m, r.path) for r in classes.router.routes for m in getattr(r, "methods", set())}
    assert ("GET", "/classes/{class_id}/enrollment-code") in methods
    assert ("PUT", "/classes/{class_id}/enrollment-code") in methods
    assert not any(path.endswith("regenerate-key") for _, path in methods)
