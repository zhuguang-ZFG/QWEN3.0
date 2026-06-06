"""Anthropic /v1/messages request handling (CQ-014 slice 12)."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass

from fastapi import Request
from fastapi.responses import JSONResponse, StreamingResponse

from chat_models import Message
from chat_request_utils import extract_last_user_text, extract_system_preview
from response_builder import build_anthropic_response
from routes.anthropic_vision_sse import anthropic_vision_messages, vision_anthropic_stream


@dataclass
class ParsedAnthropicMessages:
    messages: list[Message]
    has_image: bool
    last_user_query: str
    ide_source: str
    sys_prompt_preview: str


def anthropic_rate_limit_response() -> JSONResponse:
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


def check_anthropic_rate_limit(req: Request, client_ip: str) -> JSONResponse | None:
    import rate_limiter

    ua = req.headers.get("user-agent", "")
    is_ide_client = any(
        k in ua.lower() for k in ("opencode", "opencode-ai")
    )
    multiplier = 5 if is_ide_client else 1
    if rate_limiter.check_rate_limit(client_ip, multiplier=multiplier):
        return None
    return anthropic_rate_limit_response()


async def handle_tool_messages(
    body: dict,
    *,
    native_stream: Callable,
    native_forward: Callable,
    maybe_await: Callable,
) -> StreamingResponse | JSONResponse:
    if body.get("stream", False):
        return StreamingResponse(
            native_stream(body),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
    result = await maybe_await(native_forward(body))
    return JSONResponse(result)


def parse_anthropic_messages(body: dict, detect_ide: Callable) -> ParsedAnthropicMessages:
    raw_messages = body.get("messages", [])
    messages: list[Message] = []
    has_image = False
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
            messages.append(
                Message(
                    role=role,
                    content="\n".join(text_parts) if text_parts else "[image]",
                )
            )

    if body.get("system"):
        system = body["system"]
        if isinstance(system, str):
            messages.insert(0, Message(role="system", content=system))
        elif isinstance(system, list):
            txt = " ".join(
                block.get("text", "") for block in system if block.get("type") == "text"
            )
            if txt:
                messages.insert(0, Message(role="system", content=txt))

    return ParsedAnthropicMessages(
        messages=messages,
        has_image=has_image,
        last_user_query=extract_last_user_text(raw_messages),
        ide_source=detect_ide(raw_messages),
        sys_prompt_preview=extract_system_preview(raw_messages, system=body.get("system")),
    )


async def maybe_vision_response(
    *,
    body: dict,
    parsed: ParsedAnthropicMessages,
    req_model: str,
    is_stream: bool,
    request_started_at: float,
    client_ip: str,
    call: Callable,
    maybe_await: Callable,
) -> StreamingResponse | JSONResponse | None:
    if not parsed.has_image:
        return None

    vision_msgs = anthropic_vision_messages(body.get("messages", []))
    vision_result = await maybe_await(
        call("vision_route", vision_msgs, body.get("max_tokens", 4096), parsed.ide_source)
    )
    if vision_result:
        content_text = vision_result["answer"]
        backend_used = vision_result["backend"]
        duration_ms = call("elapsed_ms", request_started_at)
        call(
            "record_request",
            parsed.last_user_query or "[vision]",
            backend_used,
            "vision",
            duration_ms,
            True,
            client_ip=client_ip,
            ide_source=parsed.ide_source,
            sys_prompt_preview=parsed.sys_prompt_preview,
        )
        if is_stream:
            return StreamingResponse(
                vision_anthropic_stream(content_text, req_model),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
            )
        return JSONResponse(
            build_anthropic_response(
                f"msg_{uuid.uuid4().hex[:24]}",
                content_text,
                backend_used,
                req_model,
            )
        )

    if is_stream:
        return StreamingResponse(
            call("anthropic_stream_passthrough", body, req_model),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
    return None
