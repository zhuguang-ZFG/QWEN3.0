from observability.backend_telemetry import record_backend_attempt
from observability.routing_guard import backend_guard_snapshot, is_backend_quarantined, penalty_multiplier


def test_recent_empty_response_quarantines_backend(monkeypatch, tmp_path):
    monkeypatch.setenv("LIMA_DATA_DIR", str(tmp_path))

    assert record_backend_attempt(
        backend="flaky_backend",
        scenario="coding",
        request_type="chat",
        success=False,
        response_empty=True,
        latency_ms=65000,
    )

    snapshot = backend_guard_snapshot(limit=10)
    decision = snapshot["decisions"]["flaky_backend"]

    assert snapshot["enabled"] is True
    assert decision["status"] == "quarantined"
    assert decision["reason"] == "recent_hard_failure"
    assert is_backend_quarantined("flaky_backend") is True
    assert penalty_multiplier("flaky_backend") == decision["penalty_multiplier"]


def test_newer_success_clears_short_quarantine(monkeypatch, tmp_path):
    monkeypatch.setenv("LIMA_DATA_DIR", str(tmp_path))

    assert record_backend_attempt(
        backend="recovering_backend",
        success=False,
        status_code=504,
        error="timeout",
    )
    assert record_backend_attempt(
        backend="recovering_backend",
        success=True,
        latency_ms=200,
    )

    decision = backend_guard_snapshot(limit=10)["decisions"]["recovering_backend"]

    assert decision["status"] == "penalized"
    assert decision["reason"] == "recent_failure_ratio"
    assert is_backend_quarantined("recovering_backend") is False
    assert 0.0 < penalty_multiplier("recovering_backend") < 1.0


def test_repeated_soft_failures_are_quarantined(monkeypatch, tmp_path):
    monkeypatch.setenv("LIMA_DATA_DIR", str(tmp_path))

    for _ in range(3):
        assert record_backend_attempt(
            backend="unknown_failing_backend",
            success=False,
            error="opaque issue",
        )

    decision = backend_guard_snapshot(limit=10)["decisions"]["unknown_failing_backend"]

    assert decision["status"] == "quarantined"
    assert decision["reason"] == "repeated_recent_failures"
    assert decision["failures"] == 3


def test_same_second_failure_after_success_is_quarantined(monkeypatch, tmp_path):
    monkeypatch.setenv("LIMA_DATA_DIR", str(tmp_path))

    assert record_backend_attempt(
        backend="same_second_backend",
        success=True,
        latency_ms=100,
    )
    assert record_backend_attempt(
        backend="same_second_backend",
        success=False,
        response_empty=True,
    )

    decision = backend_guard_snapshot(limit=10)["decisions"]["same_second_backend"]

    assert decision["status"] == "quarantined"
    assert decision["reason"] == "recent_hard_failure"


def test_routing_guard_can_be_disabled(monkeypatch, tmp_path):
    monkeypatch.setenv("LIMA_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("LIMA_ROUTING_GUARD_ENABLED", "0")

    assert record_backend_attempt(
        backend="disabled_backend",
        success=False,
        response_empty=True,
    )

    snapshot = backend_guard_snapshot(limit=10)

    assert snapshot["enabled"] is False
    assert snapshot["decisions"] == {}
    assert is_backend_quarantined("disabled_backend") is False
    assert penalty_multiplier("disabled_backend") == 1.0
