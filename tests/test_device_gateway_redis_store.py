import json

from device_gateway.redis_store import RedisDeviceTaskStore


class _FakeRedis:
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
        return lst[start:end if end >= 0 else None]

    def time(self):
        return [self.now, 0]

    def delete(self, *keys):
        for key in keys:
            self.values.pop(key, None)
            self.hashes.pop(key, None)
            self.lists.pop(key, None)


def _task(task_id, device_id="dev-1"):
    return {"type": "motion_task", "task_id": task_id, "device_id": device_id, "params": {"path": []}}


def test_redis_store_lists_tasks_for_device_with_status_and_limit():
    client = _FakeRedis()
    store = RedisDeviceTaskStore("redis://unused", client=client, key_prefix="test:device")
    first = _task(store.next_task_id(), "dev-1")
    second = _task(store.next_task_id(), "dev-1")
    other = _task(store.next_task_id(), "dev-2")

    store.create_task_state(first, status="created")
    store.create_task_state(second, status="queued")
    store.create_task_state(other, status="created")

    assert store.list_tasks_for_device("dev-1", limit=1) == [
        {
            "task_id": first["task_id"],
            "status": "created",
            "capability": "",
            "source": "",
        }
    ]
    assert store.list_tasks_for_device("dev-1", status="queued", limit=20) == [
        {
            "task_id": second["task_id"],
            "status": "queued",
            "capability": "",
            "source": "",
        }
    ]


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


def test_redis_store_ack_processing_removes_full_processing_task_payload():
    client = _FakeRedis()
    store = RedisDeviceTaskStore("redis://unused", client=client, key_prefix="test:device")
    task = _task(store.next_task_id())

    store.create_task_state(task)
    store.enqueue_pending_task("dev-1", task)
    assert store.pop_pending_tasks("dev-1", limit=1)[0]["task_id"] == task["task_id"]

    assert client.lists["test:device:processing:dev-1"]
    assert store.ack_processing("dev-1", task["task_id"]) is True
    assert client.lists["test:device:processing:dev-1"] == []


def test_redis_store_recovers_by_processing_age_not_pending_age():
    client = _FakeRedis()
    store = RedisDeviceTaskStore("redis://unused", client=client, key_prefix="test:device")
    task = _task(store.next_task_id())

    store.create_task_state(task)
    store.enqueue_pending_task("dev-1", task)
    client.now += 300
    assert store.pop_pending_tasks("dev-1", limit=1)[0]["task_id"] == task["task_id"]

    assert store.recover_stale_processing("dev-1", timeout_sec=120) == 0
    assert store.pending_count("dev-1") == 0

    client.now += 121
    assert store.recover_stale_processing("dev-1", timeout_sec=120) == 1
    assert store.pending_count("dev-1") == 1
    assert client.lists["test:device:processing:dev-1"] == []


def test_redis_store_tracks_retry_count_and_resets_for_retry():
    client = _FakeRedis()
    store = RedisDeviceTaskStore("redis://unused", client=client, key_prefix="test:device")
    task = _task(store.next_task_id())

    store.create_task_state(task, status="failed")
    assert store.increment_retry_count(task["task_id"]) == 1
    assert store.increment_retry_count(task["task_id"]) == 2
    assert store.task_snapshot(task["task_id"])["retry_count"] == 2

    store.reset_task_for_retry(task["task_id"])
    assert store.task_snapshot(task["task_id"])["status"] == "queued"


def test_redis_store_remove_pending_task_drops_only_matching_task():
    client = _FakeRedis()
    store = RedisDeviceTaskStore("redis://unused", client=client, key_prefix="test:device")
    first = _task(store.next_task_id())
    second = _task(store.next_task_id())

    store.create_task_state(first)
    store.create_task_state(second)
    store.enqueue_pending_task("dev-1", first)
    store.enqueue_pending_task("dev-1", second)

    assert store.remove_pending_task("dev-1", first["task_id"]) is True
    assert store.pending_count("dev-1") == 1
    assert store.remove_pending_task("dev-1", first["task_id"]) is False
    assert store.remove_pending_task("dev-unknown", second["task_id"]) is False
