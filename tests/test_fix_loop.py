from __future__ import annotations

import pytest

import fix_loop

pytestmark = pytest.mark.asyncio


async def test_fix_loop_rejects_unsafe_test_command(monkeypatch) -> None:
    monkeypatch.setattr("checkpoint.checkpoint_files", lambda files, reason: None)

    async def prompt_fn(messages):
        return {"ok": True, "content": ""}

    result = await fix_loop.fix_loop(
        "pytest -q; whoami",
        ["README.md"],
        prompt_fn,
        lambda name, args: "",
        max_rounds=1,
    )

    assert result["ok"] is False
    assert "unsafe test command rejected" in result["error"]
