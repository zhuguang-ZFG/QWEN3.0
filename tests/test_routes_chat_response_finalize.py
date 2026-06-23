"""Tests for routes/chat_response_finalize.py."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.responses import JSONResponse

from chat_models import ChatRequest, Message
from routes import chat_response_finalize as finalize


def _ctx(fmt: str = "openai"):
    return SimpleNamespace(
        chat_id="chat-123",
        query="hello",
        t0=0.0,
        fmt=fmt,
        request_model=None,
        client_ip="127.0.0.1",
        ide_source="test",
        sys_prompt_preview="sys",
        memory_recall_meta={"checked": True},
        memory_session_id="sess-1",
        preflight=SimpleNamespace(request_messages=[{"role": "user", "content": "hello"}]),
    )


def _req(system: str = "") -> ChatRequest:
    messages = [Message(role="user", content="hello")]
    if system:
        messages.insert(0, Message(role="system", content=system))
    return ChatRequest(messages=messages)


@pytest.fixture(autouse=True)
def _patch_side_effects():
    with (
        patch("routes.chat_response_finalize.persist_session_memory") as mock_persist,
        patch("routes.chat_response_finalize.record_chat_observability") as mock_obs,
        patch("routes.chat_response_finalize.record_capability_evidence") as mock_ev,
        patch("routes.chat_response_finalize.maybe_log_distill_queue") as mock_distill,
        patch("routes.chat_response_finalize.log_sys_prompt") as mock_log_sys,
    ):
        yield SimpleNamespace(
            persist=mock_persist,
            observability=mock_obs,
            evidence=mock_ev,
            distill=mock_distill,
            log_sys=mock_log_sys,
        )


@pytest.mark.asyncio
@patch("routes.chat_response_finalize.clean_response", return_value="cleaned")
@patch("routes.chat_response_finalize.build_response", return_value={"id": "chat-123", "answer": "cleaned"})
@patch("routes.chat_response_finalize.attach_memory_recall_meta", side_effect=lambda r, m: r)
async def test_finalize_openai_success(mock_attach, mock_build, mock_clean, _patch_side_effects):
    ctx = _ctx()
    req = _req()
    result = {"answer": "raw", "backend": "backend-a", "intent": "chat"}
    record_request = MagicMock()

    response = await finalize.finalize_success_response(
        ctx, req, result, {"intent": "chat"}, model_id="lima-test", record_request=record_request
    )

    assert isinstance(response, JSONResponse)
    assert response.status_code == 200
    mock_clean.assert_called_once_with("raw", "backend-a")
    mock_build.assert_called_once()
    record_request.assert_called_once()
    _patch_side_effects.persist.assert_called_once()
    _patch_side_effects.observability.assert_called_once()
    _patch_side_effects.evidence.assert_called_once()
    _patch_side_effects.distill.assert_called_once()


@pytest.mark.asyncio
@patch("routes.chat_response_finalize.clean_response", return_value="")
@patch("routes.chat_response_finalize.build_response", return_value={"id": "chat-123", "answer": "raw"})
@patch("routes.chat_response_finalize.attach_memory_recall_meta", side_effect=lambda r, m: r)
async def test_finalize_uses_raw_when_clean_empty(mock_attach, mock_build, mock_clean, _patch_side_effects):
    ctx = _ctx()
    req = _req()
    result = {"answer": "raw", "backend": "backend-a"}

    response = await finalize.finalize_success_response(
        ctx, req, result, {"intent": "chat"}, model_id="lima-test", record_request=MagicMock()
    )

    body = response.body.decode()
    assert "raw" in body


@pytest.mark.asyncio
@patch("routes.chat_response_finalize.clean_response", return_value="cleaned")
@patch("routes.chat_response_finalize.build_anthropic_response", return_value={"id": "msg-123", "content": "cleaned"})
async def test_finalize_anthropic_format(mock_build, mock_clean, _patch_side_effects):
    ctx = _ctx(fmt="anthropic")
    req = _req()
    result = {"answer": "raw", "backend": "backend-a"}

    response = await finalize.finalize_success_response(
        ctx, req, result, {"intent": "chat"}, model_id="lima-test", record_request=MagicMock()
    )

    assert isinstance(response, JSONResponse)
    assert response.status_code == 200
    mock_build.assert_called_once()


@pytest.mark.asyncio
@patch("routes.chat_response_finalize.clean_response", return_value="cleaned")
@patch("routes.chat_response_finalize.build_response", return_value={"id": "chat-123", "answer": "cleaned"})
@patch("routes.chat_response_finalize.attach_memory_recall_meta", side_effect=lambda r, m: r)
async def test_finalize_uses_result_total_ms(mock_attach, mock_build, mock_clean, _patch_side_effects):
    ctx = _ctx()
    req = _req()
    result = {"answer": "ok", "backend": "backend-a", "total_ms": 999}

    await finalize.finalize_success_response(
        ctx, req, result, {"intent": "chat"}, model_id="lima-test", record_request=MagicMock()
    )

    assert mock_build.call_args.args[3] == 999


@pytest.mark.asyncio
@patch("routes.chat_response_finalize.clean_response", return_value="cleaned")
@patch("routes.chat_response_finalize.build_response", return_value={"id": "chat-123", "answer": "cleaned"})
@patch("routes.chat_response_finalize.attach_memory_recall_meta", side_effect=lambda r, m: r)
async def test_finalize_survives_side_effect_failure(mock_attach, mock_build, mock_clean, _patch_side_effects):
    ctx = _ctx()
    req = _req()
    result = {"answer": "ok", "backend": "backend-a"}
    _patch_side_effects.persist.side_effect = RuntimeError("db down")

    response = await finalize.finalize_success_response(
        ctx, req, result, {"intent": "chat"}, model_id="lima-test", record_request=MagicMock()
    )

    assert isinstance(response, JSONResponse)
    assert response.status_code == 200


@pytest.mark.asyncio
@patch("routes.chat_response_finalize.clean_response", return_value="cleaned")
@patch("routes.chat_response_finalize.build_response", return_value={"id": "chat-123", "answer": "cleaned"})
@patch("routes.chat_response_finalize.attach_memory_recall_meta", side_effect=lambda r, m: r)
async def test_finalize_logs_system_prompt(mock_attach, mock_build, mock_clean, _patch_side_effects):
    ctx = _ctx()
    req = _req(system="be helpful")
    result = {"answer": "ok", "backend": "backend-a"}

    await finalize.finalize_success_response(
        ctx, req, result, {"intent": "chat"}, model_id="lima-test", record_request=MagicMock()
    )

    _patch_side_effects.log_sys.assert_called_once()
