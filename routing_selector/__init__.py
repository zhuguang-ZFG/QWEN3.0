"""Layer 2: backend selection and ranking (CQ-014 slice 11)."""

from routing_selector.constants import (
    MAX_FALLBACKS,
    STRONG_CODING_TOOL_BACKENDS,
    _STATIC_LATENCY_ESTIMATE,
)
from routing_selector.core import select
from routing_selector.helpers import (
    _has_valid_key,
    _is_retired,
    _is_strong_coding_tool_backend,
    _pin_if_selectable,
    _prioritize,
)

__all__ = [
    "select",
    "MAX_FALLBACKS",
    "STRONG_CODING_TOOL_BACKENDS",
    "_STATIC_LATENCY_ESTIMATE",
    "_has_valid_key",
    "_is_retired",
    "_is_strong_coding_tool_backend",
    "_pin_if_selectable",
    "_prioritize",
]
