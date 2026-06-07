"""Sync HTTP API calls extracted from http_caller (CQ-014 slice 10)."""

from __future__ import annotations

import logging
import sys
import threading
import time

import httpx

from backends import BACKENDS
from http_errors import BackendError, _emit_backend_error, _extract_code, _extract_retry_after
from http_response import _extract_answer, _extract_usage
from opencode_error_adapter import detect_context_overflow
from response_cleaner import _is_backend_error, clean_response

_log = logging.getLogger(__name__)

# ── Usage tracking (thread-safe) ───────────────────────────────────────────
_last_usage: dict[str, dict] = {}
_usage_lock = threading.Lock()
"""Per-backend last usage cache. Protected by _usage_lock for thread safety."""


def record_last_usage(backend: str, usage: dict) -> None:
    """Record usage for a backend (thread-safe)."""
    with _usage_lock:
        _last_usage[backend] = usage


def get_last_usage(backend: str) -> dict | None:
    """Return the last recorded usage dict for a backend, or None."""
    with _usage_lock:
        return _last_usage.get(backend)


def _caller():
    import http_caller

    return http_caller


def _apply_artifact_handles(messages: list[dict]) -> None:
    try:
        from context_pipeline.artifact import create_handle, should_use_handle

        for index, msg in enumerate(messages):
            if isinstance(msg, dict) and msg.get("role") == "user":
                content = msg.get("content", "")
                if isinstance(content, str) and should_use_handle(content):
                    messages[index] = {**msg, "content": create_handle(content)}
    except ImportError:
        _log.debug("context_pipeline.artifact not installed; artifact handles skipped")


def _record_success_telemetry(
    backend: str,
    payload: dict,
    fmt: str,
    latency_ms: int,
    cleaned: str,
) -> None:
    hc = _caller()
    hc.health_tracker.record_response_quality(backend, len(cleaned) if cleaned else 0)
    prompt_tokens, completion_tokens = _extract_usage(payload, fmt)
    record_last_usage(backend, {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
    })
    try:
        import budget_manager

        budget_manager.record_token_usage(backend, prompt_tokens, completion_tokens)
    except ImportError:
        _log.debug("budget_manager not installed; token usage skipped")
    try:
        from observability.events import backend_call_event
        from observability.metrics import record as obs_record

        obs_record(backend_call_event("", backend, "", latency_ms=latency_ms))
    except ImportError:
        _log.debug("observability.metrics not installed; backend_call_event skipped")


def _handle_call_error(
    backend: str,
    key_provider: str,
    selected_key: str,
    exc: Exception,
    *,
    emit_obs: bool,
) -> None:
    hc = _caller()
    if isinstance(exc, BackendError):
        hc._report_key_result(
            key_provider,
            selected_key,
            False,
            error_code=exc.status_code or 0,
            retry_after=0,
        )
        if emit_obs:
            _emit_backend_error(backend, exc.status_code, str(exc))
        raise
    if isinstance(exc, httpx.HTTPStatusError):
        error_code = exc.response.status_code
        hc.health_tracker.record_failure(
            backend, error_code=error_code, error_text=str(exc)
        )
        hc._report_key_result(
            key_provider,
            selected_key,
            False,
            error_code=error_code,
            retry_after=_extract_retry_after(exc),
        )
        if emit_obs:
            _emit_backend_error(backend, error_code, str(exc))
        # 检测上下文溢出（context overflow）：停止 fallback 并返回 OpenCode 可识别的错误
        response_text = exc.response.text if hasattr(exc.response, "text") else str(exc)
        is_overflow = detect_context_overflow(
            str(exc), status_code=error_code, response_body=response_text,
        )
        raise BackendError(str(exc), status_code=error_code, is_overflow=is_overflow) from exc
    error_code = _extract_code(exc)
    hc.health_tracker.record_failure(
        backend, error_code=error_code, error_text=str(exc)
    )
    hc._report_key_result(
        key_provider,
        selected_key,
        False,
        error_code=error_code or 0,
        retry_after=_extract_retry_after(exc),
    )
    if emit_obs:
        _emit_backend_error(backend, error_code, str(exc))
    if hc.DEBUG:
        print(f"[HTTP] {backend} error: {exc}", file=sys.stderr)
    is_overflow = detect_context_overflow(str(exc), status_code=error_code)
    raise BackendError(str(exc), status_code=error_code, is_overflow=is_overflow) from exc


def call_api(
    backend: str,
    messages: list[dict],
    max_tokens: int = 4096,
    *,
    system_prompt: str = "",
    ide: str = "",
    tools: list[dict] | None = None,
    reasoning_effort: str | None = None,
    sampling: dict | None = None,
) -> str:
    hc = _caller()
    cfg = BACKENDS.get(backend)
    if not cfg:
        raise BackendError(f"{backend} unavailable (no key)", status_code=404)
    selected_key, key_provider = hc._select_key(backend, cfg)
    if not selected_key:
        raise BackendError(f"{backend} unavailable (no key)", status_code=404)
    if hc.health_tracker.is_cooled_down(backend):
        raise BackendError(f"{backend} is cooled down", status_code=503)

    _apply_artifact_handles(messages)
    started = time.time()
    headers = hc._build_headers(cfg, key=selected_key)
    body = hc._build_body(cfg, messages, max_tokens, system_prompt, ide, tools=tools,
                          reasoning_effort=reasoning_effort, backend_name=backend,
                          sampling=sampling)
    timeout = cfg.get("timeout", 60)

    try:
        client = hc._get_client(backend, timeout)
        resp = client.post(cfg["url"], content=body, headers=headers)
        resp.raise_for_status()
        payload = resp.json()

        answer = _extract_answer(payload, cfg["fmt"])
        if not (answer or "").strip():
            hc.health_tracker.record_failure(
                backend, error_code=502, error_text="empty response body"
            )
            raise BackendError(
                f"{backend} returned empty response",
                status_code=502,
            )
        if _is_backend_error(answer):
            hc.health_tracker.record_failure(
                backend, error_code=429, error_text=answer
            )
            raise BackendError(
                f"{backend} returned error response: {answer[:60]}",
                status_code=429,
            )

        latency_ms = int((time.time() - started) * 1000)
        hc.health_tracker.record_success(backend, latency_ms)
        hc._report_key_result(key_provider, selected_key, True)
        cleaned = clean_response(answer, backend)
        _record_success_telemetry(backend, payload, cfg["fmt"], latency_ms, cleaned)
        return cleaned
    except Exception as exc:
        _handle_call_error(backend, key_provider, selected_key, exc, emit_obs=True)


def call_raw(backend: str, payload: bytes) -> dict:
    hc = _caller()
    cfg = BACKENDS.get(backend)
    if not cfg:
        raise BackendError(f"{backend} unavailable", status_code=404)
    selected_key, key_provider = hc._select_key(backend, cfg)
    if not selected_key:
        raise BackendError(f"{backend} unavailable", status_code=404)
    started = time.time()
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {selected_key}",
    }
    try:
        client = hc._get_client(backend, cfg.get("timeout", 30))
        resp = client.post(cfg["url"], content=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        latency_ms = int((time.time() - started) * 1000)
        hc.health_tracker.record_success(backend, latency_ms)
        hc._report_key_result(key_provider, selected_key, True)
        return data
    except Exception as exc:
        _handle_call_error(backend, key_provider, selected_key, exc, emit_obs=False)


def probe(backend: str) -> bool:
    try:
        call_api(
            backend,
            [{"role": "user", "content": "hi"}],
            max_tokens=1,
            system_prompt="Reply with one word.",
        )
        return True
    except BackendError:
        return False
