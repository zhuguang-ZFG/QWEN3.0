"""Tests for routing_executor_telemetry.py (P1-5)."""

from __future__ import annotations

from unittest.mock import patch


from routing_executor.telemetry import _record_backend_attempt, extract_error_code


class FakeExceptionWithStatusCode(Exception):
    status_code = 429


class FakeExceptionWithCode(Exception):
    code = 401


class FakeExceptionWithStatus(Exception):
    status = 503


def test_extract_error_code_prefers_status_code():
    assert extract_error_code(FakeExceptionWithStatusCode("rate limited")) == 429


def test_extract_error_code_falls_back_to_code():
    assert extract_error_code(FakeExceptionWithCode("unauthorized")) == 401


def test_extract_error_code_falls_back_to_status():
    assert extract_error_code(FakeExceptionWithStatus("unavailable")) == 503


def test_extract_error_code_from_message():
    assert extract_error_code(Exception("server returned 403")) == 403


def test_extract_error_code_unknown_returns_none():
    assert extract_error_code(Exception("boom")) is None


def test_record_backend_attempt_logs_when_telemetry_missing(caplog):
    """If observability.backend_telemetry is unavailable, a warning is emitted but no exception propagates."""
    with patch.dict("sys.modules", {"observability.backend_telemetry": None}):
        _record_backend_attempt(
            backend="b",
            scenario="chat",
            request_type="chat",
            success=True,
            latency_ms=10.0,
        )
    assert any("not installed" in m for m in caplog.messages)


def test_record_backend_attempt_logs_on_telemetry_failure(monkeypatch, caplog):
    def raise_exc(**kwargs):
        raise RuntimeError("telemetry down")

    monkeypatch.setattr("observability.backend_telemetry.record_backend_attempt", raise_exc)
    _record_backend_attempt(
        backend="b",
        scenario="chat",
        request_type="chat",
        success=False,
        latency_ms=10.0,
    )
    assert any("telemetry recording failed" in m for m in caplog.messages)
