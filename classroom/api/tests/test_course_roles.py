"""Row-level fakes for the role helpers in services.class_access.

The suite has no engine (the models use JSONB/UUID), so these tests drive the
functions directly with a stub session that answers by table name.
"""
import asyncio
import re
import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from services.class_access import (
    ASSISTANT, STUDENT, TEACHER, can_author, can_grade, class_role, enrollment_role, system_roles,
)

CID, UID, OTHER = (uuid.uuid4() for _ in range(3))


class _Result:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows

    def first(self):
        return self.rows[0] if self.rows else None

    def scalar(self):
        return self.rows[0][0] if self.rows else None

    def scalar_one_or_none(self):
        if not self.rows:
            return None
        row = self.rows[0]
        return row[0] if len(row) == 1 else row

    def scalars(self):
        return SimpleNamespace(all=lambda: [row[0] for row in self.rows])


class FakeDb:
    """``FakeDb(roles=[("admin",)])`` — one tuple per row, matched on FROM <table>."""

    def __init__(self, **rows_by_table):
        self.rows_by_table = rows_by_table

    async def execute(self, statement):
        sql = str(statement).lower()
        for table, rows in self.rows_by_table.items():
            if re.search(rf"\bfrom {table}\b", sql):
                return _Result(rows)
        raise AssertionError(f"Unexpected query: {sql}")


def _run(coro):
    return asyncio.run(coro)


def _user(user_id=UID):
    return SimpleNamespace(id=user_id)


def _cls(teacher_id=OTHER):
    return SimpleNamespace(id=CID, teacher_id=teacher_id)


# ─── system roles ───────────────────────────────────────────────

def test_system_roles_come_from_the_join():
    assert _run(system_roles(FakeDb(roles=[("user",), ("moderator",)]), UID)) == {"user", "moderator"}


# ─── the four answers class_role can give ───────────────────────

def test_the_owner_of_a_class_is_its_teacher():
    db = FakeDb(roles=[("user",)], enrollments=[("student",)])
    assert _run(class_role(db, _cls(teacher_id=UID), _user())) == TEACHER


def test_an_admin_is_a_teacher_in_every_class():
    assert _run(class_role(FakeDb(roles=[("admin",)]), _cls(), _user())) == TEACHER


def test_an_appointed_assistant_keeps_a_distinct_role():
    db = FakeDb(roles=[("user",)], enrollments=[(ASSISTANT,)])
    assert _run(class_role(db, _cls(), _user())) == ASSISTANT


def test_an_ordinary_enrollment_is_a_student():
    db = FakeDb(roles=[("user",)], enrollments=[(STUDENT,)])
    assert _run(class_role(db, _cls(), _user())) == STUDENT


def test_someone_with_no_active_enrollment_cannot_read_the_class():
    """Leaving a class, or never joining, drops the enrollment row out of the lookup."""
    with pytest.raises(HTTPException) as err:
        _run(class_role(FakeDb(roles=[("user",)], enrollments=[]), _cls(), _user()))
    assert err.value.status_code == 403


# ─── what each role is allowed to do ────────────────────────────

def test_only_the_teacher_and_the_assistant_grade():
    assert can_grade(TEACHER) and can_grade(ASSISTANT)
    assert not can_grade(STUDENT)


def test_only_the_teacher_writes_content_and_settings():
    assert can_author(TEACHER)
    assert not can_author(ASSISTANT)
    assert not can_author(STUDENT)


def test_enrollment_role_is_none_for_a_stranger():
    assert _run(enrollment_role(FakeDb(enrollments=[]), CID, UID)) is None
