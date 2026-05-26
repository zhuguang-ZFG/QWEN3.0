"""Tests for unified Telegram digest (TG-GH-3)."""

from __future__ import annotations

from unittest.mock import patch

import webhook_activity_buffer as buf
from telegram_digest import build_unified_digest_text


def test_build_unified_digest_includes_git_activity(tmp_path, monkeypatch):
    monkeypatch.setenv("LIMA_DATA_DIR", str(tmp_path))
    buf.reset_for_tests()
    buf.record_webhook_event(source="github", kind="push", repo="o/r")
    buf.record_webhook_event(source="gitee", kind="push", repo="zhuguang-cn/QWEN3.0")

    text = build_unified_digest_text()
    assert "LiMa Daily" in text
    assert "GitHub 24h: 1 push" in text
    assert "Gitee 24h: 1 push" in text
    assert "Tasks:" in text


def test_format_activity_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("LIMA_DATA_DIR", str(tmp_path))
    buf.reset_for_tests()
    lines = buf.format_activity_lines()
    assert "no webhook events" in lines[0]


async def test_send_unified_digest_calls_telegram(monkeypatch, tmp_path):
    monkeypatch.setenv("LIMA_DATA_DIR", str(tmp_path))
    buf.reset_for_tests()
    with patch("telegram_bot.is_configured", return_value=True), patch(
        "telegram_bot.send_message", return_value=True
    ) as send:
        from telegram_digest import send_unified_digest

        ok = await send_unified_digest()
    assert ok is True
    send.assert_called_once()
    assert "LiMa Daily" in send.call_args.args[0]
