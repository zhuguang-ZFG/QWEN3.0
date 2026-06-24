# DEPRECATED v3.0 — coding capability retired
"""Suppress noisy Telegram health alerts during coding eval runs.

DEPRECATED v3.0: Coding capability retired. Functions are kept with safe default
returns to avoid breaking imports, but eval quiet mode is permanently disabled.
"""

from __future__ import annotations


def set_eval_quiet(active: bool) -> None:
    """DEPRECATED — no-op."""
    pass


def eval_quiet_active() -> bool:
    """DEPRECATED — always returns False."""
    return False
