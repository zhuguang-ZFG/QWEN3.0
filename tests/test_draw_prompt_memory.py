"""Unit tests for device_gateway.draw_prompt_memory.

The module is a thin facade over the optional `session_memory.device_draw_memory`
package. These tests pin two contracts:

1. When session_memory is absent/raises, every function degrades loudly (logs a
   warning) and returns a safe empty value — never propagates. This is the
   intended fail-open, NOT the forbidden silent `except: pass`.
2. When session_memory is present, calls delegate with cleaned/truncated args.
3. Missing device_id short-circuits before touching the backend.
"""

from __future__ import annotations

import importlib
import logging
import sys
import types
from unittest.mock import MagicMock

import device_gateway.draw_prompt_memory as dpm


def _reload_without_session_memory() -> None:
    """Ensure session_memory is not importable for the duration of a test."""
    sys.modules.pop("session_memory", None)
    sys.modules.pop("session_memory.device_draw_memory", None)
    importlib.reload(dpm)


def _install_fake_session_memory() -> types.ModuleType:
    """Inject a fake session_memory package; return its device_draw_memory mock."""
    pkg = types.ModuleType("session_memory")
    pkg.__path__ = []  # mark as package
    draw_mem = types.ModuleType("session_memory.device_draw_memory")
    draw_mem.reset_device_draw_session = MagicMock()
    draw_mem.format_device_draw_conversation_context = MagicMock(return_value="CTX")
    draw_mem.record_device_draw_turn = MagicMock()
    draw_mem.record_device_draw_failure = MagicMock()
    draw_mem.list_device_draw_failures = MagicMock(return_value=["bad1", "bad2"])
    pkg.device_draw_memory = draw_mem
    sys.modules["session_memory"] = pkg
    sys.modules["session_memory.device_draw_memory"] = draw_mem
    importlib.reload(dpm)
    return draw_mem


def teardown_function() -> None:
    sys.modules.pop("session_memory", None)
    sys.modules.pop("session_memory.device_draw_memory", None)
    importlib.reload(dpm)


def test_get_context_degrades_to_empty_without_session_memory(caplog) -> None:
    _reload_without_session_memory()
    with caplog.at_level(logging.WARNING):
        assert dpm.get_draw_conversation_context("dev-1", "cat") == ""
    assert any("get_draw_conversation_context failed" in r.message for r in caplog.records)


def test_get_context_delegates_when_backend_present() -> None:
    draw_mem = _install_fake_session_memory()
    assert dpm.get_draw_conversation_context("dev-1", "  cat  ") == "CTX"
    draw_mem.format_device_draw_conversation_context.assert_called_once_with("dev-1", exclude_prompt="cat")


def test_get_context_short_circuits_without_device_id() -> None:
    draw_mem = _install_fake_session_memory()
    assert dpm.get_draw_conversation_context(None, "cat") == ""
    draw_mem.format_device_draw_conversation_context.assert_not_called()


def test_record_turn_degrades_without_session_memory(caplog) -> None:
    _reload_without_session_memory()
    with caplog.at_level(logging.WARNING):
        dpm.record_device_draw_turn("dev-1", "cat", status="ok")  # must not raise
    assert any("record_device_draw_turn failed" in r.message for r in caplog.records)


def test_record_turn_truncates_and_skips_empty_prompt() -> None:
    draw_mem = _install_fake_session_memory()
    long_prompt = "x" * 500
    dpm.record_device_draw_turn("dev-1", long_prompt, status="ok", error="")
    draw_mem.record_device_draw_turn.assert_called_once()
    args, kwargs = draw_mem.record_device_draw_turn.call_args
    assert args == ("dev-1", "x" * 120)  # (device_id, truncated prompt)
    assert kwargs["status"] == "ok"
    # Empty / whitespace prompt short-circuits
    draw_mem.record_device_draw_turn.reset_mock()
    dpm.record_device_draw_turn("dev-1", "   ", status="ok")
    draw_mem.record_device_draw_turn.assert_not_called()


def test_record_failed_prompt_degrades_without_session_memory(caplog) -> None:
    _reload_without_session_memory()
    with caplog.at_level(logging.WARNING):
        dpm.record_failed_draw_prompt("dev-1", "cat", error="e")  # must not raise
    assert any("record_failed_draw_prompt persistence failed" in r.message for r in caplog.records)


def test_get_failed_prompts_delegates_and_caps_limit() -> None:
    draw_mem = _install_fake_session_memory()
    assert dpm.get_failed_draw_prompts("dev-1") == ["bad1", "bad2"]
    draw_mem.list_device_draw_failures.assert_called_once_with("dev-1", limit=5)


def test_get_failed_prompts_degrades_to_empty_without_device_id() -> None:
    _install_fake_session_memory()
    assert dpm.get_failed_draw_prompts(None) == []


def test_reset_history_degrades_without_session_memory(caplog) -> None:
    _reload_without_session_memory()
    with caplog.at_level(logging.INFO):  # reset uses info, not warning
        dpm.reset_draw_prompt_history_for_tests("dev-1")  # must not raise
