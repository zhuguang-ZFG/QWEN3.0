"""Tests for context_pipeline/tracing.py — request lifecycle tracing."""

from unittest.mock import patch

import pytest

from context_pipeline.tracing import new_trace, RequestTrace, reset_current_trace, Span
from routing_engine import route
from routing_engine_intent import resolve_intent


@pytest.fixture(autouse=True)
def _reset_trace():
    reset_current_trace()
    yield
    reset_current_trace()


class TestSpan:
    def test_duration_ms_with_end_time(self):
        span = Span(name="test", trace_id="t1", start_time=100.0, end_time=103.0)
        assert span.duration_ms == 3000

    def test_duration_ms_without_end_time(self):
        span = Span(name="test", trace_id="t1", start_time=100.0)
        assert span.duration_ms >= 0

    def test_is_complete_true(self):
        span = Span(name="t", trace_id="t", start_time=0, end_time=1)
        assert span.is_complete is True

    def test_is_complete_false(self):
        span = Span(name="t", trace_id="t", start_time=0)
        assert span.is_complete is False

    def test_unique_span_id(self):
        s1 = Span(name="a", trace_id="t1", start_time=0)
        s2 = Span(name="b", trace_id="t1", start_time=0)
        assert s1.span_id != s2.span_id


class TestRequestTrace:
    def test_trace_id_is_unique(self):
        t1 = RequestTrace()
        t2 = RequestTrace()
        assert t1.trace_id != t2.trace_id

    def test_start_span_returns_span(self):
        trace = RequestTrace()
        span = trace.start_span("test_span")
        assert isinstance(span, Span)
        assert span.name == "test_span"

    def test_span_added_to_trace(self):
        trace = RequestTrace()
        trace.start_span("s1")
        assert len(trace.spans) == 1

    def test_multiple_spans(self):
        trace = RequestTrace()
        trace.start_span("s1")
        trace.start_span("s2")
        assert len(trace.spans) == 2

    def test_end_span(self):
        trace = RequestTrace()
        trace.start_span("test")
        trace.end_span()
        assert trace.spans[0].is_complete

    def test_end_span_no_active_span(self):
        trace = RequestTrace()
        trace.end_span()  # Should not raise
        assert len(trace.spans) == 0

    def test_end_span_sets_time(self):
        trace = RequestTrace()
        span = trace.start_span("test")
        trace.end_span(span)
        assert span.is_complete is True

    def test_export(self):
        trace = RequestTrace()
        span = trace.start_span("test")
        trace.end_span(span)
        d = trace.export()
        assert d["trace_id"] == trace.trace_id
        assert len(d["spans"]) == 1

    def test_finish_ends_all_spans_and_exports(self):
        trace = RequestTrace()
        trace.start_span("s1")
        trace.start_span("s2")
        result = trace.finish()
        assert all(s.is_complete for s in trace.spans)
        assert result["trace_id"] == trace.trace_id
        assert result["span_count"] == 2


class TestTracingSemanticCache:
    def _route_with_cache(self, lookup_return, monkeypatch):
        monkeypatch.setenv("LIMA_TRACING_ENABLED", "1")
        trace = new_trace()
        fake_cache = object()

        with (
            patch("routing_engine.identity_guard.detect_identity_question", return_value=None),
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
            patch("routing_engine_cache.lookup_cached_response", return_value=lookup_return),
            patch("routing_engine_cache.get_cache", return_value=fake_cache),
            patch("routing_engine_helpers.post_route"),
            patch("routing_engine.get_injected_ids", return_value=[]),
        ):
            return route(
                "hello",
                [{"role": "user", "content": "hello"}],
                call_fn=None,
                cache_enabled=True,
            ), trace

    def test_semantic_cache_hit_span(self, monkeypatch):
        result, trace = self._route_with_cache("cached answer", monkeypatch)
        assert result.answer == "cached answer"
        cache_spans = [s for s in trace.spans if s.name == "semantic_cache"]
        assert len(cache_spans) == 1
        assert cache_spans[0].metadata["cache_enabled"] is True
        assert cache_spans[0].metadata["cache_status"] == "hit"
        assert isinstance(cache_spans[0].metadata["cache_lookup_ms"], int)

    def test_semantic_cache_miss_span(self, monkeypatch):
        monkeypatch.setenv("LIMA_TRACING_ENABLED", "1")
        trace = new_trace()
        fake_cache = object()

        with (
            patch("routing_engine.identity_guard.detect_identity_question", return_value=None),
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
            patch("routing_engine_cache.lookup_cached_response", return_value=None),
            patch("routing_engine_cache.get_cache", return_value=fake_cache),
            patch("routing_engine.execute_with_strategy", return_value=("longcat_chat", "generated answer")),
            patch("routing_engine.store_cached_response"),
            patch("routing_engine_helpers.post_route"),
            patch("routing_engine.get_injected_ids", return_value=[]),
        ):
            result = route(
                "hello",
                [{"role": "user", "content": "hello"}],
                call_fn=lambda _b, _m, _t: "generated answer",
                cache_enabled=True,
            )

        assert result.answer == "generated answer"
        cache_spans = [s for s in trace.spans if s.name == "semantic_cache"]
        assert len(cache_spans) == 1
        assert cache_spans[0].metadata["cache_enabled"] is True
        assert cache_spans[0].metadata["cache_status"] == "miss"
        assert isinstance(cache_spans[0].metadata["cache_lookup_ms"], int)


class TestTracingIntent:
    def test_intent_span_records_source_and_confidence(self, monkeypatch):
        monkeypatch.setenv("LIMA_TRACING_ENABLED", "1")
        trace = new_trace()

        with (
            patch("routing_engine_intent.semantic_router_enabled", return_value=False),
            patch(
                "routing_engine_intent.analyze_intent",
                return_value={
                    "intent": "code_generation",
                    "source": "signal_v2",
                    "confidence": 0.9,
                    "instructor_used": False,
                },
            ),
        ):
            intent = resolve_intent("write python", "", "vscode")

        assert intent == "code_generation"
        intent_spans = [s for s in trace.spans if s.name == "intent"]
        assert len(intent_spans) == 1
        md = intent_spans[0].metadata
        assert md["intent"] == "code_generation"
        assert md["intent_source"] == "signal_v2"
        assert md["intent_confidence"] == 0.9
        assert md["instructor_used"] is False
