"""Tests for context_pipeline/tracing.py — request lifecycle tracing."""

from context_pipeline.tracing import RequestTrace, Span


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
