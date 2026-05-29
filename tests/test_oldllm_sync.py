"""Tests for TheOldLLM token sync helpers."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import oldllm_sync


def test_trigger_refresh_url_ok():
    payload = json.dumps({"ok": True, "token_present": True}).encode()
    resp = MagicMock()
    resp.status = 200
    resp.read.return_value = payload
    resp.__enter__.return_value = resp
    resp.__exit__.return_value = False
    with patch("oldllm_sync.urllib.request.urlopen", return_value=resp):
        result = oldllm_sync.trigger_refresh_url("http://127.0.0.1:4501")
    assert result["ok"] is True
    assert result["method"] == "refresh_url"


def test_try_sync_uses_refresh_url_first(monkeypatch):
    monkeypatch.setattr(oldllm_sync, "DEFAULT_REFRESH_URL", "http://tunnel.test")
    monkeypatch.setattr(
        oldllm_sync,
        "trigger_refresh_url",
        lambda url="": {"ok": True, "method": "refresh_url"},
    )
    called = {"local": False}

    def _local(**kwargs):
        called["local"] = True
        return {"ok": True, "method": "local_sync"}

    monkeypatch.setattr(oldllm_sync, "run_local_sync", _local)
    result = oldllm_sync.try_sync()
    assert result["ok"] is True
    assert called["local"] is False


def test_format_sync_result_includes_hint():
    text = oldllm_sync.format_sync_result(
        {"ok": False, "attempts": [{"ok": False, "method": "refresh_url", "status": 500}], "hint": "retry"}
    )
    assert "FAIL" in text
    assert "retry" in text
