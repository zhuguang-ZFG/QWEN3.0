"""Tests for web browsing tools (Phase 2.1)."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lima_fc_tools.web_tools import _browse_webpage, _clean_text, _fetch_url


def test_clean_text_collapses_whitespace():
    assert _clean_text("  hello   world  ") == "hello world"


def test_clean_text_truncates():
    long = "a" * 5000
    result = _clean_text(long, 100)
    assert len(result) == 100 + len("...")
    assert result.endswith("...")


@pytest.mark.asyncio
async def test_browse_webpage_returns_error_on_bad_url():
    result = await _browse_webpage("http://localhost:19999/nonexistent")
    assert "error" in result


@pytest.mark.asyncio
async def test_fetch_url_returns_error_on_bad_url():
    result = await _fetch_url("http://localhost:19999/nonexistent")
    assert isinstance(result, dict)
    assert "error" in result


@pytest.mark.asyncio
async def test_browse_webpage_parses_html():
    """Test HTML parsing with inline mock HTML via monkeypatch."""

    class FakeResponse:
        status_code = 200
        headers = {"content-type": "text/html"}
        text = "<html><head><title>Test Page</title></head><body><p>Hello World</p><a href='https://example.com'>Example</a></body></html>"

        def raise_for_status(self):
            pass

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def get(self, url, headers=None, timeout=None):
            return FakeResponse()

    # Patch httpx.AsyncClient at module level so the import inside _browse_webpage sees it
    import httpx as _httpx_mod
    original_client = _httpx_mod.AsyncClient
    _httpx_mod.AsyncClient = FakeClient
    try:
        result = await _browse_webpage("http://example.com")
        assert result["title"] == "Test Page"
        assert "Hello World" in result["text"]
        assert len(result["links"]) >= 1
        assert result["links"][0]["href"] == "https://example.com"
    finally:
        _httpx_mod.AsyncClient = original_client
