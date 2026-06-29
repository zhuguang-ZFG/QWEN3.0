"""OpenAI chat endpoint adapter.

The heavy request execution path lives in routes/chat_handler.py; this module
owns HTTP parsing, rate limiting, vision short-circuiting, and protocol wrapping.
"""

import logging
import time
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import ValidationError

import rate_limiter
from access_guard import require_public_or_private_api_key
from chat_models import ChatRequest
from chat_request_utils import extract_system_preview
from context_pipeline.tracing import get_current_trace, new_trace
from prompt_engineering.layers import PROMPT_VERSION
from response_builder import build_response, make_chat_id
from routes.async_compat import maybe_await
from routes.json_body import read_json_object
from vision_handler import detect_vision_request

router = APIRouter()
_log = logging.getLogger(__name__)

_deps: dict[str, Any] = {}


def inject_deps(**kwargs: Any) -> None:
    _deps.update(kwargs)


def _dep(name: str) -> Any:
    try:
        return _deps[name]
    except KeyError as exc:
        raise RuntimeError(f"routes.chat_endpoints missing dependency: {name}") from exc


def _call(name: str, *args: Any, **kwargs: Any) -> Any:
    fn = _dep(name)
    if fn is None:
        raise RuntimeError(f"routes.chat_endpoints dependency is None: {name}")
    return fn(*args, **kwargs)


def _model_id() -> str:
    return str(_dep("model_id"))


async def _read_json_body(request: Request) -> dict[str, Any] | JSONResponse:
    return await read_json_object(request, openai_error=True)


def _invalid_chat_request(exc: ValidationError) -> JSONResponse:
    details = []
    for error in exc.errors()[:3]:
        loc = ".".join(str(part) for part in error.get("loc", ()))
        msg = str(error.get("msg", "invalid value"))
        details.append(f"{loc}: {msg}" if loc else msg)
    message = "; ".join(details) or "invalid chat request"
    return JSONResponse(
        status_code=400,
        content={"error": {"message": message, "type": "invalid_request_error"}},
    )


async def _handle_vision_shortcut(
    raw_messages: list,
    body: dict,
    ide_source: str,
    client_ip: str,
    sys_prompt_preview: str,
) -> JSONResponse | StreamingResponse | None:
    """Handle vision requests (image analysis) as a fast-path shortcut."""
    if not detect_vision_request(raw_messages):
        return None
    chat_id = make_chat_id()
    t0 = time.time()
    from chat_request_utils import extract_last_user_text

    query_text = extract_last_user_text(raw_messages)
    vision_result = await maybe_await(_call("vision_route", raw_messages, body.get("max_tokens", 4096), ide_source))
    if not vision_result:
        return None
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


def _check_rate_limit(client_ip: str, ide_source: str) -> JSONResponse | None:
    """Return 429 response if rate limit exceeded, otherwise None."""
    rate_limit_multiplier = 5 if ide_source else 1
    if rate_limiter.check_rate_limit(client_ip, multiplier=rate_limit_multiplier):
        return None
    return JSONResponse(
        status_code=429,
        content={
            "error": {
                "message": "Rate limit exceeded. Try again later.",
                "type": "rate_limit_error",
            }
        },
    )


def _build_chat_request(body: dict[str, Any]) -> ChatRequest | JSONResponse:
    """Parse and validate the request body into a ChatRequest."""
    try:
        chat_req = ChatRequest(**body)
    except ValidationError as exc:
        return _invalid_chat_request(exc)
    if body.get("thinking", False):
        chat_req.thinking = True
    return chat_req


@router.post(
    "/v1/chat/completions",
    dependencies=[Depends(require_public_or_private_api_key)],
    response_model=None,
)
async def chat_completions(request: Request):
    """OpenAI-compatible chat completions endpoint."""
    body = await _read_json_body(request)
    if isinstance(body, JSONResponse):
        return body
    raw_messages = body.get("messages", [])
    client_ip = _call("client_ip", request)
    ide_source = _call("detect_ide", raw_messages)

    rate_limit_response = _check_rate_limit(client_ip, ide_source)
    if rate_limit_response is not None:
        return rate_limit_response

    sys_prompt_preview = extract_system_preview(raw_messages)
    # Create the request-level trace once per successful request.
    new_trace()

    vision_resp = await _handle_vision_shortcut(
        raw_messages,
        body,
        ide_source,
        client_ip,
        sys_prompt_preview,
    )
    if vision_resp is not None:
        _attach_trace_header_and_record(vision_resp)
        return vision_resp

    # Tool calls: use standard routing (native tool forwarding removed in Phase 0)
    # OpenAI-compatible tools are handled by the routing_engine's native support
    if body.get("tools"):
        _log.info("Tool call request routed through standard chat pipeline (native forwarding removed)")
        # Fall through to standard chat_req handling below

    chat_req = _build_chat_request(body)
    if isinstance(chat_req, JSONResponse):
        return chat_req

    response = await maybe_await(
        _dep("handle_chat")(
            chat_req,
            fmt="openai",
            client_ip=client_ip,
            ide_source=ide_source,
            sys_prompt_preview=sys_prompt_preview,
            request_headers=dict(request.headers),
        )
    )
    _attach_trace_header_and_record(response)
    return response


def _attach_trace_header_and_record(response) -> None:
    if hasattr(response, "headers") and not response.headers.get("X-LiMa-Prompt-Version"):
        response.headers["X-LiMa-Prompt-Version"] = PROMPT_VERSION
    trace = get_current_trace()
    if trace is None:
        return
    if hasattr(response, "headers") and not response.headers.get("X-LiMa-Trace-Id"):
        response.headers["X-LiMa-Trace-Id"] = trace.trace_id
    try:
        from observability.metrics import record_trace

        record_trace(trace.finish())
    except Exception as exc:
        _log.warning("record_trace failed: %s", exc, exc_info=True)
