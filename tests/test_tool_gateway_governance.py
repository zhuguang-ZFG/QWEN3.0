"""Tests for tool_gateway.governance."""

from __future__ import annotations

import os
import tempfile
import time

import pytest

from tool_gateway.governance import (
    WorkerRecord,
    get_worker,
    heartbeat,
    list_workers,
    mark_offline_stale,
    quarantine_worker,
    register_worker,
    reset_for_tests,
)


@pytest.fixture(autouse=True)
def isolated_worker_db(monkeypatch: pytest.MonkeyPatch) -> None:
    """Point worker registry storage at a temporary SQLite DB."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "workers.db")
        monkeypatch.setenv("LIMA_WORKER_DB", db_path)
        reset_for_tests()
        yield
        reset_for_tests()


class TestRegisterWorker:
    def test_register_worker_returns_record(self) -> None:
        rec = register_worker("w1", version="1.0", capacity=4)
        assert isinstance(rec, WorkerRecord)
        assert rec.worker_id == "w1"
        assert rec.version == "1.0"
        assert rec.capacity == 4
        assert rec.status == "idle"

    def test_register_worker_overwrites_existing(self) -> None:
        register_worker("w1", version="1.0")
        rec = register_worker("w1", version="2.0")
        fetched = get_worker("w1")
        assert fetched is not None
        assert fetched.version == "2.0"
        assert fetched.registered_at >= rec.registered_at


class TestHeartbeat:
    def test_heartbeat_updates_status_and_tasks(self) -> None:
        register_worker("w1")
        ok = heartbeat("w1", status="busy", active_tasks=["t1", "t2"])
        assert ok is True
        fetched = get_worker("w1")
        assert fetched is not None
        assert fetched.status == "busy"
        assert fetched.active_tasks == ["t1", "t2"]
        assert fetched.last_heartbeat >= fetched.registered_at

    def test_heartbeat_for_unknown_worker_returns_false(self) -> None:
        assert heartbeat("unknown") is False


class TestGetWorker:
    def test_get_worker_returns_none_for_unknown(self) -> None:
        assert get_worker("noone") is None

    def test_get_worker_returns_full_record(self) -> None:
        register_worker("w1", version="v3", capacity=2)
        fetched = get_worker("w1")
        assert fetched is not None
        assert fetched.worker_id == "w1"
        assert fetched.version == "v3"
        assert fetched.capacity == 2


class TestListWorkers:
    def test_list_workers_returns_all_by_default(self) -> None:
        register_worker("w1")
        register_worker("w2")
        workers = list_workers()
        assert len(workers) == 2
        assert {w.worker_id for w in workers} == {"w1", "w2"}

    def test_list_workers_filters_by_status(self) -> None:
        register_worker("w1")
        register_worker("w2")
        heartbeat("w2", status="busy")
        busy_workers = list_workers(status="busy")
        assert len(busy_workers) == 1
        assert busy_workers[0].worker_id == "w2"


class TestQuarantineWorker:
    def test_quarantine_updates_status(self) -> None:
        register_worker("w1")
        heartbeat("w1", status="busy")
        assert quarantine_worker("w1") is True
        fetched = get_worker("w1")
        assert fetched is not None
        assert fetched.status == "quarantined"

    def test_quarantine_unknown_worker_returns_false(self) -> None:
        assert quarantine_worker("unknown") is False


class TestMarkOfflineStale:
    def test_marks_old_heartbeats_offline(self) -> None:
        register_worker("w1")
        # Simulate an old heartbeat by directly updating the DB timestamp.
        rec = get_worker("w1")
        assert rec is not None
        # Re-register with an old timestamp is not supported, so we use a tiny timeout.
        time.sleep(0.05)
        assert mark_offline_stale(timeout_sec=0.01) == 1
        fetched = get_worker("w1")
        assert fetched is not None
        assert fetched.status == "offline"

    def test_does_not_mark_quarantined_workers(self) -> None:
        register_worker("w1")
        quarantine_worker("w1")
        time.sleep(0.05)
        assert mark_offline_stale(timeout_sec=0.01) == 0
        fetched = get_worker("w1")
        assert fetched is not None
        assert fetched.status == "quarantined"


class TestResetForTests:
    def test_reset_clears_registry(self) -> None:
        register_worker("w1")
        assert get_worker("w1") is not None
        reset_for_tests()
        assert get_worker("w1") is None
