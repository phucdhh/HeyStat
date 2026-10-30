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
