"""Tests for HTTP backend URL scheme enforcement (P2-16/P2-17)."""

from __future__ import annotations

import pytest

import http_async
import http_stream
import http_sync
from http_errors import BackendError
from http_sync import _enforce_https_scheme


@pytest.fixture
def clear_allow_http(monkeypatch):
    monkeypatch.setattr("http_sync.FLAGS.allow_http_backends", False)


@pytest.fixture
def allow_http(monkeypatch):
    monkeypatch.setattr("http_sync.FLAGS.allow_http_backends", True)


@pytest.fixture
def http_backend():
    return {
        "url": "http://public.example.com/v1/chat/completions",
        "fmt": "openai",
        "timeout": 5,
    }


@pytest.fixture
def patched_caller_deps(monkeypatch):
    """Patch http_caller helpers so scheme enforcement is the first real check."""
    monkeypatch.setattr("http_caller._select_key", lambda backend, cfg: ("test-key", "test-pool"))
    monkeypatch.setattr("http_caller._build_headers", lambda cfg, key: {"Authorization": f"Bearer {key}"})
    monkeypatch.setattr("http_caller._build_body", lambda *args, **kwargs: b"{}")
    monkeypatch.setattr("http_caller.health_tracker.is_cooled_down", lambda backend: False)


class TestEnforceHttpsScheme:
    def test_https_url_allowed(self, clear_allow_http):
        _enforce_https_scheme("https://example.com", "secure-backend")

    def test_http_localhost_allowed(self, clear_allow_http):
        _enforce_https_scheme("http://localhost:8080/v1", "local-backend")
        _enforce_https_scheme("http://127.0.0.1:8080/v1", "local-backend")

    def test_http_public_blocked(self, clear_allow_http):
        with pytest.raises(BackendError) as exc_info:
            _enforce_https_scheme("http://public.example.com/v1", "public-backend")
        assert "plaintext HTTP" in str(exc_info.value)
        assert exc_info.value.status_code == 400

    def test_http_allowed_when_env_set(self, allow_http, caplog):
        _enforce_https_scheme("http://public.example.com/v1", "public-backend")

    def test_non_http_url_no_op(self, clear_allow_http):
        _enforce_https_scheme("ftp://example.com", "ftp-backend")


class TestCallApiSchemeEnforcement:
    def test_call_api_blocks_http_public(
        self, clear_allow_http, monkeypatch, http_backend, patched_caller_deps
    ):
        monkeypatch.setattr(http_sync, "BACKENDS", {"http-backend": http_backend})
        with pytest.raises(BackendError) as exc_info:
            http_sync.call_api("http-backend", [{"role": "user", "content": "hi"}])
        assert "plaintext HTTP" in str(exc_info.value)

    def test_call_api_allows_https(
        self, monkeypatch, patched_caller_deps
    ):
        cfg = {
            "url": "https://example.com/v1",
            "fmt": "openai",
            "timeout": 5,
        }
        monkeypatch.setattr(http_sync, "BACKENDS", {"https-backend": cfg})
        monkeypatch.setattr(
            "http_caller._build_client",
            lambda backend, timeout: _FakeClient(),
        )
        result = http_sync.call_api("https-backend", [{"role": "user", "content": "hi"}])
        assert result == "ok"


class TestStreamSchemeEnforcement:
    def test_call_api_stream_blocks_http_public(
        self, clear_allow_http, monkeypatch, http_backend, patched_caller_deps
    ):
        monkeypatch.setattr(http_stream, "BACKENDS", {"http-backend": http_backend})
        with pytest.raises(BackendError) as exc_info:
            list(http_stream.call_api_stream("http-backend", [{"role": "user", "content": "hi"}]))
        assert "plaintext HTTP" in str(exc_info.value)


class TestAsyncSchemeEnforcement:
    async def test_call_api_async_blocks_http_public(
        self, clear_allow_http, monkeypatch, http_backend, patched_caller_deps
    ):
        monkeypatch.setattr(http_async, "BACKENDS", {"http-backend": http_backend})
        with pytest.raises(BackendError) as exc_info:
            await http_async.call_api_async("http-backend", [{"role": "user", "content": "hi"}])
        assert "plaintext HTTP" in str(exc_info.value)


class _FakeClient:
    """Minimal sync httpx client stand-in."""

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def post(self, url, *, content, headers):
        return _FakeResponse()


class _FakeResponse:
    text = '{"choices": [{"message": {"content": "ok"}}]}'

    def raise_for_status(self):
        pass

    def json(self):
        return {"choices": [{"message": {"content": "ok"}}]}
