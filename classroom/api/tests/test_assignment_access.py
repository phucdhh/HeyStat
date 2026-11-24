"""A closed assignment must stay closed across every file and session route."""
import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy.dialects import postgresql

from routers import assignments
from routers.assignments import AssignmentCreate, AssignmentUpdate, _to_response
from services import assignment_access
from services.assignment_access import require_assignment_open, require_file_open

NOW = datetime(2026, 11, 1, tzinfo=timezone.utc)
CID, AID, FID = uuid.UUID(int=1), uuid.UUID(int=2), uuid.UUID(int=3)


def _file(**changes):
    fields = dict(id=FID, class_id=CID, file_name="source.csv", file_path="source.csv", student_access=True)
    return SimpleNamespace(**(fields | changes))


def _assignment(**changes):
    fields = dict(
        id=AID, class_id=CID, title="Kiểm tra", description="Đề bí mật",
        assignment_type="exam", is_open=False, file_id=FID, max_score=10,
        deadline=NOW, allow_resubmit=False, group_size=1, allow_sharing=False,
        answer_key={"questions": [{"id": "q1", "label": "Trung bình?", "type": "number",
                                   "points": 2, "answer": 3.14}]},
        grading_config={"checks": [{"id": "c1", "value": 3.14}]}, created_at=NOW,
    )
    return SimpleNamespace(**(fields | changes))


class _Db:
    """Answer one query and remember the SQL it was asked for."""

    def __init__(self, result=None):
        self.result = result if result is not None else []
        self.sql = []

    async def execute(self, statement):
        self.sql.append(str(statement.compile(
            dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})))
        result = self.result
        return SimpleNamespace(
            scalars=lambda: SimpleNamespace(all=lambda: result),
            scalar_one_or_none=lambda: result,
            all=lambda: result,
        )


def test_a_closed_assignment_is_refused_and_an_open_one_passes():
    with pytest.raises(HTTPException) as err:
        require_assignment_open(_assignment(is_open=False))
    assert err.value.status_code == 403
    assert require_assignment_open(_assignment(is_open=True)) is None


def test_closed_file_ids_only_gathers_this_class_and_only_closed_assignments():
    db = _Db([FID])
    assert asyncio.run(assignment_access.closed_file_ids(db, CID)) == {FID}
    sql = db.sql[0]
    assert f"assignments.class_id = '{CID}'" in sql
    assert "assignments.is_open IS false" in sql
    assert "assignments.file_id IS NOT NULL" in sql


def test_a_manual_lock_closes_a_file_even_when_no_assignment_uses_it():
    with pytest.raises(HTTPException) as err:
        asyncio.run(require_file_open(_Db(), _file(student_access=False)))
    assert err.value.status_code == 403


def test_an_attached_file_stays_closed_while_any_assignment_is_closed():
    """A file shared with one closed exam must not leak through its other, open use."""
    with pytest.raises(HTTPException) as err:
        asyncio.run(require_file_open(_Db([FID]), _file(student_access=True)))
    assert err.value.status_code == 403


def test_an_open_attached_file_is_readable():
    assert asyncio.run(require_file_open(_Db(), _file())) is None


def test_a_closed_assignment_hides_the_prompt_and_dataset_from_students():
    student = _to_response(_assignment(is_open=False), with_key=False)
    assert student.is_open is False
    assert student.description == ""
    assert student.questions is None
    assert student.file_id is None
    assert student.answer_key is None and student.grading_config is None
    assert student.deadline == NOW


def test_an_open_assignment_still_shows_questions_without_the_answers():
    student = _to_response(_assignment(is_open=True), with_key=False)
    assert student.questions[0]["label"] == "Trung bình?"
    assert "answer" not in student.questions[0]
    assert student.file_id == str(FID)


def test_a_teacher_sees_the_closed_assignment_in_full():
    teacher = _to_response(_assignment(is_open=False), with_key=True)
    assert teacher.description == "Đề bí mật"
    assert teacher.answer_key["questions"][0]["answer"] == 3.14
    assert teacher.file_id == str(FID)


class _Redis:
    def __init__(self, value=None):
        self.value = value
        self.keys = []

    async def getdel(self, key):
        self.keys.append(key)
        value, self.value = self.value, None
        return value


def _redeem(monkeypatch, user_id=uuid.UUID(int=4), access="student", token="abc"):
    from routers import class_files

    redis = _Redis(f"{FID}|{user_id}")

    async def get_redis():
        return redis

    async def class_(*_a, **_k):
        return SimpleNamespace(id=CID, teacher_id=uuid.UUID(int=9))

    async def current(*_a, **_k):
        if isinstance(access, Exception):
            raise access
        return access

    async def rows(statement):
        if "class_files" in str(statement):
            return SimpleNamespace(scalar_one_or_none=lambda: _file())
        return SimpleNamespace(scalar_one_or_none=lambda: SimpleNamespace(id=user_id))

    class _Db:
        async def execute(self, statement):
            return await rows(statement)

    monkeypatch.setattr("auth.redis_client.get_redis", get_redis)
    monkeypatch.setattr(class_files, "_get_class_or_404", class_)
    monkeypatch.setattr(class_files, "_check_class_access", current)
    return redis, class_files.one_time_download(token, _Db())


def test_a_file_token_is_single_use(monkeypatch):
    redis, call = _redeem(monkeypatch, access="teacher")
    # The fixture has no bytes on disk, but the token must already be spent.
    with pytest.raises(HTTPException) as err:
        asyncio.run(call)
    assert err.value.status_code == 404
    assert redis.keys == ["file_ot_access:abc"]
    assert redis.value is None


def test_a_token_issued_before_enrolment_ended_is_refused(monkeypatch):
    with pytest.raises(HTTPException) as err:
        asyncio.run(_redeem(monkeypatch, access=HTTPException(403, "not enrolled"))[1])
    assert err.value.status_code == 403


def test_redeeming_an_old_token_rechecks_the_current_file_lock(monkeypatch):
    from routers import class_files

    async def locked(*_a, **_k):
        raise HTTPException(403, "Tệp đang khoá")

    monkeypatch.setattr(class_files, "require_file_open", locked)
    with pytest.raises(HTTPException) as err:
        asyncio.run(_redeem(monkeypatch, access="student")[1])
    assert err.value.status_code == 403


class _WriteDb:
    def __init__(self):
        self.added = []

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        for obj in self.added:
            if obj.id is None:
                obj.id = uuid.uuid4()
            if obj.created_at is None:
                obj.created_at = NOW


def _teacher():
    return SimpleNamespace(id=uuid.UUID(int=9))


def _wire_assignment_routes(monkeypatch, file, current=None):
    async def class_(*_a, **_k):
        return SimpleNamespace(id=CID, teacher_id=uuid.UUID(int=9))

    async def roles(*_a, **_k):
        return {"teacher"}

    async def ensure(*_a, **_k):
        return file

    async def current_assignment(*_a, **_k):
        return current

    monkeypatch.setattr(assignments, "_get_class_or_404", class_)
    monkeypatch.setattr(assignments, "_get_user_roles_set", roles)
    monkeypatch.setattr(assignments, "_ensure_file_in_class", ensure)
    monkeypatch.setattr(assignments, "_get_assignment_or_404", current_assignment)


def _create_body(kind):
    return AssignmentCreate(
        title="Bài", description="Mô tả", file_id=FID, assignment_type=kind,
        deadline=datetime.now(tz=timezone.utc) + timedelta(days=1),
    )


def test_a_new_exam_is_created_closed_and_keeps_its_dataset_private(monkeypatch):
    file = _file(student_access=False)
    _wire_assignment_routes(monkeypatch, file)
    db = _WriteDb()
    result = asyncio.run(assignments.create_assignment(CID, _create_body("exam"), _teacher(), db))
    assert result.is_open is False
    assert db.added[0].is_open is False
    assert file.student_access is False


def test_a_new_homework_is_open_and_releases_its_dataset(monkeypatch):
    file = _file(student_access=False)
    _wire_assignment_routes(monkeypatch, file)
    db = _WriteDb()
    result = asyncio.run(assignments.create_assignment(CID, _create_body("homework"), _teacher(), db))
    assert result.is_open is True
    assert file.student_access is True


def test_opening_a_locked_assignment_releases_its_dataset(monkeypatch):
    file = _file(student_access=False)
    current = _assignment(is_open=False)
    _wire_assignment_routes(monkeypatch, file, current)
    db = _WriteDb()
    result = asyncio.run(assignments.update_assignment(
        CID, AID, AssignmentUpdate(is_open=True), _teacher(), db))
    assert result.is_open is True
    assert current.is_open is True
    assert file.student_access is True


# ─── scheduled start ("Giờ bắt đầu") ─────────────────────────────

FUTURE = NOW + timedelta(days=30)


def test_a_scheduled_start_blocks_access_even_when_the_assignment_is_open():
    with pytest.raises(HTTPException) as err:
        require_assignment_open(_assignment(is_open=True, start_at=FUTURE))
    assert err.value.status_code == 403
    assert "giờ bắt đầu" in err.value.detail.lower()
    assert require_assignment_open(_assignment(is_open=True, start_at=NOW)) is None
    assert require_assignment_open(_assignment(is_open=True, start_at=None)) is None


def test_a_naive_start_datetime_is_compared_as_utc():
    with pytest.raises(HTTPException):
        require_assignment_open(_assignment(is_open=True, start_at=FUTURE.replace(tzinfo=None)))


def test_an_upcoming_assignment_hides_the_prompt_and_dataset_from_students():
    upcoming = _assignment(is_open=True, start_at=FUTURE)
    student = _to_response(upcoming, with_key=False)
    assert student.is_open is True
    assert student.start_at == FUTURE
    assert student.description == ""
    assert student.questions is None
    assert student.file_id is None
    assert student.answer_key is None and student.grading_config is None
    teacher = _to_response(upcoming, with_key=True)
    assert teacher.description == "Đề bí mật"
    assert teacher.file_id == str(FID)


def test_file_queries_treat_an_upcoming_assignment_as_closed():
    db = _Db([FID])
    assert asyncio.run(assignment_access.closed_file_ids(db, CID)) == {FID}
    assert "start_at IS NULL" in db.sql[0]
    assert "start_at <=" in db.sql[0]
    db = _Db([FID])
    asyncio.run(assignment_access.open_file_ids(db, CID))
    assert "start_at IS NULL" in db.sql[0]


@pytest.mark.parametrize("start,end", [
    (FUTURE, FUTURE),
    (FUTURE, FUTURE - timedelta(hours=1)),
])
def test_start_time_must_be_before_the_deadline(start, end):
    with pytest.raises(HTTPException) as err:
        assignments._validate_window(start, end)
    assert err.value.status_code == 400


def test_a_start_before_the_deadline_is_accepted():
    assert assignments._validate_window(FUTURE, FUTURE + timedelta(hours=1)) is None
    assert assignments._validate_window(None, FUTURE) is None


def test_a_new_assignment_stores_its_start_time(monkeypatch):
    start = datetime.now(tz=timezone.utc) + timedelta(hours=1)
    body = _create_body("homework").model_copy(update={
        "start_at": start, "deadline": start + timedelta(hours=2),
    })
    _wire_assignment_routes(monkeypatch, _file(student_access=False))
    db = _WriteDb()
    result = asyncio.run(assignments.create_assignment(CID, body, _teacher(), db))
    assert result.start_at == start
    assert db.added[0].start_at == start


def test_updating_and_clearing_the_start_time(monkeypatch):
    current = _assignment(is_open=True, deadline=datetime.now(tz=timezone.utc) + timedelta(days=1))
    _wire_assignment_routes(monkeypatch, _file(), current)
    db = _WriteDb()
    start = datetime.now(tz=timezone.utc) + timedelta(hours=2)
    result = asyncio.run(assignments.update_assignment(
        CID, AID, AssignmentUpdate(start_at=start), _teacher(), db))
    assert result.start_at == start
    assert current.start_at == start
    result = asyncio.run(assignments.update_assignment(
        CID, AID, AssignmentUpdate(start_at=None), _teacher(), db))
    assert result.start_at is None
    assert current.start_at is None
