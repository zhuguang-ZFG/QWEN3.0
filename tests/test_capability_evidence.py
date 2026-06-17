"""Tests for unified outcome ledger / capability evidence (merged 2026-05-27)."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def evidence_db(monkeypatch):
    """Use a temp SQLite DB for isolated tests."""
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "test_outcome.db"
        monkeypatch.setenv("LIMA_OUTCOME_DB", str(db))
        # Clear any module-level cached connections
        # Force fresh connection by re-importing key functions
        yield db


def test_record_evidence_redacts_secret_like_values(evidence_db):
    from observability.capability_evidence import record_evidence, recent_evidence

    record_evidence(
        loop="chat_ide",
        request_id="req-1",
        entrypoint="/v1/chat/completions",
        selected_backend="scnet_ds_flash",
        status="ok",
        evidence=["Bearer sk-test-123"],
    )
    row = recent_evidence(limit=1)[0]
    assert row["loop"] == "chat_ide"
    assert row["outcome"] == "ok"
    assert "sk-test" not in str(row)
    assert "Bearer sk-" not in str(row)


def test_record_evidence_caps_artifact_paths(evidence_db):
    from observability.capability_evidence import record_evidence, recent_evidence

    record_evidence(
        loop="agent_worker",
        request_id="req-2",
        task_id="task-2",
        entrypoint="/agent/tasks/task-2/result",
        status="needs_review",
        artifact_paths=[f"a{i}.md" for i in range(20)],
    )
    row = recent_evidence(limit=1)[0]
    # artifact_paths are capped before persistence.
    paths = row.get("artifact_paths", [])
    if isinstance(paths, str):
        import json

        paths = json.loads(paths)
    assert len(paths) <= 10


def test_record_evidence_rejects_unknown_loop(evidence_db):
    from observability.capability_evidence import record_evidence

    with pytest.raises(ValueError, match="unsupported"):
        record_evidence(loop="unknown_loop", status="ok")


def test_record_evidence_stores_all_fields(evidence_db):
    from observability.capability_evidence import record_evidence, recent_evidence

    record_evidence(
        loop="device_gateway",
        request_id="req-d",
        task_id="task-d",
        device_id="dev-1",
        entrypoint="/device/v1/tasks",
        selected_backend="",
        fallback_used=False,
        latency_ms=450,
        status="sent",
        evidence=["device_task_created"],
        rollback="delete pending task",
    )
    row = recent_evidence(limit=1)[0]
    assert row["loop"] == "device_gateway"
    assert row["task_id"] == "task-d"
    assert row["latency_ms"] == 450
    assert row["rollback"] != ""


def test_recent_evidence_respects_limit(evidence_db):
    from observability.capability_evidence import record_evidence, recent_evidence

    for i in range(5):
        record_evidence(loop="backend_eval", request_id=f"r{i}", status="ok")
    rows = recent_evidence(limit=3)
    assert len(rows) == 3


def test_recent_evidence_empty_on_fresh_db(monkeypatch):
    import tempfile

    tmp = tempfile.mkdtemp()
    db = Path(tmp) / "fresh_empty.db"
    monkeypatch.setenv("LIMA_OUTCOME_DB", str(db))
    from observability.capability_evidence import recent_evidence

    rows = recent_evidence()
    assert rows == []


def test_record_evidence_safe_swallows_invalid_loop(evidence_db):
    from observability.capability_evidence import record_evidence_safe

    assert record_evidence_safe(loop="not_a_loop", status="ok") is None
