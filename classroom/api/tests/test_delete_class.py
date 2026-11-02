"""A class delete is the one action in Classroom that has no way back.

``PATCH /classes/{id} {status: archived}`` is the reversible answer and already
existed, so ``DELETE /classes/{id}`` has to be the real one — otherwise a teacher
who pressed "Xoá" would find the class still sitting in the list. The cascade in
``models.py`` covers the rows; what it cannot reach is the uploads those rows
pointed at, so those are the files these tests care about.
"""
import asyncio
import uuid
from types import SimpleNamespace

import pytest

from routers import classes
from routers.classes import ClassRiskResponse, class_risk, delete_class


class _Db:
    """Answers each select the route makes, in the order the test scripts it."""

    def __init__(self, *results):
        self._results = list(results)
        self.deleted = []
        self.commits = 0
        self.seen_at_commit = None

    async def execute(self, statement):
        assert self._results, "the route asked the database more than the test scripted"
        return self._results.pop(0)

    async def delete(self, obj):
        self.deleted.append(obj)

    async def commit(self):
        self.commits += 1


def _res(value=None, many=()):
    return SimpleNamespace(
        scalar=lambda: value,
        scalars=lambda: SimpleNamespace(all=lambda: list(many)),
    )


def _class(**kw):
    base = dict(id=uuid.uuid4(), teacher_id=uuid.uuid4(), title="Thống kê 2026", status="active")
    base.update(kw)
    return SimpleNamespace(**base)


def _user():
    return SimpleNamespace(id=uuid.uuid4())


@pytest.fixture
def owning(monkeypatch):
    """Both routes start by loading the class and checking who owns it."""
    cls = _class()

    async def load(_db, class_id):
        return cls

    async def owns(_db, _cls, _user):
        return None

    monkeypatch.setattr(classes, "_get_class_or_404", load)
    monkeypatch.setattr(classes, "_require_teacher_owns", owns)
    return cls


@pytest.fixture
def uploads(tmp_path, monkeypatch):
    """The two trees a class owns: shared datasets and handed-in workbooks."""
    monkeypatch.setattr(classes, "settings", SimpleNamespace(upload_dir=str(tmp_path)))
    paths = [f"class/{uuid.uuid4()}/du_lieu.omv", f"submissions/{uuid.uuid4()}/{uuid.uuid4()}/bai_lam.omv"]
    for rel in paths:
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("x")
    return tmp_path, paths


def test_a_delete_removes_the_row_instead_of_hiding_it(owning, uploads):
    tmp, paths = uploads
    db = _Db(*[_res(many=[p]) for p in paths])

    asyncio.run(delete_class(owning.id, _user(), db))

    assert db.deleted == [owning]
    # archiving leaves the class in the teacher's list, which is what "Đóng tạm"
    # is for; the row itself has to go.
    assert owning.status == "active"


def test_a_delete_takes_the_uploaded_files_with_it(owning, uploads):
    tmp, paths = uploads
    db = _Db(*[_res(many=[p]) for p in paths])

    asyncio.run(delete_class(owning.id, _user(), db))

    assert not any((tmp / p).exists() for p in paths)


def test_files_survive_until_the_delete_is_committed(owning, uploads):
    """Rollback-safe: rows first, disk after. Deleting the workbooks of a class
    that is still in the database would leave a teacher graded work without
    files, which is the worse half of a failed delete."""
    tmp, paths = uploads
    db = _Db(*[_res(many=[p]) for p in paths])
    db.commit = lambda: _commit_and_watch(db, tmp, paths)

    asyncio.run(delete_class(owning.id, _user(), db))

    assert db.seen_at_commit == [True] * len(paths)
    assert not any((tmp / p).exists() for p in paths)


def _commit_and_watch(db, tmp, paths):
    async def _commit():
        db.commits += 1
        db.seen_at_commit = [(tmp / p).exists() for p in paths]
    return _commit()


def test_a_delete_the_database_refused_leaves_the_files_alone(owning, uploads):
    tmp, paths = uploads
    db = _Db(*[_res(many=[p]) for p in paths])

    async def refuses():
        raise RuntimeError("foreign key still points at this class")

    db.commit = refuses

    with pytest.raises(RuntimeError):
        asyncio.run(delete_class(owning.id, _user(), db))

    assert all((tmp / p).exists() for p in paths)


def test_the_empty_upload_folders_go_too(owning, uploads):
    """class/<classId> and submissions/<assignmentId>/<studentId> are created per
    object, so deleting the files alone would leave the volume full of husks."""
    tmp, paths = uploads
    db = _Db(*[_res(many=[p]) for p in paths])

    asyncio.run(delete_class(owning.id, _user(), db))

    assert not any((tmp / p).parent.exists() for p in paths)


def test_a_folder_holding_another_classes_work_is_left_alone(owning, uploads):
    tmp, paths = uploads
    sibling_dir = (tmp / paths[1]).parent
    keeper = sibling_dir / "lop_khac.omv"
    keeper.write_text("x")
    db = _Db(*[_res(many=[p]) for p in paths])

    asyncio.run(delete_class(owning.id, _user(), db))

    assert not (tmp / paths[1]).exists()
    assert keeper.exists() and keeper.parent.exists()
    assert keeper.parent.parent.exists()


def test_the_owner_check_runs_before_anything_is_deleted(monkeypatch, owning):
    async def not_mine(_db, _cls, _user):
        raise classes.HTTPException(status_code=403, detail="Không có quyền thực hiện")

    monkeypatch.setattr(classes, "_require_teacher_owns", not_mine)
    db = _Db()

    with pytest.raises(classes.HTTPException) as e:
        asyncio.run(delete_class(owning.id, _user(), db))

    assert e.value.status_code == 403
    assert db.deleted == []


def test_the_warning_names_everything_a_delete_would_take(owning):
    # assignments, submissions, lessons, quizzes, files, students
    db = _Db(_res(4), _res(37), _res(9), _res(2), _res(11), _res(48))

    risk = asyncio.run(class_risk(owning.id, _user(), db))

    assert risk == ClassRiskResponse(
        assignments=4, submissions=37, lessons=9, quizzes=2, files=11, students=48
    )


def test_an_empty_class_reports_zeroes_rather_than_nulls(owning):
    db = _Db(*[_res(None)] * 6)

    assert asyncio.run(class_risk(owning.id, _user(), db)).students == 0


def test_the_dialog_has_a_route_to_ask_and_the_class_list_has_a_delete():
    methods = {(m, r.path) for r in classes.router.routes for m in getattr(r, "methods", set())}
    assert ("GET", "/classes/{class_id}/risk") in methods
    assert ("DELETE", "/classes/{class_id}") in methods
