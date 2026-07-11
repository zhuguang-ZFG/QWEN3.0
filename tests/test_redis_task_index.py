"""Tests for per-device Redis task index (LIMA_REDIS_TASK_INDEX feature flag)."""

from __future__ import annotations

from tests.test_device_gateway_redis_store import _FakeRedis, _task

from device_gateway.redis_store import RedisDeviceTaskStore


class _FakeRedisWithSets(_FakeRedis):
    """Extends _FakeRedis with Set commands (sadd/smembers/srem) and hmget."""

    def __init__(self):
        super().__init__()
        self.sets: dict[str, set[str]] = {}

    def sadd(self, key, *members):
        s = self.sets.setdefault(key, set())
        added = 0
        for m in members:
            if m not in s:
                s.add(m)
                added += 1
        return added

    def smembers(self, key):
        return set(self.sets.get(key, set()))

    def srem(self, key, *members):
        s = self.sets.get(key, set())
        removed = 0
        for m in members:
            if m in s:
                s.discard(m)
                removed += 1
        return removed

    def hmget(self, name, keys):
        bucket = self.hashes.get(name, {})
        return [bucket.get(k) for k in keys]

    def delete(self, *keys):
        super().delete(*keys)
        for key in keys:
            self.sets.pop(key, None)


def _store(client):
    return RedisDeviceTaskStore("redis://unused", client=client, key_prefix="test:device")


def test_index_on_create_populates_set(monkeypatch):
    monkeypatch.setenv("LIMA_REDIS_TASK_INDEX", "1")
    client = _FakeRedisWithSets()
    store = _store(client)
    task = _task(store.next_task_id(), "dev-1")
    store.create_task_state(task)

    index_key = store._index_key("dev-1")
    assert task["task_id"] in client.smembers(index_key)


def test_index_off_create_does_not_populate_set(monkeypatch):
    monkeypatch.setenv("LIMA_REDIS_TASK_INDEX", "0")
    client = _FakeRedisWithSets()
    store = _store(client)
    task = _task(store.next_task_id(), "dev-1")
    store.create_task_state(task)

    index_key = store._index_key("dev-1")
    assert client.smembers(index_key) == set()


def test_list_tasks_consistent_on_and_off(monkeypatch):
    client = _FakeRedisWithSets()
    store = _store(client)

    monkeypatch.setenv("LIMA_REDIS_TASK_INDEX", "1")
    t1 = _task(store.next_task_id(), "dev-1")
    t2 = _task(store.next_task_id(), "dev-1")
    store.create_task_state(t1, status="created")
    store.create_task_state(t2, status="queued")

    result_on = store.list_tasks_for_device("dev-1")

    monkeypatch.setenv("LIMA_REDIS_TASK_INDEX", "0")
    result_off = store.list_tasks_for_device("dev-1")

    assert sorted(result_on, key=lambda x: x["task_id"]) == sorted(result_off, key=lambda x: x["task_id"])


def test_active_tasks_filters_terminal_status(monkeypatch):
    monkeypatch.setenv("LIMA_REDIS_TASK_INDEX", "1")
    client = _FakeRedisWithSets()
    store = _store(client)

    active_task = _task(store.next_task_id(), "dev-1")
    done_task = _task(store.next_task_id(), "dev-1")
    store.create_task_state(active_task, status="dispatched")
    store.create_task_state(done_task, status="done")

    result = store.active_tasks_for_device("dev-1")
    task_ids = [t["task_id"] for t in result]
    assert active_task["task_id"] in task_ids
    assert done_task["task_id"] not in task_ids


def test_self_heal_fallback_warms_index(monkeypatch):
    client = _FakeRedisWithSets()
    store = _store(client)

    monkeypatch.setenv("LIMA_REDIS_TASK_INDEX", "0")
    task = _task(store.next_task_id(), "dev-1")
    store.create_task_state(task, status="created")

    index_key = store._index_key("dev-1")
    assert client.smembers(index_key) == set()

    monkeypatch.setenv("LIMA_REDIS_TASK_INDEX", "1")
    result = store.list_tasks_for_device("dev-1")
    assert any(r["task_id"] == task["task_id"] for r in result)
    assert client.smembers(index_key) != set()


def test_ghost_index_entry_skipped_gracefully(monkeypatch):
    monkeypatch.setenv("LIMA_REDIS_TASK_INDEX", "1")
    client = _FakeRedisWithSets()
    store = _store(client)

    real_task = _task(store.next_task_id(), "dev-1")
    store.create_task_state(real_task, status="dispatched")

    index_key = store._index_key("dev-1")
    client.sadd(index_key, "ghost-task")

    result = store.active_tasks_for_device("dev-1")
    task_ids = [t["task_id"] for t in result]
    assert real_task["task_id"] in task_ids
    assert "ghost-task" not in task_ids
