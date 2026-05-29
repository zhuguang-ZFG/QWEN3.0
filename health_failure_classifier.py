"""Failure classification for health_tracker (CQ-014 slice 9)."""

from __future__ import annotations

from typing import Optional


def classify_failure(error_code: Optional[int] = None, error_text: str = "") -> str:
    lowered = (error_text or "").lower()
    if "anonymous_usage_exceeded" in lowered:
        return "manual_refresh_required"
    if error_code in (401, 403) or any(
        marker in lowered
        for marker in (
            "unauthorized",
            "forbidden",
            "invalid token",
            "invalid api key",
            "not authenticated",
        )
    ):
        return "auth_expired"
    if error_code == 429 or any(
        marker in lowered
        for marker in ("too many requests", "rate limit", "rate exceeded", "slow down")
    ):
        return "rate_limited"
    if any(
        marker in lowered
        for marker in (
            "quota",
            "usage exhausted",
            "limit exceeded",
            "billing",
            "insufficient_quota",
        )
    ):
        return "quota_exhausted"
    if any(
        marker in lowered
        for marker in (
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
        )
    ) or error_code in (502, 503, 504):
        return "network_error"
    if any(marker in lowered for marker in ("timeout", "timed out")) and error_code != 408:
        if (
            "read timed" in lowered
            or "connect timed" in lowered
            or "connection timed" in lowered
        ):
            return "network_error"
        return "timeout"
    if any(
        marker in lowered
        for marker in (
            "jsondecodeerror",
            "expecting value",
            "unterminated string",
            "unexpected token",
            "invalid json",
            "syntax error",
            "expected",
            "malformed",
            "parse error",
        )
    ):
        return "malformed_response"
    if error_code == 400:
        return "malformed_response"
    if error_code is not None and 500 <= error_code <= 599:
        return "provider_error"
    return "unknown_error"
