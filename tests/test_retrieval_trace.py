"""Tests for context_pipeline/retrieval_trace.py — retrieval trace ring buffer."""

from context_pipeline.retrieval_trace import RetrievalTrace, record_trace, get_recent_traces


class TestRetrievalTrace:
    def test_to_dict(self):
        trace = RetrievalTrace(backend="groq", request_type="chat")
        d = trace.to_dict()
        assert d["backend"] == "groq"
        assert d["request_type"] == "chat"


class TestRecordTrace:
    def test_records_trace(self):
        trace = RetrievalTrace(query_entities=["server.py"], injected_text="context", backend="groq")
        record_trace(trace)
        traces = get_recent_traces()
        assert len(traces) >= 1
        assert traces[0]["backend"] == "groq"

    def test_respects_limit(self):
        for i in range(60):
            record_trace(RetrievalTrace(query_entities=[f"e{i}"], backend="x"))
        assert len(get_recent_traces()) <= 50


class TestGetRecentTraces:
    def test_returns_list(self):
        assert isinstance(get_recent_traces(), list)
