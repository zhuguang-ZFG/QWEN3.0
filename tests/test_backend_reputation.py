"""Tests for backend_reputation.py — failure classification integration."""
import backend_reputation


def setup_function():
    # Reset module state for clean tests
    backend_reputation._scores.clear()
    backend_reputation._history.clear()
    backend_reputation._cooldowns.clear()


# ── Basic scoring ──────────────────────────────────────────────────────────────

def test_initial_score():
    assert backend_reputation.get_score("any_backend") == 70


def test_success_increases_score():
    backend_reputation.record("test", True, "code")
    assert backend_reputation.get_score("test") == 72


def test_failure_decreases_score():
    backend_reputation.record("test", False, "code")
    assert backend_reputation.get_score("test") == 60


def test_consecutive_failures_trigger_cooldown():
    for _ in range(3):
        backend_reputation.record("bad", False, "code")
    assert backend_reputation.is_reputation_cooled("bad") is True


def test_cooldown_backend_removed_from_sort():
    backend_reputation.record("cooling", False, "code")
    backend_reputation.record("cooling", False, "code")
    backend_reputation.record("cooling", False, "code")

    pool = ["cooling", "good"]
    # Mark good as high score
    backend_reputation._scores["good"] = 90
    result = backend_reputation.sort_by_reputation(pool)
    assert "cooling" not in result
    assert "good" in result


# ── Failure class penalties ───────────────────────────────────────────────────

def test_auth_failure_heavy_penalty():
    backend_reputation.record_failure_class("auth_test", "auth_expired")
    score = backend_reputation.get_score("auth_test")
    # PENALTY=10 * multiplier=5.0 = 50
    assert score == 20, f"Auth failure should drop from 70 to 20, got {score}"


def test_rate_limit_moderate_penalty():
    backend_reputation.record_failure_class("ratelimit_test", "rate_limited")
    score = backend_reputation.get_score("ratelimit_test")
    # PENALTY=10 * multiplier=1.5 = 15
    assert score == 55, f"Rate limit should drop from 70 to 55, got {score}"


def test_network_error_light_penalty():
    backend_reputation.record_failure_class("net_test", "network_error")
    score = backend_reputation.get_score("net_test")
    # PENALTY=10 * multiplier=0.3 = 3
    assert score == 67, f"Network error should drop from 70 to 67, got {score}"


def test_malformed_response_moderate_penalty():
    backend_reputation.record_failure_class("malform_test", "malformed_response")
    score = backend_reputation.get_score("malform_test")
    # PENALTY=10 * multiplier=0.5 = 5
    assert score == 65, f"Malformed response should drop from 70 to 65, got {score}"


def test_auth_failure_triggers_cooldown():
    backend_reputation.record_failure_class("auth_cooldown", "auth_expired")
    assert backend_reputation.is_reputation_cooled("auth_cooldown") is True


def test_network_error_does_not_trigger_cooldown():
    backend_reputation.record_failure_class("net_ok", "network_error")
    assert backend_reputation.is_reputation_cooled("net_ok") is False


# ── Sort by reputation ─────────────────────────────────────────────────────────

def test_sort_by_reputation_ranks_higher_first():
    backend_reputation._scores = {"A": 90, "B": 50, "C": 75}
    pool = ["B", "A", "C"]
    result = backend_reputation.sort_by_reputation(pool)
    assert result == ["A", "C", "B"]


# ── get_stats ──────────────────────────────────────────────────────────────────

def test_get_stats_returns_dict():
    backend_reputation.record("stats_test", True)
    stats = backend_reputation.get_stats()
    assert "scores" in stats
    assert "cooldowns" in stats
    assert stats["scores"]["stats_test"] == 72
