"""OpenCode fast path: pin backend and passthrough OpenAI SSE (tools + stream)."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator

import health_tracker
from backends import BACKENDS
from backends_constants import TOOL_CAPABLE_BACKENDS
from http_errors import BackendError
from http_request_builder import _build_body, _build_headers, _select_key
from opencode_config import (
    OPENCODE_FAST_BACKENDS,
    OPENCODE_PREFERRED_BACKEND,
    OPENCODE_TOOL_STABLE_BACKENDS,
)
from opencode_sse_adapter import (
    content_chunk as _content_chunk,
)
from opencode_sse_adapter import (
    content_delta as _content_delta,
)
from opencode_sse_adapter import (
    has_meaningful_delta as _has_meaningful_delta,
)
from opencode_sse_adapter import (
    read_timeout_for as _read_timeout_for,
)
from opencode_sse_adapter import (
    rewrite_sse_model as _rewrite_sse_model,
)
from opencode_text_tool_payload import prepare_opencode_text_tool_payload
from response_cleaner import _is_backend_error
from text_tool_extractor import (
    TEXT_TOOL_BACKENDS,
    extract_tool_calls_from_text,
)

_log = logging.getLogger(__name__)


def resolve_opencode_backend(prefer: str | None = None, *, require_tools: bool = False) -> str:
    """Pick a healthy OpenCode backend with minimal routing overhead."""
    candidates: list[str] = []
    if require_tools and prefer in OPENCODE_TOOL_STABLE_BACKENDS:
        candidates.append(prefer)
    if require_tools:
        for name in OPENCODE_TOOL_STABLE_BACKENDS:
            _append_candidate(candidates, name)
    if prefer:
        _append_candidate(candidates, prefer)
    if OPENCODE_PREFERRED_BACKEND not in candidates:
        candidates.append(OPENCODE_PREFERRED_BACKEND)
    for prefix in sorted(OPENCODE_FAST_BACKENDS):
        for name in BACKENDS:
            if name.startswith(prefix) or name == prefix:
                if name not in candidates:
                    candidates.append(name)
    if require_tools:
        for name in sorted(TOOL_CAPABLE_BACKENDS):
            if name in BACKENDS and name not in candidates:
                candidates.append(name)

    _log.info("[OPENCODE_ROUTE] candidates=%s (require_tools=%s, prefer=%s)",
              candidates[:5], require_tools, prefer)

    for name in candidates:
        cfg = BACKENDS.get(name)
        if not cfg:
            _log.debug("[OPENCODE_ROUTE] %s: no config", name)
            continue
        if require_tools and not _supports_tools(name, cfg):
            _log.debug("[OPENCODE_ROUTE] %s: tools not supported", name)
            continue
        if not health_tracker.is_cooled_down(name):
            key, _ = _select_key(name, cfg)
            if key:
                _log.info("[OPENCODE_ROUTE] selected=%s", name)
                return name
            else:
                _log.debug("[OPENCODE_ROUTE] %s: no key available", name)
        else:
            _log.debug("[OPENCODE_ROUTE] %s: cooled down", name)
    raise BackendError("No healthy OpenCode backend available", status_code=503)


def _append_candidate(candidates: list[str], name: str | None) -> None:
    if name and name not in candidates:
        candidates.append(name)


def _supports_tools(name: str, cfg: dict) -> bool:
    return (
        name in TOOL_CAPABLE_BACKENDS
        or name in TEXT_TOOL_BACKENDS
        or "tool_calls" in cfg.get("caps", [])
    )


def _ensure_not_backend_error_text(backend: str, text: str) -> None:
    if not _is_backend_error(text):
        return
    health_tracker.record_failure(backend, error_code=429, error_text=text)
    raise BackendError(
        f"{backend} returned error response: {text[:60]}",
        status_code=429,
    )


async def stream_openai_passthrough(
    *,
    backend: str,
    messages: list[dict],
    chat_id: str,
    model: str,
    tools: list[dict] | None = None,
    tool_choice: str | dict | None = None,
    max_tokens: int = 4096,
    system_prompt: str = "",
    ide: str = "OpenCode",
    reasoning_effort: str | None = None,
    sampling: dict | None = None,
    request_headers: dict | None = None,
) -> AsyncIterator[str]:
    """Stream raw OpenAI SSE from a pinned backend (preserves tool_call deltas).

    For backends in TEXT_TOOL_BACKENDS (e.g. scnet_ds_flash), injects a tool
    system prompt and extracts tool_calls from the text response at stream end.

    Args:
        request_headers: 原始 HTTP 请求头 (用于解析 OpenCode 会话上下文)。
    """
    import httpx

    # M-OC12: parse OpenCode session headers for affinity routing
    oc_ctx = None
    if request_headers:
        try:
            from opencode_request_headers import parse_opencode_headers
            oc_ctx = parse_opencode_headers(request_headers)
            if oc_ctx.has_session:
                _log.debug(
                    "[OPENCODE_DIRECT] session=%s request=%s compaction=%s",
                    oc_ctx.session_id[:12], oc_ctx.request_id[:12] if oc_ctx.request_id else "",
                    oc_ctx.is_compaction_request,
                )
        except Exception as exc:
            _log.debug("failed to parse opencode headers: %s", exc)

    cfg = BACKENDS.get(backend)
    if not cfg:
        raise BackendError(f"{backend} unavailable", status_code=404)
    selected_key, _ = _select_key(backend, cfg)
    if not selected_key:
        raise BackendError(f"{backend} unavailable (no key)", status_code=404)
    if health_tracker.is_cooled_down(backend):
        raise BackendError(f"{backend} is cooling down", status_code=503)

    effective_messages, native_tools, text_tool_prompt = prepare_opencode_text_tool_payload(
        backend, messages, tools, tool_choice
    )
    if text_tool_prompt:
        _log.info("[OPENCODE_DIRECT] %s is TEXT_TOOL_BACKEND, injected tool prompt", backend)

    headers = _build_headers(cfg, key=selected_key)
    body = _build_body(
        cfg,
        effective_messages,
        max_tokens,
        system_prompt,
        ide,
        stream=True,
        tools=native_tools,
        reasoning_effort=reasoning_effort,
        backend_name=backend,
        sampling=sampling,
    )
    if native_tools and tool_choice is not None:
        # _build_body returns bytes; parse, modify, re-encode
        if isinstance(body, bytes):
            body_dict = json.loads(body)
        else:
            body_dict = body
        body_dict["tool_choice"] = tool_choice
        body = json.dumps(body_dict).encode()

    timeout = httpx.Timeout(
        connect=15.0,
        read=_read_timeout_for(cfg),
        write=30.0,
        pool=30.0,
    )
    started = False
    emitted_payload = False
    accumulated_content = ""
    has_native_tool_calls = False
    async with httpx.AsyncClient(timeout=timeout) as client, client.stream(
        "POST", cfg["url"], headers=headers, content=body
    ) as resp:
        if resp.status_code != 200:
            detail = (await resp.aread()).decode("utf-8", errors="replace")[:300]
            raise BackendError(
                f"{backend} stream HTTP {resp.status_code}: {detail}",
                status_code=resp.status_code,
            )
        current_event = None  # Track current SSE event type
        async for line in resp.aiter_lines():
            if not line:
                continue
            # Anthropic uses event: + data: format, track event type
            if line.startswith("event: "):
                current_event = line[7:].strip()
                # Don't yield event: lines, we'll convert to OpenAI format
                continue
            if line.startswith("data: "):
                if line[6:].strip() == "[DONE]" and not emitted_payload:
                    break
                started = True
                emitted_payload = emitted_payload or _has_meaningful_delta(line)
                content_delta = _content_delta(line)
                if content_delta:
                    accumulated_content += content_delta
                    _ensure_not_backend_error_text(backend, accumulated_content)
                # Track if native tool_calls appear in the stream
                if text_tool_prompt:
                    try:
                        chunk = json.loads(line[6:].strip())
                        delta = (chunk.get("choices") or [{}])[0].get("delta", {})
                        if delta.get("tool_calls"):
                            has_native_tool_calls = True
                    except (json.JSONDecodeError, IndexError, KeyError):
                        _log.debug("failed to parse text-tool stream chunk", exc_info=True)
                yield _rewrite_sse_model(line + "\n\n", model, chat_id, backend)
                current_event = None  # Reset after processing data
            elif started:
                # Skip other lines (like empty lines between event/data pairs)
                pass

    if not emitted_payload:
        import http_caller

        answer = await asyncio.to_thread(
            http_caller.call_api,
            backend,
            effective_messages,
            max_tokens,
            system_prompt=system_prompt,
            ide=ide,
            tools=native_tools,
            reasoning_effort=reasoning_effort,
            sampling=sampling,
        )
        _ensure_not_backend_error_text(backend, answer)
        if answer:
            yield _content_chunk(chat_id, model, answer)
        yield _content_chunk(chat_id, model, "", finish=True)
        return

    # For TEXT_TOOL_BACKENDS: if no native tool_calls in stream, extract from text
    if text_tool_prompt and not has_native_tool_calls and accumulated_content:
        cleaned, tool_calls = extract_tool_calls_from_text(accumulated_content)
        if tool_calls:
            _log.info(
                "[OPENCODE_DIRECT] Extracted %d tool_calls from %s text response",
                len(tool_calls), backend,
            )
            # Emit synthetic tool_call SSE events
            tool_call_chunk = {
                "id": chat_id or "chatcmpl-text-tools",
                "object": "chat.completion.chunk",
                "model": model,
                "choices": [{
                    "index": 0,
                    "delta": {"tool_calls": tool_calls},
                    "finish_reason": None,
                }],
            }
            yield f"data: {json.dumps(tool_call_chunk, ensure_ascii=False)}\n\n"
            # Emit finish_reason: tool_calls
            finish_chunk = {
                "id": chat_id or "chatcmpl-text-tools",
                "object": "chat.completion.chunk",
                "model": model,
                "choices": [{
                    "index": 0,
                    "delta": {},
                    "finish_reason": "tool_calls",
                }],
            }
            yield f"data: {json.dumps(finish_chunk, ensure_ascii=False)}\n\n"
