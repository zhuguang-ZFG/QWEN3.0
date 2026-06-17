"""M5: Tests for recovery execution pipeline (execute_recovery + retry dispatch)."""

from __future__ import annotations

import pytest

from device_gateway.tasks import (
    create_task_from_transcript,
    execute_recovery,
    reset_tasks_for_tests,
    task_snapshot,
)
from device_gateway.store import InMemoryDeviceTaskStore
from device_gateway import tasks as tasks_mod
from device_gateway import store as store_mod
from device_intelligence.recovery import recovery_action


@pytest.fixture(autouse=True)
def _isolate_store(monkeypatch):
    """Give each test a fresh in-memory store."""
    store = InMemoryDeviceTaskStore()
    monkeypatch.setattr(store_mod, "task_store", store)
    reset_tasks_for_tests()
    yield
    reset_tasks_for_tests()


class TestExecuteRecoveryNonePhase:
    def test_non_failed_phase_returns_none(self):
        result = execute_recovery("task-1", "dev-1", {"phase": "accepted", "task_id": "task-1"})
        assert result is None

    def test_running_phase_returns_none(self):
        result = execute_recovery("task-1", "dev-1", {"phase": "running", "task_id": "task-1"})
        assert result is None

    def test_no_error_code_returns_none(self):
        result = execute_recovery(
            "task-1",
            "dev-1",
            {
                "phase": "failed",
                "task_id": "task-1",
            },
        )
        assert result is None


class TestRecoveryActions:
    def test_e_missing_path_retry(self):
        task = create_task_from_transcript("dev-1", "写你好")
        task_id = task["task_id"]
        result = execute_recovery(
            task_id,
            "dev-1",
            {
                "phase": "failed",
                "task_id": task_id,
                "error": {"code": "E_MISSING_PATH", "reason": "path missing"},
            },
        )
        assert result is not None
        assert result["action"] == "retry"
        assert result["attempt"] == 1
        assert "task" in result

    def test_e_estop_stop(self):
        task = create_task_from_transcript("dev-1", "写你好")
        task_id = task["task_id"]
        result = execute_recovery(
            task_id,
            "dev-1",
            {
                "phase": "failed",
                "task_id": task_id,
                "error": {"code": "E_ESTOP", "reason": "emergency stop"},
            },
        )
        assert result is not None
        assert result["action"] == "stop"
        assert result["attempt"] == 1
        assert "task" not in result  # stop does not produce a retry task

    def test_e_not_homed_home(self):
        task = create_task_from_transcript("dev-1", "写你好")
        task_id = task["task_id"]
        result = execute_recovery(
            task_id,
            "dev-1",
            {
                "phase": "failed",
                "task_id": task_id,
                "error": {"code": "E_NOT_HOMED", "reason": "not homed"},
            },
        )
        assert result is not None
        assert result["action"] == "home"
        assert result["attempt"] == 1

    def test_error_code_from_alternate_field(self):
        task = create_task_from_transcript("dev-1", "写你好")
        task_id = task["task_id"]
        result = execute_recovery(
            task_id,
            "dev-1",
            {
                "phase": "failed",
                "task_id": task_id,
                "error_code": "E_LIMIT",
            },
        )
        assert result is not None
        assert result["action"] == "retry"


class TestRetryCountTracking:
    def test_retry_count_increments(self):
        task = create_task_from_transcript("dev-1", "写你好")
        task_id = task["task_id"]

        # First failure
        r1 = execute_recovery(
            task_id,
            "dev-1",
            {
                "phase": "failed",
                "task_id": task_id,
                "error": {"code": "E_MISSING_PATH"},
            },
        )
        assert r1["attempt"] == 1

        # Second failure
        r2 = execute_recovery(
            task_id,
            "dev-1",
            {
                "phase": "failed",
                "task_id": task_id,
                "error": {"code": "E_MISSING_PATH"},
            },
        )
        assert r2["attempt"] == 2

        # Third failure
        r3 = execute_recovery(
            task_id,
            "dev-1",
            {
                "phase": "failed",
                "task_id": task_id,
                "error": {"code": "E_MISSING_PATH"},
            },
        )
        assert r3["attempt"] == 3

    def test_retry_count_persisted_in_snapshot(self):
        task = create_task_from_transcript("dev-1", "写你好")
        task_id = task["task_id"]

        execute_recovery(
            task_id,
            "dev-1",
            {
                "phase": "failed",
                "task_id": task_id,
                "error": {"code": "E_MISSING_PATH"},
            },
        )
        execute_recovery(
            task_id,
            "dev-1",
            {
                "phase": "failed",
                "task_id": task_id,
                "error": {"code": "E_MISSING_PATH"},
            },
        )

        snap = task_snapshot(task_id)
        assert snap is not None
        assert snap.get("retry_count") == 2


class TestRetryExhaustion:
    def test_e_missing_path_exhausted_after_3_retries(self):
        task = create_task_from_transcript("dev-1", "写你好")
        task_id = task["task_id"]

        for i in range(4):
            result = execute_recovery(
                task_id,
                "dev-1",
                {
                    "phase": "failed",
                    "task_id": task_id,
                    "error": {"code": "E_MISSING_PATH"},
                },
            )
            assert result is not None

        # 4th attempt (index 3) should stop, not retry
        r4 = execute_recovery(
            task_id,
            "dev-1",
            {
                "phase": "failed",
                "task_id": task_id,
                "error": {"code": "E_MISSING_PATH"},
            },
        )
        assert r4 is not None
        # After 4 increments, attempt=5, but should_retry(attempt-1=4) with max_retries=3 → False
        assert r4["action"] == "stop"
        assert "task" not in r4

    def test_e_limit_exhausted_after_1_retry(self):
        task = create_task_from_transcript("dev-1", "写你好")
        task_id = task["task_id"]

        # First: retry
        r1 = execute_recovery(
            task_id,
            "dev-1",
            {
                "phase": "failed",
                "task_id": task_id,
                "error": {"code": "E_LIMIT"},
            },
        )
        assert r1["action"] == "retry"

        # Second: exhausted
        r2 = execute_recovery(
            task_id,
            "dev-1",
            {
                "phase": "failed",
                "task_id": task_id,
                "error": {"code": "E_LIMIT"},
            },
        )
        assert r2 is not None
        assert r2["action"] == "stop"
        assert "task" not in r2


class TestRetryTaskDispatch:
    def test_retry_enqueues_task_for_dispatch(self):
        task = create_task_from_transcript("dev-1", "写你好")
        task_id = task["task_id"]

        result = execute_recovery(
            task_id,
            "dev-1",
            {
                "phase": "failed",
                "task_id": task_id,
                "error": {"code": "E_MISSING_PATH"},
            },
        )
        assert result is not None
        assert result["action"] == "retry"
        assert "task" in result

        retried_task = result["task"]
        assert retried_task["task_id"] == task_id
        assert retried_task["capability"] == "run_path"

        # Task should be in pending queue
        pending = store_mod.task_store.pending_count("dev-1")
        assert pending >= 1

    def test_retry_task_has_original_params(self):
        task = create_task_from_transcript("dev-1", "写你好")
        task_id = task["task_id"]

        result = execute_recovery(
            task_id,
            "dev-1",
            {
                "phase": "failed",
                "task_id": task_id,
                "error": {"code": "E_MISSING_PATH"},
            },
        )

        retried_task = result["task"]
        # Verify route_policy is preserved
        assert "route_policy" in retried_task
        # Verify params are preserved
        assert "params" in retried_task


class TestExplanationZh:
    def test_explanation_zh_in_result(self):
        task = create_task_from_transcript("dev-1", "写你好")
        task_id = task["task_id"]

        result = execute_recovery(
            task_id,
            "dev-1",
            {
                "phase": "failed",
                "task_id": task_id,
                "error": {"code": "E_ESTOP"},
            },
        )
        assert result is not None
        assert "explanation_zh" in result
        assert "急停" in result["explanation_zh"]
