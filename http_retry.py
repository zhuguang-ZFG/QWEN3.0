"""Shared HTTP transient-error retry helpers (AUDIT-4-F1).

Retries transient errors (network / 408 / 429 / 502 / 503 / 504) a bounded
number of times with exponential backoff + jitter. During retries it does NOT
call _handle_call_error/record_failure (avoids double-penalising cooldown);
non-retryable errors (400/401/403 etc.) raise immediately; on exhaustion the
last exception is re-raised so the caller's _handle_call_error records one
failure.
"""

from __future__ import annotations

import asyncio
import logging
import os
import random
import time

from http_errors import BackendError, _extract_retry_after, is_retryable_error

_log = logging.getLogger(__name__)


def _max_retries() -> int:
    """Transient-error retry count (default 2, override via LIMA_HTTP_MAX_RETRIES)."""
    try:
        return max(0, int(os.environ.get("LIMA_HTTP_MAX_RETRIES", "2")))
    except (TypeError, ValueError):
        return 2


def _retry_backoff_seconds(attempt: int, exc: Exception) -> float:
    """Exponential backoff + jitter; 429 honours Retry-After (capped)."""
    retry_after = _extract_retry_after(exc)
    if retry_after > 0:
        return float(min(retry_after, 30))
    return 0.5 * (2**attempt) + random.uniform(0, 0.25)


def _log_retry(backend: str, attempt: int, total: int, delay: float, exc: Exception) -> None:
    _log.warning(
        "backend %s transient error (attempt %d/%d), retrying in %.2fs: %s",
        backend,
        attempt + 1,
        total,
        delay,
        type(exc).__name__,
    )


def _post_with_retry(client, url, *, content, headers, backend):
    """Sync POST with bounded transient-error retry."""
    retries = _max_retries()
    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        try:
            resp = client.post(url, content=content, headers=headers)
            resp.raise_for_status()
            return resp
        except Exception as exc:
            last_exc = exc
            if attempt >= retries or not is_retryable_error(exc):
                raise
            delay = _retry_backoff_seconds(attempt, exc)
            _log_retry(backend, attempt, retries + 1, delay, exc)
            time.sleep(delay)
    if last_exc is not None:
        raise last_exc
    raise BackendError(f"{backend} retry loop exhausted", status_code=None)


async def _post_with_retry_async(client, url, *, content, headers, backend):
    """Async POST with bounded transient-error retry (mirrors post_with_retry)."""
    retries = _max_retries()
    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        try:
            resp = await client.post(url, content=content, headers=headers)
            resp.raise_for_status()
            return resp
        except Exception as exc:
            last_exc = exc
            if attempt >= retries or not is_retryable_error(exc):
                raise
            delay = _retry_backoff_seconds(attempt, exc)
            _log_retry(backend, attempt, retries + 1, delay, exc)
            await asyncio.sleep(delay)
    if last_exc is not None:
        raise last_exc
    raise BackendError(f"{backend} retry loop exhausted", status_code=None)
