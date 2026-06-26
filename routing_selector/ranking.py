"""Routing selector ranking and pinning helpers."""

from __future__ import annotations

import random

import budget_manager
import health_tracker
import route_scorer
import sticky_session

from routing_selector.helpers import _pin_if_selectable, _prioritize


def _rank_backends(result: list[str], scores: dict, request_type: str, scenario: str) -> list[str]:
    """Sort, cool-down filter, selectability filter and rank candidates."""
    result.sort(key=lambda b: -(scores.get(b, 50) * budget_manager.get_budget_priority(b) + random.uniform(0, 3)))
    result = [b for b in result if not health_tracker.is_cooled_down(b)]
    states = {b: health_tracker.get_backend_state(b) for b in result}
    result = [b for b in result if route_scorer.is_selectable(b, request_type, states.get(b))]
    return route_scorer.rank_backends(
        result,
        request_type,
        scenario,
        health_scores=scores,
        states=states,
        latency_map=health_tracker.get_latency_map(),
    )


def _apply_pin(
    result: list[str],
    sticky_key: str | None,
    preferred_backend: str,
    recalled_backend: str | None,
    health_map: dict,
    request_type: str,
) -> list[str]:
    """Apply sticky/preferred/recalled backend pinning."""
    if sticky_key:
        pinned = sticky_session.get_pinned_backend(sticky_key)
        if (
            pinned
            and health_map.get(pinned, "healthy") != "dead"
            and route_scorer.is_selectable(
                pinned,
                request_type,
                health_tracker.get_backend_state(pinned),
            )
        ):
            return _prioritize(pinned, result)
    if preferred_backend:
        return _pin_if_selectable(preferred_backend, result, health_map, request_type)
    if recalled_backend and recalled_backend in result:
        if health_map.get(recalled_backend, "healthy") != "dead" and route_scorer.is_selectable(
            recalled_backend,
            request_type,
            health_tracker.get_backend_state(recalled_backend),
        ):
            return _prioritize(recalled_backend, result)
    return result
