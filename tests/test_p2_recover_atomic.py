"""P2-c: recover_stale_processing 的 LREM+LPUSH 必须原子化。

原实现（redis_store_recover.py）先 `lrem` 再 `lpush`，两步之间崩溃会导致任务
既不在 processing 也不在 pending，永久丢失（at-most-once）。改为单次原子操作
（Lua，测试 fake 走 fallback），且 LREM 未命中时不得 LPUSH（避免与并发 pop 竞争
误删兄弟副本后重复入队）。

RED until requeue_item_atomic is implemented and wired into recover.
"""

from __future__ import annotations


def test_requeue_item_atomic_helper_exists():
    """redis_cas 必须提供 requeue_item_atomic 原子迁移 helper。"""
    from device_gateway import redis_cas

    assert hasattr(redis_cas, "requeue_item_atomic"), "缺少 requeue_item_atomic 原子迁移 helper"


def test_requeue_moves_item_from_processing_to_pending():
    """命中的 item 从 processing 移除并进入 pending 头部；返回 1。"""
    from device_gateway import redis_cas

    class _Fake:
        def __init__(self):
            self.lists = {"proc": ["A", "B"], "pend": []}

        def lrem(self, key, count, value):
            lst = self.lists.get(key, [])
            n = 0
            while value in lst and n < (count if count > 0 else len(lst)):
                lst.remove(value)
                n += 1
            return n

        def lpush(self, key, *values):
            q = self.lists.setdefault(key, [])
            for v in values:
                q.insert(0, v)
            return len(q)

        def expire(self, key, ttl):
            return True

    fake = _Fake()
    moved = redis_cas.requeue_item_atomic(fake, "proc", "pend", "A", 600)
    assert moved == 1
    assert "A" not in fake.lists["proc"]
    assert fake.lists["pend"] == ["A"]


def test_requeue_absent_item_does_not_lpush():
    """LREM 未命中（item 已被并发 pop）时绝不 LPUSH，返回 0，避免重复入队。"""
    from device_gateway import redis_cas

    class _Fake:
        def __init__(self):
            self.lists = {"proc": [], "pend": []}
            self.lpush_calls = 0

        def lrem(self, key, count, value):
            return 0  # 未命中

        def lpush(self, key, *values):
            self.lpush_calls += 1
            q = self.lists.setdefault(key, [])
            for v in values:
                q.insert(0, v)
            return len(q)

        def expire(self, key, ttl):
            return True

    fake = _Fake()
    moved = redis_cas.requeue_item_atomic(fake, "proc", "pend", "ghost", 600)
    assert moved == 0
    assert fake.lpush_calls == 0, "LREM 未命中却仍 LPUSH，会造成重复入队"
    assert fake.lists["pend"] == []


def test_recover_still_requeues_via_atomic_path():
    """回归：recover_stale_processing 走原子 helper 后行为不变。"""
    import importlib

    mod = importlib.import_module("tests.test_device_gateway_redis_store")
    _FakeRedis = mod._FakeRedis
    from device_gateway.redis_store import RedisDeviceTaskStore

    client = _FakeRedis()
    store = RedisDeviceTaskStore("redis://unused", client=client, key_prefix="test:device")
    # GW-R3-4: SEC-06 pop re-validates params, so write_text needs a valid text.
    task = {
        "task_id": store.next_task_id(),
        "device_id": "dev-1",
        "capability": "write_text",
        "params": {"text": "hi"},
    }
    store.create_task_state(task)
    store.enqueue_pending_task("dev-1", task)
    client.now += 300
    store.pop_pending_tasks("dev-1", limit=1)

    assert store.recover_stale_processing("dev-1", timeout_sec=120) == 0
    client.now += 121
    assert store.recover_stale_processing("dev-1", timeout_sec=120) == 1
    assert store.pending_count("dev-1") == 1
    assert client.lists["test:device:processing:dev-1"] == []
