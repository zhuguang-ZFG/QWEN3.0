"""Small async helpers shared by route modules."""

from __future__ import annotations

from typing import Any


async def maybe_await(value: Any) -> Any:
    if hasattr(value, "__await__"):
        return await value
    return value
