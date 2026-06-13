"""P0: speculative stream routing uses the same preflight context as v3_select."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

import pytest

import streaming
from routes import v3_adapters


@dataclass
class _RecordedPick:
    query: str
    messages: list
    system_prompt: str
    ide: str


@pytest.fixture
def recorded_pick(monkeypatch):
    calls: list[_RecordedPick] = []

    def _fake_pick_backend(query, messages, **kwargs):
        calls.append(_RecordedPick(
            query=query,
            messages=list(messages),
            system_prompt=kwargs.get("system_prompt", ""),
            ide=kwargs.get("ide_source", ""),
        ))
        backend = "backend_a" if kwargs.get("system_prompt") else "backend_b"
        return v3_adapters.routing_engine.PickResult(
            backend=backend,
            backends=[backend],
            messages=list(messages),
        )

    monkeypatch.setattr(v3_adapters.routing_engine, "pick_backend", _fake_pick_backend)
    return calls


def test_v3_predict_and_select_share_pick_backend_context(recorded_pick):
    messages = [
        {"role": "user", "content": "earlier"},
        {"role": "assistant", "content": "ok"},
        {"role": "user", "content": "follow up"},
    ]
    system_prompt = "You are a coding assistant."
    ide = "cursor"

    backend = v3_adapters.v3_predict(
        "follow up", messages, system_prompt=system_prompt, ide=ide,
    )
    select_backend, select_messages = v3_adapters.v3_select(
        "follow up", system_prompt, ide, messages,
    )

    assert len(recorded_pick) == 2
    assert recorded_pick[0] == recorded_pick[1]
    assert backend == select_backend == "backend_a"
    assert select_messages == messages


def test_speculative_stream_passes_system_prompt_to_predict_and_select():
    captured: dict[str, object] = {}

    def _predict(query, messages, system_prompt, ide):
        captured["predict"] = (query, list(messages), system_prompt, ide)
        return "predict_backend"

    def _select(query, system_prompt, ide, messages):
        captured["select"] = (query, system_prompt, ide, list(messages))
        return "select_backend", messages

    async def _stream_async(backend, msgs, max_tokens, ide):
        yield "chunk"

    async def _api_async(backend, msgs, max_tokens, ide):
        return "fallback"

    messages = [{"role": "user", "content": "debug this"}]
    system_prompt = "system digest"

    async def _run():
        items = []
        async for item in streaming.speculative_stream(
            "debug this",
            messages,
            4096,
            "cursor",
            predict_fn=_predict,
            select_fn=_select,
            call_stream_fn=lambda *a, **k: iter(()),
            call_fn=lambda *a, **k: "",
            system_prompt=system_prompt,
            call_stream_async_fn=_stream_async,
            call_api_async_fn=_api_async,
        ):
            items.append(item)
        return items

    asyncio.run(_run())

    assert captured["predict"] == ("debug this", messages, system_prompt, "cursor")
    assert captured["select"] == ("debug this", system_prompt, "cursor", messages)
