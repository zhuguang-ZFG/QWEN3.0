import pytest

from context_pipeline.tracing import new_trace, reset_current_trace


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
