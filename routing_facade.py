"""Facade for gradual smart_router → routing_engine migration (CQ-014 P2).

Slice 1: classify/intent wrappers — chat hot path no longer imports smart_router.
Slice 5: ROUTE / PUBLIC_MODEL_NAME → routing_constants (status zero legacy import).
"""

from __future__ import annotations

from typing import Any

# ── Slice 1: classify / intent thin wrappers ────────────────────────────────
from router_classifier import analyze
from router_image import detect_image_intent
from router_intent import detect_thinking_intent


def router_status_payload() -> dict[str, Any]:
    """Status dict for /v1/status without importing smart_router."""
    from backends import BACKENDS
    from router_circuit_breaker import cb_status
    from routing_constants import PUBLIC_MODEL_NAME, ROUTE

    return {
        "circuit_breakers": cb_status(),
        "backends": list(BACKENDS.keys()),
        "route_table": ROUTE,
        "public_model": PUBLIC_MODEL_NAME,
        "routing_entry": "routing_engine.route",
    }


def ide_coder_pool() -> list[str]:
    """Eval-evidence ranked IDE coder pool (replaces direct POOLS['coder'] reads)."""
    import code_orchestrator
    from coding_pool_admission import tier_pool_from_evidence

    base = code_orchestrator.backend_reputation.sort_by_reputation(
        code_orchestrator.POOLS["coder"]
    )
    return tier_pool_from_evidence("coder", base)
