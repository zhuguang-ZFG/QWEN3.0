"""OpenAI and Anthropic chat endpoint adapters.

The heavy request execution path lives in routes/chat_handler.py; this module
owns HTTP parsing, rate limiting, vision short-circuiting, and protocol wrapping.
"""
import json
import time
import uuid
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse

from access_guard import require_private_api_key
from chat_models import ChatRequest
from chat_request_utils import extract_system_preview
from response_builder import build_response, make_chat_id
from routes.json_body import read_json_object
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


async def _read_json_body(request: Request) -> dict[str, Any] | JSONResponse:
    return await read_json_object(request, openai_error=True)


# Backward-compatible test hook (CQ-014 slice 12).
_anthropic_vision_messages = anthropic_vision_messages


@router.post(
    "/v1/chat/completions",
    dependencies=[Depends(require_private_api_key)],
)
async def chat_completions(request: Request):
    """OpenAI-compatible chat completions endpoint."""
    body = await _read_json_body(request)
    if isinstance(body, JSONResponse):
        return body
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

    # Route tool requests through the dedicated tool forwarding pipeline
    # (GPT-4o/GitHub → real tool calls, unlike open-source models)
    if body.get("tools") and body.get("stream"):
        return StreamingResponse(
            _call("anthropic_native_stream", _openai_to_anthropic_tool_body(body)),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
    if body.get("tools"):
        result = await _maybe_await(
            _call("anthropic_native_forward", _openai_to_anthropic_tool_body(body))
        )
        return JSONResponse(_convert_anthropic_tool_response_to_openai(result, body))

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
    body = await _read_json_body(req)
    if isinstance(body, JSONResponse):
        return body
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


# ── OpenAI ↔ Anthropic tool format conversion ─────────────────────────────────

def _openai_to_anthropic_tool_body(body: dict) -> dict:
    """Convert OpenAI-format tool request to Anthropic-format for tool_forward pipeline."""
    tools = []
    for t in body.get("tools", []):
        fn = t.get("function", {})
        tools.append({
            "name": fn.get("name", ""),
            "description": fn.get("description", ""),
            "input_schema": fn.get("parameters", {"type": "object", "properties": {}}),
        })
    messages, system = _convert_openai_tool_messages_to_anthropic(body.get("messages", []))
    explicit_system = body.get("system", "")
    if explicit_system:
        system = f"{system}\n\n{explicit_system}".strip() if system else explicit_system
    return {
        "model": body.get("model", "lima-1.3"),
        "messages": messages,
        "tools": tools,
        "max_tokens": body.get("max_tokens", 4096),
        "system": system,
    }


def _convert_openai_tool_messages_to_anthropic(messages: list) -> tuple[list, str]:
    converted = []
    system_parts = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role == "system":
            if isinstance(content, str) and content:
                system_parts.append(content)
            continue
        if role == "assistant" and msg.get("tool_calls"):
            blocks = []
            if isinstance(content, str) and content:
                blocks.append({"type": "text", "text": content})
            for tool_call in msg.get("tool_calls") or []:
                function = tool_call.get("function", {}) if isinstance(tool_call, dict) else {}
                if not isinstance(function, dict) or not function.get("name"):
                    continue
                blocks.append({
                    "type": "tool_use",
                    "id": tool_call.get("id", f"call_{uuid.uuid4().hex[:24]}"),
                    "name": function["name"],
                    "input": _parse_openai_tool_arguments(function.get("arguments", {})),
                })
            converted.append({"role": "assistant", "content": blocks})
            continue
        if role == "tool":
            converted.append({
                "role": "user",
                "content": [{
                    "type": "tool_result",
                    "tool_use_id": msg.get("tool_call_id", ""),
                    "content": "" if content is None else str(content),
                }],
            })
            continue
        converted.append({"role": role, "content": content})
    return converted, "\n\n".join(system_parts)


def _parse_openai_tool_arguments(value) -> dict:
    if isinstance(value, dict):
        return value
    if not isinstance(value, str) or not value.strip():
        return {}
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _convert_anthropic_tool_response_to_openai(result: dict, original_body: dict) -> dict:
    """Convert Anthropic tool response back to OpenAI format."""
    content_parts = result.get("content", [])
    text_parts = [b["text"] for b in content_parts if b.get("type") == "text"]
    tool_parts = [b for b in content_parts if b.get("type") == "tool_use"]

    openai_tool_calls = []
    for tc in tool_parts:
        openai_tool_calls.append({
            "id": tc.get("id", f"call_{uuid.uuid4().hex[:24]}"),
            "type": "function",
            "function": {
                "name": tc.get("name", ""),
                "arguments": json.dumps(tc.get("input", {})),
            },
        })

    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": original_body.get("model", "lima-1.3"),
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "\n".join(text_parts) if text_parts else None,
                "tool_calls": openai_tool_calls if openai_tool_calls else None,
            },
            "finish_reason": "tool_calls" if openai_tool_calls else "stop",
        }],
        "usage": result.get("usage", {}),
    }
