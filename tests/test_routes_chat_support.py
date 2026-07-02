"""Tests for routes/chat_support.py."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from routes import chat_support as cs


@pytest.fixture(autouse=True)
def _reset_backends():
    with patch.object(cs, "BACKENDS", {"longcat_thinking": {"key": "k"}, "groq": {"key": "k"}}):
        yield


@patch.object(cs.health_tracker, "is_cooled_down", return_value=False)
@patch.object(cs, "_call_thinking_backend", return_value="thought")
@pytest.mark.asyncio
async def test_thinking_route_returns_result(mock_call, mock_cool):
    result = await cs.thinking_route("solve this", max_tokens=100, ide="vscode")
    assert result is not None
    assert result["answer"] == "thought"
    assert result["thinking_mode"] is True


@patch.object(cs.health_tracker, "is_cooled_down", return_value=False)
@patch.object(cs, "_call_thinking_backend", return_value=None)
@pytest.mark.asyncio
async def test_thinking_route_returns_none_when_all_fail(mock_call, mock_cool):
    result = await cs.thinking_route("solve this")
    assert result is None


def test_attach_memory_recall_meta_adds_meta():
    response = {"choices": []}
    meta = {"checked": True, "backend": "groq"}
    result = cs.attach_memory_recall_meta(response, meta)
    assert result["x_lima_meta"]["memory_recall"] == meta


def test_attach_memory_recall_meta_unchecked():
    response = {"choices": []}
    result = cs.attach_memory_recall_meta(response, {"checked": False})
    assert "x_lima_meta" not in result
