"""Tests for Telegram command dispatch cleanup behavior."""

from __future__ import annotations

import pytest

from routes import telegram_dispatch as mod


async def _noop_status(chat_id: str) -> None:
    return None


async def _noop_health(chat_id: str, arg: str) -> None:
    return None


async def _noop_budget(chat_id: str) -> None:
    return None


async def _noop_logs(chat_id: str, arg: str) -> None:
    return None


async def _noop_restart(chat_id: str) -> None:
    return None


@pytest.mark.asyncio
async def test_unknown_command_reports_failure_once_and_shows_menu(monkeypatch):
    sent: list[dict] = []
    menus: list[tuple[str, bool]] = []
    outcomes: list[tuple[str, str, bool]] = []

    async def fake_send_message(text, *, chat_id=None, parse_mode=None):
        sent.append({"text": text, "chat_id": chat_id, "parse_mode": parse_mode})

    async def fake_menu(chat_id, *, with_reply_keyboard=False):
        menus.append((chat_id, with_reply_keyboard))

    def fake_record(cmd, chat_id, ok):
        outcomes.append((cmd, chat_id, ok))

    monkeypatch.setattr(mod.telegram_bot, "send_message", fake_send_message)
    monkeypatch.setattr(mod, "cmd_menu", fake_menu)
    monkeypatch.setattr(mod, "_record_command_outcome", fake_record)

    await mod.dispatch_command(
        "chat-1",
        "/doesnotexist",
        status_fn=_noop_status,
        health_fn=_noop_health,
        budget_fn=_noop_budget,
        logs_fn=_noop_logs,
        restart_fn=_noop_restart,
    )

    assert sent == [{"text": "Unknown command", "chat_id": "chat-1", "parse_mode": None}]
    assert menus == [("chat-1", True)]
    assert outcomes == [("/doesnotexist", "chat-1", False)]


@pytest.mark.asyncio
async def test_handler_exception_is_not_swallowed_by_menu_cleanup(monkeypatch):
    menus: list[tuple[str, bool]] = []
    outcomes: list[tuple[str, str, bool]] = []

    async def fake_send_message(*args, **kwargs):
        return None

    async def fake_menu(chat_id, *, with_reply_keyboard=False):
        menus.append((chat_id, with_reply_keyboard))

    async def failing_status(chat_id: str) -> None:
        raise RuntimeError("status failed")

    def fake_record(cmd, chat_id, ok):
        outcomes.append((cmd, chat_id, ok))

    monkeypatch.setattr(mod.telegram_bot, "send_message", fake_send_message)
    monkeypatch.setattr(mod, "cmd_menu", fake_menu)
    monkeypatch.setattr(mod, "_record_command_outcome", fake_record)

    with pytest.raises(RuntimeError, match="status failed"):
        await mod.dispatch_command(
            "chat-1",
            "/status",
            status_fn=failing_status,
            health_fn=_noop_health,
            budget_fn=_noop_budget,
            logs_fn=_noop_logs,
            restart_fn=_noop_restart,
        )

    assert menus == [("chat-1", True)]
    assert outcomes == [("/status", "chat-1", False)]
