"""Tests for Telegram Bot-to-Bot ingress (TG-10.0-2)."""

import json
import os

import pytest

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-token")
os.environ.setdefault("TELEGRAM_CHAT_ID", "987654321")

import telegram_b2b
import telegram_notify


class TestTelegramB2BParse:
    def setup_method(self) -> None:
        telegram_b2b.reset_b2b_rate_limit_for_tests()

    def test_parse_valid_payload(self) -> None:
        raw = telegram_b2b.PREFIX + json.dumps(
            {"v": 1, "type": "task_needs_review", "task_id": "t1", "summary": "ok"}
        )
        payload = telegram_b2b.parse_b2b_payload(raw)
        assert payload is not None
        assert payload["type"] == "task_needs_review"

    def test_parse_rejects_invalid_version(self) -> None:
        raw = telegram_b2b.PREFIX + json.dumps({"v": 2, "type": "task_started"})
        assert telegram_b2b.parse_b2b_payload(raw) is None


class TestTelegramB2BDispatch:
    def setup_method(self) -> None:
        telegram_b2b.reset_b2b_rate_limit_for_tests()

    def test_dispatch_needs_review(self, monkeypatch) -> None:
        calls: list[tuple] = []

        def fake_ready(task_id, summary, files):
            calls.append((task_id, summary, files))

        monkeypatch.setattr(telegram_notify, "notify_task_ready", fake_ready)
        ok, detail = telegram_b2b._dispatch_event(
            {
                "v": 1,
                "type": "task_needs_review",
                "task_id": "abc",
                "summary": "review me",
                "changed_files": ["a.py"],
            }
        )
        assert ok is True
        assert detail == ""
        assert calls == [("abc", "review me", ["a.py"])]

    def test_dispatch_lifecycle(self, monkeypatch) -> None:
        calls: list[str] = []

        monkeypatch.setattr(
            telegram_notify,
            "notify_code_lifecycle",
            lambda event_type, task_id, summary, files: calls.append(event_type),
        )
        ok, _ = telegram_b2b._dispatch_event(
            {"v": 1, "type": "task_started", "task_id": "t2", "summary": "go"}
        )
        assert ok is True
        assert calls == ["task_started"]


@pytest.mark.asyncio
class TestTelegramB2BInbound:
    def setup_method(self) -> None:
        telegram_b2b.reset_b2b_rate_limit_for_tests()

    async def test_rejects_non_bot(self, monkeypatch) -> None:
        monkeypatch.setenv("TELEGRAM_B2B_ENABLED", "1")
        monkeypatch.setenv("TELEGRAM_CODE_BOT_USERNAMES", "lima_bot")
        handled, chat, ack = await telegram_b2b.handle_inbound_b2b(
            {"from": {"is_bot": False, "username": "human"}, "chat": {"id": 1}, "text": "hi"}
        )
        assert handled is False

    async def test_accepts_code_bot(self, monkeypatch) -> None:
        monkeypatch.setenv("TELEGRAM_B2B_ENABLED", "1")
        monkeypatch.setenv("TELEGRAM_CODE_BOT_USERNAMES", "lima_bot")
        monkeypatch.setattr(
            telegram_notify,
            "notify_task_ready",
            lambda *_a, **_k: None,
        )
        text = telegram_b2b.PREFIX + json.dumps(
            {
                "v": 1,
                "type": "task_needs_review",
                "task_id": "t9",
                "summary": "done",
                "changed_files": [],
            }
        )
        handled, chat, ack = await telegram_b2b.handle_inbound_b2b(
            {
                "from": {"is_bot": True, "username": "lima_bot"},
                "chat": {"id": 999},
                "text": text,
            }
        )
        assert handled is True
        assert chat == "999"
        assert "LIMA_B2B_ACK" in ack
        assert json.loads(ack.split("\n", 1)[1])["ok"] is True
