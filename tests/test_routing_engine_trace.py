"""Tests for routing_engine trace spans and trace_span API."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from context_pipeline.tracing import new_trace, reset_current_trace
from routing_engine import route


@pytest.fixture(autouse=True)
def _reset_trace():
    reset_current_trace()
    yield
    reset_current_trace()


class TestTraceSpan:
    def test_trace_span_disabled_returns_none(self, monkeypatch):
        monkeypatch.setenv("LIMA_TRACING_ENABLED", "0")
        from routing_engine.trace import trace_span

        new_trace()
        with trace_span("test") as span:
            assert span is None

    def test_trace_span_creates_and_ends_span(self, monkeypatch):
        monkeypatch.setenv("LIMA_TRACING_ENABLED", "1")
        from routing_engine.trace import trace_span

        trace = new_trace()
        with trace_span("step", request_type="chat") as span:
            assert span is not None
            assert span.name == "step"
            assert span.metadata["request_type"] == "chat"
        assert span.is_complete
        assert any(s.name == "step" for s in trace.spans)

    def test_trace_span_ends_on_exception(self, monkeypatch):
        monkeypatch.setenv("LIMA_TRACING_ENABLED", "1")
        from routing_engine.trace import trace_span

        trace = new_trace()
        with pytest.raises(ValueError):
            with trace_span("step") as span:
                assert span is not None
                raise ValueError("boom")
        assert trace.spans[0].is_complete
        assert trace.spans[0].metadata.get("error") == "ValueError"


def test_route_generates_required_spans(monkeypatch):
    monkeypatch.setenv("LIMA_TRACING_ENABLED", "1")
    reset_current_trace()
    trace = new_trace()

    def fake_call_fn(backend, messages, max_tokens, tools=None):
        return f"answer-from-{backend}"

    with (
        patch("routing_engine.classify", return_value="chat"),
        patch("routing_engine.classify_scenario", return_value="general"),
        patch("routing_engine.sticky_session.compute_key", return_value="key"),
        patch("routing_engine.health_tracker.get_health_map", return_value={}),
        patch("routing_engine.select", return_value=["longcat_chat"]),
        patch("routing_engine.resolve_intent", return_value="chat"),
        patch("routing_engine.inject_skills", side_effect=lambda messages, **kw: messages),
        patch("routing_engine.auto_compress", side_effect=lambda msgs, *a, **kw: msgs),
        patch("routing_engine.try_recall_backend", return_value=None),
        patch("routing_engine.inject_retrieval_context", return_value=([], "")),
        patch("routing_engine.cache.lookup_cached_response", return_value=None),
        patch("routing_engine.store_cached_response"),
        patch("routing_engine.execute_strategy.speculative.classify_complexity", return_value="complex"),
        patch(
            "routing_engine.execute_strategy.execute", return_value=("longcat_chat", "answer-from-longcat_chat", None)
        ),
    ):
        result = route(
            "hello",
            [{"role": "user", "content": "hello"}],
            call_fn=fake_call_fn,
            cache_enabled=True,
        )

    names = [s.name for s in trace.spans]
    required = {"classify", "scenario", "recall", "retrieval", "select", "skills", "execute", "post_process"}
    assert result.backend == "longcat_chat"
    assert required.issubset(set(names)), f"missing spans: {required - set(names)}, got {names}"
