"""健康探针标准化接口测试 — health_probe.py。"""

from __future__ import annotations

import pytest

from health_probe import (
    ProbeResult,
    classify_probe_error,
    make_result,
)


class TestProbeResult:
    def test_defaults(self):
        r = ProbeResult(backend="groq", status="healthy")
        assert r.backend == "groq"
        assert r.status == "healthy"
        assert r.latency_ms == 0
        assert r.success is True

    def test_success_property(self):
        assert ProbeResult(backend="x", status="healthy").success is True
        assert ProbeResult(backend="x", status="failed").success is False
        assert ProbeResult(backend="x", status="empty").success is False

    def test_to_dict_minimal(self):
        r = ProbeResult(backend="groq", status="healthy", latency_ms=42)
        d = r.to_dict()
        assert d["backend"] == "groq"
        assert d["status"] == "healthy"
        assert d["latency_ms"] == 42
        assert "error" not in d
        assert "recorded" not in d

    def test_to_dict_with_error(self):
        r = ProbeResult(
            backend="nvidia",
            status="failed",
            latency_ms=100,
            error="timeout",
            error_class="timeout",
        )
        d = r.to_dict()
        assert d["error"] == "timeout"
        assert d["error_class"] == "timeout"

    def test_to_dict_with_extras(self):
        r = ProbeResult(backend="x", status="healthy", recorded=True, timed_out=False)
        d = r.to_dict()
        assert d["recorded"] is True
        assert "timed_out" not in d  # False → omitted


class TestClassifyProbeError:
    def test_auth_error(self):
        assert classify_probe_error("401 unauthorized") == "auth_expired"

    def test_rate_limited(self):
        assert classify_probe_error("429 too many requests") == "rate_limited"

    def test_timeout(self):
        assert classify_probe_error("connection timed out") == "network_error"

    def test_network_error(self):
        assert classify_probe_error("connection refused") == "network_error"

    def test_with_error_code(self):
        result = classify_probe_error("server error", error_code=503)
        assert result == "network_error"

    def test_unknown_error(self):
        result = classify_probe_error("something weird happened")
        assert result == "unknown_error"

    def test_delegates_to_health_recorder(self):
        """classify_probe_error 应委托至 health_recorder.classify_failure。"""
        from health_recorder import classify_failure

        assert classify_probe_error("unauthorized", 401) == classify_failure(401, "unauthorized")


class TestMakeResult:
    def test_healthy_result(self):
        r = make_result("groq", status="healthy", latency_ms=42, response_len=10)
        assert r.backend == "groq"
        assert r.status == "healthy"
        assert r.success is True
        assert r.error_class is None

    def test_failed_result_auto_classifies(self):
        r = make_result("nvidia", status="failed", latency_ms=100, error="401 unauthorized")
        assert r.status == "failed"
        assert r.error_class == "auth_expired"

    def test_failed_result_with_error_code(self):
        r = make_result("cf", status="failed", latency_ms=50, error="rate limited", error_code=429)
        assert r.error_class == "rate_limited"

    def test_timed_out(self):
        r = make_result("slow", status="failed", error="timed out", timed_out=True)
        assert r.timed_out is True
        assert r.error_class is not None

    def test_no_error_no_classification(self):
        r = make_result("ok", status="healthy")
        assert r.error_class is None
        assert r.error is None
