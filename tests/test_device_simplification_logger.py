"""Test device_simplification_logger module."""

import json
from pathlib import Path
from device_gateway.device_simplification_logger import (
    record_simplification,
    ARTIFACT_DIR,
)


def test_log_creation() -> None:
    """Test that log creation works and file is created."""
    reset_logs()

    record_simplification(
        device_id="device_001",
        task_id="task_001",
        simplification_type="cap",
        reason="test reason",
        original={"param": 100},
        constrained={"param": 50},
    )

    log_path = ARTIFACT_DIR / "simplification_device_001.log"
    assert log_path.exists()


def test_log_retrieval() -> None:
    """Test that log file can be read and contains expected data."""
    reset_logs()

    device_id = "device_002"
    task_id = "task_002"
    simplification_type = "gate"
    reason = "test reason 2"
    original = {"value": "original"}
    constrained = {"value": "constrained"}

    record_simplification(
        device_id=device_id,
        task_id=task_id,
        simplification_type=simplification_type,
        reason=reason,
        original=original,
        constrained=constrained,
    )

    log_path = ARTIFACT_DIR / f"simplification_{device_id}.log"
    with log_path.open("r", encoding="utf-8") as f:
        lines = f.readlines()

    assert len(lines) == 1

    log_entry = json.loads(lines[0])
    assert log_entry["device_id"] == device_id
    assert log_entry["task_id"] == task_id
    assert log_entry["simplification_type"] == simplification_type
    assert log_entry["reason"] == reason
    assert log_entry["original"] == original
    assert log_entry["constrained"] == constrained


def test_jsonl_format_validity() -> None:
    """Test that each line in log files is valid JSON."""
    reset_logs()

    device_id = "device_003"
    record_simplification(
        device_id=device_id,
        task_id="task_003",
        simplification_type="downgrade",
        reason="test reason 3",
        original={"key": "value"},
        constrained={"key": "value"},
    )

    log_path = ARTIFACT_DIR / f"simplification_{device_id}.log"
    with log_path.open("r", encoding="utf-8") as f:
        for line in f:
            json.loads(line.strip())


def test_empty_device_id() -> None:
    """Test that record_simplification with empty device_id logs warning and doesn't create file."""
    reset_logs()

    record_simplification(
        device_id="",
        task_id="task_004",
        simplification_type="cap",
        reason="test reason",
        original={"param": 100},
        constrained={"param": 50},
    )

    log_path = ARTIFACT_DIR / "simplification_.log"
    assert not log_path.exists()


def test_empty_task_id() -> None:
    """Test that record_simplification with empty task_id logs warning and doesn't create file."""
    reset_logs()

    record_simplification(
        device_id="device_005",
        task_id="",
        simplification_type="cap",
        reason="test reason",
        original={"param": 100},
        constrained={"param": 50},
    )

    log_path = ARTIFACT_DIR / "simplification_device_005.log"
    assert not log_path.exists()


def reset_logs() -> None:
    """Clear all log files."""
    for log_file in ARTIFACT_DIR.glob("simplification_*.log"):
        log_file.unlink()
    ARTIFACT_DIR.mkdir(exist_ok=True)
