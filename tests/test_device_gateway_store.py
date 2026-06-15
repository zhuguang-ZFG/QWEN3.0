from concurrent.futures import ThreadPoolExecutor

from device_gateway.store import InMemoryDeviceTaskStore


def _task(task_id: str, device_id: str = "dev-1") -> dict:
    return {
        "type": "motion_task",
        "task_id": task_id,
        "device_id": device_id,
        "capability": "run_path",
        "params": {"feed": 900, "path": []},
    }


def test_in_memory_store_contract_records_events_and_copied_snapshots():
    store = InMemoryDeviceTaskStore()
    task = _task(store.next_task_id())

    store.create_task_state(task)
    summary = store.record_motion_event(
        {"type": "motion_event", "device_id": "dev-1", "task_id": task["task_id"], "phase": "progress"}
    )
    snapshot = store.task_snapshot(task["task_id"])
    snapshot["task"]["params"]["path"].append({"x": 1, "y": 1, "z": 0})
    snapshot["events"].append({"phase": "local mutation"})
    snapshot["events"][0]["phase"] = "mutated"

    assert summary == {"task_id": task["task_id"], "phase": "progress", "event_count": 1}
    assert store.task_snapshot(task["task_id"])["status"] == "progress"
    assert store.task_snapshot(task["task_id"])["task"]["params"]["path"] == []
    assert store.task_snapshot(task["task_id"])["events"][0]["phase"] == "progress"
    assert len(store.task_snapshot(task["task_id"])["events"]) == 1


def test_in_memory_store_contract_preserves_fifo_and_device_isolation():
    store = InMemoryDeviceTaskStore()
    dev_1_tasks = [_task(store.next_task_id(), "dev-1") for _ in range(3)]
    dev_2_task = _task(store.next_task_id(), "dev-2")

    for task in dev_1_tasks:
        store.enqueue_pending_task("dev-1", task)
    store.enqueue_pending_task("dev-2", dev_2_task)

    first_batch = store.pop_pending_tasks("dev-1", limit=2)
    store.requeue_pending_tasks("dev-1", first_batch[1:])
    second_batch = store.pop_pending_tasks("dev-1", limit=10)

    assert [task["task_id"] for task in first_batch] == [task["task_id"] for task in dev_1_tasks[:2]]
    assert [task["task_id"] for task in second_batch] == [task["task_id"] for task in dev_1_tasks[1:]]
    assert store.pending_count("dev-1") == 0
    assert store.pending_count("dev-2") == 1


def test_in_memory_store_contract_generates_unique_ids_under_parallel_calls():
    store = InMemoryDeviceTaskStore()

    with ThreadPoolExecutor(max_workers=8) as executor:
        task_ids = list(executor.map(lambda _: store.next_task_id(), range(80)))

    assert len(task_ids) == 80
    assert len(set(task_ids)) == 80


def test_remove_pending_task_drops_only_matching_task():
    store = InMemoryDeviceTaskStore()
    t1 = _task(store.next_task_id(), "dev-1")
    t2 = _task(store.next_task_id(), "dev-1")
    t3 = _task(store.next_task_id(), "dev-2")

    store.enqueue_pending_task("dev-1", t1)
    store.enqueue_pending_task("dev-1", t2)
    store.enqueue_pending_task("dev-2", t3)

    assert store.remove_pending_task("dev-1", t1["task_id"]) is True
    assert store.pending_count("dev-1") == 1
    assert store.remove_pending_task("dev-1", t1["task_id"]) is False
    assert store.remove_pending_task("dev-unknown", t2["task_id"]) is False
    assert store.pending_count("dev-2") == 1
