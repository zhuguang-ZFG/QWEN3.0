"""OpenAI Responses API shim for OpenCode Build mode."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse

from access_guard import require_private_api_key
from chat_models import ChatRequest
from chat_request_utils import extract_system_preview
from converters.responses_api import (
    chat_completion_to_response,
    responses_body_to_chat,
    transform_chat_sse_stream,
)
from opencode_config import OPENCODE_RATE_MULTIPLIER, OPENCODE_TOOL_MODE

router = APIRouter()

_deps: dict[str, Any] = {}


def inject_deps(**kwargs: Any) -> None:
    _deps.update(kwargs)


def _dep(name: str) -> Any:
    try:
        return _deps[name]
    except KeyError as exc:
        raise RuntimeError(f"routes.responses_endpoints missing dependency: {name}") from exc


def _resolve_ide_source(messages: list[dict], request: Request) -> str:
    ide = _dep("detect_ide")(messages)
    if ide:
        return ide
    ua = request.headers.get("user-agent", "").lower()
    if "opencode" in ua:
        return "OpenCode"
    return ""


@router.post("/v1/responses", dependencies=[Depends(require_private_api_key)])
async def responses_create(request: Request):
    """OpenAI Responses API → internal chat/completions pipeline."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            status_code=400,
            content={"error": {"message": "Invalid JSON body", "type": "invalid_request_error"}},
        )
    if not isinstance(body, dict):
        return JSONResponse(
            status_code=400,
            content={"error": {"message": "Request body must be an object", "type": "invalid_request_error"}},
        )

    chat_body = responses_body_to_chat(body)
    raw_messages = chat_body.get("messages", [])
    if not raw_messages:
        return JSONResponse(
            status_code=400,
            content={"error": {"message": "Missing input", "type": "invalid_request_error"}},
        )

    client_ip = _dep("client_ip")(request)
    ide_source = _resolve_ide_source(raw_messages, request)

    import rate_limiter

    rate_limit_multiplier = OPENCODE_RATE_MULTIPLIER if ide_source else 1
    if not rate_limiter.check_rate_limit(client_ip, multiplier=rate_limit_multiplier):
        return JSONResponse(
            status_code=429,
            content={
                "error": {
                    "message": "Rate limit exceeded. Try again later.",
                    "type": "rate_limit_error",
                }
            },
        )

    sys_prompt_preview = extract_system_preview(raw_messages)
    chat_req = ChatRequest(**chat_body)
    request_headers = dict(request.headers)
    model_name = chat_body.get("model", "lima-1.3")
    stream = bool(chat_body.get("stream", False))
    has_tools = bool(chat_body.get("tools"))

    # OpenCode Build: tools + stream → direct OpenAI path (not Anthropic forward).
    if has_tools and stream and ide_source == "OpenCode" and OPENCODE_TOOL_MODE == "direct":
        pass  # fall through to handle_chat below
    elif has_tools and stream:
        from routes.chat_endpoints import _openai_to_anthropic_tool_body, _wrap_tool_stream_with_recording

        anthropic_body = _openai_to_anthropic_tool_body(chat_body)
        return StreamingResponse(
            _wrap_tool_stream_with_recording(
                _dep("anthropic_native_stream")(anthropic_body),
                raw_messages,
                client_ip,
                ide_source,
                sys_prompt_preview,
            ),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
    elif has_tools and not stream:
        from routes.chat_endpoints import (
            _convert_anthropic_tool_response_to_openai,
            _openai_to_anthropic_tool_body,
            _maybe_await,
        )
        import time

        tool_t0 = time.time()
        result = await _maybe_await(
            _dep("anthropic_native_forward")(_openai_to_anthropic_tool_body(chat_body))
        )
        openai_result = _convert_anthropic_tool_response_to_openai(result, chat_body)
        return JSONResponse(chat_completion_to_response(openai_result))

    handle_chat = _dep("handle_chat")
    result = await handle_chat(
        chat_req,
        fmt="openai",
        request_model=model_name,
        client_ip=client_ip,
        ide_source=ide_source,
        sys_prompt_preview=sys_prompt_preview,
        request_headers=request_headers,
    )

    if isinstance(result, StreamingResponse):
        return StreamingResponse(
            transform_chat_sse_stream(
                result.body_iterator,
                model=model_name,
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    if isinstance(result, JSONResponse):
        try:
            payload = json.loads(result.body)
        except (TypeError, json.JSONDecodeError):
            return result
        if "choices" in payload:
            return JSONResponse(chat_completion_to_response(payload))
        return result

    return result
