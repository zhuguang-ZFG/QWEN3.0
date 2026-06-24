# DEPRECATED v3.0 — coding capability retired
"""coding_backend_scorer.py — Dynamic coding quality scoring for routing.

Loads coding_backend_scores from data/ and provides per-backend quality weights
used by routing_selector to prefer proven coding backends.

DEPRECATED v3.0: Coding capability retired. Functions are kept with safe default
returns to avoid breaking imports, but no longer load or use scoring data.
"""

from __future__ import annotations

import logging

_log = logging.getLogger(__name__)


def _load_scores() -> dict[str, float]:
    """DEPRECATED — returns empty dict."""
    _log.debug("coding_backend_scorer is deprecated; _load_scores returns empty")
    return {}


def get_coding_weight(backend: str) -> float:
    """DEPRECATED — always returns 1.0 (neutral weight)."""
    return 1.0


def get_coding_tier(backend: str) -> str:
    """DEPRECATED — always returns 'unknown'."""
    return "unknown"


def refresh() -> None:
    """DEPRECATED — no-op."""
    pass
