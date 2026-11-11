"""Autosaved drafts reuse one row; answer-only work can still be submitted."""
import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from routers.submissions import _create_submission

NOW = datetime.now(tz=timezone.utc)
CID, AID = uuid.uuid4(), uuid.uuid4()
STUDENT = SimpleNamespace(id=uuid.uuid4())


def _assignment(**changes):
    fields = dict(
        id=AID, class_id=CID, title="Bài 1", is_open=True,
        deadline=NOW + timedelta(days=1), allow_resubmit=True, max_score=10.0,
        answer_key={"questions": [{"id": "q1", "label": "Mean", "type": "number",
                                  "answer": 3.14, "tolerance": 0.01, "points": 1}]},
        grading_config=None,
    )
    return SimpleNamespace(**(fields | changes))


def _draft(**changes):
    fields = dict(
        id=uuid.uuid4(), assignment_id=AID, student_id=STUDENT.id, is_final=False,
        file_path=None, session_snapshot={"draft": True, "tables": []}, answers={"q1": "1"},
        score=None, feedback=None, auto_grade=None, graded_at=None, graded_by=None,
        submitted_at=NOW - timedelta(minutes=1),
    )
    return SimpleNamespace(**(fields | changes))


class _Db:
    def __init__(self, assignment, *, enrolled=True, draft=None, finals=()):
        self.assignment = assignment
        self.enrolled = enrolled
        self.draft = draft
        self.finals = list(finals)
        self.added = []
        self.commits = 0

    async def execute(self, statement):
        sql = str(statement).lower()
        one = lambda value: SimpleNamespace(  # noqa: E731 - tiny result double
            scalar_one_or_none=lambda: value,
            scalars=lambda: SimpleNamespace(all=lambda: list(self.finals)),
            all=lambda: list(self.finals),
        )
        if "from assignments" in sql:
            return one(self.assignment)
        if "from enrollments" in sql:
            return one(SimpleNamespace(id=uuid.uuid4()) if self.enrolled else None)
        if "from submissions" in sql:
            if "for update" in sql:
                return one(self.draft)
            return one(None)
        raise AssertionError(f"Unexpected query: {statement}")

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        for obj in self.added:
            if getattr(obj, "id", None) is None:
                obj.id = uuid.uuid4()

    async def commit(self):
        self.commits += 1


def _call(db, **kwargs):
    return asyncio.run(_create_submission(AID, STUDENT, db, **kwargs))


def test_an_answer_only_draft_is_saved_and_reuses_its_row():
    db = _Db(_assignment())
    first = _call(db, answers={"q1": "3.14"}, is_final=False)
    assert first.is_final is False and first.answers == {"q1": "3.14"}
    draft = db.added[0]
    assert draft.session_snapshot["draft"] is True
    assert db.commits == 1
    db.draft = draft

    second = _call(db, answers={"q1": "3.15"}, is_final=False, draft_id=draft.id)
    assert second.id == first.id
    assert draft.answers == {"q1": "3.15"}
    assert len(db.added) == 1
    assert db.commits == 2


def test_a_draft_can_become_the_final_submission_without_a_dataset():
    db = _Db(_assignment())
    result = _call(db, answers={"q1": "3.14"}, is_final=True)
    saved = db.added[0]
    assert saved.is_final is True
    assert saved.score == 10.0
    assert result.score is None  # students never receive the mark
    assert saved.session_snapshot is None


def test_the_draft_row_itself_becomes_the_final_submission():
    db = _Db(_assignment())
    _call(db, answers={"q1": "3.14"}, is_final=False)
    draft = db.added[0]
    db.draft = draft
    result = _call(db, answers={"q1": "3.14"}, is_final=True, draft_id=draft.id)
    assert result.id == str(draft.id)
    assert draft.is_final is True
    assert draft.score == 10.0
    assert len([x for x in db.added if x.__class__.__name__ == "Submission"]) == 1


def test_an_essay_only_submission_waits_for_the_teacher_instead_of_scoring_zero():
    essay = {"questions": [{"id": "e1", "label": "Nhận xét", "type": "essay", "points": 3}]}
    db = _Db(_assignment(answer_key=essay))
    _call(db, answers={"e1": "Kết quả có ý nghĩa thống kê."}, is_final=True)
    saved = db.added[0]
    assert saved.score is None and saved.graded_at is None
    assert saved.auto_grade["items"][0]["pending"] is True


def test_a_closed_assignment_accepts_neither_drafts_nor_submissions():
    for final in (False, True):
        db = _Db(_assignment(is_open=False))
        with pytest.raises(HTTPException) as err:
            _call(db, answers={"q1": "3.14"}, is_final=final)
        assert err.value.status_code == 403
        assert db.added == [] and db.commits == 0


def test_a_student_cannot_overwrite_someone_elses_or_a_graded_draft():
    # The query is scoped to the caller, so another student's row is simply absent.
    foreign = _draft(student_id=uuid.uuid4())
    db = _Db(_assignment(), draft=None)
    with pytest.raises(HTTPException) as err:
        _call(db, answers={"q1": "2"}, is_final=False, draft_id=foreign.id)
    assert err.value.status_code == 409

    for bad in (_draft(is_final=True), _draft(graded_at=NOW), _draft(graded_by=uuid.uuid4()),
                _draft(score=5.0), _draft(session_snapshot={"tables": []})):
        db = _Db(_assignment(), draft=bad)
        with pytest.raises(HTTPException) as err:
            _call(db, answers={"q1": "2"}, is_final=False, draft_id=bad.id)
        assert err.value.status_code == 409
        assert db.added == [] and db.commits == 0


def test_a_non_object_answers_field_is_rejected():
    db = _Db(_assignment())
    with pytest.raises(HTTPException) as err:
        _call(db, answers=[1, 2], is_final=False)
    assert err.value.status_code == 400
