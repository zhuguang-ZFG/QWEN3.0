"""Sync HTTP API calls extracted from http_caller (CQ-014 slice 10)."""

from __future__ import annotations

import json
import logging
import sys
import time
from typing import NoReturn

import httpx
from response_cleaner import clean_response, _is_backend_error

from backends_registry import BACKENDS
from http_errors import BackendError, _emit_backend_error, _extract_code, _extract_retry_after
from http_response import _extract_answer, _extract_usage

_log = logging.getLogger(__name__)


def _extract_answer_from_sse(text: str) -> str:
    """Extract answer content from SSE streaming response chunks."""
    content_parts = []
    reasoning_parts = []
    for line in text.split("\n"):
        if not line.startswith("data: "):
            continue
        data_str = line[6:].strip()
        if data_str == "[DONE]":
            break
        try:
            chunk = json.loads(data_str)
            choices = chunk.get("choices", [])
            if choices:
                delta = choices[0].get("delta", {})
                if delta.get("content"):
                    content_parts.append(delta["content"])
                if delta.get("reasoning_content"):
                    reasoning_parts.append(delta["reasoning_content"])
        except (json.JSONDecodeError, KeyError, IndexError):
            continue
    return "".join(content_parts) or "".join(reasoning_parts)


def _caller():
    import http_caller

    return http_caller


def _apply_artifact_handles(messages: list[dict]) -> None:
    """Artifact handle compression retired with context_pipeline.artifact (CP-1)."""
    return


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
    try:
        import budget_manager

        budget_manager.record_token_usage(backend, prompt_tokens, completion_tokens)
    except ImportError as exc:
        _log.warning("budget_manager not installed; token usage not recorded: %s", exc)
    try:
        from observability.metrics import record as obs_record
        from observability.events import backend_call_event

        obs_record(backend_call_event("", backend, "", latency_ms=latency_ms))
    except ImportError as exc:
        _log.warning("observability.metrics not installed; backend_call_event not recorded: %s", exc)


def _handle_call_error(
    backend: str,
    key_provider: str,
    selected_key: str,
    exc: Exception,
    *,
    emit_obs: bool,
) -> NoReturn:
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
        hc.health_tracker.record_failure(backend, error_code=error_code, error_text=str(exc))
        hc._report_key_result(
            key_provider,
            selected_key,
            False,
            error_code=error_code,
            retry_after=_extract_retry_after(exc),
        )
        if emit_obs:
            _emit_backend_error(backend, error_code, str(exc))
        raise BackendError(str(exc), status_code=error_code) from exc
    error_code = _extract_code(exc)
    hc.health_tracker.record_failure(backend, error_code=error_code, error_text=str(exc))
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
    raise BackendError(str(exc), status_code=error_code) from exc


def _process_response(
    text: str,
    backend: str,
    cfg: dict,
    started: float,
    key_provider: str,
    selected_key: str,
    hc,
) -> str:
    """Parse HTTP response text, validate content, and record telemetry."""
    try:
        payload = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        content = _extract_answer_from_sse(text)
        if content:
            if _is_backend_error(content):
                hc.health_tracker.record_failure(backend, error_code=429, error_text=content)
                raise BackendError(f"{backend} returned error response: {content[:60]}", status_code=429)
            latency_ms = (time.time() - started) * 1000
            hc.health_tracker.record_success(backend, latency_ms)
            hc._report_key_result(key_provider, selected_key, True)
            cleaned = clean_response(content, backend)
            hc.health_tracker.record_response_quality(backend, len(cleaned) if cleaned else 0)
            return cleaned
        hc.health_tracker.record_failure(backend, error_code=502, error_text="invalid JSON and no SSE content")
        raise BackendError(f"{backend} returned unparseable response", status_code=502)

    answer = _extract_answer(payload, cfg["fmt"])
    if not (answer or "").strip():
        hc.health_tracker.record_failure(backend, error_code=502, error_text="empty response body")
        raise BackendError(f"{backend} returned empty response", status_code=502)
    if _is_backend_error(answer):
        hc.health_tracker.record_failure(backend, error_code=429, error_text=answer)
        raise BackendError(f"{backend} returned error response: {answer[:60]}", status_code=429)

    latency_ms = int((time.time() - started) * 1000)
    hc.health_tracker.record_success(backend, latency_ms)
    hc._report_key_result(key_provider, selected_key, True)
    cleaned = clean_response(answer, backend)
    _record_success_telemetry(backend, payload, cfg["fmt"], latency_ms, cleaned)
    return cleaned


def call_api(
    backend: str,
    messages: list[dict],
    max_tokens: int = 4096,
    *,
    system_prompt: str = "",
    ide: str = "",
    tools: list[dict] | None = None,
    ignore_cooldown: bool = False,
) -> str:
    hc = _caller()
    cfg = BACKENDS.get(backend)
    if not cfg:
        raise BackendError(f"{backend} unavailable (no key)", status_code=404)
    selected_key, key_provider = hc._select_key(backend, cfg)
    if not selected_key:
        raise BackendError(f"{backend} unavailable (no key)", status_code=404)
    if not ignore_cooldown and hc.health_tracker.is_cooled_down(backend):
        raise BackendError(f"{backend} is cooled down", status_code=503)

    _apply_artifact_handles(messages)
    started = time.time()
    headers = hc._build_headers(cfg, key=selected_key)
    body = hc._build_body(cfg, messages, max_tokens, system_prompt, ide, tools=tools)
    timeout = cfg.get("timeout", 60)

    try:
        with hc._build_client(backend, timeout) as client:
            resp = client.post(cfg["url"], content=body, headers=headers)
            resp.raise_for_status()
            return _process_response(
                resp.text,
                backend,
                cfg,
                started,
                key_provider,
                selected_key,
                hc,
            )
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
        with hc._build_client(backend, cfg.get("timeout", 30)) as client:
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
