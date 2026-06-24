# DEPRECATED v3.0 — coding capability retired
"""Health preflight and defaults for coding-backend eval runs.

DEPRECATED v3.0: Coding capability retired. Functions are kept with safe default
returns to avoid breaking imports, but eval preflight is permanently disabled.
"""

from __future__ import annotations

import logging

_log = logging.getLogger(__name__)


def eval_base_url() -> str:
    """DEPRECATED — returns empty string."""
    return ""


def quick_backend_list() -> list[str]:
    """DEPRECATED — returns empty list."""
    return []


def full_backend_list() -> list[str]:
    """DEPRECATED — returns empty list."""
    return []


def check_eval_health(base_url: str = "") -> tuple[bool, str]:
    """DEPRECATED — always returns (False, 'eval retired')."""
    return False, "eval retired"
