"""Redis-backed memory and ledger store tests."""

from __future__ import annotations

import json
import time

import pytest

from device_ledger.events import DuplicateLedgerEvent, new_event
from device_ledger.redis_store import RedisLedgerStore
from device_memory.redis_store import RedisMemoryStore
from device_memory.schemas import MemoryEntry, MemoryType


class _FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.sets: dict[str, set[str]] = {}
        self.lists: dict[str, list[str]] = {}

    def set(self, key: str, value: str) -> None:
        self.values[key] = value

    def get(self, key: str) -> str | None:
        return self.values.get(key)

    def delete(self, *keys: str) -> None:
        for key in keys:
            self.values.pop(key, None)
            self.sets.pop(key, None)
            self.lists.pop(key, None)

    def sadd(self, key: str, *values: str) -> int:
        bucket = self.sets.setdefault(key, set())
        before = len(bucket)
        bucket.update(values)
        return len(bucket) - before

    def smembers(self, key: str) -> set[str]:
        return set(self.sets.get(key, set()))

    def srem(self, key: str, value: str) -> int:
        bucket = self.sets.get(key, set())
        if value in bucket:
            bucket.remove(value)
            return 1
        return 0

    def rpush(self, key: str, *values: str) -> int:
        bucket = self.lists.setdefault(key, [])
        bucket.extend(values)
        return len(bucket)

    def lrange(self, key: str, start: int, end: int) -> list[str]:
        bucket = self.lists.get(key, [])
        if end == -1:
            return bucket[start:]
        return bucket[start : end + 1]

    def scan_iter(self, match: str):
        prefix = match[:-1] if match.endswith("*") else match
        for key in {*self.values, *self.sets, *self.lists}:
            if key.startswith(prefix):
                yield key


def _memory_entry(entry_id: str = "mem_redis_1", device_id: str = "dev_a") -> MemoryEntry:
    return MemoryEntry(
        id=entry_id,
        device_id=device_id,
        type=MemoryType.PREFERENCE,
        key="favorite_color",
        value="blue",
        ttl_days=30,
        created_at=int(time.time()),
        source="user_explicit",
    )


def test_redis_memory_store_create_recall_and_reset():
    store = RedisMemoryStore("redis://unused", client=_FakeRedis(), key_prefix="test:memory")
    entry = _memory_entry()
    store.create(entry)
    recalled = store.recall("dev_a", "favorite_color")
    assert recalled is not None
    assert recalled.value == "blue"
    assert store.reset("dev_a") == 1
    assert store.recall("dev_a", "favorite_color") is None


def test_redis_memory_store_disable_and_export():
    store = RedisMemoryStore("redis://unused", client=_FakeRedis(), key_prefix="test:memory")
    store.create(_memory_entry())
    assert store.disable("mem_redis_1") is True
    assert store.recall("dev_a", "favorite_color") is None
    exported = store.export("dev_a")
    assert "favorite_color" in exported


def test_configure_memory_store_from_env_requires_redis_url(monkeypatch):
    from device_memory import store as memory_store_mod

    monkeypatch.setenv("LIMA_DEVICE_MEMORY_STORE", "redis")
    monkeypatch.delenv("LIMA_DEVICE_REDIS_URL", raising=False)
    with pytest.raises(RuntimeError, match="LIMA_DEVICE_REDIS_URL"):
        memory_store_mod.configure_memory_store_from_env()


def test_redis_ledger_store_append_replay_and_dedup():
    store = RedisLedgerStore("redis://unused", client=_FakeRedis(), key_prefix="test:ledger")
    created = new_event(
        event_type="task_created",
        task_id="task-1",
        device_id="dev-1",
        payload={"task": {"task_id": "task-1"}, "status": "created"},
        event_id="evt-1",
    )
    store.append_event(created)
    with pytest.raises(DuplicateLedgerEvent):
        store.append_event(created)

    replay = store.replay_task("task-1")
    assert replay["task_id"] == "task-1"
    assert replay["status"] == "created"
    assert replay["event_count"] == 1


def test_configure_ledger_store_from_env_requires_redis_url(monkeypatch):
    from device_ledger import store as ledger_store_mod

    monkeypatch.setenv("LIMA_DEVICE_LEDGER_STORE", "redis")
    monkeypatch.delenv("LIMA_DEVICE_REDIS_URL", raising=False)
    with pytest.raises(RuntimeError, match="LIMA_DEVICE_REDIS_URL"):
        ledger_store_mod.configure_ledger_store_from_env()
