"""OpenAI and Anthropic chat endpoint adapters.

The heavy request execution path lives in routes/chat_handler.py; this module
owns HTTP parsing, rate limiting, vision short-circuiting, and protocol wrapping.
"""
from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse

from access_guard import require_private_api_key
from chat_models import ChatRequest
from chat_request_utils import extract_system_preview
from response_builder import build_response, make_chat_id
from routes.anthropic_messages_handler import (
    check_anthropic_rate_limit,
    handle_tool_messages,
    maybe_vision_response,
    parse_anthropic_messages,
)
from routes.anthropic_vision_sse import anthropic_vision_messages
from vision_handler import detect_vision_request

router = APIRouter()

_deps: dict[str, Any] = {}


def inject_deps(**kwargs: Any) -> None:
    _deps.update(kwargs)


def _dep(name: str) -> Any:
    try:
        return _deps[name]
    except KeyError as exc:
        raise RuntimeError(f"routes.chat_endpoints missing dependency: {name}") from exc


def _call(name: str, *args: Any, **kwargs: Any) -> Any:
    return _dep(name)(*args, **kwargs)


def _model_id() -> str:
    return str(_dep("model_id"))


async def _maybe_await(value: Any) -> Any:
    if hasattr(value, "__await__"):
        return await value
    return value


# Backward-compatible test hook (CQ-014 slice 12).
_anthropic_vision_messages = anthropic_vision_messages


@router.post(
    "/v1/chat/completions",
    dependencies=[Depends(require_private_api_key)],
)
async def chat_completions(request: Request):
    """OpenAI-compatible chat completions endpoint."""
    body = await request.json()
    raw_messages = body.get("messages", [])
    client_ip = _call("client_ip", request)
    ide_source = _call("detect_ide", raw_messages)

    import rate_limiter

    rate_limit_multiplier = 5 if ide_source else 1
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

    if detect_vision_request(raw_messages):
        chat_id = make_chat_id()
        t0 = time.time()
        from chat_request_utils import extract_last_user_text

        query_text = extract_last_user_text(raw_messages)
        vision_result = await _maybe_await(
            _call("vision_route", raw_messages, body.get("max_tokens", 4096), ide_source)
        )
        if vision_result:
            content = vision_result["answer"]
            backend = vision_result["backend"]
            duration_ms = int((time.time() - t0) * 1000)
            _call(
                "record_request",
                query_text or "[vision]",
                backend,
                "vision",
                duration_ms,
                True,
                client_ip=client_ip,
                ide_source=ide_source,
                sys_prompt_preview=sys_prompt_preview,
            )
            if body.get("stream", False):
                return StreamingResponse(
                    _call("stream_vision_response", chat_id, content),
                    media_type="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
                )
            return JSONResponse(build_response(chat_id, content, backend, duration_ms))

    chat_req = ChatRequest(**body)
    if body.get("thinking", False):
        chat_req.thinking = True
    return await _dep("handle_chat")(
        chat_req,
        fmt="openai",
        client_ip=client_ip,
        ide_source=ide_source,
        sys_prompt_preview=sys_prompt_preview,
        request_headers=dict(request.headers),
    )


@router.post("/v1/messages", dependencies=[Depends(require_private_api_key)])
async def anthropic_messages(req: Request):
    """Anthropic-compatible Messages endpoint."""
    request_started_at = time.time()
    body = await req.json()
    client_ip = _call("client_ip", req)

    rate_error = check_anthropic_rate_limit(req, client_ip)
    if rate_error is not None:
        return rate_error

    if body.get("tools"):
        return await handle_tool_messages(
            body,
            native_stream=lambda payload: _call("anthropic_native_stream", payload),
            native_forward=lambda payload: _call("anthropic_native_forward", payload),
            maybe_await=_maybe_await,
        )

    parsed = parse_anthropic_messages(body, _dep("detect_ide"))
    req_model = body.get("model", _model_id())
    is_stream = body.get("stream", False)

    vision_resp = await maybe_vision_response(
        body=body,
        parsed=parsed,
        req_model=req_model,
        is_stream=is_stream,
        request_started_at=request_started_at,
        client_ip=client_ip,
        call=_call,
        maybe_await=_maybe_await,
    )
    if vision_resp is not None:
        return vision_resp

    chat_req = ChatRequest(
        model=req_model.replace("[1m]", ""),
        messages=parsed.messages,
        stream=False,
        max_tokens=body.get("max_tokens", 4096),
    )

    if is_stream:
        return StreamingResponse(
            _call(
                "anthropic_stream",
                chat_req,
                req_model,
                client_ip=client_ip,
                ide_source=parsed.ide_source,
                sys_prompt_preview=parsed.sys_prompt_preview,
            ),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
    return await _dep("handle_chat")(
        chat_req,
        fmt="anthropic",
        request_model=req_model,
        client_ip=client_ip,
        ide_source=parsed.ide_source,
        sys_prompt_preview=parsed.sys_prompt_preview,
        request_headers=dict(req.headers),
    )
