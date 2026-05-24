from concurrent.futures import ThreadPoolExecutor

from device_gateway.tasks import (
    create_task_from_transcript,
    enqueue_pending_task,
    install_task_store_for_tests,
    pending_count,
    pop_pending_tasks,
    requeue_pending_tasks,
    reset_tasks_for_tests,
    task_snapshot,
)
from device_gateway.store import InMemoryDeviceTaskStore


def setup_function():
    install_task_store_for_tests()
    reset_tasks_for_tests()


def test_concurrent_task_creation_uses_unique_task_ids():
    def create(index: int) -> str:
        task = create_task_from_transcript(f"dev-{index % 4}", f"写并发{index}")
        return task["task_id"]

    with ThreadPoolExecutor(max_workers=8) as executor:
        task_ids = list(executor.map(create, range(40)))

    assert len(task_ids) == 40
    assert len(set(task_ids)) == 40


def test_pending_queues_are_isolated_per_device_under_parallel_writes():
    def enqueue(index: int) -> None:
        device_id = f"dev-{index % 3}"
        task = create_task_from_transcript(device_id, f"画星星{index}")
        enqueue_pending_task(device_id, task)

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(enqueue, range(30)))

    assert pending_count() == 30
    assert len(pop_pending_tasks("dev-0", limit=100)) == 10
    assert pending_count("dev-0") == 0
    assert pending_count() == 20


def test_task_helpers_use_replaced_store_instance():
    first_store = install_task_store_for_tests(InMemoryDeviceTaskStore())
    first = create_task_from_transcript("dev-1", "write one")
    enqueue_pending_task("dev-1", first)
    assert pending_count() == 1

    second_store = install_task_store_for_tests(InMemoryDeviceTaskStore())
    second = create_task_from_transcript("dev-2", "write two")

    assert second["task_id"] == "task-000001"
    assert pending_count() == 0
    assert first_store.pending_count() == 1
    assert second_store.task_snapshot(second["task_id"])["task"] == second


def test_requeue_pending_tasks_preserves_fifo_order_after_dispatch_failure():
    tasks = [create_task_from_transcript("dev-1", f"write {index}") for index in range(4)]
    for task in tasks:
        enqueue_pending_task("dev-1", task)

    batch = pop_pending_tasks("dev-1", limit=4)
    assert [task["task_id"] for task in batch] == [task["task_id"] for task in tasks]

    requeue_pending_tasks("dev-1", batch[1:])

    redelivered = pop_pending_tasks("dev-1", limit=4)
    assert [task["task_id"] for task in redelivered] == [task["task_id"] for task in tasks[1:]]
    assert task_snapshot(tasks[1]["task_id"])["status"] == "dispatching"
