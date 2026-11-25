"""Counters shown on each class card of the teacher dashboard."""
import asyncio
import uuid
from types import SimpleNamespace

from routers import classes

CID = uuid.UUID(int=1)
UID1, UID2 = uuid.UUID(int=2), uuid.UUID(int=3)


class _Db:
    """Return one prepared result set per execute() call, in order."""

    def __init__(self, *results):
        self.results = list(results)
        self.calls = 0

    async def execute(self, statement):
        rows = self.results[self.calls]
        self.calls += 1
        return SimpleNamespace(all=lambda: rows)


def test_class_stats_groups_students_lessons_and_submitters():
    db = _Db([(CID, UID1), (CID, UID2)], [(CID, 4)], [(CID, 1)])
    students, lessons, submitted, rosters = asyncio.run(classes._class_stats(db, [CID]))
    assert students == {CID: 2}
    assert lessons == {CID: 4}
    assert submitted == {CID: 1}
    assert rosters[CID] == {str(UID1), str(UID2)}


def test_class_stats_short_circuits_when_there_are_no_classes():
    assert asyncio.run(classes._class_stats(_Db(), [])) == ({}, {}, {}, {})


def test_online_count_counts_only_enrolled_students(monkeypatch):
    async def redis():
        return object()

    async def claims(_redis, _class_id, _now):
        return {str(UID1): (False, 1.0), "assistant-or-outsider": (False, 1.0)}

    monkeypatch.setattr(classes, "get_redis", redis)
    monkeypatch.setattr(classes, "read_claims", claims)
    counts = asyncio.run(classes._online_counts([CID], {CID: {str(UID1)}}))
    assert counts == {CID: 1}


def test_online_count_degrades_to_zero_when_redis_is_down(monkeypatch):
    async def boom():
        raise RuntimeError("redis down")

    monkeypatch.setattr(classes, "get_redis", boom)
    counts = asyncio.run(classes._online_counts([CID], {CID: {str(UID1)}}))
    assert counts == {CID: 0}
