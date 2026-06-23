"""Tests for routes/chat_fallback.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from routes import chat_fallback as cf
from routes.chat_fallback import QualityFallbackRequest


@pytest.fixture(autouse=True)
def _inject_deps():
    cf.inject_deps(model_id="lima-test", record_request=MagicMock(), record_fallback=MagicMock())
    yield
    cf.inject_deps(model_id="lima-test", record_request=MagicMock(), record_fallback=MagicMock())


def _make_req() -> QualityFallbackRequest:
    return QualityFallbackRequest(
        chat_id="c1",
        query="hi",
        content="",
        backend="groq",
        complexity=0.5,
        intent_name="chat",
        fmt="openai",
        request_model=None,
        max_tokens=100,
        ide_source="vscode",
        client_ip="127.0.0.1",
        sys_prompt_preview="",
        prompt_context_messages=[],
        memory_recall_meta={},
        elapsed_ms=10,
    )


@pytest.mark.asyncio
@patch.object(cf, "try_backend", return_value={"answer": "alt answer"})
@patch.object(cf, "get_same_tier_backends", return_value=["alt1"])
@patch.object(cf, "get_upgrade_chain", return_value=[])
async def test_resolve_same_tier_fallback_success(mock_upgrade, mock_same, mock_try):
    req = _make_req()
    response = await cf.resolve_quality_fallback(req)
    assert response.status_code == 200
    assert "alt answer" in response.body.decode()


@pytest.mark.asyncio
@patch.object(cf, "try_backend", side_effect=[None, {"answer": "upgrade answer"}])
@patch.object(cf, "get_same_tier_backends", return_value=["alt1"])
@patch.object(cf, "get_upgrade_chain", return_value=["up1"])
async def test_resolve_upgrade_fallback_success(mock_upgrade, mock_same, mock_try):
    req = _make_req()
    response = await cf.resolve_quality_fallback(req)
    assert response.status_code == 200
    assert "upgrade answer" in response.body.decode()


@pytest.mark.asyncio
@patch.object(cf, "try_backend", return_value=None)
@patch.object(cf, "get_same_tier_backends", return_value=[])
@patch.object(cf, "get_upgrade_chain", return_value=[])
async def test_resolve_fallback_exhausted(mock_upgrade, mock_same, mock_try):
    req = _make_req()
    response = await cf.resolve_quality_fallback(req)
    assert response.status_code == 200
    assert "服务暂时不可用" in response.body.decode()
    assert cf._record_request.called
