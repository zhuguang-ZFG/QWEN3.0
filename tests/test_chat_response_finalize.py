"""Tests for routes/chat_response_finalize.py (CQ-014 closeout extract)."""

import asyncio
import json
import time
from unittest.mock import patch

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
        t0=time.time() - 0.05,
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
def test_finalize_openai_fmt_attaches_memory_meta(
    mock_persist,
    mock_obs,
    mock_evidence,
    mock_distill,
    _log_prompt,
):
    recorded = []

    def record_request(*args, **kwargs):
        recorded.append((args, kwargs))

    response = asyncio.run(
        finalize_success_response(
            _ctx(),
            _req(),
            {"answer": "hi there", "backend": "test_backend", "total_ms": 42},
            {"intent": "chat"},
            model_id="lima-1.3",
            record_request=record_request,
        )
    )

    assert response.status_code == 200
    body = json.loads(response.body.decode("utf-8"))
    assert body["choices"][0]["message"]["content"] == "hi there"
    assert body["x_lima_meta"]["memory_recall"]["recalled_memory_ids"] == ["m1"]
    mock_persist.assert_called_once()
    mock_obs.assert_called_once()
    mock_evidence.assert_called_once()
    mock_distill.assert_called_once()
    assert recorded[0][0][1] == "test_backend"
    assert recorded[0][0][2] == "chat"


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


@patch("routes.chat_response_finalize._log_system_prompt")
@patch("routes.chat_response_finalize.maybe_log_distill_queue")
@patch("routes.chat_response_finalize.record_capability_evidence")
@patch("routes.chat_response_finalize.record_chat_observability")
@patch("routes.chat_response_finalize.persist_session_memory")
@patch("routes.chat_response_finalize.time.time", return_value=1000.0)
def test_missing_total_ms_uses_duration_ms(
    mock_time,
    _persist,
    _obs,
    _evidence,
    _distill,
    _log_prompt,
):
    ctx = _ctx()
    ctx.t0 = 999.0

    response = asyncio.run(
        finalize_success_response(
            ctx,
            _req(),
            {"answer": "hi", "backend": "test_backend"},
            {"intent": "chat"},
            model_id="lima-1.3",
            record_request=lambda *a, **k: None,
        )
    )

    body = json.loads(response.body.decode("utf-8"))
    assert body["x_lima_meta"]["total_ms"] == 1000
    mock_time.assert_called()


@patch("routes.chat_response_finalize._log_system_prompt")
@patch("routes.chat_response_finalize.maybe_log_distill_queue")
@patch("routes.chat_response_finalize.record_capability_evidence")
@patch("routes.chat_response_finalize.record_chat_observability")
@patch("routes.chat_response_finalize.persist_session_memory")
@patch("routes.chat_response_finalize.time.time", return_value=1000.0)
def test_explicit_total_ms_zero_not_replaced_by_duration(
    _mock_time,
    _persist,
    _obs,
    _evidence,
    _distill,
    _log_prompt,
):
    ctx = _ctx()
    ctx.t0 = 999.0

    response = asyncio.run(
        finalize_success_response(
            ctx,
            _req(),
            {"answer": "hi", "backend": "test_backend", "total_ms": 0},
            {"intent": "chat"},
            model_id="lima-1.3",
            record_request=lambda *a, **k: None,
        )
    )

    body = json.loads(response.body.decode("utf-8"))
    assert body["x_lima_meta"]["total_ms"] == 0


@patch("routes.chat_response_finalize._log_system_prompt")
@patch("routes.chat_response_finalize.maybe_log_distill_queue")
@patch("routes.chat_response_finalize.record_capability_evidence")
@patch("routes.chat_response_finalize.record_chat_observability")
@patch("routes.chat_response_finalize.persist_session_memory")
def test_finalize_anthropic_fmt(
    _persist,
    _obs,
    _evidence,
    _distill,
    _log_prompt,
):
    response = asyncio.run(
        finalize_success_response(
            _ctx(fmt="anthropic", memory_recall_meta={}),
            _req(),
            {"answer": "anthropic answer", "backend": "scnet_ds_pro", "total_ms": 10},
            {"intent": "chat"},
            model_id="lima-1.3",
            record_request=lambda *a, **k: None,
        )
    )

    assert response.status_code == 200
    body = json.loads(response.body.decode("utf-8"))
    assert body["type"] == "message"
    assert body["content"][0]["text"] == "anthropic answer"
    assert body["model"] == "lima-1.3"


@patch("routes.chat_response_finalize.clean_response", return_value="")
@patch("routes.chat_response_finalize._log_system_prompt")
@patch("routes.chat_response_finalize.maybe_log_distill_queue")
@patch("routes.chat_response_finalize.record_capability_evidence")
@patch("routes.chat_response_finalize.record_chat_observability")
@patch("routes.chat_response_finalize.persist_session_memory")
def test_finalize_clean_response_empty_fallback(
    mock_persist,
    _obs,
    _evidence,
    _distill,
    _log_prompt,
    _clean,
):
    response = asyncio.run(
        finalize_success_response(
            _ctx(memory_recall_meta={}),
            _req(),
            {"answer": "raw fallback", "backend": "test_backend", "total_ms": 1},
            {"intent": "chat"},
            model_id="lima-1.3",
            record_request=lambda *a, **k: None,
        )
    )

    body = json.loads(response.body.decode("utf-8"))
    assert body["choices"][0]["message"]["content"] == "raw fallback"
    mock_persist.assert_called_once_with(
        client_ip="127.0.0.1",
        memory_session_id="sess-1",
        query="hello",
        content="raw fallback",
    )
