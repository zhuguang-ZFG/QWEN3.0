"""Tests for ops Apprise alerts."""

from __future__ import annotations

from notify import ops_alerts


def test_maybe_notify_skipped_when_disabled(monkeypatch):
    monkeypatch.setattr(ops_alerts, "ops_alerts_enabled", lambda: False)
    ok, detail = ops_alerts.maybe_notify_oldllm_failure({"any_chat_ok": False})
    assert ok is False
    assert detail == "disabled"


def test_maybe_notify_skipped_when_healthy(monkeypatch):
    monkeypatch.setattr(ops_alerts, "ops_alerts_enabled", lambda: True)
    ok, detail = ops_alerts.maybe_notify_oldllm_failure({"upstream_chat_ok": True})
    assert ok is False
    assert detail == "healthy"


def test_maybe_notify_sends_on_failure(monkeypatch):
    monkeypatch.setattr(ops_alerts, "ops_alerts_enabled", lambda: True)
    monkeypatch.setattr(ops_alerts, "notify", lambda body, title="LiMa": (True, "sent"))
    ok, detail = ops_alerts.maybe_notify_oldllm_failure(
        {
            "upstream_chat_ok": False,
            "results": [{"label": "upstream", "kind": "chat", "ok": False, "status": 502}],
            "hints": ["refresh token"],
        }
    )
    assert ok is True
    assert detail == "sent"
