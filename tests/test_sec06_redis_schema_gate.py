"""SEC-06: Redis task queue schema gate.

A malicious actor with Redis write access could RPUSH a crafted JSON payload
directly into a device's pending queue, bypassing all HTTP-level validation.
``pop_pending_tasks`` must reject (drop + log) any task whose ``capability``
is not on a strict allowlist, or that is missing required fields (task_id,
device_id).

These tests are RED until the gate is implemented.
"""

from __future__ import annotations

import json

from device_gateway.redis_store import RedisDeviceTaskStore


class _FakeRedis:
    """Minimal fake Redis supporting only the ops used by pop_pending_tasks."""

    def __init__(self):
        self.values = {}
        self.hashes = {}
        self.lists = {}
        self.now = 1000.0

    def incr(self, key):
        self.values[key] = int(self.values.get(key, 0)) + 1
        return self.values[key]

    def hset(self, name, key=None, value=None, mapping=None):
        bucket = self.hashes.setdefault(name, {})
        if mapping is not None:
            bucket.update(mapping)
            return len(mapping)
        bucket[key] = value
        return 1

    def hget(self, name, key):
        return self.hashes.get(name, {}).get(key)

    def hgetall(self, name):
        return dict(self.hashes.get(name, {}))

    def rpush(self, key, *values):
        queue = self.lists.setdefault(key, [])
        queue.extend(values)
        return len(queue)

    def lpop(self, key, count=None):
        queue = self.lists.setdefault(key, [])
        if count is None:
            return queue.pop(0) if queue else None
        popped = queue[:count]
        del queue[:count]
        return popped

    def llen(self, key):
        return len(self.lists.get(key, []))

    def scan_iter(self, match):
        prefix = match[:-1] if match.endswith("*") else match
        for key in [*self.values, *self.hashes, *self.lists]:
            if key.startswith(prefix):
                yield key

    def lmove(self, src_key, dst_key, src_pos="RIGHT", dest_pos="LEFT"):
        lst = self.lists.get(src_key, [])
        if not lst:
            return None
        item = lst.pop(-1) if src_pos == "RIGHT" else lst.pop(0)
        self.lists.setdefault(dst_key, []).insert(0 if dest_pos == "LEFT" else len(self.lists[dst_key]), item)
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

    def time(self):
        return [self.now, 0]

    def expire(self, key, ttl):
        return True

    def delete(self, *keys):
        for key in keys:
            self.values.pop(key, None)
            self.hashes.pop(key, None)
            self.lists.pop(key, None)


def _params_for(capability: str) -> dict:
    """Capability-appropriate params that pass SEC-06's validate_capability_params
    re-check (GW-R3-4): draw_generated needs a prompt, run_path needs an in-bounds
    path, control caps need nothing, write_text/handwriting need text."""
    if capability == "draw_generated":
        return {"prompt": "cat"}
    if capability == "run_path":
        return {"path": [{"x": 10.0, "y": 10.0, "z": 0.0}], "feed": 500}
    if capability in ("write_text", "handwriting"):
        return {"text": "你好"}
    return {}


def _valid_task(task_id="task-000001", device_id="dev-1", capability="write_text"):
    return {
        "task_id": task_id,
        "device_id": device_id,
        "capability": capability,
        "params": _params_for(capability),
        "source": "voice",
    }


def _store(client):
    return RedisDeviceTaskStore("redis://unused", client=client, key_prefix="test:device")


# ── RED: valid tasks pass through unchanged ──────────────────────────────────


def test_pop_returns_valid_write_text_task():
    client = _FakeRedis()
    store = _store(client)
    task = _valid_task(capability="write_text")
    store.create_task_state(task, status="created")
    store.enqueue_pending_task("dev-1", task)
    popped = store.pop_pending_tasks("dev-1")
    assert len(popped) == 1
    assert popped[0]["capability"] == "write_text"


def test_pop_returns_valid_draw_generated_task():
    client = _FakeRedis()
    store = _store(client)
    task = _valid_task(capability="draw_generated")
    store.create_task_state(task, status="created")
    store.enqueue_pending_task("dev-1", task)
    popped = store.pop_pending_tasks("dev-1")
    assert len(popped) == 1
    assert popped[0]["capability"] == "draw_generated"


def test_pop_returns_valid_home_task():
    """home is a control capability, not motion — still on allowlist."""
    client = _FakeRedis()
    store = _store(client)
    task = _valid_task(capability="home")
    store.create_task_state(task, status="created")
    store.enqueue_pending_task("dev-1", task)
    popped = store.pop_pending_tasks("dev-1")
    assert len(popped) == 1


# ── RED: malicious / malformed tasks must be dropped ──────────────────────────


def test_pop_drops_unknown_capability():
    """A task with capability 'delete_everything' must be filtered out."""
    client = _FakeRedis()
    store = _store(client)
    malicious = {
        "task_id": "task-evil",
        "device_id": "dev-1",
        "capability": "delete_everything",
        "params": {"confirm": True},
        "source": "redis_inject",
    }
    store.create_task_state(malicious, status="created")
    store.enqueue_pending_task("dev-1", malicious)
    popped = store.pop_pending_tasks("dev-1")
    assert popped == [], "malicious capability must be dropped on pop"


def test_pop_drops_missing_capability():
    """A task with no capability field at all must be dropped."""
    client = _FakeRedis()
    store = _store(client)
    bare = {"task_id": "task-bare", "device_id": "dev-1", "params": {}, "source": "x"}
    store.create_task_state(bare, status="created")
    store.enqueue_pending_task("dev-1", bare)
    popped = store.pop_pending_tasks("dev-1")
    assert popped == [], "task without capability must be dropped on pop"


def test_pop_drops_missing_task_id():
    """A task with no task_id must be dropped (cannot track state)."""
    client = _FakeRedis()
    store = _store(client)
    no_id = {
        "device_id": "dev-1",
        "capability": "write_text",
        "params": {"text": "hi"},
        "source": "redis_inject",
    }
    # Manually push to simulate Redis injection without task_id
    client.rpush("test:device:pending:dev-1", json.dumps(no_id))
    popped = store.pop_pending_tasks("dev-1")
    assert popped == [], "task without task_id must be dropped on pop"


def test_pop_drops_missing_device_id():
    """A task with no device_id must be dropped."""
    client = _FakeRedis()
    store = _store(client)
    no_device = {
        "task_id": "task-x",
        "capability": "write_text",
        "params": {"text": "hi"},
        "source": "redis_inject",
    }
    client.rpush("test:device:pending:dev-1", json.dumps(no_device))
    popped = store.pop_pending_tasks("dev-1")
    assert popped == [], "task without device_id must be dropped on pop"


def test_pop_filters_malicious_keeps_valid():
    """When a malicious task sits beside a valid one, only the valid one pops."""
    client = _FakeRedis()
    store = _store(client)
    valid = _valid_task(task_id="task-valid", capability="write_text")
    malicious = _valid_task(task_id="task-evil", capability="rm_dash_rf")

    store.create_task_state(valid, status="created")
    store.enqueue_pending_task("dev-1", valid)
    # Manually push malicious after the valid one (simulates Redis injection)
    client.rpush(
        "test:device:pending:dev-1",
        json.dumps(malicious),
    )

    popped = store.pop_pending_tasks("dev-1", limit=10)
    assert [t["task_id"] for t in popped] == ["task-valid"], "only valid task should pop"
