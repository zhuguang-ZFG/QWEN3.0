"""Retired channel registry and startup cleanup helpers."""

from __future__ import annotations

from collections.abc import MutableMapping

RETIRED_CHANNELS = frozenset({"telegram", "channel_gateway"})
RETIRED_ROUTE_PREFIXES = frozenset({"/telegram", "/channel"})


def mark_retired_modules(loaded_modules: MutableMapping[str, bool]) -> None:
    """Expose retired channels as intentionally unavailable in health output."""
    for channel in RETIRED_CHANNELS:
        loaded_modules[channel] = False
