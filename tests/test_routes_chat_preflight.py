"""Tests for routes/chat_preflight.py."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from chat_models import ChatRequest, Message
from routes import chat_preflight


def _req(messages=None) -> ChatRequest:
    return ChatRequest(messages=messages or [Message(role="user", content="hello")])


@patch("routes.chat_preflight.should_skip_context_pipeline", return_value=False)
@patch("context_pipeline.guardrails.run_input_guardrails")
@patch("context_pipeline.guardrails.GuardrailSeverity")
def test_run_input_guardrails_passes(mock_severity, mock_run, mock_skip):
    mock_run.return_value = SimpleNamespace(passed=True, severity=None, violations=[])
    chat_preflight.run_input_guardrails(_req())
    mock_run.assert_called_once()


@patch("routes.chat_preflight.should_skip_context_pipeline", return_value=False)
@patch("context_pipeline.guardrails.run_input_guardrails")
@patch("context_pipeline.guardrails.GuardrailSeverity")
def test_run_input_guardrails_blocks(mock_severity, mock_run, mock_skip):
    mock_severity.BLOCK = "block"
    mock_run.return_value = SimpleNamespace(passed=False, severity="block", violations=["bad"])
    with pytest.raises(HTTPException) as exc_info:
        chat_preflight.run_input_guardrails(_req())
    assert exc_info.value.status_code == 422


@patch("routes.chat_preflight.should_skip_context_pipeline", return_value=True)
def test_run_input_guardrails_skips_device_mode(mock_skip):
    # Should not import or call guardrails when device mode is active.
    chat_preflight.run_input_guardrails(_req())


@patch("routes.chat_preflight.should_skip_context_pipeline", return_value=False)
@patch("context_pipeline.token_budget.check_budget")
def test_apply_token_budget_truncates(mock_check, mock_skip):
    mock_check.return_value = {"within_budget": False, "action": "truncate_context"}
    messages = [{"role": "user", "content": f"msg-{i}"} for i in range(12)]
    req = ChatRequest(messages=[Message(role="user", content=f"msg-{i}") for i in range(12)])
    request_messages, prompt_messages = chat_preflight.apply_token_budget(req, messages, "sys", "coding")
    assert len(req.messages) == 10
    assert request_messages[0] == messages[0]


@patch("routes.chat_preflight.should_skip_context_pipeline", return_value=True)
def test_apply_token_budget_skips_device_mode(mock_skip):
    messages = [{"role": "user", "content": "hi"}]
    req = _req()
    request_messages, prompt_messages = chat_preflight.apply_token_budget(req, messages, "sys", "")
    assert request_messages is messages


def test_adapt_identity_prompt_changes_system_prompt(monkeypatch):
    import user_identity.adapter

    monkeypatch.setattr(user_identity.adapter, "adapt_system_prompt", lambda sp, ip: "adapted", raising=False)
    system_prompt, prompt_messages = chat_preflight.adapt_identity_prompt(
        "sys", "1.2.3.4", [{"role": "user", "content": "hi"}]
    )
    assert system_prompt == "adapted"
    assert prompt_messages[0]["content"] == "adapted"


def test_adapt_identity_prompt_unchanged(monkeypatch):
    import user_identity.adapter

    monkeypatch.setattr(user_identity.adapter, "adapt_system_prompt", lambda sp, ip: sp, raising=False)
    system_prompt, prompt_messages = chat_preflight.adapt_identity_prompt(
        "sys", "1.2.3.4", [{"role": "user", "content": "hi"}]
    )
    assert system_prompt == "sys"


def test_prepare_chat_preflight_success():
    prompt_ctx = SimpleNamespace(
        request_messages=[{"role": "user", "content": "hi"}],
        prompt_context_messages=[{"role": "user", "content": "hi"}],
        system_prompt="sys",
        memory_recall_meta={"checked": True},
        memory_session_id="sess-1",
    )
    with (
        patch("routes.chat_preflight.build_prompt_context", return_value=prompt_ctx),
        patch("routes.chat_preflight.run_input_guardrails") as mock_guardrails,
        patch(
            "routes.chat_preflight.apply_token_budget",
            return_value=(prompt_ctx.request_messages, prompt_ctx.prompt_context_messages),
        ) as mock_budget,
        patch(
            "routes.chat_preflight.adapt_identity_prompt",
            return_value=("adapted", [{"role": "system", "content": "adapted"}, {"role": "user", "content": "hi"}]),
        ) as mock_identity,
        patch("routes.chat_preflight.merge_device_intent_system_prompt", return_value="merged") as mock_merge,
    ):
        req = _req()
        result = chat_preflight.prepare_chat_preflight(
            req,
            client_ip="1.2.3.4",
            ide_source="test",
            sys_prompt_preview="preview",
            request_headers={},
            trace=None,
        )
        assert result.system_prompt == "adapted"
        assert result.memory_session_id == "sess-1"
        assert result.request_messages[0]["role"] == "user"
        mock_guardrails.assert_called_once_with(req)
        mock_budget.assert_called_once()
        mock_identity.assert_called_once()


def test_prepare_chat_preflight_import_error_paths():
    prompt_ctx = SimpleNamespace(
        request_messages=[{"role": "user", "content": "hi"}],
        prompt_context_messages=[{"role": "user", "content": "hi"}],
        system_prompt="sys",
        memory_recall_meta={},
        memory_session_id=None,
    )
    with (
        patch("routes.chat_preflight.build_prompt_context", return_value=prompt_ctx),
        patch("routes.chat_preflight.run_input_guardrails", side_effect=ImportError("no guardrails")),
        patch("routes.chat_preflight.apply_token_budget", side_effect=ImportError("no budget")),
        patch("routes.chat_preflight.adapt_identity_prompt", side_effect=ImportError("no identity")),
        patch("routes.chat_preflight.merge_device_intent_system_prompt", return_value="merged"),
    ):
        req = _req()
        result = chat_preflight.prepare_chat_preflight(req)
        assert result.request_messages == prompt_ctx.request_messages
