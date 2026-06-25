"""Tests for backend_retirement.py — automatic degradation module."""

import time

import pytest

MOCK_NOW = 2_000_000_000.0  # fixed deterministic timestamp for stable tests
import backend_retirement as br
import backend_profile as bp


def test_check_retirement_not_enough_data():
    bp._profiles.clear()
    bp.record_request("new_backend", 100.0, True, "coding", 500)
    result = br.check_retirement("new_backend")
    assert result is None, "Should not retire with only 1 request"


def test_check_retirement_healthy_backend():
    bp._profiles.clear()
    for _ in range(10):
        bp.record_request("healthy", 100.0, True, "coding", 500)
    result = br.check_retirement("healthy")
    assert result is None, "Healthy backend should not be retired"


def test_check_retirement_low_success_rate():
    bp._profiles.clear()
    for _ in range(25):
        bp.record_request("failing", 100.0, False, "coding", 0)
    bp.record_request("failing", 100.0, True, "coding", 100)
    result = br.check_retirement("failing")
    assert result is not None
    assert result["action"] == "retire"
    assert result["backend"] == "failing"


def test_apply_retirement():
    br.reactivate("test_backend")
    br._retired_backends.clear()
    br._last_reload_ts = MOCK_NOW
    bp._profiles.clear()
    assert not br.is_retired("test_backend")
    br.apply_retirement(
        {
            "action": "retire",
            "backend": "test_backend",
            "reason": "test",
            "status": "retired",
        }
    )
    assert br.is_retired("test_backend")


def test_apply_retirement_is_idempotent(monkeypatch):
    br._retired_backends.clear()
    br._last_reload_ts = MOCK_NOW
    calls = {"save": 0, "notify": 0}

    monkeypatch.setattr(br, "_save_retirement", lambda *a, **k: calls.__setitem__("save", calls["save"] + 1))
    monkeypatch.setattr(br, "_notify_retirement", lambda *a, **k: calls.__setitem__("notify", calls["notify"] + 1))

    action = {
        "action": "retire",
        "backend": "idempotent_backend",
        "reason": "test",
        "status": "retired",
    }
    br.apply_retirement(action)
    br.apply_retirement(action)

    assert br.is_retired("idempotent_backend")
    assert calls == {"save": 1, "notify": 1}


def test_reactivate():
    br._retired_backends.add("react_test")
    assert br.is_retired("react_test")
    br.reactivate("react_test")
    assert not br.is_retired("react_test")


def test_load_retired():
    br._retired_backends.clear()
    br.apply_retirement(
        {
            "action": "retire",
            "backend": "load_test",
            "reason": "test",
            "status": "retired",
        }
    )
    br._retired_backends.clear()
    loaded = br.load_retired()
    assert loaded >= 1
    assert br.is_retired("load_test")


def test_load_retired_marks_health_dead():
    import health_state as hs

    br._retired_backends.clear()
    hs.reset_all_state()
    br.apply_retirement(
        {
            "action": "retire",
            "backend": "load_health_test",
            "reason": "test",
            "status": "retired",
        }
    )
    br._retired_backends.clear()
    hs.reset_all_state()

    br.load_retired()

    assert br.is_retired("load_health_test")
    assert hs.get_health("load_health_test") == "dead"
    assert hs.get_backend_state("load_health_test")["state"] == "retired"


def test_recovery_snapshot_keeps_retired_out_of_probe_candidates():
    br._retired_backends.clear()
    br._retired_backends.add("retired_one")

    snapshot = br.get_recovery_snapshot(
        dead_backends=["retired_one", "dead_one"],
        degraded_backends=["degraded_one"],
    )

    assert snapshot["retired_list"] == ["retired_one"]
    assert snapshot["probe_candidates"] == ["dead_one", "degraded_one"]


def test_is_retired_reloads_from_sqlite(monkeypatch):
    br._retired_backends.clear()
    br._last_reload_ts = 0.0
    monkeypatch.setattr(br, "_RELOAD_INTERVAL_SEC", 0.0)
    br.apply_retirement(
        {
            "action": "retire",
            "backend": "reload_sync_backend",
            "reason": "test",
            "status": "retired",
        }
    )
    br._retired_backends.clear()
    assert br.is_retired("reload_sync_backend")


@pytest.fixture(autouse=True)
def fixed_time(monkeypatch):
    monkeypatch.setattr(time, "time", lambda: MOCK_NOW)
