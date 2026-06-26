from observability.metrics import get_recent_traces, record_trace, reset_metrics, reset_traces


class TestTraceBuffer:
    def test_record_and_get_recent_traces(self):
        reset_traces()
        record_trace({"trace_id": "t1"})
        record_trace({"trace_id": "t2"})
        recent = get_recent_traces(limit=10)
        assert [t["trace_id"] for t in recent] == ["t1", "t2"]

    def test_get_recent_traces_respects_limit(self):
        reset_traces()
        for i in range(5):
            record_trace({"trace_id": f"t{i}"})
        recent = get_recent_traces(limit=2)
        assert len(recent) == 2
        assert recent[-1]["trace_id"] == "t4"

    def test_reset_traces_clears_buffer(self):
        reset_traces()
        record_trace({"trace_id": "tx"})
        reset_traces()
        assert get_recent_traces(limit=10) == []

    def test_reset_metrics_clears_traces(self):
        reset_traces()
        record_trace({"trace_id": "ty"})
        reset_metrics()
        assert get_recent_traces(limit=10) == []
