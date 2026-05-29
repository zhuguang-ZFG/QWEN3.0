"""Tests for telegram_outbound (TG-GH-1)."""

from __future__ import annotations

from unittest.mock import MagicMock

import httpx

import telegram_outbound as outbound


def test_check_getme_success_on_second_proxy(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:test")
    calls: list[str | None] = []

    class FakeClient:
        def __init__(self, *, proxy=None, timeout=15.0, follow_redirects=True):
            calls.append(proxy)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, url):
            if calls[-1] is not None:
                raise httpx.ConnectError("proxy down", request=MagicMock())
            response = MagicMock()
            response.status_code = 200
            response.json.return_value = {"ok": True, "result": {"username": "lima_bot"}}
            return response

    ok, detail = outbound.check_telegram_getme(client_factory=FakeClient)
    assert ok is True
    assert "@lima_bot" in detail
    assert calls == ["http://127.0.0.1:7897", None]


def test_check_getme_missing_token(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    ok, detail = outbound.check_telegram_getme(token="")
    assert ok is False
    assert "TOKEN" in detail


def test_smoke_script_dry_run():
    import subprocess
    import sys

    proc = subprocess.run(
        [sys.executable, "scripts/smoke_telegram_outbound.py", "--dry-run"],
        text=True,
        capture_output=True,
        check=True,
    )
    assert "proxies=" in proc.stdout
