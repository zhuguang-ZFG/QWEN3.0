"""Tests for chat preflight device prompt integration."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from routes.chat_preflight import prepare_chat_preflight


def _make_req(content: str):
    return SimpleNamespace(messages=[SimpleNamespace(role="user", content=content)])


@patch("routes.chat_preflight.build_prompt_context")
def test_prepare_chat_preflight_merges_device_control_prompt(mock_build_ctx):
    mock_build_ctx.return_value = SimpleNamespace(
        request_messages=[{"role": "user", "content": "急停"}],
        prompt_context_messages=[],
        system_prompt="",
        memory_recall_meta={},
        memory_session_id=None,
    )

    result = prepare_chat_preflight(_make_req("急停"), ide_source="", sys_prompt_preview="")

    assert "设备控制助手" in result.system_prompt
    assert result.prompt_context_messages[0]["role"] == "system"
    assert "设备控制助手" in result.prompt_context_messages[0]["content"]
