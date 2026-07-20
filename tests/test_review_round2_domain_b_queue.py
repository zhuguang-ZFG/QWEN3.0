"""2026-07-20 第二轮审查 域 B 队列语义回归测试。

覆盖:
- B4 (GW-WA/WB) SEC-06 丢弃任务置 failed / restart 离线诚实失败
- B5 (GW-WC)    dispatch generation:重派发后陈旧 ack 被拒
- B7 (GW-WG)    queued 幽灵任务 max-age 回收

边界校验(B1/B2/B3)见 test_review_round2_domain_b.py。
"""

from __future__ import annotations

import time

import pytest

from device_gateway.memory_store import InMemoryDeviceTaskStore
from device_gateway.redis_store import RedisDeviceTaskStore


# ── Fake Redis (minimal ops used by the queue mixins) ─────────────────────────


class _FakeRedis:
    def __init__(self):
        self.values = {}
        self.hashes = {}
        self.lists = {}
        self.now = 1000.0

    def time(self):
        return [self.now, 0]

    def incr(self, key):
        self.values[key] = int(self.values.get(key, 0)) + 1
        return self.values[key]

    def hset(self, name, key=None, value=None, mapping=None):
        bucket = self.hashes.setdefault(name, {})
        if mapping is not None:
            bucket.update(mapping)
        else:
            bucket[key] = value

    def hget(self, name, key):
        return self.hashes.get(name, {}).get(key)

    def hgetall(self, name):
        return dict(self.hashes.get(name, {}))

    def rpush(self, key, *values):
        queue = self.lists.setdefault(key, [])
        queue.extend(values)
        return len(queue)

    def lpush(self, key, *values):
        queue = self.lists.setdefault(key, [])
        for v in values:
            queue.insert(0, v)
        return len(queue)

    def lmove(self, src_key, dst_key, src_pos="RIGHT", dest_pos="LEFT"):
        lst = self.lists.get(src_key, [])
        if not lst:
            return None
        item = lst.pop(-1) if src_pos == "RIGHT" else lst.pop(0)
        dst = self.lists.setdefault(dst_key, [])
        dst.insert(0 if dest_pos == "LEFT" else len(dst), item)
        return item

    def lrem(self, key, count, value):
        lst = self.lists.get(key, [])
        removed = 0
        while value in lst and removed < (count if count > 0 else len(lst)):
            lst.remove(value)
            removed += 1
        return removed

    def lrange(self, key, start, end):
        lst = self.lists.get(key, [])
        return lst[start : end if end >= 0 else None]

    def llen(self, key):
        return len(self.lists.get(key, []))

    def expire(self, key, ttl):
        return True

    def scan_iter(self, match):
        prefix = match[:-1] if match.endswith("*") else match
        for key in [*self.values, *self.hashes, *self.lists]:
            if key.startswith(prefix):
                yield key

    def delete(self, *keys):
        for key in keys:
            self.values.pop(key, None)
            self.hashes.pop(key, None)
            self.lists.pop(key, None)


def _redis_store():
    return RedisDeviceTaskStore("redis://unused", client=_FakeRedis(), key_prefix="tb")


def _task(task_id="task-b-001", device_id="dev-b", capability="write_text"):
    return {
        "task_id": task_id,
        "device_id": device_id,
        "capability": capability,
        "params": {"text": "hi"},
        "source": "test",
    }


# ── B4: SEC-06 drop must mark task failed (no ghost busy / false success) ────


def test_sec06_dropped_task_state_becomes_failed():
    store = _redis_store()
    ghost = _task(task_id="task-ghost", capability="draw_svg")
    store.create_task_state(ghost, status="created")
    store.enqueue_pending_task("dev-b", ghost)

    popped = store.pop_pending_tasks("dev-b")

    assert popped == []
    snapshot = store.task_snapshot("task-ghost")
    assert snapshot is not None
    assert snapshot["status"] == "failed"
    assert store.active_tasks_for_device("dev-b") == []


@pytest.mark.asyncio
async def test_restart_device_offline_returns_honest_failure():
    from device_gateway.registry import restart_device
    from device_gateway.sessions import registry as session_registry

    session_registry.clear()
    result = await restart_device("dev-offline-restart")
    assert result["ok"] is False
    assert result["delivered"] is False
    assert result["queued"] is False
    assert result["error"] == "device_offline"


# ── B5: dispatch generation rejects stale acks after re-dispatch ─────────────


def test_redis_stale_ack_rejected_after_redispatch():
    fake = _FakeRedis()
    store = RedisDeviceTaskStore("redis://unused", client=fake, key_prefix="tb")
    task = _task(task_id="task-gen-1")
    store.create_task_state(task, status="created")
    store.enqueue_pending_task("dev-b", task)

    first = store.pop_pending_tasks("dev-b")[0]
    stale_gen = first["_dispatch_gen"]
    assert stale_gen == 0

    # Task goes stale in processing; recovery bumps the generation.
    fake.now += 500
    assert store.recover_stale_processing("dev-b") == 1

    second = store.pop_pending_tasks("dev-b")[0]
    assert second["_dispatch_gen"] == 1

    # Old worker acks with the pre-recovery generation → rejected.
    assert store.ack_processing("dev-b", "task-gen-1", dispatch_gen=stale_gen) is False
    # Current worker acks with the live generation → accepted.
    assert store.ack_processing("dev-b", "task-gen-1", dispatch_gen=second["_dispatch_gen"]) is True


def test_memory_stale_ack_rejected_after_redispatch():
    store = InMemoryDeviceTaskStore()
    task = _task(task_id="task-gen-mem")
    store.create_task_state(task, status="created")
    store.enqueue_pending_task("dev-b", task)

    first = store.pop_pending_tasks("dev-b")[0]
    stale_gen = first["_dispatch_gen"]

    # Backdate the processing entry so recovery sees it as stale.
    store._processing_by_device["dev-b"]["task-gen-mem"]["processing_started_at"] = time.time() - 500
    assert store.recover_stale_processing("dev-b") == 1

    second = store.pop_pending_tasks("dev-b")[0]
    assert second["_dispatch_gen"] == stale_gen + 1

    assert store.ack_processing("dev-b", "task-gen-mem", dispatch_gen=stale_gen) is False
    assert store.ack_processing("dev-b", "task-gen-mem", dispatch_gen=second["_dispatch_gen"]) is True


def test_ack_without_generation_keeps_legacy_behavior():
    store = InMemoryDeviceTaskStore()
    task = _task(task_id="task-legacy-ack")
    store.create_task_state(task, status="created")
    store.enqueue_pending_task("dev-b", task)
    store.pop_pending_tasks("dev-b")
    assert store.ack_processing("dev-b", "task-legacy-ack") is True


# ── B7: queued ghost tasks age out instead of holding busy forever ───────────


def test_memory_expired_queued_task_releases_busy():
    store = InMemoryDeviceTaskStore()
    task = _task(task_id="task-old-queued")
    store.create_task_state(task, status="created")
    store.enqueue_pending_task("dev-b", task)
    # Backdate the enqueue timestamp past the max age.
    task["_enqueued_at"] = time.time() - 4000

    assert store.active_tasks_for_device("dev-b") == []
    snapshot = store.task_snapshot("task-old-queued")
    assert snapshot is not None and snapshot["status"] == "expired"
    assert store.pending_count("dev-b") == 0


def test_memory_fresh_queued_task_stays_busy():
    store = InMemoryDeviceTaskStore()
    task = _task(task_id="task-fresh-queued")
    store.create_task_state(task, status="created")
    store.enqueue_pending_task("dev-b", task)

    active = store.active_tasks_for_device("dev-b")
    assert [t["task_id"] for t in active] == ["task-fresh-queued"]


def test_redis_expired_queued_task_releases_busy():
    fake = _FakeRedis()
    store = RedisDeviceTaskStore("redis://unused", client=fake, key_prefix="tb")
    task = _task(task_id="task-old-redis")
    store.create_task_state(task, status="created")
    store.enqueue_pending_task("dev-b", task)  # _enqueued_at = 1000

    fake.now += 4000
    assert store.active_tasks_for_device("dev-b") == []
    snapshot = store.task_snapshot("task-old-redis")
    assert snapshot is not None and snapshot["status"] == "expired"
    assert store.pending_count("dev-b") == 0
