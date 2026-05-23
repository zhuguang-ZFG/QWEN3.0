"""Tests for telegram_bot, telegram_notify, and routes/telegram."""

import asyncio
import os
import time
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-token-123")
os.environ.setdefault("TELEGRAM_CHAT_ID", "987654321")

import telegram_bot
import telegram_notify


class TestTelegramBot:
    def test_is_configured_with_env(self):
        assert telegram_bot.is_configured()

    def test_is_authorized_matching(self):
        assert telegram_bot.is_authorized("987654321")
        assert telegram_bot.is_authorized(987654321)

    def test_is_authorized_mismatch(self):
        assert not telegram_bot.is_authorized("111111")

    @pytest.mark.asyncio
    async def test_send_message_calls_api(self):
        with patch.object(telegram_bot, "_api_call", new_callable=AsyncMock) as mock:
            mock.return_value = {"ok": True}
            result = await telegram_bot.send_message("hello")
            assert result is True
            mock.assert_called_once()
            args = mock.call_args[0]
            assert args[0] == "sendMessage"
            assert args[1]["text"] == "hello"
            assert args[1]["chat_id"] == "987654321"

    @pytest.mark.asyncio
    async def test_send_approval_builds_keyboard(self):
        with patch.object(telegram_bot, "_api_call", new_callable=AsyncMock) as mock:
            mock.return_value = {"ok": True}
            await telegram_bot.send_approval("abc123", "Fix bug", ["a.py"])
            data = mock.call_args[0][1]
            kb = data["reply_markup"]["inline_keyboard"][0]
            assert kb[0]["callback_data"] == "approve:abc123"
            assert kb[1]["callback_data"] == "reject:abc123"

    def test_parse_approval_callback_accepts_approve_and_reject(self):
        assert telegram_bot.parse_approval_callback("approve:abc123") == {
            "ok": True,
            "decision": "approved",
            "task_id": "abc123",
        }
        assert telegram_bot.parse_approval_callback("reject:abc123") == {
            "ok": True,
            "decision": "rejected",
            "task_id": "abc123",
        }

    def test_parse_approval_callback_rejects_unknown_payloads(self):
        assert telegram_bot.parse_approval_callback("delete:abc123")["ok"] is False
        assert telegram_bot.parse_approval_callback("approve:")["ok"] is False
        assert telegram_bot.parse_approval_callback("")["ok"] is False

    @pytest.mark.asyncio
    async def test_send_alert_prepends_emoji(self):
        with patch.object(telegram_bot, "_api_call", new_callable=AsyncMock) as mock:
            mock.return_value = {"ok": True}
            await telegram_bot.send_alert("critical", "Backend down")
            text = mock.call_args[0][1]["text"]
            assert text.startswith("\U0001f534")


class TestTelegramNotify:
    def test_notify_health_dead_fires(self):
        telegram_notify._health_last_notified.clear()
        with patch.object(telegram_bot, "is_configured", return_value=True):
            with patch.object(telegram_notify, "_fire_and_forget") as mock_ff:
                telegram_notify.notify_health_change("test_be", "healthy", "dead")
                mock_ff.assert_called_once()

    def test_notify_health_rate_limited(self):
        telegram_notify._health_last_notified.clear()
        telegram_notify._health_last_notified["test_be"] = time.time()
        with patch.object(telegram_bot, "is_configured", return_value=True):
            with patch.object(telegram_notify, "_fire_and_forget") as mock_ff:
                telegram_notify.notify_health_change("test_be", "healthy", "dead")
                mock_ff.assert_not_called()

    def test_notify_health_degraded_from_healthy(self):
        telegram_notify._health_last_notified.clear()
        with patch.object(telegram_bot, "is_configured", return_value=True):
            with patch.object(telegram_notify, "_fire_and_forget") as mock_ff:
                telegram_notify.notify_health_change("x", "healthy", "degraded")
                mock_ff.assert_called_once()

    def test_notify_health_degraded_from_degraded_ignored(self):
        with patch.object(telegram_bot, "is_configured", return_value=True):
            with patch.object(telegram_notify, "_fire_and_forget") as mock_ff:
                telegram_notify.notify_health_change("x", "degraded", "degraded")
                mock_ff.assert_not_called()

    def test_notify_task_ready(self):
        with patch.object(telegram_bot, "is_configured", return_value=True):
            with patch.object(telegram_notify, "_fire_and_forget") as mock_ff:
                telegram_notify.notify_task_ready("t1", "Fix", ["a.py"])
                mock_ff.assert_called_once()

    def test_not_configured_skips(self):
        with patch.object(telegram_bot, "is_configured", return_value=False):
            with patch.object(telegram_notify, "_fire_and_forget") as mock_ff:
                telegram_notify.notify_health_change("x", "healthy", "dead")
                mock_ff.assert_not_called()
