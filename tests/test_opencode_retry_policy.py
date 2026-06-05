"""Tests for opencode_retry_policy.py — retry decision and backoff computation."""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from opencode_retry_policy import (
    is_retryable_error,
    compute_retry_delay,
    classify_retry_error,
    RETRY_INITIAL_DELAY_MS,
    RETRY_MAX_DELAY_NO_HEADERS_MS,
)


class _FakeError(Exception):
    """Minimal exception with configurable attributes."""
    def __init__(self, msg="", status_code=None, is_overflow=False, is_retryable=False):
        super().__init__(msg)
        if status_code is not None:
            self.status_code = status_code
        self.is_overflow = is_overflow
        self.is_retryable = is_retryable


class TestIsRetryableError:
    def test_context_overflow_not_retryable(self):
        e = _FakeError("overflow", is_overflow=True)
        assert not is_retryable_error(e)

    def test_5xx_always_retryable(self):
        e = _FakeError("server error", status_code=500)
        assert is_retryable_error(e)
        e2 = _FakeError("bad gateway", status_code=502)
        assert is_retryable_error(e2)

    def test_4xx_not_retryable_by_default(self):
        e = _FakeError("bad request", status_code=400)
        assert not is_retryable_error(e)

    def test_is_retryable_marker(self):
        e = _FakeError("transient", is_retryable=True)
        assert is_retryable_error(e)

    def test_rate_limit_keyword(self):
        e = _FakeError("Rate limit exceeded")
        assert is_retryable_error(e)

    def test_too_many_requests_keyword(self):
        e = _FakeError("Too Many Requests")
        assert is_retryable_error(e)

    def test_rate_increased_too_quickly(self):
        e = _FakeError("rate increased too quickly")
        assert is_retryable_error(e)

    def test_json_too_many_requests(self):
        import json
        body = json.dumps({"type": "error", "error": {"type": "too_many_requests"}})
        e = _FakeError(body)
        assert is_retryable_error(e)

    def test_json_rate_limit_code(self):
        import json
        body = json.dumps({"type": "error", "error": {"code": "rate_limit_exceeded"}})
        e = _FakeError(body)
        assert is_retryable_error(e)

    def test_json_exhausted(self):
        import json
        body = json.dumps({"code": "RESOURCE_EXHAUSTED"})
        e = _FakeError(body)
        assert is_retryable_error(e)

    def test_normal_error_not_retryable(self):
        e = _FakeError("something went wrong")
        assert not is_retryable_error(e)


class TestComputeRetryDelay:
    def test_first_attempt_no_headers(self):
        delay = compute_retry_delay(1)
        assert delay == RETRY_INITIAL_DELAY_MS

    def test_second_attempt_no_headers(self):
        delay = compute_retry_delay(2)
        assert delay == RETRY_INITIAL_DELAY_MS * 2

    def test_third_attempt_no_headers(self):
        delay = compute_retry_delay(3)
        assert delay == RETRY_INITIAL_DELAY_MS * 4

    def test_capped_at_30s_no_headers(self):
        delay = compute_retry_delay(10)
        assert delay <= RETRY_MAX_DELAY_NO_HEADERS_MS

    def test_retry_after_ms_header(self):
        delay = compute_retry_delay(1, {"retry-after-ms": "5000"})
        assert delay == 5000

    def test_retry_after_seconds_header(self):
        delay = compute_retry_delay(1, {"retry-after": "10"})
        assert delay == 10_000

    def test_case_insensitive_headers(self):
        delay = compute_retry_delay(1, {"Retry-After-Ms": "3000"})
        assert delay == 3000


class TestClassifyRetryError:
    def test_not_retryable_returns_none(self):
        e = _FakeError("normal error")
        assert classify_retry_error(e) is None

    def test_overloaded(self):
        e = _FakeError("Overloaded", status_code=503, is_retryable=True)
        result = classify_retry_error(e)
        assert result is not None
        assert "overloaded" in result["message"].lower()

    def test_rate_limit(self):
        e = _FakeError("Rate limit exceeded")
        result = classify_retry_error(e)
        assert result is not None
        assert "message" in result
