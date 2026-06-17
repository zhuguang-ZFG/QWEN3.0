from unittest.mock import patch

import routing_engine
from context_pipeline.retrieval_injection import (
    build_retrieval_text,
    inject_retrieval_context,
    run_retrieval,
)


def test_build_and_inject_share_same_payload(monkeypatch):
    payload = type(
        "Payload",
        (),
        {
            "query_terms": ["routing_engine.py"],
            "candidates_searched": 3,
            "reranked_results": [],
            "text": "[代码上下文]\n[routing_engine.py]",
        },
    )()

    with patch(
        "context_pipeline.retrieval_injection.run_retrieval",
        return_value=payload,
    ):
        text = build_retrieval_text([{"role": "user", "content": "fix routing_engine.py"}])
        msgs, injected = inject_retrieval_context(
            [{"role": "user", "content": "fix routing_engine.py"}],
        )

    assert text == payload.text
    assert injected == payload.text
    assert msgs[0]["content"] == payload.text


def test_inject_retrieval_context_empty_messages():
    result_msgs, text = inject_retrieval_context([])
    assert result_msgs == []
    assert text == ""


def test_routing_engine_reuses_shared_injector(monkeypatch):
    calls = {"count": 0}

    def fake_inject(messages):
        calls["count"] += 1
        return [{"role": "system", "content": "[retrieval]"}] + list(messages), "[retrieval]"

    monkeypatch.setattr(routing_engine, "inject_retrieval_context", fake_inject)
    monkeypatch.setattr(routing_engine, "classify_scenario", lambda *a, **kw: "chat")
    monkeypatch.setattr(routing_engine, "select", lambda *a, **kw: ["unit_backend"])
    monkeypatch.setattr(routing_engine.health_tracker, "get_health_map", lambda: {})

    def call_fn(backend, messages, max_tokens):
        assert messages[0]["content"] == "[retrieval]"
        return "ok done"

    result = routing_engine.route(
        "hello",
        [{"role": "user", "content": "hello"}],
        call_fn=call_fn,
        cache_enabled=False,
    )

    assert result.answer == "ok done"
    assert result.retrieval_context == "[retrieval]"
    assert calls["count"] == 1


def test_run_retrieval_returns_none_without_entities():
    assert run_retrieval([{"role": "user", "content": "hello"}]) is None
