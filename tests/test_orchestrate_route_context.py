"""P1: orchestrate routes HTTP calls with the same ide/system_prompt context as v3_route."""

from __future__ import annotations

import orchestrate


def test_route_via_engine_passes_ide_and_system_prompt_to_http_caller(monkeypatch):
    captured: dict[str, object] = {}

    def _fake_call_api(backend, msgs, max_tokens, *, system_prompt="", ide="", tools=None):
        captured.update({
            "backend": backend,
            "system_prompt": system_prompt,
            "ide": ide,
            "tools": tools,
        })
        return "ok"

    def _fake_route(query, messages, **kwargs):
        captured["route_kwargs"] = kwargs
        answer = kwargs["call_fn"](
            "test_backend",
            messages,
            kwargs["max_tokens"],
            tools=kwargs.get("tools"),
        )
        captured["answer"] = answer
        return type("RouteResult", (), {
            "answer": answer,
            "backend": "test_backend",
            "ms": 1,
        })()

    monkeypatch.setattr(orchestrate.http_caller, "call_api", _fake_call_api)
    monkeypatch.setattr(orchestrate.routing_engine, "route", _fake_route)

    orchestrate._route_via_engine(
        "hello",
        messages=[{"role": "user", "content": "hello"}],
        ide_source="cursor",
        system_prompt="digest",
        max_tokens=2048,
        needs_tools=True,
        tools=[{"type": "function", "function": {"name": "x"}}],
    )

    assert captured["system_prompt"] == "digest"
    assert captured["ide"] == "cursor"
    assert captured["tools"] == [{"type": "function", "function": {"name": "x"}}]
    assert captured["route_kwargs"]["ide_source"] == "cursor"
    assert captured["route_kwargs"]["system_prompt"] == "digest"
