"""Tests for config/backend_config.py — backend credential centralization (P1-2)."""

from __future__ import annotations

import pytest

from config import backend_config


@pytest.fixture(autouse=True)
def _reset_cloudflare_singleton(monkeypatch):
    """Patch the module-level CLOUDFLARE singleton for each test."""
    monkeypatch.setattr(
        backend_config,
        "CLOUDFLARE",
        backend_config.CloudflareCredentials(account_id="acct-123", token="tok-abc"),
    )


def test_cloudflare_chat_url():
    assert (
        backend_config.CLOUDFLARE.chat_url()
        == "https://api.cloudflare.com/client/v4/accounts/acct-123/ai/v1/chat/completions"
    )


def test_cloudflare_search_url():
    assert (
        backend_config.CLOUDFLARE.search_url()
        == "https://api.cloudflare.com/client/v4/accounts/acct-123/ai/models/search"
    )


def test_cloudflare_configured_true():
    assert backend_config.CLOUDFLARE.configured is True


def test_cloudflare_configured_false(monkeypatch):
    monkeypatch.setattr(
        backend_config,
        "CLOUDFLARE",
        backend_config.CloudflareCredentials(account_id="", token=""),
    )
    assert backend_config.CLOUDFLARE.configured is False


def test_cloudflare_backend_url_uses_config(monkeypatch):
    import importlib

    import backends_registry.cloudflare as cf_mod

    monkeypatch.setattr(
        backend_config,
        "CLOUDFLARE",
        backend_config.CloudflareCredentials(account_id="acct-123", token="tok-abc"),
    )
    importlib.reload(cf_mod)

    url = cf_mod.BACKENDS["cf_llama70b"]["url"]
    assert "acct-123" in url
    assert cf_mod.BACKENDS["cf_llama70b"]["key"] == "tok-abc"
