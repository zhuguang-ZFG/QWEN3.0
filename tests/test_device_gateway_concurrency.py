from concurrent.futures import ThreadPoolExecutor

from device_gateway.tasks import (
    create_task_from_transcript,
    enqueue_pending_task,
    pending_count,
    pop_pending_tasks,
    reset_tasks_for_tests,
)


def setup_function():
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
