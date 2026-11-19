"""Who is in class right now: the seat claims behind the teacher's live counts."""
import asyncio
import time
import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from routers import presence

CID = uuid.uuid4()
UID = uuid.uuid4()
GONE = uuid.uuid4()
TEACHER = uuid.uuid4()
OTHER = uuid.uuid4()
TAB = "a1b2c3d4e5f6"
NOW = 1_700_000_000.0


class _Redis:
    def __init__(self):
        self.zsets = {}
        self.kvs = {}

    async def zadd(self, key, mapping):
        self.zsets.setdefault(key, {}).update(mapping)

    async def zrem(self, key, *members):
        for member in members:
            self.zsets.get(key, {}).pop(member, None)

    async def zrangebyscore(self, key, min=None, max=None, withscores=False):
        hits = [(m, s) for m, s in self.zsets.get(key, {}).items() if min <= s <= max]
        return sorted(hits, key=lambda hit: hit[1])

    async def zremrangebyscore(self, key, min=None, max=None):
        for member, score in list(self.zsets.get(key, {}).items()):
            if min <= score <= max:
                self.zsets[key].pop(member)

    async def expire(self, key, seconds):
        pass

    async def setex(self, key, ttl, value):
        self.kvs[key] = value

    async def get(self, key):
        return self.kvs.get(key)

    async def delete(self, *keys):
        for key in keys:
            self.kvs.pop(key, None)


class _Result:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        if isinstance(self.value, list):
            return self.value[0] if self.value else None
        return self.value

    def scalars(self):
        return self

    def all(self):
        return self.value if isinstance(self.value, list) else [self.value]


_TABLES = {"roles": "from roles", "classes": "from classes", "enrollments": "from enrollments"}


class _Db:
    """Each route here touches one table at a time, so the fake answers by table."""
    def __init__(self, **results):
        self.results = results

    async def execute(self, statement):
        sql = str(statement).lower()
        for table, needle in _TABLES.items():
            if table in self.results and needle in sql:
                return _Result(self.results[table])
        raise AssertionError(f"Unexpected query: {sql}")


@pytest.fixture
def redis(monkeypatch):
    r = _Redis()

    async def get_redis():
        return r

    monkeypatch.setattr(presence, "get_redis", get_redis)
    return r


def _request(cookie=None) -> Request:
    headers = [(b"cookie", f"hs_session={cookie}".encode())] if cookie else []
    return Request({"type": "http", "path": "/", "headers": headers})


def _beat(class_id=CID, user_id=UID, tab=TAB, editing=False):
    return presence.BeatRequest(class_id=class_id, tab_id=tab, editing=editing)


# ── the two levels the teacher wants kept apart ──────────────────

def test_a_seat_is_claimed_without_claiming_the_editor(redis):
    asyncio.run(presence.record_beat(redis, CID, UID, TAB, editing=False, now=NOW))
    assert redis.zsets[presence._online_key(CID)] == {f"{TAB}:{UID}": NOW}
    assert presence._editing_key(CID) not in redis.zsets


def test_an_open_editor_is_reported_separately():
    async def scenario():
        r = _Redis()
        await presence.record_beat(r, CID, UID, TAB, editing=True, now=NOW)
        return await presence.read_claims(r, CID, NOW)

    assert asyncio.run(scenario()) == {str(UID): (True, NOW)}


def test_closing_the_editor_keeps_the_seat():
    async def scenario():
        r = _Redis()
        await presence.record_beat(r, CID, UID, TAB, editing=True, now=NOW - 10)
        await presence.record_beat(r, CID, UID, TAB, editing=False, now=NOW)
        return await presence.read_claims(r, CID, NOW)

    assert asyncio.run(scenario()) == {str(UID): (False, NOW)}


def test_a_stale_seat_is_forgotten():
    async def scenario():
        r = _Redis()
        await presence.record_beat(r, CID, UID, TAB, editing=True, now=NOW)
        return await presence.read_claims(r, CID, NOW + presence.ONLINE_WINDOW + 1)

    assert asyncio.run(scenario()) == {}


def test_two_tabs_of_one_student_are_one_student():
    async def scenario():
        r = _Redis()
        await presence.record_beat(r, CID, UID, TAB, editing=False, now=NOW)
        await presence.record_beat(r, CID, UID, "zeta000001", editing=True, now=NOW - 5)
        return await presence.read_claims(r, CID, NOW)

    assert asyncio.run(scenario()) == {str(UID): (True, NOW)}


# ── the beat endpoint ────────────────────────────────────────────

def test_a_member_claims_a_seat(redis):
    asyncio.run(presence.beat(_beat(editing=True), SimpleNamespace(id=UID), _Db(enrollments=1)))
    member = f"{TAB}:{UID}"
    assert member in redis.zsets[presence._online_key(CID)]
    assert member in redis.zsets[presence._editing_key(CID)]


def test_a_stranger_cannot_claim_a_seat_in_a_class(redis):
    db = _Db(enrollments=None, classes=SimpleNamespace(id=CID, teacher_id=TEACHER))
    with pytest.raises(HTTPException) as err:
        asyncio.run(presence.beat(_beat(), SimpleNamespace(id=UID), db))
    assert err.value.status_code == 403
    assert redis.zsets == {}


def test_the_running_teacher_may_claim_a_seat(redis):
    db = _Db(enrollments=None, classes=SimpleNamespace(id=CID, teacher_id=TEACHER))
    asyncio.run(presence.beat(_beat(), SimpleNamespace(id=TEACHER), db))
    assert presence._online_key(CID) in redis.zsets


def test_a_malformed_tab_id_is_refused(redis):
    with pytest.raises(HTTPException) as err:
        asyncio.run(presence.beat(_beat(tab="ab"), SimpleNamespace(id=UID), _Db(enrollments=1)))
    assert err.value.status_code == 400


# ── leaving: a beacon, so it survives the tab closing ────────────

def test_a_closed_tab_loses_both_claims(redis, monkeypatch):
    async def validate(_token):
        return str(UID)

    monkeypatch.setattr(presence, "validate_refresh_token", validate)
    asyncio.run(presence.record_beat(redis, CID, UID, TAB, editing=True, now=time.time()))

    asyncio.run(presence.leave(_request("token"), tab=TAB))

    assert redis.zsets[presence._online_key(CID)] == {}
    assert redis.zsets[presence._editing_key(CID)] == {}
    assert redis.kvs == {}


def test_a_beacon_cannot_free_another_students_seat(redis, monkeypatch):
    async def validate(_token):
        return str(OTHER)

    monkeypatch.setattr(presence, "validate_refresh_token", validate)
    asyncio.run(presence.record_beat(redis, CID, UID, TAB, editing=True, now=time.time()))

    asyncio.run(presence.leave(_request("token"), tab=TAB))

    assert f"{TAB}:{UID}" in redis.zsets[presence._online_key(CID)]


def test_a_beacon_without_a_session_cookie_is_refused(redis):
    with pytest.raises(HTTPException) as err:
        asyncio.run(presence.leave(_request(), tab=TAB))
    assert err.value.status_code == 401


# ── the teacher's readout ────────────────────────────────────────

def _read(r, roster, claims, viewer=TEACHER, roles=("teacher",), cls_teacher=TEACHER):
    async def scenario():
        for user_id, tab, editing in claims:
            await presence.record_beat(r, CID, user_id, tab, editing=editing, now=time.time())
        return await presence.class_presence(
            CID, SimpleNamespace(id=viewer),
            _Db(roles=[(role,) for role in roles],
                classes=SimpleNamespace(id=CID, teacher_id=cls_teacher),
                enrollments=list(roster)),
        )

    return asyncio.run(scenario())


def test_the_counts_separate_present_from_working(redis):
    out = _read(
        redis,
        roster=[UID, GONE],
        claims=[(UID, TAB, True), (GONE, "tabbbbbbbb", False)],
    )
    assert (out.enrolled_total, out.online_total, out.editing_total) == (2, 2, 1)
    by_user = {s.user_id: s for s in out.students}
    assert (by_user[str(UID)].online, by_user[str(UID)].editing) == (True, True)
    assert (by_user[str(GONE)].online, by_user[str(GONE)].editing) == (True, False)


def test_a_removed_student_is_not_counted_even_with_a_live_claim(redis):
    out = _read(redis, roster=[UID], claims=[(OTHER, "tabccccccc", True)])
    assert (out.online_total, out.editing_total) == (0, 0)
    assert [s.user_id for s in out.students] == [str(UID)]


def test_only_the_running_teacher_or_an_admin_may_read(redis):
    with pytest.raises(HTTPException) as err:
        _read(redis, roster=[UID], claims=[], viewer=OTHER)
    assert err.value.status_code == 403
    assert _read(redis, roster=[UID], claims=[], viewer=OTHER, roles=("admin",)).enrolled_total == 1


def test_a_blank_class_reads_zero_but_still_lists_nobody(redis):
    out = _read(redis, roster=[], claims=[])
    assert (out.online_total, out.editing_total, out.students) == (0, 0, [])
    assert out.window_seconds == presence.ONLINE_WINDOW


# ── the routes as the browser calls them ─────────────────────────

def test_the_routes_serve_the_beat_the_beacon_and_the_readout(redis, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from auth.deps import get_current_user
    from database import get_db

    async def validate(_token):
        return str(UID)

    monkeypatch.setattr(presence, "validate_refresh_token", validate)
    db = _Db(roles=[("teacher",)], classes=SimpleNamespace(id=CID, teacher_id=UID), enrollments=[UID])

    app = FastAPI()
    app.include_router(presence.router, prefix="/api/v1")
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=UID)

    async def db_override():
        yield db

    app.dependency_overrides[get_db] = db_override
    client = TestClient(app)

    assert client.post("/api/v1/presence/beat",
                       json={"class_id": str(CID), "tab_id": TAB, "editing": True}).status_code == 204
    readout = client.get(f"/api/v1/classes/{CID}/presence")
    assert readout.status_code == 200
    assert readout.json()["online_total"] == 1 and readout.json()["editing_total"] == 1

    client.cookies.set("hs_session", "cookie-token")
    assert client.post("/api/v1/presence/leave", params={"tab": TAB}).status_code == 204
    assert client.get(f"/api/v1/classes/{CID}/presence").json()["online_total"] == 0
