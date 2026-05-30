"""Tests for Telegram quick menu and shortcuts."""

from __future__ import annotations


import pytest

from routes.telegram_quick_menu import (
    COMMAND_ALIASES,
    expand_command_alias,
    handle_quick_callback,
    main_menu_keyboard,
    resolve_text_shortcut,
)


def test_expand_command_alias():
    assert expand_command_alias("/h") == "/help"
    assert expand_command_alias("/m") == "/menu"
    assert expand_command_alias("/s") == "/status"
    assert expand_command_alias("/n 头条") == "/news 头条"
    assert expand_command_alias("/status") == "/status"


def test_resolve_text_shortcut():
    assert resolve_text_shortcut("菜单") == "/menu"
    assert resolve_text_shortcut("📋 菜单") == "/menu"
    assert resolve_text_shortcut("hello") is None


def test_main_menu_keyboard_has_quick_actions():
    kb = main_menu_keyboard()["inline_keyboard"]
    callbacks = {
        btn["callback_data"]
        for row in kb
        for btn in row
    }
    assert "qm:status" in callbacks
    assert "qm:evalreport" in callbacks


@pytest.mark.asyncio
async def test_handle_quick_callback_dispatches():
    calls: list[str] = []

    async def dispatch(chat_id: str, command: str) -> None:
        calls.append(f"{chat_id}:{command}")

    ok = await handle_quick_callback("1", "qm:status", dispatch)
    assert ok is True
    assert calls == ["1:/status"]


@pytest.mark.asyncio
async def test_cmd_menu_sends_inline_keyboard(monkeypatch):
    from routes import telegram_quick_menu as mod

    api_calls: list[dict] = []

    async def fake_api(method, data):
        api_calls.append({"method": method, **data})
        return {"ok": True}

    monkeypatch.setattr(mod.telegram_bot, "_api_call", fake_api)
    await mod.cmd_menu("chat-1", with_reply_keyboard=True)
    assert api_calls
    assert api_calls[0]["reply_markup"]["inline_keyboard"]
    assert api_calls[-1]["reply_markup"]["keyboard"]


def test_aliases_cover_help_and_menu():
    assert COMMAND_ALIASES["/h"] == "/help"
    assert COMMAND_ALIASES["/m"] == "/menu"
