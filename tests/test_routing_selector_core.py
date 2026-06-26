"""Direct tests for routing_selector.select pool routing (analyzer misses test_route_scorer.py)."""

from __future__ import annotations

import health_tracker
import routing_selector.core as selector_core
from routing_selector import select


def test_select_no_longer_maps_coding_to_code_pool(monkeypatch):
    captured: dict[str, str] = {}

    def fake_build(pool_key, health_map, needs_tools, scenario):
        captured["pool_key"] = pool_key
        captured["scenario"] = scenario
        return ["backend-a"]

    monkeypatch.setattr(selector_core, "_build_initial_pool", fake_build)
    monkeypatch.setattr(selector_core, "_apply_guard_decisions", lambda pool: (pool, {}))
    monkeypatch.setattr(health_tracker, "get_scores", lambda: {})
    monkeypatch.setattr(health_tracker, "get_latency_map", lambda: {})
    monkeypatch.setattr(health_tracker, "get_health_map", lambda: {})
    monkeypatch.setattr(selector_core, "_score_backends", lambda *args, **kwargs: None)
    monkeypatch.setattr(selector_core, "_apply_ml_boost", lambda *args, **kwargs: None)
    monkeypatch.setattr(selector_core, "_rank_backends", lambda pool, *args, **kwargs: pool)
    monkeypatch.setattr(selector_core, "_apply_pin", lambda pool, *args, **kwargs: pool)

    result = select("chat", {}, scenario="coding")
    assert captured["pool_key"] == "chat"
    assert result == ["backend-a"]


def test_select_maps_chat_scenario_to_chat_fast_pool(monkeypatch):
    captured: dict[str, str] = {}

    def fake_build(pool_key, health_map, needs_tools, scenario):
        captured["pool_key"] = pool_key
        return ["backend-b"]

    monkeypatch.setattr(selector_core, "_build_initial_pool", fake_build)
    monkeypatch.setattr(selector_core, "_apply_guard_decisions", lambda pool: (pool, {}))
    monkeypatch.setattr(health_tracker, "get_scores", lambda: {})
    monkeypatch.setattr(health_tracker, "get_latency_map", lambda: {})
    monkeypatch.setattr(health_tracker, "get_health_map", lambda: {})
    monkeypatch.setattr(selector_core, "_score_backends", lambda *args, **kwargs: None)
    monkeypatch.setattr(selector_core, "_apply_ml_boost", lambda *args, **kwargs: None)
    monkeypatch.setattr(selector_core, "_rank_backends", lambda pool, *args, **kwargs: pool)
    monkeypatch.setattr(selector_core, "_apply_pin", lambda pool, *args, **kwargs: pool)

    select("chat", {}, scenario="chat")
    assert captured["pool_key"] == "chat_fast"


def test_select_respects_max_fallbacks(monkeypatch):
    from routing_selector.constants import MAX_FALLBACKS

    long_pool = [f"backend-{idx}" for idx in range(MAX_FALLBACKS + 5)]

    monkeypatch.setattr(selector_core, "_build_initial_pool", lambda *args, **kwargs: list(long_pool))
    monkeypatch.setattr(selector_core, "_apply_guard_decisions", lambda pool: (pool, {}))
    monkeypatch.setattr(health_tracker, "get_scores", lambda: {})
    monkeypatch.setattr(health_tracker, "get_latency_map", lambda: {})
    monkeypatch.setattr(health_tracker, "get_health_map", lambda: {})
    monkeypatch.setattr(selector_core, "_score_backends", lambda *args, **kwargs: None)
    monkeypatch.setattr(selector_core, "_apply_ml_boost", lambda *args, **kwargs: None)
    monkeypatch.setattr(selector_core, "_rank_backends", lambda pool, *args, **kwargs: pool)
    monkeypatch.setattr(selector_core, "_apply_pin", lambda pool, *args, **kwargs: pool)

    result = select("chat", {}, scenario="chat")
    assert len(result) == MAX_FALLBACKS
