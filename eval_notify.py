# DEPRECATED v3.0 — coding capability retired
"""Local notifications after coding eval runs (periodic or manual hook).

DEPRECATED v3.0: Coding capability retired. Functions are kept with safe default
returns to avoid breaking imports, but eval notifications are permanently disabled.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def periodic_notify_enabled() -> bool:
    """DEPRECATED — always returns False."""
    return False


def periodic_full_eval() -> bool:
    """DEPRECATED — always returns False."""
    return False


def _build_message(*, code: int, quick: bool, source: str) -> str:
    """DEPRECATED — returns empty string."""
    return ""


def notify_eval_finished(*, code: int, quick: bool, source: str = "periodic") -> None:
    """DEPRECATED — no-op."""
    logger.debug("eval_notify is deprecated; notify_eval_finished skipped")


def schedule_status_lines() -> list[str]:
    """DEPRECATED — returns minimal status indicating eval is retired."""
    return [
        "Eval 周期任务 (已退役)",
        "LIMA_PERIODIC_CODING_EVAL=0",
        "interval_hours=0",
        "full=0 (quick only if 0)",
        "notify=0",
    ]
