"""Routing executor respects is_retryable stream errors (M-OC7)."""

from __future__ import annotations

from http_errors import BackendError

import routing_executor as mod


def test_execute_falls_back_on_retryable_error():
    calls: list[str] = []

    def call_fn(backend, messages, max_tokens, tools=None):
        calls.append(backend)
        if backend == "first":
            raise BackendError("quota", status_code=429, is_retryable=True)
        return "ok answer"

    backend, answer, errors = mod.execute(
        ["first", "second"],
        call_fn,
        [{"role": "user", "content": "hi"}],
    )
    assert backend == "second"
    assert answer == "ok answer"
    assert errors >= 1
    assert calls == ["first", "second"]


def test_execute_stops_on_overflow():
    def call_fn(backend, messages, max_tokens, tools=None):
        raise BackendError("overflow", status_code=413, is_overflow=True)

    try:
        mod.execute(["only"], call_fn, [{"role": "user", "content": "hi"}])
        raise AssertionError("expected overflow to propagate")
    except BackendError as exc:
        assert exc.is_overflow is True
