"""The «Học viên» tab exports to CSV so a teacher can hand the roster to Excel.

One row per student, one column per assignment; the cell has to say the same
thing the tab says, in a form that survives a comma.
"""
from datetime import datetime, timezone

from routers.classes import StudentProgress, _ascii_slug, _progress_cell, router

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
