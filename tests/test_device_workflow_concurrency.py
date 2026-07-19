"""C1 Phase 4: workflow concurrency and per-task locking."""

from __future__ import annotations

import threading
from typing import Any

import pytest

from device_ledger.store import ledger_store
from device_workflow.lock import RedisTaskLock, ThreadTaskLock
from device_workflow.orchestrator import WorkflowOrchestrator
from device_workflow.state import TaskState, WorkflowTransitionError


class TestThreadTaskLock:
    """Per-task RLock serialization within one process."""

    def test_same_task_blocks_concurrent_acquire(self) -> None:
        lock = ThreadTaskLock()
        assert lock.acquire("task-a") is True
        assert lock.acquire("task-a") is False
        lock.release("task-a")

    def test_different_tasks_acquire_independently(self) -> None:
        lock = ThreadTaskLock()
        assert lock.acquire("task-a") is True
        assert lock.acquire("task-b") is True
        lock.release("task-a")
        lock.release("task-b")

    def test_release_without_acquire_is_safe(self) -> None:
        lock = ThreadTaskLock()
        lock.release("task-c")  # should not raise


class TestWorkflowOrchestratorConcurrency:
    """Concurrent advances on the same task are serialized."""

    def setup_method(self) -> None:
        ledger_store.reset()

    def test_concurrent_advance_same_task_only_one_succeeds(self) -> None:
        workflow = WorkflowOrchestrator()
        workflow.register("task-race", device_id="dev-1", task={"task_id": "task-race", "device_id": "dev-1"})
        workflow.advance("task-race", TaskState.PLANNED)
        workflow.advance("task-race", TaskState.SIMULATED)

        results: list[Any] = []
        errors: list[Exception] = []

        def _advance() -> None:
            try:
                results.append(workflow.advance("task-race", TaskState.READY_TO_DISPATCH))
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=_advance) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        success_count = len(results)
        assert success_count == 1, f"expected 1 success, got {success_count}"
        assert len(errors) == 9
        assert all(isinstance(e, WorkflowTransitionError) for e in errors)

        # Ledger should contain exactly one READY_TO_DISPATCH event.
        events = ledger_store.events_for_task("task-race")
        updated_events = [e for e in events if e.event_type == "task_updated" and e.payload.get("state") == "ready_to_dispatch"]
        assert len(updated_events) == 1

    def test_advance_after_successful_lock_release_allows_next_transition(self) -> None:
        workflow = WorkflowOrchestrator()
        workflow.register("task-seq", device_id="dev-1", task={"task_id": "task-seq", "device_id": "dev-1"})
        workflow.advance("task-seq", TaskState.PLANNED)
        workflow.advance("task-seq", TaskState.SIMULATED)
        workflow.advance("task-seq", TaskState.READY_TO_DISPATCH)
        assert workflow.get_state("task-seq") == TaskState.READY_TO_DISPATCH


class TestRedisTaskLock:
    """Redis-backed per-task lock behavior (skipped if no local Redis)."""

    @pytest.fixture
    def redis_client(self):
        try:
            import redis as _redis
        except ImportError:
            pytest.skip("redis package not installed")
        client = _redis.Redis.from_url("redis://127.0.0.1:6379/0", decode_responses=True, socket_timeout=2.0)
        try:
            client.ping()
        except Exception as exc:
            pytest.skip(f"local Redis unavailable: {exc}")
        yield client
        try:
            client.close()
        except Exception:
            pass

    def test_two_instances_compete_for_same_task(self, redis_client: Any) -> None:
        lock_a = RedisTaskLock(redis_client, key_prefix="lima:test:workflow")
        lock_b = RedisTaskLock(redis_client, key_prefix="lima:test:workflow")

        assert lock_a.acquire("task-redis") is True
        assert lock_b.acquire("task-redis") is False
        lock_a.release("task-redis")
        assert lock_b.acquire("task-redis") is True
        lock_b.release("task-redis")

    def test_release_only_removes_owned_lock(self, redis_client: Any) -> None:
        lock_a = RedisTaskLock(redis_client, key_prefix="lima:test:workflow")
        lock_b = RedisTaskLock(redis_client, key_prefix="lima:test:workflow")

        assert lock_a.acquire("task-owner") is True
        # Another instance releasing should not remove the lock.
        lock_b.release("task-owner")
        assert lock_b.acquire("task-owner") is False
        lock_a.release("task-owner")
        assert lock_b.acquire("task-owner") is True
        lock_b.release("task-owner")
