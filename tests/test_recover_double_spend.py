"""Verify recover_stale_processing anti-double-spend: late ack rejected after recovery."""

from __future__ import annotations

import json

from device_gateway.redis_store import RedisDeviceTaskStore
from device_gateway.redis_store_helpers import encode_redis_json


class _FakeRedis:
    """Minimal Redis mock — no register_script so cas/requeue use fallback paths."""

    def __init__(self):
        self.hashes: dict[str, dict] = {}
        self.lists: dict[str, list] = {}
        self.values: dict[str, int] = {}
        self.now = 1000.0

    def time(self):
        return (self.now, 0)

    def incr(self, key):
        self.values[key] = int(self.values.get(key, 0)) + 1
        return self.values[key]

    def hset(self, name, key=None, value=None, mapping=None):
        bucket = self.hashes.setdefault(name, {})
        if mapping:
            bucket.update(mapping)
        elif key is not None:
            bucket[key] = value

    def hget(self, name, key):
        return self.hashes.get(name, {}).get(key)

    def hgetall(self, name):
        return dict(self.hashes.get(name, {}))

    def rpush(self, key, *values):
        q = self.lists.setdefault(key, [])
        q.extend(values)
        return len(q)

    def lpush(self, key, *values):
        q = self.lists.setdefault(key, [])
        for v in values:
            q.insert(0, v)
        return len(q)

    def lrange(self, key, start, end):
        q = self.lists.get(key, [])
        if end == -1:
            return q[start:]
        return q[start : end + 1]

    def lrem(self, key, count, value):
        q = self.lists.get(key, [])
        if value in q:
            q.remove(value)
            return 1
        return 0

    def llen(self, key):
        return len(self.lists.get(key, []))

    def expire(self, key, ttl):
        pass

    def scan_iter(self, match):
        prefix = match.rstrip("*")
        for key in [*self.values, *self.hashes, *self.lists]:
            if key.startswith(prefix):
                yield key


def _make_store(fake_redis: _FakeRedis) -> RedisDeviceTaskStore:
    return RedisDeviceTaskStore("redis://unused", client=fake_redis, key_prefix="test")


def _set_task_state(fake: _FakeRedis, prefix: str, task_id: str, state: dict) -> None:
    """Write task state into the fake hash the same way the real store does."""
    tasks_key = f"{prefix}:tasks"
    fake.hset(tasks_key, task_id, encode_redis_json(state))


def test_late_ack_rejected_after_recover() -> None:
    """Worker ack after task was recovered should return False (anti-double-spend)."""
    fake = _FakeRedis()
    store = _make_store(fake)
    device_id = "dev1"
    task_id = "task-001"

    # Place task in processing list
    task_item = json.dumps({"task_id": task_id, "_processing_at": "800"})
    proc_key = "test:processing:dev1"
    fake.lists[proc_key] = [task_item]

    # Set task state as processing
    _set_task_state(
        fake,
        "test",
        task_id,
        {
            "status": "processing",
            "processing_started_at": "800",
            "_version": 1,
        },
    )

    # Time=1000, started=800 → 200s > 120s default → stale
    recovered = store.recover_stale_processing(device_id)
    assert recovered == 1

    # Task state should now be queued with recovered_at
    state = store._read_task_state(task_id)
    assert state is not None
    assert state["status"] == "queued"
    assert "recovered_at" in state

    # Late ack from old worker should be rejected
    result = store.ack_processing(device_id, task_id)
    assert result is False


def test_normal_ack_succeeds() -> None:
    """Normal ack (no recovery) should succeed."""
    fake = _FakeRedis()
    store = _make_store(fake)
    device_id = "dev1"
    task_id = "task-002"

    # Task in processing, no recovery
    task_item = json.dumps({"task_id": task_id, "_processing_at": "950"})
    proc_key = "test:processing:dev1"
    fake.lists[proc_key] = [task_item]

    _set_task_state(
        fake,
        "test",
        task_id,
        {
            "status": "processing",
            "processing_started_at": "950",
            "_version": 1,
        },
    )

    result = store.ack_processing(device_id, task_id)
    assert result is True


def test_recover_skips_fresh_task() -> None:
    """Task within timeout should NOT be recovered."""
    fake = _FakeRedis()
    store = _make_store(fake)
    device_id = "dev1"
    task_id = "task-003"

    # processing_started_at=950, now=1000, elapsed=50s < 120s
    task_item = json.dumps({"task_id": task_id, "_processing_at": "950"})
    fake.lists["test:processing:dev1"] = [task_item]

    _set_task_state(
        fake,
        "test",
        task_id,
        {
            "status": "processing",
            "processing_started_at": "950",
            "_version": 1,
        },
    )

    recovered = store.recover_stale_processing(device_id)
    assert recovered == 0
    # Task still in processing list
    assert len(fake.lists.get("test:processing:dev1", [])) == 1
