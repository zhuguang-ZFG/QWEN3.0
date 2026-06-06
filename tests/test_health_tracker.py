import sys
from types import SimpleNamespace

import backend_reputation
import health_tracker


def setup_function():
    health_tracker.reset_all_state()
    backend_reputation._scores.clear()
    backend_reputation._history.clear()
    backend_reputation._cooldowns.clear()


def test_record_failure_notifies_health_transition(monkeypatch):
    calls = []

    def notify_health_change(backend, old, new):
        calls.append((backend, old, new))

    monkeypatch.setitem(
        sys.modules,
        "telegram_notify",
        SimpleNamespace(notify_health_change=notify_health_change),
    )

    health_tracker.record_failure("unit_backend", error_code=429, error_text="rate limit")

    assert calls == [("unit_backend", "healthy", "degraded")]


def test_record_failure_feeds_classified_reputation():
    health_tracker.record_failure("auth_backend", error_code=401, error_text="unauthorized")

    assert backend_reputation.get_score("auth_backend") == 20
    assert backend_reputation.is_reputation_cooled("auth_backend") is True
