"""Tests for eval_pinned_call (routing_executor convergence)."""

from __future__ import annotations


def test_call_pinned_backend_delegates_to_execute(monkeypatch):
    captured: dict[str, object] = {}

    def _fake_execute(backends, call_fn, messages, max_tokens, **kwargs):
        captured["backends"] = backends
        captured["kwargs"] = kwargs
        answer = call_fn(backends[0], messages, max_tokens)
        return backends[0], answer, 0

    def _fake_call_api(backend, messages, max_tokens):
        captured["http"] = (backend, messages, max_tokens)
        return "eval answer"

    monkeypatch.setattr("eval_pinned_call.execute", _fake_execute)
    monkeypatch.setattr("eval_pinned_call.http_caller.call_api", _fake_call_api)

    from eval_pinned_call import call_pinned_backend

    final, answer = call_pinned_backend(
        "scnet_qwen30b",
        [{"role": "user", "content": "hi"}],
        128,
    )

    assert final == "scnet_qwen30b"
    assert answer == "eval answer"
    assert captured["backends"] == ["scnet_qwen30b"]
    assert captured["kwargs"] == {
        "scenario": "eval",
        "request_type": "eval",
    }


def test_call_pinned_backend_returns_exhausted(monkeypatch):
    monkeypatch.setattr(
        "eval_pinned_call.execute",
        lambda *a, **k: ("exhausted", "", 1),
    )

    from eval_pinned_call import call_pinned_backend

    final, answer = call_pinned_backend("dead_backend", [], 64)
    assert final == "exhausted"
    assert answer == ""
