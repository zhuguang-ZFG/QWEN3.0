"""Tests for device_gateway protocol — motion error codes and lifecycle validation."""

from device_gateway.protocol import (
    motion_failure_event,
    validate_motion_event,
    validate_motion_task_lifecycle,
    TERMINAL_MOTION_PHASES,
)
from device_gateway.protocol_families import MotionErrorCode


def test_motion_failure_event_builds_standards_frame():
    frame = motion_failure_event(
        "dev-1",
        "task-001",
        MotionErrorCode.E_MISSING_PATH,
        reason="path is empty",
        request_id="req-1",
    )
    assert frame["type"] == "motion_event"
    assert frame["phase"] == "failed"
    assert frame["error"]["code"] == "E_MISSING_PATH"
    assert frame["error"]["reason"] == "path is empty"
    assert frame["request_id"] == "req-1"


def test_motion_failure_event_defaults_reason_to_error_code():
    frame = motion_failure_event("dev-1", "task-001", MotionErrorCode.E_UNSUPPORTED_CAPABILITY)
    assert frame["error"]["reason"] == "E_UNSUPPORTED_CAPABILITY"


def test_validate_motion_event_preserves_nested_error():
    event = validate_motion_event(
        {
            "type": "motion_event",
            "device_id": "dev-1",
            "task_id": "task-001",
            "phase": "failed",
            "error": {"code": "E_MISSING_PATH", "reason": "path missing"},
        }
    )

    assert event["error"] == {"code": "E_MISSING_PATH", "reason": "path missing"}


def test_validate_motion_event_normalizes_firmware_error_fields():
    event = validate_motion_event(
        {
            "type": "motion_event",
            "device_id": "dev-1",
            "task_id": "task-001",
            "phase": "failed",
            "error_code": "E_UNSUPPORTED_BOARD",
            "error_message": "board does not support motion tasks",
        }
    )

    assert event["error"] == {
        "code": "E_UNSUPPORTED_BOARD",
        "reason": "board does not support motion tasks",
    }


def test_validate_motion_task_lifecycle_empty_events():
    result = validate_motion_task_lifecycle([])
    assert not result["ok"]
    assert result["missing_phase"] == "accepted"


def test_validate_motion_task_lifecycle_no_terminal():
    result = validate_motion_task_lifecycle(
        [
            {"phase": "accepted"},
            {"phase": "running"},
            {"phase": "progress"},
        ]
    )
    assert not result["ok"]
    assert "no terminal phase" in result["reason"]


def test_validate_motion_task_lifecycle_done():
    result = validate_motion_task_lifecycle(
        [
            {"phase": "accepted"},
            {"phase": "running"},
            {"phase": "done"},
        ]
    )
    assert result["ok"]
    assert result["terminal_phase"] == "done"


def test_validate_motion_task_lifecycle_failed_with_error():
    result = validate_motion_task_lifecycle(
        [
            {"phase": "accepted"},
            {"phase": "running"},
            {"phase": "failed", "error": {"code": "E_EXECUTION_FAILED", "reason": "motor stall"}},
        ]
    )
    assert result["ok"]
    assert result["terminal_phase"] == "failed"
    assert result["error"]["code"] == "E_EXECUTION_FAILED"


def test_validate_motion_task_lifecycle_failed_without_error_code():
    result = validate_motion_task_lifecycle(
        [
            {"phase": "accepted"},
            {"phase": "failed"},
        ]
    )
    assert not result["ok"]
    assert "missing error code" in result["reason"]


def test_all_motion_error_codes_are_strings():
    for code in MotionErrorCode:
        assert isinstance(code.value, str)
        assert code.value.startswith("E_")


def test_terminal_phases_cover_all_end_states():
    assert "done" in TERMINAL_MOTION_PHASES
    assert "failed" in TERMINAL_MOTION_PHASES
    assert "cancelled" in TERMINAL_MOTION_PHASES
