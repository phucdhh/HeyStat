"""The create-assignment dialog reads a class file's tables before saving."""
from routers.assignments import AssignmentCreate
from routers.class_files import router


def test_file_schema_preview_route_is_registered():
    paths = [r.path for r in router.routes if "GET" in getattr(r, "methods", set())]
    assert "/classes/{class_id}/files/{file_id}/omv-schema" in paths


def test_create_accepts_the_grading_the_dialog_builds():
    body = AssignmentCreate(
        title="Kiểm định t",
        description="Chạy One Sample T-Test",
        deadline="2026-11-01T23:59:00+00:00",
        assignment_type="exam",
        answer_key={"questions": [{"id": "q1", "label": "p", "type": "number",
                                   "answer": 0.02, "tolerance": 0.01, "points": 2}]},
        grading_config={"checks": [{"id": "c1", "label": "T-test", "analysis":
                                    "One Sample T-Test", "op": "ran", "points": 1}]},
    )
    assert body.group_size == 1 and body.allow_sharing is False
