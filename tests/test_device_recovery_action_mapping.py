"""M5: Tests for recovery action mapping from error codes."""

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
