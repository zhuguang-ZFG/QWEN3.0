"""Tests for AUDIT-9-S4 task state CAS optimistic locking."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest

from device_gateway.redis_cas import (
    VERSION_FIELD,
    append_event_atomic,
    bump_version,
    cas_write_state,
    get_version,
)


class _FakeRedis:
    """Minimal in-memory Redis fake supporting HGET/HSET/EXPIRE (no Lua)."""

    def __init__(self):
        self._hash: dict[str, str] = {}
        self._ttls: dict[str, int] = {}

    def hget(self, key, field):
        return self._hash.get(field)

    def hset(self, key, field, value):
        self._hash[field] = value

    def expire(self, key, ttl):
        self._ttls[key] = ttl


TASKS_KEY = "lima:device:tasks"


def _state(status="created", events=None, version=0, **extra):
    s = {"task": {"task_id": "t1"}, "status": status, "events": events or []}
    if version:
        s[VERSION_FIELD] = version
    s.update(extra)
    return s


def test_cas_write_succeeds_on_matching_version():
    r = _FakeRedis()
    r.hset(TASKS_KEY, "t1", '{"status":"created","events":[],"_version":2}')
    new = _state(status="queued", version=3)
    assert cas_write_state(r, TASKS_KEY, "t1", new, expected_version=2, ttl_seconds=300) is True


def test_cas_write_fails_on_version_mismatch():
    r = _FakeRedis()
    r.hset(TASKS_KEY, "t1", '{"status":"created","events":[],"_version":5}')
    new = _state(status="queued", version=6)
    assert cas_write_state(r, TASKS_KEY, "t1", new, expected_version=2, ttl_seconds=300) is False


def test_cas_write_fails_on_missing_when_expected_nonzero():
    r = _FakeRedis()
    new = _state(status="queued")
    assert cas_write_state(r, TASKS_KEY, "missing", new, expected_version=0, ttl_seconds=300) is False


def test_cas_write_creates_when_expected_negative():
    r = _FakeRedis()
    new = _state(status="created")
    assert cas_write_state(r, TASKS_KEY, "new_task", new, expected_version=-1, ttl_seconds=300) is True


def test_append_event_atomic_appends_and_bumps_version():
    r = _FakeRedis()
    r.hset(TASKS_KEY, "t1", '{"task":{"task_id":"t1"},"status":"dispatched","events":[{"phase":"accepted"}],"_version":1}')
    updated = append_event_atomic(r, TASKS_KEY, "t1", {"phase": "done"}, 300, new_status="done")
    assert updated is not None
    assert len(updated["events"]) == 2
    assert updated["events"][1]["phase"] == "done"
    assert updated["status"] == "done"
    assert updated[VERSION_FIELD] == 2


def test_append_event_atomic_returns_none_for_missing_task():
    r = _FakeRedis()
    assert append_event_atomic(r, TASKS_KEY, "ghost", {"phase": "done"}, 300) is None


def test_append_event_concurrent_no_lost_append():
    """Two sequential appends both preserved (simulating concurrent appends)."""
    r = _FakeRedis()
    r.hset(TASKS_KEY, "t1", '{"task":{"task_id":"t1"},"status":"accepted","events":[],"_version":0}')
    append_event_atomic(r, TASKS_KEY, "t1", {"phase": "progress", "msg": "A"}, 300)
    append_event_atomic(r, TASKS_KEY, "t1", {"phase": "done", "msg": "B"}, 300)
    # Both events should be present — no lost append.
    cur = r.hget(TASKS_KEY, "t1")
    import json

    state = json.loads(cur)
    assert len(state["events"]) == 2
    assert state["events"][0]["msg"] == "A"
    assert state["events"][1]["msg"] == "B"


def test_backward_compat_old_state_without_version():
    """Old state blobs without _version should be treated as version 0."""
    r = _FakeRedis()
    r.hset(TASKS_KEY, "t1", '{"task":{"task_id":"t1"},"status":"created","events":[]}')
    new = _state(status="queued", version=1)
    assert cas_write_state(r, TASKS_KEY, "t1", new, expected_version=0, ttl_seconds=300) is True


def test_bump_version_and_get_version():
    state = {"status": "created"}
    assert get_version(state) == 0
    assert bump_version(state) == 1
    assert get_version(state) == 1
    assert bump_version(state) == 2


def test_bump_version_preserves_other_fields():
    state = {"status": "queued", "retry_count": 3, "events": [{"phase": "done"}]}
    bump_version(state)
    assert state["status"] == "queued"
    assert state["retry_count"] == 3
    assert len(state["events"]) == 1
