import json

from device_gateway.redis_store import RedisDeviceTaskStore


class _FakeRedis:
    def __init__(self):
        self.values = {}
        self.hashes = {}
        self.lists = {}

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

    def lpush(self, key, *values):
        queue = self.lists.setdefault(key, [])
        for value in values:
            queue.insert(0, value)
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

    def delete(self, *keys):
        for key in keys:
            self.values.pop(key, None)
            self.hashes.pop(key, None)
            self.lists.pop(key, None)


def _task(task_id, device_id="dev-1"):
    return {"type": "motion_task", "task_id": task_id, "device_id": device_id, "params": {"path": []}}


def test_redis_store_preserves_task_state_queue_order_and_events():
    client = _FakeRedis()
    store = RedisDeviceTaskStore("redis://unused", client=client, key_prefix="test:device")
    first = _task(store.next_task_id())
    second = _task(store.next_task_id())

    assert store.backend_name == "redis"
    assert store.shared_across_processes is True
    assert first["task_id"] == "task-000001"
    assert second["task_id"] == "task-000002"

    store.create_task_state(first)
    store.create_task_state(second)
    assert store.enqueue_pending_task("dev-1", first) == 1
    assert store.enqueue_pending_task("dev-1", second) == 2
    assert store.pending_count("dev-1") == 2

    popped = store.pop_pending_tasks("dev-1", limit=1)
    assert [task["task_id"] for task in popped] == [first["task_id"]]
    assert store.task_snapshot(first["task_id"])["status"] == "dispatching"

    assert store.requeue_pending_tasks("dev-1", popped) == 2
    redelivered = store.pop_pending_tasks("dev-1", limit=10)
    assert [task["task_id"] for task in redelivered] == [first["task_id"], second["task_id"]]

    store.mark_task_dispatched(first["task_id"])
    summary = store.record_motion_event(
        {"type": "motion_event", "device_id": "dev-1", "task_id": first["task_id"], "phase": "done"}
    )

    snapshot = store.task_snapshot(first["task_id"])
    assert summary == {"task_id": first["task_id"], "phase": "done", "event_count": 1}
    assert snapshot["status"] == "done"
    assert snapshot["events"][0]["phase"] == "done"
    assert json.loads(client.hashes["test:device:tasks"][first["task_id"]])["status"] == "done"
