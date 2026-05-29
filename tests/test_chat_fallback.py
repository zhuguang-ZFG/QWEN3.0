"""Tests for routes/chat_fallback.py (CQ-014 slice 5)."""

import asyncio
from unittest.mock import AsyncMock, patch

import routes.chat_fallback as chat_fallback
from routes.chat_fallback import QualityFallbackRequest, resolve_quality_fallback


def _base_request(**overrides):
    defaults = dict(
        chat_id="chat-test",
        query="hello",
        content="bad",
        backend="weak_backend",
        complexity=0.5,
        intent_name="chat",
        fmt="openai",
        request_model=None,
        max_tokens=128,
        ide_source="cursor",
        client_ip="127.0.0.1",
        sys_prompt_preview="base",
        prompt_context_messages=[{"role": "user", "content": "hello"}],
        memory_recall_meta={"checked": True, "applied": False},
        elapsed_ms=12,
    )
    defaults.update(overrides)
    return QualityFallbackRequest(**defaults)


@patch.object(chat_fallback, "_record_request")
@patch.object(chat_fallback, "_record_fallback")
@patch("routes.chat_fallback.try_backend", new_callable=AsyncMock)
@patch("routes.chat_fallback.get_same_tier_backends", return_value=["alt_backend"])
@patch("routes.chat_fallback.get_upgrade_chain", return_value=[])
@patch("routes.chat_fallback.default_route", return_value="weak_backend")
@patch("routes.chat_fallback.quality_check", side_effect=[True])
def test_resolve_quality_fallback_same_tier_success(
    mock_quality,
    _default_route,
    _upgrade,
    _same_tier,
    mock_try_backend,
    _record_fallback,
    _record_request,
):
    mock_try_backend.return_value = {"answer": "good answer from alt", "backend": "alt_backend"}
    chat_fallback._model_id = "lima-test"

    response = asyncio.run(resolve_quality_fallback(_base_request()))

    assert response.status_code == 200
    body = response.body.decode("utf-8")
    assert "good answer from alt" in body
    _record_fallback.assert_called_once()


@patch.object(chat_fallback, "_record_request")
@patch.object(chat_fallback, "_record_fallback")
@patch("routes.chat_fallback.try_backend", new_callable=AsyncMock)
@patch("routes.chat_fallback.get_same_tier_backends", return_value=[])
@patch("routes.chat_fallback.get_upgrade_chain", return_value=[])
@patch("routes.chat_fallback.default_route", return_value="weak_backend")
@patch("routes.chat_fallback.quality_check")
def test_resolve_quality_fallback_exhausted(
    mock_quality,
    _default_route,
    _upgrade,
    _same_tier,
    mock_try_backend,
    _record_fallback,
    _record_request,
):
    chat_fallback._model_id = "lima-test"

    response = asyncio.run(resolve_quality_fallback(_base_request()))

    assert response.status_code == 200
    mock_try_backend.assert_not_called()
    _record_request.assert_called_once()
    assert "fallback_exhausted" in _record_request.call_args[0][1]
