from __future__ import annotations

import pytest

from routes import telegram_code_tools

pytestmark = pytest.mark.asyncio


async def test_code_test_rejects_shell_metacharacters(monkeypatch) -> None:
    sent: list[str] = []
    prompts: list[str] = []

    async def fake_send_message(text: str, **kwargs) -> None:
        sent.append(text)

    async def fake_call_llm(prompt: str, system: str = "", max_tokens: int = 4096) -> str:
        prompts.append(prompt)
        return "analysis"

    monkeypatch.setattr(telegram_code_tools.telegram_bot, "send_message", fake_send_message)
    monkeypatch.setattr(telegram_code_tools, "_call_llm", fake_call_llm)

    await telegram_code_tools._handle_code_test("chat-1", "pytest -q; whoami")

    assert any("Running test command" in item for item in sent)
    assert "unsafe command rejected" in prompts[0]


async def test_code_review_uses_fixed_git_command(monkeypatch) -> None:
    calls: list[list[str]] = []

    class Result:
        stdout = "diff --git a/a b/a\n"
        stderr = ""

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return Result()

    async def fake_send_message(text: str, **kwargs) -> None:
        return None

    async def fake_call_llm(prompt: str, system: str = "", max_tokens: int = 4096) -> str:
        return "review"

    monkeypatch.setattr(telegram_code_tools.subprocess, "run", fake_run)
    monkeypatch.setattr(telegram_code_tools.telegram_bot, "send_message", fake_send_message)
    monkeypatch.setattr(telegram_code_tools, "_call_llm", fake_call_llm)

    await telegram_code_tools._handle_code_review("chat-1", "")

    assert calls == [["git", "diff"], ["git", "diff", "--stat"]]
