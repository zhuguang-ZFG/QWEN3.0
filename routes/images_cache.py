"""Process-local image generation cache.

Keyed by (prompt, size, n, variant) with TTL and max-entry eviction.
"""

from __future__ import annotations

import logging
import os
import time

from fastapi import Request

from observability import prometheus_metrics as _prom_metrics

_log = logging.getLogger(__name__)

_IMAGE_CACHE_TTL_SECONDS = int(os.environ.get("LIMA_IMAGE_CACHE_TTL_SECONDS", "3600"))
_IMAGE_CACHE_MAX_ENTRIES = int(os.environ.get("LIMA_IMAGE_CACHE_MAX_ENTRIES", "100"))
_image_cache: dict[tuple[str, str, int, str], tuple[list[dict], str, float]] = {}


def _image_cache_key(prompt: str, size: str, n: int, variant: str) -> tuple[str, str, int, str]:
    return (prompt.strip().lower(), size, n, variant)


def get_cached_image(prompt: str, size: str, n: int, variant: str = "") -> tuple[list[dict], str] | None:
    """Return cached (items, backend) or None if absent/expired."""
    if _IMAGE_CACHE_TTL_SECONDS <= 0:
        return None
    key = _image_cache_key(prompt, size, n, variant)
    entry = _image_cache.get(key)
    if not entry:
        return None
    data_items, backend, cached_at = entry
    if time.time() - cached_at > _IMAGE_CACHE_TTL_SECONDS:
        _image_cache.pop(key, None)
        return None
    _log.info("image cache hit for prompt=%s size=%s backend=%s", prompt[:40], size, backend)
    _prom_metrics.record_image_cache_lookup("hit")
    return data_items, backend


def set_cached_image(prompt: str, size: str, n: int, variant: str, data_items: list[dict], backend: str) -> None:
    """Store a successful image generation result in the cache."""
    if _IMAGE_CACHE_TTL_SECONDS <= 0:
        return
    key = _image_cache_key(prompt, size, n, variant)
    if len(_image_cache) >= _IMAGE_CACHE_MAX_ENTRIES:
        oldest = min(_image_cache, key=lambda k: _image_cache[k][2])
        _image_cache.pop(oldest, None)
    _image_cache[key] = (data_items, backend, time.time())
    _log.info(
        "image cache set for prompt=%s size=%s backend=%s entries=%d", prompt[:40], size, backend, len(_image_cache)
    )
    _prom_metrics.record_image_cache_entries(len(_image_cache))


def should_skip_cache(request: Request) -> bool:
    return request.headers.get("x-skip-cache", "").strip().lower() in ("1", "true", "yes")


def clear_cache() -> None:
    _image_cache.clear()
