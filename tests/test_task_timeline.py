"""设备任务历史时间线查询测试 — device_gateway/task_timeline.py。"""

from __future__ import annotations

import pytest

from device_ledger.events import LedgerEvent, new_event
from device_ledger.store import InMemoryLedgerStore, set_ledger_store_for_tests


@pytest.fixture(autouse=True)
def _fresh_ledger():
    store = InMemoryLedgerStore()
    set_ledger_store_for_tests(store)
    yield store


def _make_event(
    event_type: str = "task_created",
    task_id: str = "task-001",
    device_id: str = "dev-A",
    payload: dict | None = None,
    created_at: str = "2026-07-02T10:00:00Z",
) -> LedgerEvent:
    return new_event(
        event_type=event_type,
        task_id=task_id,
        device_id=device_id,
        payload=payload or {},
        event_id=f"evt-{event_type}-{task_id}",
        created_at=created_at,
    )


class TestBuildTaskTimeline:
    def test_returns_none_for_unknown_task(self):
        from device_gateway.task_timeline import build_task_timeline

        assert build_task_timeline("nonexistent") is None

    def test_single_event_timeline(self, _fresh_ledger):
        from device_gateway.task_timeline import build_task_timeline

        _fresh_ledger.append_event(_make_event(payload={"task": {"task_id": "task-001"}, "status": "created"}))
        result = build_task_timeline("task-001")

        assert result is not None
        assert result["task_id"] == "task-001"
        assert result["current_status"] == "created"
        assert result["is_terminal"] is False
        assert result["event_count"] == 1
        assert len(result["timeline"]) == 1
        assert result["timeline"][0]["label"] == "任务创建"
        assert result["timeline"][0]["duration_ms"] == 0

    def test_multi_event_timeline_with_durations(self, _fresh_ledger):
        from device_gateway.task_timeline import build_task_timeline

        _fresh_ledger.append_event(
            _make_event(
                payload={"task": {"task_id": "task-001"}, "status": "created"}, created_at="2026-07-02T10:00:00Z"
            )
        )
        _fresh_ledger.append_event(
            _make_event(
                event_type="task_dispatched",
                task_id="task-001",
                created_at="2026-07-02T10:00:05Z",
            )
        )
        _fresh_ledger.append_event(
            _make_event(
                event_type="motion_event",
                task_id="task-001",
                payload={"motion_event": {"phase": "executing"}},
                created_at="2026-07-02T10:00:10Z",
            )
        )
        _fresh_ledger.append_event(
            _make_event(
                event_type="task_terminal",
                task_id="task-001",
                payload={"terminal_event": {"phase": "done"}},
                created_at="2026-07-02T10:00:30Z",
            )
        )

        result = build_task_timeline("task-001")
        assert result is not None
        assert result["current_status"] == "done"
        assert result["is_terminal"] is True
        assert result["event_count"] == 4
        assert len(result["timeline"]) == 4

        # First entry has 0 duration
        assert result["timeline"][0]["duration_ms"] == 0
        # Second entry: 5 seconds = 5000ms
        assert result["timeline"][1]["duration_ms"] == 5000
        # Third entry: 5 seconds = 5000ms
        assert result["timeline"][2]["duration_ms"] == 5000
        # Fourth entry: 20 seconds = 20000ms
        assert result["timeline"][3]["duration_ms"] == 20000

        # Total duration
        assert result["total_duration_ms"] == 30000

    def test_timeline_labels(self, _fresh_ledger):
        from device_gateway.task_timeline import build_task_timeline

        _fresh_ledger.append_event(_make_event(payload={"status": "created"}))
        _fresh_ledger.append_event(_make_event(event_type="task_dispatched", created_at="2026-07-02T10:00:01Z"))

        result = build_task_timeline("task-001")
        labels = [e["label"] for e in result["timeline"]]
        assert "任务创建" in labels
        assert "已分发至设备" in labels


class TestBuildDeviceTimeline:
    def test_empty_device(self):
        from device_gateway.task_timeline import build_device_timeline

        assert build_device_timeline("dev-X") == []

    def test_single_task_device_timeline(self, _fresh_ledger):
        from device_gateway.task_timeline import build_device_timeline

        _fresh_ledger.append_event(_make_event(device_id="dev-A", payload={"status": "created"}))
        _fresh_ledger.append_event(
            _make_event(
                event_type="task_dispatched",
                device_id="dev-A",
                created_at="2026-07-02T10:00:05Z",
            )
        )

        result = build_device_timeline("dev-A")
        assert len(result) == 1
        assert result[0]["task_id"] == "task-001"
        assert result[0]["device_id"] == "dev-A"
        assert result[0]["event_count"] == 2
        assert result[0]["current_status"] == "dispatched"
        assert result[0]["is_terminal"] is False
        assert len(result[0]["phases"]) == 2

    def test_multiple_tasks_sorted_by_last_seen_desc(self, _fresh_ledger):
        from device_gateway.task_timeline import build_device_timeline

        # Task A: earlier
        _fresh_ledger.append_event(_make_event(task_id="task-A", device_id="dev-A", created_at="2026-07-02T09:00:00Z"))
        # Task B: later
        _fresh_ledger.append_event(_make_event(task_id="task-B", device_id="dev-A", created_at="2026-07-02T10:00:00Z"))

        result = build_device_timeline("dev-A")
        assert len(result) == 2
        assert result[0]["task_id"] == "task-B"  # More recent first
        assert result[1]["task_id"] == "task-A"

    def test_limit_truncation(self, _fresh_ledger):
        from device_gateway.task_timeline import build_device_timeline

        for i in range(5):
            _fresh_ledger.append_event(
                _make_event(
                    task_id=f"task-{i:03d}",
                    device_id="dev-A",
                    created_at=f"2026-07-02T10:00:{i:02d}Z",
                )
            )

        result = build_device_timeline("dev-A", limit=3)
        assert len(result) == 3

    def test_is_terminal_flag(self, _fresh_ledger):
        from device_gateway.task_timeline import build_device_timeline

        _fresh_ledger.append_event(
            _make_event(task_id="task-done", device_id="dev-A", created_at="2026-07-02T10:00:00Z")
        )
        _fresh_ledger.append_event(
            _make_event(
                event_type="task_terminal",
                task_id="task-done",
                device_id="dev-A",
                payload={"terminal_event": {"phase": "done"}},
                created_at="2026-07-02T10:00:10Z",
            )
        )

        result = build_device_timeline("dev-A")
        assert len(result) == 1
        assert result[0]["is_terminal"] is True
