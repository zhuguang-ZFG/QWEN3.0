"""Tests for AUDIT-4-F1 client-layer transient-error retry (http_retry + http_sync/async)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

import http_caller
from http_errors import BackendError, is_retryable_error


BACKEND_CFG = {
    "url": "https://test.com/v1/chat/completions",
    "key": "sk-test",
    "model": "test-model",
    "fmt": "openai",
    "timeout": 10,
}


def _ok_response(content: str = "hello"):
    resp = MagicMock()
    resp.text = '{"choices": [{"message": {"content": "%s"}}]}' % content
    resp.json.return_value = {"choices": [{"message": {"content": content}}]}
    resp.raise_for_status.return_value = None
    return resp


def _http_status_error(code: int) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "https://test.com")
    response = httpx.Response(code, request=request)
    return httpx.HTTPStatusError(f"{code}", request=request, response=response)


# ── is_retryable_error predicate ────────────────────────────────────────────


def test_is_retryable_network_error():
    exc = httpx.ConnectError("conn refused")
    assert is_retryable_error(exc) is True


@pytest.mark.parametrize("code", [408, 429, 502, 503, 504])
def test_is_retryable_transient_status(code):
    assert is_retryable_error(_http_status_error(code)) is True


@pytest.mark.parametrize("code", [400, 401, 403, 404, 422, 500])
def test_not_retryable_status(code):
    assert is_retryable_error(_http_status_error(code)) is False


# ── sync call_api retry behaviour ───────────────────────────────────────────


class _RetryClient:
    """Sync client that fails N times then succeeds."""

    def __init__(self, fail_times: int, exc: Exception, success_content: str = "ok"):
        self.fail_times = fail_times
        self.exc = exc
        self.success_content = success_content
        self.post_calls = 0

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def post(self, *args, **kwargs):
        self.post_calls += 1
        if self.post_calls <= self.fail_times:
            raise self.exc
        return _ok_response(self.success_content)


@patch("http_caller.health_tracker")
@patch("http_caller._build_client")
def test_call_api_retries_transient_then_succeeds(mock_build_client, mock_ht):
    mock_ht.is_cooled_down.return_value = False
    client = _RetryClient(fail_times=1, exc=httpx.ConnectError("boom"))
    mock_build_client.return_value = client

    with patch.dict(http_caller.BACKENDS, {"b": dict(BACKEND_CFG)}):
        with patch("http_retry.time.sleep"):  # skip real backoff sleep
            result = http_caller.call_api("b", [{"role": "user", "content": "hi"}])

    assert result == "ok"
    assert client.post_calls == 2  # 1 fail + 1 success
    # Success after retry → record_success called, record_failure NOT called
    assert mock_ht.record_success.call_count == 1
    mock_ht.record_failure.assert_not_called()


@patch("http_caller.health_tracker")
@patch("http_caller._build_client")
def test_call_api_non_retryable_fails_immediately(mock_build_client, mock_ht):
    mock_ht.is_cooled_down.return_value = False
    client = _RetryClient(fail_times=99, exc=_http_status_error(400))
    mock_build_client.return_value = client

    with patch.dict(http_caller.BACKENDS, {"b": dict(BACKEND_CFG)}):
        with patch("http_retry.time.sleep"):
            with pytest.raises(BackendError):
                http_caller.call_api("b", [{"role": "user", "content": "hi"}])

    assert client.post_calls == 1  # no retry for 400


@patch("http_caller.health_tracker")
@patch("http_caller._build_client")
def test_call_api_retry_exhausted_records_failure_once(mock_build_client, mock_ht):
    mock_ht.is_cooled_down.return_value = False
    client = _RetryClient(fail_times=99, exc=httpx.ConnectError("always down"))
    mock_build_client.return_value = client

    # default _max_retries() == 2 → 1 initial + 2 retries = 3 attempts
    with patch.dict(http_caller.BACKENDS, {"b": dict(BACKEND_CFG)}):
        with patch("http_retry.time.sleep"):
            with pytest.raises(BackendError):
                http_caller.call_api("b", [{"role": "user", "content": "hi"}])

    assert client.post_calls == 3  # 1 initial + 2 retries
    # record_failure called exactly once (only after exhaustion, not per-retry)
    assert mock_ht.record_failure.call_count == 1
