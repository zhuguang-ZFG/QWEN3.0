"""P0: token_sync only accepts overrides after explicit 2xx validation success."""

from __future__ import annotations

import io
import json
import urllib.error
import urllib.request
from unittest.mock import MagicMock

import pytest

from routes import token_sync


def _ok_response(content: str = "hi"):
    payload = json.dumps(
        {
            "choices": [{"message": {"content": content}}],
        }
    ).encode()
    resp = MagicMock()
    resp.status = 200
    resp.read.return_value = payload
    resp.__enter__ = lambda self: self
    resp.__exit__ = lambda *args: None
    return resp


@pytest.mark.parametrize("status", [401, 403, 429, 500])
def test_validate_token_rejects_http_errors(monkeypatch, status):
    def _raise_http_error(*args, **kwargs):
        raise urllib.error.HTTPError(
            url="https://example.com",
            code=status,
            msg="error",
            hdrs=None,
            fp=io.BytesIO(b""),
        )

    monkeypatch.setattr(urllib.request, "urlopen", _raise_http_error)

    assert token_sync._validate_token("longcat", "bad-key", "https://example.com", "model") is False


def test_validate_token_accepts_successful_response(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: _ok_response("ok"))

    assert token_sync._validate_token("longcat", "good-key", "https://example.com", "model") is True


def test_validate_token_rejects_empty_content(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: _ok_response(""))

    assert token_sync._validate_token("longcat", "good-key", "https://example.com", "model") is False


def test_validate_token_rejects_network_errors(monkeypatch):
    def _fail(*args, **kwargs):
        raise TimeoutError("timeout")

    monkeypatch.setattr(urllib.request, "urlopen", _fail)

    assert token_sync._validate_token("longcat", "good-key", "https://example.com", "model") is False
