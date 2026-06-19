import rate_limiter


def test_rate_limiter_rejects_after_window_limit(monkeypatch):
    now = 1000.0
    monkeypatch.setattr(rate_limiter.time, "time", lambda: now)
    monkeypatch.setattr(rate_limiter, "MAX_PER_WINDOW", 2)
    rate_limiter.reset()

    assert rate_limiter.check_rate_limit("203.0.113.1") is True
    assert rate_limiter.check_rate_limit("203.0.113.1") is True
    assert rate_limiter.check_rate_limit("203.0.113.1") is False


def test_rate_limiter_multiplier_scales_limit(monkeypatch):
    now = 1000.0
    monkeypatch.setattr(rate_limiter.time, "time", lambda: now)
    monkeypatch.setattr(rate_limiter, "MAX_PER_WINDOW", 2)
    rate_limiter.reset()

    for _ in range(10):
        assert rate_limiter.check_rate_limit("203.0.113.2", multiplier=5) is True
    assert rate_limiter.check_rate_limit("203.0.113.2", multiplier=5) is False
