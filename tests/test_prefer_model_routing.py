"""Model alias ``prefer`` pins backend selection on stream and non-stream paths."""

from __future__ import annotations

import routing_engine
from routes import v3_adapters
from routing_selector import select


def test_v3_route_forwards_prefer(monkeypatch):
    captured: dict[str, str] = {}

    def _fake_route(*_args, **kwargs):
        captured["preferred_backend"] = kwargs.get("preferred_backend", "")
        return routing_engine.RouteResult(
            backend="scnet_qwen235b",
            answer="ok",
            request_type="chat",
            scenario="coding",
            ms=1,
        )

    monkeypatch.setattr(v3_adapters.routing_engine, "route", _fake_route)
    v3_adapters.v3_route("hello", [], prefer="scnet_qwen235b")
    assert captured["preferred_backend"] == "scnet_qwen235b"


def test_v3_predict_forwards_prefer(monkeypatch):
    captured: dict[str, str] = {}

    def _fake_pick(*_args, **kwargs):
        captured["preferred_backend"] = kwargs.get("preferred_backend", "")
        return routing_engine.PickResult(
            backend=kwargs.get("preferred_backend") or "longcat_chat",
            backends=[kwargs.get("preferred_backend") or "longcat_chat"],
            messages=[{"role": "user", "content": "hi"}],
        )

    monkeypatch.setattr(v3_adapters.routing_engine, "pick_backend", _fake_pick)
    backend = v3_adapters.v3_predict(
        "hi", [{"role": "user", "content": "hi"}],
        preferred_backend="longcat_lite",
    )
    assert captured["preferred_backend"] == "longcat_lite"
    assert backend == "longcat_lite"


def test_select_pins_preferred_backend_outside_pool(monkeypatch):
    import backends_registry as reg
    import budget_manager
    import health_tracker
    import router_v3

    preferred = "scnet_qwen235b"
    assert preferred in reg.BACKENDS

    monkeypatch.setattr(router_v3, "select_backends", lambda _pool, _hm: ["longcat_chat"])
    monkeypatch.setattr(health_tracker, "is_cooled_down", lambda _b: False)
    monkeypatch.setattr(budget_manager, "is_budget_available", lambda _b: True)
    monkeypatch.setattr(
        health_tracker,
        "get_backend_state",
        lambda _b: {"consecutive_failures": 0},
    )

    health_map = {preferred: "healthy", "longcat_chat": "healthy"}
    backends = select(
        "chat",
        health_map,
        preferred_backend=preferred,
    )
    assert backends[0] == preferred
