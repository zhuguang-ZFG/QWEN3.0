"""Tests for context_pipeline.auto_indexer scheduling and failure modes."""

from __future__ import annotations

import time


MOCK_NOW = 2_000_000_000.0  # fixed deterministic timestamp for stable tests
import pytest

from context_pipeline.auto_indexer import AutoIndexer, get_auto_indexer, run_indexer_scan, stop_auto_indexer


def test_should_scan_true_until_interval_elapsed():
    indexer = AutoIndexer(scan_interval=3600)
    assert indexer.should_scan() is True
    indexer._last_scan = MOCK_NOW
    assert indexer.should_scan() is False


def test_last_scan_property_tracks_scan_time():
    indexer = AutoIndexer()
    assert indexer.last_scan == 0.0
    indexer._last_scan = 123.0
    assert indexer.last_scan == 123.0


def test_scan_once_without_watcher_returns_error(monkeypatch):
    monkeypatch.setattr(AutoIndexer, "_init_components", lambda self: None)
    indexer = AutoIndexer()
    result = indexer.scan_once()
    assert result["error"] == "watcher not available"


def test_get_auto_indexer_returns_singleton():
    first = get_auto_indexer()
    second = get_auto_indexer()
    assert first is second


def test_run_indexer_scan_delegates_to_singleton(monkeypatch):
    monkeypatch.setattr(
        "context_pipeline.auto_indexer.get_auto_indexer",
        lambda: type("Idx", (), {"scan_once": lambda self: {"indexed": 0}})(),
    )
    assert run_indexer_scan() == {"indexed": 0}


def test_start_and_stop_auto_indexer(monkeypatch):
    stop_auto_indexer()
    monkeypatch.setattr("context_pipeline.auto_indexer.run_indexer_scan", lambda: {"ok": True})
    from context_pipeline.auto_indexer import start_auto_indexer

    start_auto_indexer(interval_sec=60)
    stop_auto_indexer()


@pytest.fixture(autouse=True)
def fixed_time(monkeypatch):
    monkeypatch.setattr(time, "time", lambda: MOCK_NOW)
