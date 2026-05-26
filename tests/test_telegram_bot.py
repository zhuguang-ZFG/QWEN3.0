"""Tests for telegram_bot, telegram_notify, and routes/telegram."""

import asyncio
import os
import time
from unittest.mock import AsyncMock, patch, MagicMock

import httpx
import pytest

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-token-123")
os.environ.setdefault("TELEGRAM_CHAT_ID", "987654321")

import telegram_bot
import telegram_notify
import routes.telegram_commands as telegram_commands


class TestTelegramBot:
    def test_is_configured_with_env(self):
        assert telegram_bot.is_configured()

    def test_is_authorized_matching(self):
        assert telegram_bot.is_authorized("987654321")
        assert telegram_bot.is_authorized(987654321)

    def test_is_authorized_mismatch(self):
        assert not telegram_bot.is_authorized("111111")

    @pytest.mark.asyncio
    async def test_api_call_falls_back_to_direct_when_proxy_fails(self, monkeypatch):
        monkeypatch.setenv("GFW_PROXY", "http://127.0.0.1:9")
        calls: list[str | None] = []

        class FakeClient:
            def __init__(self, *, proxy=None, timeout=10.0):
                calls.append(proxy)

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return False

            async def post(self, url, json=None):
                if calls[-1] is not None:
                    raise httpx.ConnectError("proxy refused", request=MagicMock())
                response = MagicMock()
                response.json.return_value = {"ok": True}
                response.raise_for_status.return_value = None
                return response

        monkeypatch.setattr(telegram_bot.httpx, "AsyncClient", FakeClient)
        result = await telegram_bot._api_call("getMe", {})
        assert result == {"ok": True}
        assert calls == ["http://127.0.0.1:9", None]

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
                assert mock_ff.call_args.args[0] is telegram_bot.send_alert

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
                assert mock_ff.call_args.args[0] is telegram_bot.send_alert

    def test_notify_health_degraded_from_degraded_ignored(self):
        with patch.object(telegram_bot, "is_configured", return_value=True):
            with patch.object(telegram_notify, "_fire_and_forget") as mock_ff:
                telegram_notify.notify_health_change("x", "degraded", "degraded")
                mock_ff.assert_not_called()

    def test_notify_task_ready(self):
        with patch.object(telegram_bot, "is_configured", return_value=True):
            with patch.object(telegram_notify, "_fire_and_forget") as mock_ff:
                telegram_notify.notify_task_ready("t1", "Fix", ["a.py"])
                mock_ff.assert_called_once_with(
                    telegram_bot.send_approval,
                    "t1",
                    "Fix",
                    ["a.py"],
                )

    def test_not_configured_skips(self):
        with patch.object(telegram_bot, "is_configured", return_value=False):
            with patch.object(telegram_notify, "_fire_and_forget") as mock_ff:
                telegram_notify.notify_health_change("x", "healthy", "dead")
                mock_ff.assert_not_called()


class TestTelegramOptionalLocalTools:
    @pytest.mark.asyncio
    async def test_cmd_chat_falls_back_when_fc_caller_is_unavailable(self, monkeypatch):
        sent = []

        async def fake_send_message(text, chat_id=None, **_kwargs):
            sent.append((text, chat_id))
            return True

        monkeypatch.setenv("TELEGRAM_STREAM_CHAT", "0")
        monkeypatch.setattr(telegram_commands, "_optional_import", lambda _name: None)
        monkeypatch.setattr(telegram_commands.telegram_bot, "send_message", fake_send_message)
        monkeypatch.setattr(
            telegram_commands.routing_engine,
            "route",
            lambda **_kwargs: {"answer": "fallback answer"},
        )

        await telegram_commands.cmd_chat("chat-1", "天气怎么样")

        assert sent[-1] == ("fallback answer", "chat-1")

    @pytest.mark.asyncio
    async def test_cmd_voice_reports_missing_tts_backend(self, monkeypatch):
        sent = []

        async def fake_send_message(text, chat_id=None, **_kwargs):
            sent.append((text, chat_id))
            return True

        monkeypatch.setattr(telegram_commands, "_optional_import", lambda _name: None)
        monkeypatch.setattr(telegram_commands.telegram_bot, "send_message", fake_send_message)

        await telegram_commands.cmd_voice("chat-1", "hello")

        assert sent[-1] == ("Voice backend not available", "chat-1")
