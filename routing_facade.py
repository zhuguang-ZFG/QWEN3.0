"""Facade for gradual smart_router → routing_engine migration (CQ-014 P2).

Slice 1: classify/intent wrappers — chat hot path no longer imports smart_router.
Slice 2 (future): call_api / cb_* → http_caller + router_circuit_breaker.
"""

from __future__ import annotations

from typing import Any

# ── Slice 1: classify / intent thin wrappers ────────────────────────────────
from router_classifier import analyze  # noqa: F401  (re-export for call sites)
from router_image import detect_image_intent  # noqa: F401
from router_intent import detect_thinking_intent, get_thinking_backend  # noqa: F401


def router_status_payload() -> dict[str, Any]:
    """Status dict for /v1/status without importing smart_router at call sites."""
    from backends import BACKENDS
    from router_circuit_breaker import cb_status
    # ROUTE table still lives on smart_router during migration
    import smart_router

    return {
        "circuit_breakers": cb_status(),
        "backends": list(BACKENDS.keys()),
        "route_table": smart_router.ROUTE,
        "public_model": smart_router.PUBLIC_MODEL_NAME,
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
