"""Failure classification for health_tracker (CQ-014 slice 9)."""

from __future__ import annotations

from typing import Optional

# Ordered (markers, classification) — first match wins
_TEXT_RULES: list[tuple[tuple[str, ...], str]] = [
    (("anonymous_usage_exceeded",), "manual_refresh_required"),
    (("unauthorized", "forbidden", "invalid token", "invalid api key", "not authenticated"), "auth_expired"),
    (("too many requests", "rate limit", "rate exceeded", "slow down"), "rate_limited"),
    (("quota", "usage exhausted", "limit exceeded", "billing", "insufficient_quota"), "quota_exhausted"),
    (
        (
            "connection refused",
            "connection reset",
            "connection aborted",
            "name or service not known",
            "no route to host",
            "connection timed out",
            "timed out",
            "read timed out",
            "could not resolve host",
            "temporary failure in name resolution",
            "network is unreachable",
            "connectionerror",
            "remote end closed",
        ),
        "network_error",
    ),
    (
        (
            "jsondecodeerror",
            "expecting value",
            "unterminated string",
            "unexpected token",
            "invalid json",
            "syntax error",
            "expected",
            "malformed",
            "parse error",
        ),
        "malformed_response",
    ),
]

_CODE_RULES: list[tuple[set[int], str]] = [
    ({401, 403}, "auth_expired"),
    ({429}, "rate_limited"),
    ({502, 503, 504}, "network_error"),
    ({400}, "malformed_response"),
]


def _match_text_rule(lowered: str) -> str | None:
    """Find the first matching text-based classification rule."""
    for markers, classification in _TEXT_RULES:
        if any(m in lowered for m in markers):
            return classification
    return None


def _classify_timeout(lowered: str, error_code: int | None) -> str:
    """Handle timeout vs network-error disambiguation."""
    if any(m in lowered for m in ("timeout", "timed out")) and error_code != 408:
        if any(m in lowered for m in ("read timed", "connect timed", "connection timed")):
            return "network_error"
        return "timeout"
    return ""


def classify_failure(error_code: Optional[int] = None, error_text: str = "") -> str:
    lowered = (error_text or "").lower()
    result = _match_text_rule(lowered)
    if result:
        return result
    result = _classify_timeout(lowered, error_code)
    if result:
        return result
    for codes, classification in _CODE_RULES:
        if error_code in codes:
            return classification
    if error_code is not None and 500 <= error_code <= 599:
        return "provider_error"
    return "unknown_error"
