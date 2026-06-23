"""Error-handling tests for routes/chat_response_finalize.py."""

import asyncio
import json
import time
from unittest.mock import patch

import pytest

MOCK_NOW = 2_000_000_000.0

from chat_models import ChatRequest, Message
from routes.chat_handler_dispatch import ChatRunContext, RoutePrefs
from routes.chat_preflight import ChatPreflightResult
from routes.chat_response_finalize import finalize_success_response


def _ctx(*, fmt: str = "openai", memory_recall_meta: dict | None = None) -> ChatRunContext:
    preflight = ChatPreflightResult(
        request_messages=[{"role": "user", "content": "hello"}],
        prompt_context_messages=[{"role": "user", "content": "hello"}],
        system_prompt="sys",
        memory_recall_meta=memory_recall_meta or {"checked": True, "applied": True, "recalled_memory_ids": ["m1"]},
        memory_session_id="sess-1",
    )
    return ChatRunContext(
        chat_id="chat-test",
        query="hello",
        t0=MOCK_NOW - 0.05,
        fmt=fmt,
        request_model=None,
        client_ip="127.0.0.1",
        ide_source="cursor",
        sys_prompt_preview="sys",
        memory_recall_meta=preflight.memory_recall_meta,
        memory_session_id=preflight.memory_session_id,
        preflight=preflight,
        prefs=RoutePrefs(prefer=None, ide_source="cursor", use_thinking=False),
    )


def _req() -> ChatRequest:
    return ChatRequest(model="lima-1.3", messages=[Message(role="user", content="hello")])


@patch("routes.chat_response_finalize._log_system_prompt")
@patch("routes.chat_response_finalize.maybe_log_distill_queue")
@patch("routes.chat_response_finalize.record_capability_evidence")
@patch("routes.chat_response_finalize.record_chat_observability")
@patch("routes.chat_response_finalize.persist_session_memory")
def test_record_request_raises_still_returns_200(
    _persist,
    _obs,
    _evidence,
    _distill,
    _log_prompt,
):
    def boom(*args, **kwargs):
        raise RuntimeError("stats db locked")

    response = asyncio.run(
        finalize_success_response(
            _ctx(),
            _req(),
            {"answer": "ok", "backend": "test_backend", "total_ms": 5},
            {"intent": "chat"},
            model_id="lima-1.3",
            record_request=boom,
        )
    )

    assert response.status_code == 200
    body = json.loads(response.body.decode("utf-8"))
    assert body["choices"][0]["message"]["content"] == "ok"


@patch("routes.chat_response_finalize._log_system_prompt")
@patch("routes.chat_response_finalize.maybe_log_distill_queue")
@patch("routes.chat_response_finalize.record_capability_evidence")
@patch("routes.chat_response_finalize.record_chat_observability")
@patch("routes.chat_response_finalize.persist_session_memory")
def test_persist_raises_still_returns_200(
    mock_persist,
    _obs,
    _evidence,
    _distill,
    _log_prompt,
):
    mock_persist.side_effect = RuntimeError("sqlite locked")

    response = asyncio.run(
        finalize_success_response(
            _ctx(),
            _req(),
            {"answer": "ok", "backend": "test_backend", "total_ms": 5},
            {"intent": "chat"},
            model_id="lima-1.3",
            record_request=lambda *a, **k: None,
        )
    )

    assert response.status_code == 200
    body = json.loads(response.body.decode("utf-8"))
    assert body["choices"][0]["message"]["content"] == "ok"


@patch("routes.chat_response_finalize._log_system_prompt")
@patch("routes.chat_response_finalize.maybe_log_distill_queue")
@patch("routes.chat_response_finalize.record_capability_evidence")
@patch("routes.chat_response_finalize.persist_session_memory")
def test_record_chat_observability_raises_still_returns_200(
    _persist,
    mock_evidence,
    mock_distill,
    _log_prompt,
):
    with patch(
        "routes.chat_response_finalize.record_chat_observability",
        side_effect=RuntimeError("metrics unavailable"),
    ):
        response = asyncio.run(
            finalize_success_response(
                _ctx(),
                _req(),
                {"answer": "ok", "backend": "test_backend", "total_ms": 5},
                {"intent": "chat"},
                model_id="lima-1.3",
                record_request=lambda *a, **k: None,
            )
        )

    assert response.status_code == 200
    body = json.loads(response.body.decode("utf-8"))
    assert body["choices"][0]["message"]["content"] == "ok"


@pytest.fixture(autouse=True)
def fixed_time(monkeypatch):
    monkeypatch.setattr(time, "time", lambda: MOCK_NOW)
