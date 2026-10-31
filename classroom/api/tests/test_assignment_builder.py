"""The create-assignment dialog reads a class file's tables before saving."""
import asyncio
import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from routers import class_files
from routers.assignments import AssignmentCreate
from routers.class_files import router


def test_file_schema_preview_route_is_registered():
    paths = [r.path for r in router.routes if "GET" in getattr(r, "methods", set())]
    assert "/classes/{class_id}/files/{file_id}/omv-schema" in paths


def _preview(file_name, stored_path, upload_dir, monkeypatch):
    """Drive preview_file_schema with one class file on record and no database."""
    cf = SimpleNamespace(file_name=file_name, file_path=stored_path)

    class _Db:
        async def execute(self, *_a, **_k):
            return SimpleNamespace(scalar_one_or_none=lambda: cf)

    async def fake_class(_db, _class_id):
        return SimpleNamespace(teacher_id=uuid.uuid4())

    async def fake_roles(_db, _user_id):
        return {"admin"}

    monkeypatch.setattr(class_files, "settings", SimpleNamespace(upload_dir=str(upload_dir)))
    monkeypatch.setattr(class_files, "_get_class_or_404", fake_class)
    monkeypatch.setattr(class_files, "_get_user_roles_set", fake_roles)
    teacher = SimpleNamespace(id=uuid.uuid4())
    return asyncio.run(class_files.preview_file_schema(uuid.uuid4(), uuid.uuid4(), teacher, _Db()))


def test_a_spss_dataset_previews_as_no_results_not_as_a_broken_file(tmp_path, monkeypatch):
    """.sav/.csv/.xlsx all open in jamovi, so they are legitimate assignment data,
    but only a saved workbook holds analyses. Reading them as a .omv raised
    "File is not a zip file" and the teacher heard that their data was corrupt."""
    assert _preview("Baitap1_Glucose.sav", "c1/f1.sav", tmp_path, monkeypatch) == {
        "file_name": "Baitap1_Glucose.sav", "analyses": []}


def test_an_unreadable_omv_still_reports_the_problem(tmp_path, monkeypatch):
    """The empty answer above is for the format, not for damage: a .omv that will
    not open is the teacher's own file breaking and must not pass silently."""
    (tmp_path / "broken.omv").write_bytes(b"not really a zip")
    with pytest.raises(HTTPException) as err:
        _preview("mau.omv", "broken.omv", tmp_path, monkeypatch)
    assert err.value.status_code == 422


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
