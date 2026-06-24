# DEPRECATED v3.0 — coding capability retired
"""Background periodic coding-backend eval (default off).

DEPRECATED v3.0: Coding capability retired. Functions are kept with safe default
returns to avoid breaking imports, but periodic coding eval is permanently disabled.
"""

from __future__ import annotations

import logging
import threading

logger = logging.getLogger("periodic_coding_eval")

_stop = threading.Event()
_thread: threading.Thread | None = None


def enabled() -> bool:
    """DEPRECATED — always False."""
    return False


def interval_seconds() -> int:
    """DEPRECATED — returns 0."""
    return 0


def run_eval_slice(*, quick: bool = True) -> int:
    """DEPRECATED — no-op, returns 0."""
    logger.debug("periodic_coding_eval is deprecated; run_eval_slice skipped")
    return 0


def start() -> None:
    """DEPRECATED — no-op."""
    global _thread
    _thread = None
    logger.debug("periodic_coding_eval is deprecated; start skipped")


def stop() -> None:
    """DEPRECATED — no-op."""
    _stop.set()
