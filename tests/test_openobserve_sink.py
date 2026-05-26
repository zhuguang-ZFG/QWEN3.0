"""Tests for observability/openobserve_sink (PE-C-2)."""

from __future__ import annotations

from observability.events import backend_error_event
from observability.openobserve_sink import (
    event_to_record,
    ingest_url,
    openobserve_enabled,
    post_records,
)


def test_openobserve_disabled_by_default(monkeypatch):
    monkeypatch.delenv("OPENOBSERVE_ENABLED", raising=False)
    assert openobserve_enabled() is False


def test_event_to_record_redacts_empty_fields():
    event = backend_error_event("req1", "google_flash_lite", "rate_limited", 120.0)
    record = event_to_record(event)
    assert record["event_type"] == "backend_error"
    assert record["request_id"] == "req1"
    assert record["backend"] == "google_flash_lite"
    assert "route_reason" not in record


def test_ingest_url_format():
    cfg = {
        "url": "http://127.0.0.1:5080",
        "org": "default",
        "stream": "lima_events",
    }
    assert ingest_url(cfg) == "http://127.0.0.1:5080/api/default/lima_events/_json"


def test_post_records_without_password(monkeypatch):
    monkeypatch.setenv("OPENOBSERVE_PASSWORD", "")
    ok = post_records([{"event_type": "test"}])
    assert ok is False
