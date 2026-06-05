import asyncio

import backends
import http_caller
import router_circuit_breaker
import routes.quality_gate as quality_gate


def test_try_backend_forwards_full_messages(monkeypatch):
    captured = {}

    monkeypatch.setitem(backends.BACKENDS, "unit_backend", {"key": "x"})
    monkeypatch.setitem(quality_gate._backend_enabled, "unit_backend", True)
    monkeypatch.setattr(router_circuit_breaker, "cb_allow", lambda name: True)
    monkeypatch.setattr(router_circuit_breaker, "cb_record", lambda *args, **kwargs: None)

    def fake_call_api(backend, messages, max_tokens):
        captured["backend"] = backend
        captured["messages"] = messages
        captured["max_tokens"] = max_tokens
        return "context preserved"

    monkeypatch.setattr(http_caller, "call_api", fake_call_api)

    messages = [
        {"role": "system", "content": "system context"},
        {"role": "user", "content": "first turn"},
        {"role": "assistant", "content": "previous answer"},
        {"role": "user", "content": "latest turn"},
    ]

    result = asyncio.run(
        quality_gate.try_backend(
            "unit_backend",
            "latest turn",
            321,
            messages=messages,
        )
    )

    assert result["answer"] == "context preserved"
    assert captured == {
        "backend": "unit_backend",
        "messages": messages,
        "max_tokens": 321,
    }
