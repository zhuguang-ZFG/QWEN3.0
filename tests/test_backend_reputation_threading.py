"""Regression tests for backend_reputation.py thread safety (P0-1)."""

import threading

import backend_reputation as br


def _reset_state():
    with br._lock:
        br._scores.clear()
        br._history.clear()
        br._cooldowns.clear()


def test_concurrent_record_and_query_no_exceptions():
    """Concurrent record/get_score must not raise and must stay consistent."""
    _reset_state()
    errors: list[Exception] = []

    def worker(_idx: int) -> None:
        try:
            for _ in range(50):
                br.record("test-backend", True)
                br.record_failure_class("test-backend", "network_error")
                br.get_score("test-backend")
                br.is_reputation_cooled("test-backend")
        except Exception as exc:  # pragma: no cover - failures are bugs
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(100)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"thread worker raised: {errors[:3]}"
    assert br.get_score("test-backend") >= 0
    stats = br.get_stats()
    assert "scores" in stats
    assert "test-backend" in stats["scores"]


def test_consecutive_failures_trigger_cooldown():
    """Three consecutive failures within the window must trigger cooldown."""
    _reset_state()
    for _ in range(3):
        br.record("cool-backend", False)
    assert br.is_reputation_cooled("cool-backend")


def test_record_failure_class_high_multiplier_triggers_cooldown():
    """Auth-expired class has a >=5.0 multiplier and should immediately cooldown."""
    _reset_state()
    br.record_failure_class("auth-backend", "auth_expired")
    assert br.is_reputation_cooled("auth-backend")
