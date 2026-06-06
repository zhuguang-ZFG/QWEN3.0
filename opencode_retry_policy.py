"""opencode_retry_policy.py — Retry policy with exponential backoff.

复刻 OpenCode session/retry.ts (L1-202)。
提供完整的重试判定和退避延迟计算:

核心功能:
  1. is_retryable_error() — 判断异常是否可重试
  2. compute_retry_delay() — 计算重试延迟 (指数退避 + Retry-After header)
  3. classify_retry_error() — 分类重试原因 (用于 UI 提示)

退避策略 (retry.ts:35-66):
  - 基础延迟: 2000 * 2^(attempt-1) ms
  - 无 header 上限: 30s
  - 有 header 上限: 2^31-1 ms
  - 优先使用 retry-after-ms / retry-after header
"""

from __future__ import annotations

import json
import logging
import math
from email.utils import parsedate_to_datetime
from typing import Any

_log = logging.getLogger(__name__)

# ── Constants (retry.ts:26-29) ──────────────────────────────────────────────

RETRY_INITIAL_DELAY_MS = 2000
RETRY_BACKOFF_FACTOR = 2
RETRY_MAX_DELAY_NO_HEADERS_MS = 30_000  # 30 seconds
RETRY_MAX_DELAY_MS = 2_147_483_647  # max 32-bit signed int

# ── Rate limit keywords (retry.ts:129-135) ──────────────────────────────────

_RATE_LIMIT_KEYWORDS = (
    "rate increased too quickly",
    "rate limit",
    "too many requests",
)


def is_retryable_error(error: Exception) -> bool:
    """Determine if an exception is retryable per OpenCode policy.

    Ported from retry.ts retryable() (L68-151).

    Rules:
      - context_overflow → NOT retryable
      - 5xx status → always retryable
      - is_retryable marker → retryable
      - rate limit keywords in message → retryable
      - JSON error patterns → retryable
    """
    # Context overflow → never retry (retry.ts:70)
    if getattr(error, "is_overflow", False):
        return False

    status = _extract_status(error)

    # 5xx → always retry (retry.ts:75)
    if status is not None and status >= 500:
        return True

    # Explicit is_retryable marker (from SDK)
    if getattr(error, "is_retryable", False):
        return True

    # Rate limit patterns in error message
    msg = str(error)
    lower = msg.lower()
    if any(kw in lower for kw in _RATE_LIMIT_KEYWORDS):
        return True

    # JSON error patterns (retry.ts:138-151)
    json_body = _try_parse_json(msg)
    if json_body and isinstance(json_body, dict):
        # too_many_requests
        if json_body.get("type") == "error":
            err = json_body.get("error", {})
            if isinstance(err, dict):
                if err.get("type") == "too_many_requests":
                    return True
                code = err.get("code", "")
                if isinstance(code, str) and "rate_limit" in code:
                    return True
        # exhausted / unavailable
        code = json_body.get("code", "")
        if isinstance(code, str):
            code_lower = code.lower()
            if "exhausted" in code_lower or "unavailable" in code_lower:
                return True

    return False


def compute_retry_delay(
    attempt: int,
    response_headers: dict[str, str] | None = None,
) -> int:
    """Compute retry delay in milliseconds.

    Ported from retry.ts delay() (L35-66).

    Args:
        attempt: Current attempt number (1-based).
        response_headers: Optional HTTP response headers.

    Returns:
        Delay in milliseconds before next retry.
    """
    if response_headers:
        # Normalize header keys to lowercase for case-insensitive lookup
        headers = {k.lower(): v for k, v in response_headers.items()}

        # Try retry-after-ms first (retry.ts:39-45)
        retry_after_ms = headers.get("retry-after-ms")
        if retry_after_ms:
            try:
                parsed = float(retry_after_ms)
                if not math.isnan(parsed):
                    return _cap_delay(parsed)
            except (ValueError, TypeError):
                pass

        # Try retry-after (seconds or HTTP date) (retry.ts:47-59)
        retry_after = headers.get("retry-after")
        if retry_after:
            # Try as seconds
            try:
                parsed_seconds = float(retry_after)
                if not math.isnan(parsed_seconds):
                    return _cap_delay(math.ceil(parsed_seconds * 1000))
            except (ValueError, TypeError):
                pass

            # Try as HTTP date
            try:
                from datetime import datetime, timezone

                target = parsedate_to_datetime(retry_after)
                if target.tzinfo is None:
                    target = target.replace(tzinfo=timezone.utc)
                now = datetime.now(timezone.utc)
                delta_ms = (target - now).total_seconds() * 1000
                if delta_ms > 0:
                    return _cap_delay(math.ceil(delta_ms))
            except Exception as exc:
                _log.debug("retry_policy: retry-after date parsing failed", exc_info=True)

        # Exponential backoff with headers (higher cap)
        return _cap_delay(RETRY_INITIAL_DELAY_MS * (RETRY_BACKOFF_FACTOR ** (attempt - 1)))

    # No headers: exponential backoff with lower cap
    raw = RETRY_INITIAL_DELAY_MS * (RETRY_BACKOFF_FACTOR ** (attempt - 1))
    return _cap_delay(min(raw, RETRY_MAX_DELAY_NO_HEADERS_MS))


def classify_retry_error(
    error: Exception,
    provider: str = "",
) -> dict[str, Any] | None:
    """Classify a retryable error for UI display.

    Ported from retry.ts retryable() (L68-152).

    Returns:
        Dict with 'message' and optional 'action' fields, or None if not retryable.
    """
    if not is_retryable_error(error):
        return None

    msg = str(error)
    status = _extract_status(error)

    # Check response body for special error types
    body = getattr(error, "response_body", "") or ""

    # FreeUsageLimitError (retry.ts:76-88)
    if "FreeUsageLimitError" in body:
        return {
            "message": "Free usage exceeded, subscribe to Go",
            "action": {
                "reason": "free_tier_limit",
                "provider": provider,
                "title": "Free limit reached",
                "message": "Subscribe to OpenCode Go for reliable access.",
                "label": "subscribe",
            },
        }

    # GoUsageLimitError (retry.ts:89-121)
    if "GoUsageLimitError" in body:
        json_body = _try_parse_json(body)
        metadata = (json_body or {}).get("metadata", {}) if isinstance(json_body, dict) else {}
        limit_name = str(metadata.get("limitName", "")) if metadata else ""
        return {
            "message": f"{limit_name + ' ' if limit_name else ''}usage limit reached",
            "action": {
                "reason": "account_rate_limit",
                "provider": provider,
                "title": "Go limit reached",
                "message": f"{limit_name} usage limit reached.",
                "label": "open settings",
            },
        }

    # Overloaded
    if "Overloaded" in msg:
        return {"message": "Provider is overloaded"}

    return {"message": msg}


# ── Internal helpers ─────────────────────────────────────────────────────────


def _extract_status(error: Exception) -> int | None:
    """Extract HTTP status code from exception."""
    for attr in ("status_code", "code", "status"):
        val = getattr(error, attr, None)
        if isinstance(val, int):
            return val
    s = str(error)
    for code in (429, 500, 502, 503, 504):
        if str(code) in s:
            return code
    return None


def _cap_delay(ms: float) -> int:
    """Cap delay to RETRY_MAX_DELAY_MS."""
    return min(int(ms), RETRY_MAX_DELAY_MS)


def _try_parse_json(value: str) -> Any:
    """Try to parse a string as JSON, return None on failure."""
    if not value:
        return None
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return None
