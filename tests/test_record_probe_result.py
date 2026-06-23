"""Tests for record_probe_result and its helpers in backend_probe_loop."""
from __future__ import annotations

import importlib.abc
import sys
import types
from unittest.mock import MagicMock

import pytest


def _ht_mock():
    mod = types.ModuleType("health_tracker")
    mod.record_success = MagicMock()  # type: ignore[attr-defined]
    mod.record_failure = MagicMock()  # type: ignore[attr-defined]
    return mod


def _bp_mock():
    mod = types.ModuleType("backend_profile")
    mod.record_request = MagicMock()  # type: ignore[attr-defined]
    return mod


def _bt_mock():
    telemetry = types.ModuleType("observability.backend_telemetry")
    telemetry.record_backend_attempt = MagicMock()  # type: ignore[attr-defined]
    obs = types.ModuleType("observability")
    obs.backend_telemetry = telemetry  # type: ignore[attr-defined]
    return obs


class _BlockFinder(importlib.abc.MetaPathFinder):
    def __init__(self, blocked: frozenset[str]):
        self._blocked = blocked
    def find_spec(self, name, path, target=None):
        if name in self._blocked:
            raise ImportError(f"mocked block: {name}")
        return None


def _block(*names):
    """Return a fixture helper that blocks the given module names."""
    def _apply(monkeypatch):
        for n in names:
            monkeypatch.delitem(sys.modules, n, raising=False)
        monkeypatch.setattr(sys, "meta_path", [_BlockFinder(frozenset(names))] + sys.meta_path)
    return _apply


@pytest.fixture(autouse=True)
def _snap(monkeypatch):
    keys = ("health_tracker", "backend_profile", "observability", "observability.backend_telemetry")
    orig = {k: sys.modules.get(k) for k in keys}
    yield
    for k, v in orig.items():
        if v is None:
            sys.modules.pop(k, None)
        else:
            sys.modules[k] = v


def _inject_all(monkeypatch):
    ht, bp, obs = _ht_mock(), _bp_mock(), _bt_mock()
    monkeypatch.setitem(sys.modules, "health_tracker", ht)
    monkeypatch.setitem(sys.modules, "backend_profile", bp)
    monkeypatch.setitem(sys.modules, "observability", obs)
    monkeypatch.setitem(sys.modules, "observability.backend_telemetry", obs.backend_telemetry)
    return ht, bp, obs


def _record():
    from backend_probe_loop import record_probe_result
    return record_probe_result


def _helpers():
    from backend_probe_loop import (
        _record_backend_profile, _record_backend_telemetry, _record_health_tracker,
    )
    return _record_health_tracker, _record_backend_profile, _record_backend_telemetry


# 1. missing/empty backend → False

def test_empty_backend_returns_false():
    r = _record()
    assert r({}) is False
    assert r({"backend": ""}) is False


# 2. healthy → success=True for all 3 helpers

def test_healthy_success_paths(monkeypatch):
    ht, bp, obs = _inject_all(monkeypatch)
    assert _record()({"backend": "groq", "status": "healthy", "latency_ms": 42}) is True
    ht.record_success.assert_called_once_with("groq", 42)
    bp.record_request.assert_called_once_with("groq", 42, success=True, scenario="probe", response_len=0)
    obs.backend_telemetry.record_backend_attempt.assert_called_once_with(
        backend="groq", scenario="probe", request_type="operator_probe", success=True,
        latency_ms=42, status_code=None, error=None, response_empty=False,
        phase="operator_probe", attempt="manual",
    )


# 3. failed → success=False, error fields forwarded

def test_failed_failure_paths(monkeypatch):
    ht, bp, obs = _inject_all(monkeypatch)
    assert _record()({"backend": "nvidia", "status": "failed", "error_code": 503, "error": "timeout", "latency_ms": 999}) is True
    ht.record_failure.assert_called_once_with("nvidia", error_code=503, error_text="timeout")
    bp.record_request.assert_called_once_with("nvidia", 999, success=False, scenario="probe", response_len=0)
    obs.backend_telemetry.record_backend_attempt.assert_called_once_with(
        backend="nvidia", scenario="probe", request_type="operator_probe", success=False,
        latency_ms=999, status_code=503, error="timeout", response_empty=False,
        phase="operator_probe", attempt="manual",
    )


# 4. empty status → success=False, response_empty=True

def test_empty_status_response_empty_flag(monkeypatch):
    _, _, obs = _inject_all(monkeypatch)
    assert _record()({"backend": "cf", "status": "empty"}) is True
    kw = obs.backend_telemetry.record_backend_attempt.call_args.kwargs
    assert kw["response_empty"] is True
    assert kw["success"] is False


# 5-7. Each helper ImportError → returns False

@pytest.mark.parametrize("blocked_name, helper_idx", [
    ("health_tracker", 0),
    ("backend_profile", 1),
])
def test_helper_import_error_returns_false(monkeypatch, blocked_name, helper_idx):
    _block(blocked_name)(monkeypatch)
    assert _helpers()[helper_idx]({}, "b", 0, True) is False


def test_telemetry_import_error_returns_false(monkeypatch):
    _block("observability.backend_telemetry")(monkeypatch)
    assert _helpers()[2]({}, "b", "healthy", 0, True) is False


# 8. All 3 helpers succeed → returns True

def test_all_helpers_succeed(monkeypatch):
    _inject_all(monkeypatch)
    assert _record()({"backend": "deepseek", "status": "healthy", "latency_ms": 7}) is True


# 9. Mixed results → True if at least one; False if all fail

def test_partial_success_returns_true(monkeypatch):
    monkeypatch.setitem(sys.modules, "health_tracker", _ht_mock())
    _block("backend_profile", "observability.backend_telemetry")(monkeypatch)
    assert _record()({"backend": "openrouter", "status": "healthy", "latency_ms": 10}) is True


def test_all_blocked_returns_false(monkeypatch):
    _block("health_tracker", "backend_profile", "observability.backend_telemetry")(monkeypatch)
    assert _record()({"backend": "broken", "status": "healthy", "latency_ms": 5}) is False


# Bonus: missing latency/response_len default to 0

def test_defaults_when_fields_absent(monkeypatch):
    ht, bp, _ = _inject_all(monkeypatch)
    assert _record()({"backend": "groq", "status": "healthy"}) is True
    ht.record_success.assert_called_once_with("groq", 0)
    bp.record_request.assert_called_once_with("groq", 0, success=True, scenario="probe", response_len=0)
