"""Tests for Apprise notify bridge."""

from __future__ import annotations

import notify.apprise_bridge as mod


def test_apprise_urls_split(monkeypatch):
    monkeypatch.setenv(
        "LIMA_APPRISE_URLS",
        "ntfy://a@ntfy.sh, tgram://token/chat",
    )
    urls = mod.apprise_urls()
    assert len(urls) == 2
    assert urls[0].startswith("ntfy://")


def test_notify_no_urls():
    ok, detail = mod.notify("hello", urls=[])
    assert not ok
    assert detail == "no_urls"


def test_notify_import_error(monkeypatch):
    import builtins

    real = builtins.__import__

    def blocked(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "apprise":
            raise ImportError("blocked")
        return real(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", blocked)
    ok, detail = mod.notify("x", urls=["ntfy://a@b"])
    assert not ok
    assert detail == "apprise_not_installed"
