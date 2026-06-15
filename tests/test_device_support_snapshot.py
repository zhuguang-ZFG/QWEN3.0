"""M7: Tests for device support snapshot module."""

from __future__ import annotations

import pytest

import time

from device_support.snapshot import build_support_snapshot, _build_recommendation, _list_recent_terminal_tasks, _redact_sensitive


class TestBuildRecommendation:
    def test_empty_returns_normal(self):
        rec = _build_recommendation([], [])
        assert "正常" in rec

    def test_estop_triggers_hardware_check(self):
        warnings = [{"error_code": "E_ESTOP", "reason": "emergency"}]
        rec = _build_recommendation(warnings, [])
        assert "急停" in rec

    def test_not_homed_triggers_hardware_check(self):
        warnings = [{"error_code": "E_NOT_HOMED", "reason": "not homed"}]
        rec = _build_recommendation(warnings, [])
        assert "未回零" in rec

    def test_frequent_limit_triggers_calibration(self):
        warnings = [
            {"error_code": "E_LIMIT", "reason": "limit hit"},
            {"error_code": "E_LIMIT", "reason": "limit hit again"},
        ]
        rec = _build_recommendation(warnings, [])
        assert "限位" in rec

    def test_frequent_failures_triggers_link_check(self):
        tasks = [
            {"phase": "failed", "task_id": "t1"},
            {"phase": "failed", "task_id": "t2"},
            {"phase": "failed", "task_id": "t3"},
            {"phase": "done", "task_id": "t4"},
        ]
        rec = _build_recommendation([], tasks)
        assert "失败" in rec
        assert "通信" in rec

    def test_mixed_pattern_returns_normal(self):
        warnings = [{"error_code": "E_LIMIT"}]
        tasks = [
            {"phase": "done", "task_id": "t1"},
            {"phase": "done", "task_id": "t2"},
        ]
        rec = _build_recommendation(warnings, tasks)
        assert "正常" in rec


class TestRedactSensitive:
    def test_token_is_redacted(self):
        info = {"device_id": "dev-1", "token": "secret123"}
        redacted = _redact_sensitive(info)
        assert redacted["token"] == "***"
        assert redacted["device_id"] == "dev-1"

    def test_wifi_password_redacted(self):
        info = {"wifi_password": "mypassword"}
        redacted = _redact_sensitive(info)
        assert redacted["wifi_password"] == "***"

    def test_normal_fields_preserved(self):
        info = {"device_id": "dev-1", "firmware_rev": "v2.0"}
        redacted = _redact_sensitive(info)
        assert redacted == info


class TestRecentTerminalTasks:
    def test_recent_terminal_tasks_filter_by_time_window(self, monkeypatch):
        from device_ledger.events import new_event

        now = time.time()
        old_event = new_event(
            event_type="task_terminal",
            task_id="task-old",
            device_id="dev-1",
            payload={"terminal_event": {"phase": "failed"}},
            created_at="1970-01-01T00:00:00Z",
        )
        new_event_obj = new_event(
            event_type="task_terminal",
            task_id="task-new",
            device_id="dev-1",
            payload={"terminal_event": {"phase": "done"}},
            created_at="2099-01-01T00:00:00Z",
        )

        class _FakeLedger:
            def events_for_device(self, device_id):
                return [old_event, new_event_obj]

        monkeypatch.setattr("device_support.snapshot.ledger_store", _FakeLedger())
        tasks = _list_recent_terminal_tasks("dev-1")
        assert len(tasks) == 1
        assert tasks[0]["task_id"] == "task-new"


class TestSnapshotStructure:
    def test_snapshot_has_required_keys(self):
        snap = build_support_snapshot("dev-unknown-123")
        assert "device_id" in snap
        assert "shadow" in snap
        assert "active_tasks" in snap
        assert "failure_warnings" in snap
        assert "recommendation" in snap
        assert snap["device_id"] == "dev-unknown-123"
