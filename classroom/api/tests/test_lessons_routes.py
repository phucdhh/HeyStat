"""Route ordering guard for the lessons router.

FastAPI resolves a request against the first matching route, so a literal path
segment that also fits a parameterised route declared earlier is unreachable.
"""
from routers.lessons import router


def _patch_paths():
    return [r.path for r in router.routes if "PATCH" in getattr(r, "methods", set())]


def test_reorder_is_declared_before_the_lesson_id_route():
    paths = _patch_paths()
    reorder = paths.index("/classes/{class_id}/lessons/reorder")
    by_id = paths.index("/classes/{class_id}/lessons/{lesson_id}")
    assert reorder < by_id


def test_every_lesson_kind_has_a_matching_resource_to_lead_with():
    """The authoring UI offers one card per kind, and each kind opens on a
     specific kind of attachment — the two lists have to stay in step."""
    from routers.lessons import LESSON_TYPES, RESOURCE_TYPES

    assert LESSON_TYPES == ("standard", "practical", "video", "reading")
    assert {"data_file", "video", "pdf", "link"} == set(RESOURCE_TYPES)


def test_deleting_a_lesson_detaches_its_quiz_instead_of_failing(monkeypatch):
    """quizzes_lesson_id_fkey is NO ACTION, so Postgres would refuse to delete a
    lesson that still has a quiz parked under it and the new delete button would
    500. The quiz is listed and graded in its own tab, so it outlives the lesson."""
    import asyncio
    import uuid
    from types import SimpleNamespace

    from routers import lessons

    statements = []
    lesson = SimpleNamespace(id=uuid.uuid4())

    class _Db:
        async def execute(self, statement):
            statements.append(str(statement))
            return SimpleNamespace(scalar_one_or_none=lambda: lesson)

        async def delete(self, obj):
            statements.append(("delete", obj))

    async def access(_db, _class_id, _user):
        return SimpleNamespace(teacher_id=uuid.uuid4()), "teacher"

    monkeypatch.setattr(lessons, "_class_access", access)
    asyncio.run(lessons.delete_lesson(
        uuid.uuid4(), lesson.id, SimpleNamespace(id=uuid.uuid4()), _Db()))

    assert statements[0].startswith("SELECT lessons.id")
    assert statements[1].startswith("UPDATE quizzes SET lesson_id")
    assert statements[2] == ("delete", lesson)
