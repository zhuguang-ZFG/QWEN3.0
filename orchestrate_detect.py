# DEPRECATED v3.0 — coding capability retired
"""Orchestration trigger heuristics.

DEPRECATED: the multi-model orchestrator was retired in v3.0.  This module
now always reports that orchestration is not needed so callers fall back to
a direct route.
"""

from __future__ import annotations


from orchestrate_constants import (  # noqa: F401  kept for import compatibility
    COMPLEXITY_THRESHOLD,
    MULTI_DOMAIN_KEYWORDS,
    MULTI_STEP_INDICATORS,
)


def needs_orchestration(query: str, intent: dict) -> bool:
    """Return True when query complexity warrants multi-model orchestration.

    Always returns False since orchestration was retired in v3.0.
    """
    return False
