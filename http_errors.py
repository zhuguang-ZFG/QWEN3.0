"""Shared HTTP caller errors and status extraction (CQ-014 slice 8)."""

from __future__ import annotations

from typing import Optional

import httpx

import logging

logger = logging.getLogger(__name__)


class BackendError(Exception):
    """Backend call failed; carries status_code for health_tracker."""

    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


def _extract_retry_after(exc: Exception) -> int:
    if isinstance(exc, httpx.HTTPStatusError):
        try:
            return int(exc.response.headers.get("Retry-After", 0))
        except (TypeError, ValueError):
            return 0
    headers = getattr(exc, "headers", None)
    value = None
    if headers:
        try:
            value = headers.get("Retry-After")
        except AttributeError:
            value = None
    try:
        return int(value) if value else 0
    except (TypeError, ValueError):
        return 0


def _extract_code(exc: Exception) -> Optional[int]:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code
    if isinstance(exc, httpx.RequestError):
        return None
    for attr in ("status_code", "code", "status"):
        val = getattr(exc, attr, None)
        if isinstance(val, int):
            return val
    return None


# AUDIT-4-F1：可重试的瞬时错误状态码。408/429/502/503/504 是服务端瞬时/限流，
# 重试一次通常能成功；400/401/403 及其他 4xx 是永久错误，绝不重试。
RETRYABLE_STATUS_CODES = frozenset({408, 429, 502, 503, 504})


def is_retryable_error(exc: Exception) -> bool:
    """判定异常是否为可重试的瞬时错误。

    可重试：httpx.RequestError（连接重置/超时/网络抖动等）或 HTTP 状态码
    在 RETRYABLE_STATUS_CODES 中。不可重试：4xx 鉴权/格式错误及其他永久错误。
    """
    if isinstance(exc, httpx.RequestError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in RETRYABLE_STATUS_CODES
    return False


def _emit_backend_error(backend: str, error_code: int | None, error_text: str) -> None:
    try:
        from observability.metrics import record as obs_record
        from observability.events import backend_error_event
        from health_tracker import classify_failure

        failure_class = classify_failure(error_code, error_text)
        obs_record(backend_error_event("", backend, failure_class))
    except ImportError as exc:
        logger.warning("observability metrics not installed; backend error event not recorded: %s", exc)
