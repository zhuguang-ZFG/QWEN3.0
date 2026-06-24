# DEPRECATED v3.0 — coding capability retired
"""Pinned-backend eval calls via routing_executor (health + budget telemetry).

DEPRECATED v3.0: Coding capability retired. Functions are kept with safe default
returns to avoid breaking imports, but pinned eval calls are permanently disabled.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

EVAL_SCENARIO = "eval"
EVAL_REQUEST_TYPE = "eval"


def call_pinned_backend(
    backend: str,
    messages: list[dict],
    max_tokens: int,
) -> tuple[str, str]:
    """DEPRECATED — returns ('exhausted', '') to signal eval capability retired."""
    logger.debug("eval_pinned_call is deprecated; call_pinned_backend skipped")
    return "exhausted", ""
