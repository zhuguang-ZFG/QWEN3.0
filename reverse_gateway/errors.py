"""Reverse provider error classification."""

from __future__ import annotations


ERROR_CLASSES = {
    "auth_expired",
    "quota_exceeded",
    "captcha_required",
    "rate_limited",
    "upstream_changed",
    "network_error",
    "timeout",
    "protocol_error",
    "disabled_no_adapter",
}


def classify_error(text: str) -> str:
    value = text.lower()
    if any(token in value for token in ("captcha", "verify you are human", "人机")):
        return "captcha_required"
    if any(token in value for token in ("login", "unauthorized", "401", "cookie", "session")):
        return "auth_expired"
    if any(token in value for token in ("quota", "limit exceeded", "insufficient", "anonymous_usage_exceeded")):
        return "quota_exceeded"
    if any(token in value for token in ("429", "too many", "rate limit")):
        return "rate_limited"
    if any(token in value for token in ("timeout", "timed out")):
        return "timeout"
    if any(token in value for token in ("connection", "network", "dns", "refused")):
        return "network_error"
    if any(token in value for token in ("schema", "parse", "unexpected", "changed")):
        return "upstream_changed"
    return "protocol_error"
