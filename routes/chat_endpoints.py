"""OpenAI and Anthropic chat endpoint adapters.

The heavy request execution path intentionally remains in server._handle_chat
for compatibility; this module owns HTTP parsing, rate limiting, vision
short-circuiting, and protocol-specific response wrapping.
"""
from __future__ import annotations

import asyncio
import json
import time
import uuid
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse

from access_guard import require_private_api_key
from chat_models import ChatRequest, Message
from chat_request_utils import extract_last_user_text, extract_system_preview
from response_builder import build_anthropic_response, build_response, make_chat_id
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
    import rate_limiter

    ua = req.headers.get("user-agent", "")
    is_ide_client = any(k in ua.lower() for k in ("claude-code", "continue", "cursor", "copilot"))
    rate_limit_multiplier = 5 if is_ide_client else 1
    if not rate_limiter.check_rate_limit(client_ip, multiplier=rate_limit_multiplier):
        return JSONResponse(
            status_code=429,
            content={
                "type": "error",
                "error": {
                    "type": "rate_limit_error",
                    "message": "Rate limit exceeded. Try again later.",
                },
            },
        )

    raw_messages = body.get("messages", [])
    last_user_query = extract_last_user_text(raw_messages)

    if body.get("tools"):
        if body.get("stream", False):
            return StreamingResponse(
                _call("anthropic_native_stream", body),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
            )
        result = await _maybe_await(_call("anthropic_native_forward", body))
        return JSONResponse(result)

    has_image = False
    messages: list[Message] = []
    for msg in raw_messages:
        role = msg.get("role", "")
        if role not in ("user", "assistant"):
            continue
        content = msg.get("content", "")
        if isinstance(content, str):
            messages.append(Message(role=role, content=content))
        elif isinstance(content, list):
            text_parts = []
            for block in content:
                if block.get("type") == "text":
                    text_parts.append(block.get("text", ""))
                elif block.get("type") == "image":
                    has_image = True
            messages.append(Message(role=role, content="\n".join(text_parts) if text_parts else "[image]"))

    if body.get("system"):
        system = body["system"]
        if isinstance(system, str):
            messages.insert(0, Message(role="system", content=system))
        elif isinstance(system, list):
            txt = " ".join(block.get("text", "") for block in system if block.get("type") == "text")
            if txt:
                messages.insert(0, Message(role="system", content=txt))

    req_model = body.get("model", _model_id())
    is_stream = body.get("stream", False)
    ide_source = _call("detect_ide", raw_messages)
    sys_prompt_preview = extract_system_preview(raw_messages, system=body.get("system"))

    if has_image:
        vision_msgs = _anthropic_vision_messages(raw_messages)
        vision_result = await _maybe_await(
            _call("vision_route", vision_msgs, body.get("max_tokens", 4096), ide_source)
        )
        if vision_result:
            content_text = vision_result["answer"]
            backend_used = vision_result["backend"]
            duration_ms = _call("elapsed_ms", request_started_at)
            _call(
                "record_request",
                last_user_query or "[vision]",
                backend_used,
                "vision",
                duration_ms,
                True,
                client_ip=client_ip,
                ide_source=ide_source,
                sys_prompt_preview=sys_prompt_preview,
            )
            if is_stream:
                return StreamingResponse(
                    _vision_anthropic_stream(content_text, req_model),
                    media_type="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
                )
            return JSONResponse(
                build_anthropic_response(f"msg_{uuid.uuid4().hex[:24]}", content_text, backend_used, req_model)
            )
        if is_stream:
            return StreamingResponse(
                _call("anthropic_stream_passthrough", body, req_model),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
            )

    chat_req = ChatRequest(
        model=req_model.replace("[1m]", ""),
        messages=messages,
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
                ide_source=ide_source,
                sys_prompt_preview=sys_prompt_preview,
            ),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
    return await _dep("handle_chat")(
        chat_req,
        fmt="anthropic",
        request_model=req_model,
        client_ip=client_ip,
        ide_source=ide_source,
        sys_prompt_preview=sys_prompt_preview,
        request_headers=dict(req.headers),
    )


def _anthropic_vision_messages(raw_messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    vision_msgs: list[dict[str, Any]] = []
    for msg in raw_messages:
        if not isinstance(msg, dict) or msg.get("role") not in ("user", "assistant"):
            continue
        content = msg.get("content", "")
        if not isinstance(content, list):
            vision_msgs.append({"role": msg["role"], "content": content})
            continue
        openai_blocks = []
        for block in content:
            if block.get("type") == "text":
                openai_blocks.append({"type": "text", "text": block.get("text", "")})
            elif block.get("type") == "image":
                source = block.get("source", {})
                if source.get("type") == "base64":
                    media_type = source.get("media_type", "image/jpeg")
                    data = source.get("data", "")
                    openai_blocks.append(
                        {"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{data}"}}
                    )
            else:
                openai_blocks.append(block)
        vision_msgs.append({"role": msg["role"], "content": openai_blocks})
    return vision_msgs


async def _vision_anthropic_stream(content_text: str, req_model: str):
    msg_id = f"msg_{uuid.uuid4().hex[:24]}"
    yield (
        "event: message_start\n"
        f"data: {json.dumps({'type': 'message_start', 'message': {'id': msg_id, 'type': 'message', 'role': 'assistant', 'model': req_model, 'content': [], 'stop_reason': None, 'usage': {'input_tokens': 10, 'output_tokens': 0}}})}\n\n"
    )
    yield (
        "event: content_block_start\n"
        f"data: {json.dumps({'type': 'content_block_start', 'index': 0, 'content_block': {'type': 'text', 'text': ''}})}\n\n"
    )
    chunk_size = 30
    for i in range(0, len(content_text), chunk_size):
        chunk = content_text[i:i + chunk_size]
        yield (
            "event: content_block_delta\n"
            f"data: {json.dumps({'type': 'content_block_delta', 'index': 0, 'delta': {'type': 'text_delta', 'text': chunk}}, ensure_ascii=False)}\n\n"
        )
        await asyncio.sleep(0.01)
    yield f"event: content_block_stop\ndata: {json.dumps({'type': 'content_block_stop', 'index': 0})}\n\n"
    yield (
        "event: message_delta\n"
        f"data: {json.dumps({'type': 'message_delta', 'delta': {'stop_reason': 'end_turn', 'stop_sequence': None}, 'usage': {'output_tokens': len(content_text) // 4}})}\n\n"
    )
    yield f"event: message_stop\ndata: {json.dumps({'type': 'message_stop'})}\n\n"
