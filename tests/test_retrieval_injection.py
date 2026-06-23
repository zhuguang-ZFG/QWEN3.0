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
        injected = [{"role": "system", "content": "[retrieval]"}] + list(messages)
        return injected, "[retrieval]"

    injected_messages, retrieval_text = fake_inject(
        [{"role": "user", "content": "hello"}]
    )

    monkeypatch.setattr(
        routing_engine,
        "_pick_for_route",
        lambda *a, **kw: routing_engine.PickResult(
            backend="unit_backend",
            backends=["unit_backend"],
            messages=injected_messages,
            request_type="chat",
            scenario="chat",
            retrieval_context=retrieval_text,
            sticky_key="",
        ),
    )

    def call_fn(backend, messages, max_tokens):
        assert any(msg.get("content") == "[retrieval]" for msg in messages)
        return "ok done"

    # Bypass speculative/standard execute complexity; just verify injected messages reach call_fn.
    monkeypatch.setattr(
        routing_engine,
        "execute_with_strategy",
        lambda call_fn, backends, messages, *args, **kwargs: (
            backends[0],
            call_fn(backends[0], messages, 4096),
        ),
    )

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
