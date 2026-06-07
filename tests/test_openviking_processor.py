"""Tests for the OpenViking context pipeline processor (Stage 6)."""
import pytest
from unittest.mock import patch, MagicMock
from context_pipeline import RequestContext


def test_processor_skips_when_client_none():
    """If OpenViking is disabled, processor is a no-op."""
    from context_pipeline.openviking_processor import openviking_context_processor
    ctx = RequestContext(
        scenario="coding",
        messages=[{"role": "user", "content": "fix the bug"}],
        system_prompt="existing prompt",
    )
    with patch("context_pipeline.openviking_processor.get_openviking_client", return_value=None):
        result = openviking_context_processor(ctx)
    assert result.openviking_context == ""
    assert result.system_prompt == "existing prompt"


def test_processor_skips_non_coding_scenarios():
    """Only coding scenarios get OpenViking enrichment."""
    from context_pipeline.openviking_processor import openviking_context_processor
    ctx = RequestContext(scenario="chat", system_prompt="chat prompt")
    with patch("context_pipeline.openviking_processor.get_openviking_client") as mock_get:
        result = openviking_context_processor(ctx)
    assert result.openviking_context == ""
    mock_get.assert_not_called()


def test_processor_injects_context_into_system_prompt():
    """When OpenViking returns results, they appear in system_prompt."""
    from context_pipeline.openviking_processor import openviking_context_processor

    mock_client = MagicMock()
    mock_client.find.return_value = [
        {"uri": "viking://resources/api_docs", "content": "Use /v1/models endpoint", "score": 0.92},
    ]
    mock_client.format_context.return_value = "[OpenViking Context]\n- viking://resources/api_docs: Use /v1/models endpoint"

    ctx = RequestContext(
        scenario="coding",
        messages=[{"role": "user", "content": "how to list models?"}],
        system_prompt="You are LiMa.",
    )
    with patch("context_pipeline.openviking_processor.get_openviking_client", return_value=mock_client):
        result = openviking_context_processor(ctx)

    assert "OpenViking Context" in result.system_prompt
    assert result.openviking_context != ""


def test_processor_handles_empty_results():
    """If OpenViking returns no results, system_prompt is unchanged."""
    from context_pipeline.openviking_processor import openviking_context_processor

    mock_client = MagicMock()
    mock_client.find.return_value = []
    mock_client.format_context.return_value = ""

    ctx = RequestContext(
        scenario="coding",
        messages=[{"role": "user", "content": "hello"}],
        system_prompt="original prompt",
    )
    with patch("context_pipeline.openviking_processor.get_openviking_client", return_value=mock_client):
        result = openviking_context_processor(ctx)

    assert result.system_prompt == "original prompt"
    assert result.openviking_context == ""


def test_processor_extracts_query_from_last_user_message():
    """The search query should be the last user message content."""
    from context_pipeline.openviking_processor import _extract_query

    messages = [
        {"role": "system", "content": "You are LiMa"},
        {"role": "user", "content": "first question"},
        {"role": "assistant", "content": "answer"},
        {"role": "user", "content": "how to fix the routing bug in server.py?"},
    ]
    query = _extract_query(messages)
    assert "routing bug" in query
