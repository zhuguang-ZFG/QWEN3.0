"""Routing selector public entry point."""

from __future__ import annotations

import health_tracker

from routing_selector.constants import MAX_FALLBACKS
from routing_selector.filters import _apply_guard_decisions, _build_initial_pool
from routing_selector.ranking import _apply_pin, _rank_backends
from routing_selector.scoring import _apply_ml_boost, _score_backends


def select(
    request_type: str,
    health_map: dict,
    sticky_key: str | None = None,
    scenario: str = "",
    needs_tools: bool = False,
    recalled_backend: str = "",
    preferred_backend: str = "",
    complexity=None,
) -> list[str]:
    """从对应池选健康后端，按健康评分排序，过滤预算耗尽，sticky 优先"""
    del complexity  # reserved for future complexity-based pool selection
    pool_key = request_type
    if request_type == "chat" and scenario == "coding":
        pool_key = "code"
    elif request_type == "chat" and scenario == "chat":
        pool_key = "chat_fast"
    result = _build_initial_pool(pool_key, health_map, needs_tools, scenario)
    result, routing_guard_decisions = _apply_guard_decisions(result)
    scores = health_tracker.get_scores()
    latency_map = health_tracker.get_latency_map()
    health_map = health_tracker.get_health_map()
    _score_backends(
        result, scores, latency_map, health_map, scenario, request_type, needs_tools, routing_guard_decisions
    )
    _apply_ml_boost(result, scores, scenario, request_type, health_map)
    result = _rank_backends(result, scores, request_type, scenario)
    result = _apply_pin(result, sticky_key, preferred_backend, recalled_backend, health_map, request_type)
    return result[:MAX_FALLBACKS]
