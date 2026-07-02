"""M5: Tests for recovery retry task dispatch and params preservation."""

from __future__ import annotations

import pytest

from device_gateway.tasks import (
    create_task_from_transcript,
    execute_recovery,
    reset_tasks_for_tests,
)
from device_gateway.store import InMemoryDeviceTaskStore
from device_gateway import store as store_mod


@pytest.fixture(autouse=True)
def _isolate_store(monkeypatch):
    """Give each test a fresh in-memory store."""
    store = InMemoryDeviceTaskStore()
    monkeypatch.setattr(store_mod, "task_store", store)
    reset_tasks_for_tests()
    yield
    reset_tasks_for_tests()


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
