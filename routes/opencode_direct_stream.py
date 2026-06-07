"""OpenCode fast path: pin backend and passthrough OpenAI SSE (tools + stream)."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import AsyncIterator

import health_tracker
from backends import BACKENDS
from backends_constants import TOOL_CAPABLE_BACKENDS
from http_errors import BackendError
from http_request_builder import _build_body, _build_headers, _select_key
from opencode_config import (
    OPENCODE_DIRECT_STREAM_READ_TIMEOUT,
    OPENCODE_FAST_BACKENDS,
    OPENCODE_PREFERRED_BACKEND,
)
from text_tool_extractor import (
    TEXT_TOOL_BACKENDS,
    build_tool_system_prompt,
    extract_tool_calls_from_text,
)

_log = logging.getLogger(__name__)


def resolve_opencode_backend(prefer: str | None = None, *, require_tools: bool = False) -> str:
    """Pick a healthy OpenCode backend with minimal routing overhead."""
    candidates: list[str] = []
    if prefer:
        candidates.append(prefer)
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
    for name in candidates:
        cfg = BACKENDS.get(name)
        if not cfg:
            continue
        if require_tools and not _supports_tools(name, cfg):
            continue
        if not health_tracker.is_cooled_down(name):
            key, _ = _select_key(name, cfg)
            if key:
                return name
    raise BackendError("No healthy OpenCode backend available", status_code=503)


def _supports_tools(name: str, cfg: dict) -> bool:
    return (
        name in TOOL_CAPABLE_BACKENDS
        or name in TEXT_TOOL_BACKENDS
        or "tool_calls" in cfg.get("caps", [])
    )


def _rewrite_sse_model(line: str, model: str, chat_id: str, backend: str = "") -> str:
    """Rewrite model/id in SSE chunk AND normalize non-standard finish_reason.

    Also applies reasoning_content passthrough and tool_call normalization.
    """
    if not line.startswith("data: "):
        return line
    payload = line[6:].strip()
    if payload == "[DONE]":
        return line
    try:
        chunk = json.loads(payload)
    except json.JSONDecodeError:
        return line
    if isinstance(chunk, dict):
        chunk["model"] = model
        if chat_id:
            chunk["id"] = chat_id
        # Normalize finish_reason for OpenCode compatibility
        try:
            from opencode_protocol_adapter import normalize_sse_chunk
            chunk = normalize_sse_chunk(chunk)
        except (ImportError, Exception):
            _log.debug("opencode_direct_stream: protocol adapter not available", exc_info=True)
        # Passthrough reasoning_content (ensure not filtered)
        try:
            from opencode_reasoning_bridge import passthrough_reasoning_content
            chunk = passthrough_reasoning_content(chunk, backend)
        except (ImportError, Exception):
            _log.debug("opencode_direct_stream: reasoning bridge not available", exc_info=True)
        # Normalize tool calls (repair malformed JSON arguments, ensure fields)
        try:
            from opencode_tool_splitter import normalize_tool_calls_in_chunk
            chunk = normalize_tool_calls_in_chunk(chunk)
        except (ImportError, Exception):
            _log.debug("opencode_direct_stream: tool splitter not available", exc_info=True)
        return f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
    return line


def _read_timeout_for(cfg: dict) -> float:
    backend_timeout = float(cfg.get("timeout", 90))
    return max(backend_timeout, OPENCODE_DIRECT_STREAM_READ_TIMEOUT)


def _content_chunk(chat_id: str, model: str, content: str, *, finish: bool = False) -> str:
    chunk = {
        "id": chat_id,
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": model,
        "choices": [{
            "index": 0,
            "delta": {} if finish else {"role": "assistant", "content": content},
            "finish_reason": "stop" if finish else None,
        }],
    }
    return f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"


def _has_meaningful_delta(line: str) -> bool:
    if not line.startswith("data: "):
        return False
    payload = line[6:].strip()
    if payload == "[DONE]":
        return False
    try:
        chunk = json.loads(payload)
    except json.JSONDecodeError:
        return False
    choice = (chunk.get("choices") or [{}])[0]
    delta = choice.get("delta") or {}
    return bool(delta.get("content") or delta.get("tool_calls") or delta.get("reasoning_content"))


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

    # For TEXT_TOOL_BACKENDS: inject tool system prompt so model outputs tool calls as text
    is_text_tool = backend in TEXT_TOOL_BACKENDS and tools
    effective_messages = messages
    if is_text_tool:
        tool_prompt = build_tool_system_prompt(tools)
        effective_messages = [{"role": "system", "content": tool_prompt}] + list(messages)
        _log.info("[OPENCODE_DIRECT] %s is TEXT_TOOL_BACKEND, injected tool prompt", backend)

    headers = _build_headers(cfg, key=selected_key)
    body = _build_body(
        cfg,
        effective_messages,
        max_tokens,
        system_prompt,
        ide,
        stream=True,
        tools=None if is_text_tool else tools,  # Don't send native tools for TEXT_TOOL backends
        reasoning_effort=reasoning_effort,
        backend_name=backend,
    )
    if tools and tool_choice is not None and not is_text_tool:
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
        async for line in resp.aiter_lines():
            if not line:
                continue
            if line.startswith("data: "):
                if line[6:].strip() == "[DONE]" and not emitted_payload:
                    break
                started = True
                emitted_payload = emitted_payload or _has_meaningful_delta(line)
                # Track if native tool_calls appear in the stream
                if is_text_tool:
                    try:
                        chunk = json.loads(line[6:].strip())
                        delta = (chunk.get("choices") or [{}])[0].get("delta", {})
                        if delta.get("tool_calls"):
                            has_native_tool_calls = True
                        if delta.get("content"):
                            accumulated_content += delta["content"]
                    except (json.JSONDecodeError, IndexError, KeyError):
                        pass
                yield _rewrite_sse_model(line + "\n\n", model, chat_id, backend)
            elif started:
                yield line + "\n\n"

    if not emitted_payload:
        import http_caller

        answer = await asyncio.to_thread(
            http_caller.call_api,
            backend,
            effective_messages,
            max_tokens,
            system_prompt=system_prompt,
            ide=ide,
            tools=None if is_text_tool else tools,
            reasoning_effort=reasoning_effort,
        )
        if answer:
            yield _content_chunk(chat_id, model, answer)
        yield _content_chunk(chat_id, model, "", finish=True)
        return

    # For TEXT_TOOL_BACKENDS: if no native tool_calls in stream, extract from text
    if is_text_tool and not has_native_tool_calls and accumulated_content:
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
