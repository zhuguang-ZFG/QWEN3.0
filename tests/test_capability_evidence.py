"""Tests for observability.capability_evidence — unified evidence record."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def evidence_path(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "evidence.jsonl"
        monkeypatch.setenv("LIMA_CAPABILITY_EVIDENCE_PATH", str(p))
        yield p


def test_record_evidence_redacts_secret_like_values(evidence_path):
    from observability.capability_evidence import record_evidence, recent_evidence

    record_evidence(
        loop="chat_ide", request_id="req-1",
        entrypoint="/v1/chat/completions", selected_backend="scnet_ds_flash",
        status="ok", evidence=["Bearer sk-test-123"],
    )
    row = recent_evidence(limit=1)[0]
    assert row["loop"] == "chat_ide"
    assert row["status"] == "ok"
    assert "sk-test" not in str(row)


def test_record_evidence_caps_artifact_paths(evidence_path):
    from observability.capability_evidence import record_evidence, recent_evidence

    record_evidence(
        loop="limacode_worker", request_id="req-2", task_id="task-2",
        entrypoint="/agent/tasks/task-2/result", status="needs_review",
        artifact_paths=[f"a{i}.md" for i in range(20)],
    )
    row = recent_evidence(limit=1)[0]
    assert len(row["artifact_paths"]) == 10


def test_record_evidence_rejects_unknown_loop(evidence_path):
    from observability.capability_evidence import record_evidence

    with pytest.raises(ValueError, match="unsupported"):
        record_evidence(loop="unknown_loop", status="ok")


def test_record_evidence_stores_all_fields(evidence_path):
    from observability.capability_evidence import record_evidence, recent_evidence

    record_evidence(
        loop="device_gateway", request_id="req-d", task_id="task-d",
        device_id="dev-1", entrypoint="/device/v1/tasks",
        selected_backend="", fallback_used=False, latency_ms=450,
        status="sent", evidence=["device_task_created"],
        artifact_paths=["path.svg"], rollback="delete pending task",
    )
    row = recent_evidence(limit=1)[0]
    assert row["schema_version"] == "lima.capability_evidence.v0"
    assert row["loop"] == "device_gateway"
    assert row["task_id"] == "task-d"
    assert row["device_id"] == "dev-1"
    assert row["latency_ms"] == 450
    assert row["rollback"] != ""


def test_recent_evidence_respects_limit(evidence_path):
    from observability.capability_evidence import record_evidence, recent_evidence

    for i in range(5):
        record_evidence(loop="backend_eval", request_id=f"r{i}", status="ok")
    rows = recent_evidence(limit=3)
    assert len(rows) == 3


def test_recent_evidence_empty_when_no_file(evidence_path):
    from observability.capability_evidence import recent_evidence

    # Delete the file
    evidence_path.unlink(missing_ok=True)
    rows = recent_evidence()
    assert rows == []
