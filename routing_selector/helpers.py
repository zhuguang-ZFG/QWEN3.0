"""Routing selector helper predicates and pinning utilities."""

from __future__ import annotations

import logging
import os

import budget_manager
import health_tracker
import route_scorer

from routing_selector.constants import MAX_FALLBACKS, STRONG_CODING_TOOL_BACKENDS

_log = logging.getLogger(__name__)


def _has_valid_key(name: str) -> bool:
    """Check if a backend has a configured, non-empty API key."""
    import backends_registry as reg

    cfg = reg.BACKENDS.get(name, {})
    key = cfg.get("key", "")
    if not key or key in ("none", "YOUR_KEY_HERE", ""):
        return False
    env_var = key if key.startswith("$") else None
    if env_var and not os.environ.get(env_var.lstrip("$"), ""):
        return False
    return True


def _is_retired(name: str) -> bool:
    try:
        import backend_retirement

        return backend_retirement.is_retired(name)
    except ImportError as exc:
        _log.debug("backend_retirement not installed; retirement check disabled: %s", exc)
        return False


def _is_strong_coding_tool_backend(name: str, cfg: dict | None = None) -> bool:
    cfg = cfg or {}
    return (
        name in STRONG_CODING_TOOL_BACKENDS
        or name.endswith("_code")
        or cfg.get("admission") == "code_medium_candidate"
        or cfg.get("private_code_allowed") is True
        or "code" in cfg.get("caps", [])
    )


def _prioritize(pinned: str, backends: list[str]) -> list[str]:
    """将 pinned 后端排到第一，返回新列表"""
    others = [b for b in backends if b != pinned]
    return [pinned] + others


def _pin_if_selectable(
    name: str,
    result: list[str],
    health_map: dict,
    request_type: str,
) -> list[str]:
    """Pin explicit backend first when healthy, budgeted, and selectable."""
    import backends_registry as reg

    if not name or name not in reg.BACKENDS:
        return result
    if health_tracker.is_cooled_down(name):
        return result
    if not budget_manager.is_budget_available(name):
        return result
    if health_map.get(name, "healthy") == "dead":
        return result
    state = health_tracker.get_backend_state(name)
    if not route_scorer.is_selectable(name, request_type, state):
        return result
    if name not in result:
        return ([name] + result)[:MAX_FALLBACKS]
    return _prioritize(name, result)
