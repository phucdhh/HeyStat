"""The «Học viên» tab exports to CSV so a teacher can hand the roster to Excel.

One row per student, one column per assignment; the cell has to say the same
thing the tab says, in a form that survives a comma.
"""
import asyncio
import uuid
from datetime import datetime, timezone

import pytest
from pydantic import TypeAdapter, ValidationError

from routers.classes import (
    StudentProgress, StudentResponse, _ascii_slug, _progress_cell, list_students, router,
)

DEADLINE = datetime(2026, 11, 5, 23, 59, tzinfo=timezone.utc)


def _progress(**kw) -> StudentProgress:
    base = dict(assignment_id="a1", title="Bài 1", assignment_type="homework",
                deadline=DEADLINE, max_score=10.0, state="open")
    base.update(kw)
    return StudentProgress(**base)


def test_export_route_is_registered():
    paths = [r.path for r in router.routes if "GET" in getattr(r, "methods", set())]
    assert "/classes/{class_id}/students/export" in paths


def test_each_state_writes_one_cell():
    assert _progress_cell(_progress()) == "chưa tới hạn"
    assert _progress_cell(_progress(state="missing")).startswith("chưa nộp – quá hạn")
    assert _progress_cell(_progress(state="submitted", submitted_at=DEADLINE)).startswith("đã nộp, chờ chấm")
    assert _progress_cell(_progress(score=8.5, submitted_at=DEADLINE)).startswith("đã chấm 8.5/10")


def test_a_vietnamese_class_title_stays_header_safe():
    assert _ascii_slug("Thống kê ứng dụng 2026") == "Thong_ke_ung_dung_2026"


def test_the_tab_route_answers_with_rows_the_browser_can_validate(monkeypatch):
    """_roster also returns the class assignments, because the CSV needs one
    column per assignment. Handing that pair straight to FastAPI instead fails
    the route's response_model, so the tab 500s and reads "Chưa có học viên"
    while the export next to it still works."""
    students = [StudentResponse(
        id="u1", email="sv@test.vn", full_name="Test SV 01", enrolled_at=DEADLINE,
        status="active", assignments_total=0, submitted=0, graded=0,
        awaiting_grade=0, missing=0, progress=[],
    )]

    async def fake_roster(db, class_id, current_user):
        return students, ["an assignment"]

    monkeypatch.setattr("routers.classes._roster", fake_roster)
    as_json = lambda value: TypeAdapter(list[StudentResponse]).validate_python(value)

    assert asyncio.run(list_students(uuid.uuid4(), object(), object())) == students
    assert as_json(students)
    with pytest.raises(ValidationError):
        as_json((students, ["an assignment"]))
