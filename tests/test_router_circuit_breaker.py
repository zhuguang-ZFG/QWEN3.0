"""Tests for router_circuit_breaker (CQ-014 slice 6)."""

import router_circuit_breaker as cb


def setup_function():
    cb.reset_for_tests()


def test_cb_allow_closed_by_default():
    assert cb.cb_allow("test_backend") is True


def test_cb_opens_after_failure_threshold():
    for _ in range(cb.CB_FAILURE_THRESHOLD):
        cb.cb_record("backend_a", success=False)

    assert cb.cb_allow("backend_a") is False
    status = cb.cb_status()["backend_a"]
    assert status["state"] == "open"


def test_cb_half_open_recovers_after_successes():
    for _ in range(cb.CB_FAILURE_THRESHOLD):
        cb.cb_record("backend_b", success=False)
    assert cb.cb_allow("backend_b") is False

    cb._cb_state["backend_b"]["state"] = "half-open"
    cb._cb_state["backend_b"]["successes"] = 0

    for _ in range(cb.CB_SUCCESS_THRESHOLD):
        cb.cb_record("backend_b", success=True)

    assert cb.cb_allow("backend_b") is True
    assert cb.cb_status()["backend_b"]["state"] == "closed"


def test_cb_status_tracks_latency_and_errors():
    cb.cb_record("backend_c", success=True, latency_ms=100)
    cb.cb_record("backend_c", success=False, latency_ms=50)

    status = cb.cb_status()["backend_c"]
    assert status["total_calls"] == 2
    assert status["avg_latency_ms"] == 75
