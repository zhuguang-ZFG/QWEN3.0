"""Tests that routing_engine.route() generates the expected spans."""

from unittest.mock import patch

from context_pipeline.tracing import new_trace, reset_current_trace
from routing_engine import route


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
        patch("routing_engine_cache.lookup_cached_response", return_value=None),
        patch("routing_engine.store_cached_response"),
        patch("routing_engine_execute_strategy.speculative.classify_complexity", return_value="complex"),
        patch(
            "routing_engine_execute_strategy.execute", return_value=("longcat_chat", "answer-from-longcat_chat", None)
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
