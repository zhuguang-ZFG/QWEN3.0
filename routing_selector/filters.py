"""Routing selector backend filtering helpers."""

from __future__ import annotations

import budget_manager
import health_tracker
import router_v3

from routing_selector.constants import _NATIVE_TOOL_PREFER
from routing_selector.helpers import _is_retired


def _filter_tool_backends(result: list[str], scenario: str) -> list[str]:
    """Filter and rank backends that advertise tool_calls capability."""
    import backends_registry as reg

    result = [b for b in result if "tool_calls" in reg.BACKENDS.get(b, {}).get("caps", [])]
    if len(result) < 8:
        all_capable = [
            n
            for n, c in reg.BACKENDS.items()
            if "tool_calls" in c.get("caps", [])
            and not health_tracker.is_cooled_down(n)
            and budget_manager.is_budget_available(n)
            and not _is_retired(n)
        ]
        for b in all_capable:
            if b not in result:
                result.append(b)
    result.sort(
        key=lambda b: (
            0 if any(p in b for p in _NATIVE_TOOL_PREFER) else 1,
            reg.BACKENDS.get(b, {}).get("timeout", 30),
        )
    )
    return result


def _build_initial_pool(pool_key: str, health_map: dict, needs_tools: bool, scenario: str) -> list[str]:
    """Select backends from the pool, filter retired/budget/tool constraints."""
    result = router_v3.select_backends(pool_key, health_map)
    result = [b for b in result if not _is_retired(b)]
    if needs_tools:
        result = _filter_tool_backends(result, scenario)
    return [b for b in result if budget_manager.is_budget_available(b)]


def _apply_guard_decisions(result: list[str]) -> tuple[list[str], dict[str, dict]]:
    """Filter quarantined backends and return active decisions."""
    try:
        from observability.routing_guard import backend_guard_snapshot

        raw = backend_guard_snapshot().get("decisions", {})
        decisions = raw if isinstance(raw, dict) else {}
    except ImportError:
        decisions = {}
    non_quarantined = [b for b in result if decisions.get(b, {}).get("status") != "quarantined"]
    return (non_quarantined if non_quarantined else result), decisions
