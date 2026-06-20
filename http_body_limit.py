"""ASGI-level request body size enforcement for LiMa JSON API routes."""

from __future__ import annotations

import gzip
import json
import logging
from typing import Any, Awaitable, Callable

from fastapi import Request
from fastapi.responses import JSONResponse

_log = logging.getLogger(__name__)

JSON_BODY_METHODS = frozenset({"POST", "PUT", "PATCH"})
JSON_BODY_PREFIXES = (
    "/v1/",
    "/admin/api/",
    "/mcp/",
    "/agent/",
    "/device/",
)

ReceiveCallable = Callable[[], Awaitable[dict[str, Any]]]
SendCallable = Callable[[dict[str, Any]], Awaitable[None]]


def _scope_headers(scope: dict[str, Any]) -> dict[str, str]:
    return {key.decode("latin-1").lower(): value.decode("latin-1") for key, value in scope.get("headers", [])}


def _is_json_api_route(method: str, path: str, content_type: str) -> bool:
    if method not in JSON_BODY_METHODS:
        return False
    if not any(path.startswith(prefix) for prefix in JSON_BODY_PREFIXES):
        return False
    return "application/json" in content_type or path.startswith("/v1/")


def _oversized_payload() -> dict[str, Any]:
    return {"error": {"message": "Request body too large"}}


def _invalid_length_payload() -> dict[str, Any]:
    return {"error": {"message": "Invalid Content-Length"}}


def _length_required_payload() -> dict[str, Any]:
    return {"error": {"message": "Content-Length required for JSON API requests"}}


async def _send_json_response(send: SendCallable, status: int, payload: dict[str, Any]) -> None:
    body = json.dumps(payload).encode("utf-8")
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode("ascii")),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body, "more_body": False})


async def _drain_receive(receive: ReceiveCallable) -> None:
    while True:
        message = await receive()
        if message["type"] != "http.request" or not message.get("more_body", False):
            return


def _check_declared_content_length(
    headers: dict[str, str],
    max_size: int,
) -> int | None:
    content_length = headers.get("content-length")
    if not content_length:
        return None
    try:
        if int(content_length) > max_size:
            return 413
    except ValueError:
        return 400
    return None


def _needs_content_length(scope: dict[str, Any], headers: dict[str, str]) -> bool:
    method = scope.get("method", "GET")
    path = scope.get("path", "")
    content_type = (headers.get("content-type") or "").lower()
    if not _is_json_api_route(method, path, content_type):
        return False
    if headers.get("content-length"):
        return False
    transfer_encoding = (headers.get("transfer-encoding") or "").lower()
    return "chunked" not in transfer_encoding


def _require_content_length_for_json(request: Request) -> JSONResponse | None:
    headers = {k.lower(): v for k, v in request.headers.items()}
    scope = {"method": request.method, "path": request.url.path}
    if not _needs_content_length(scope, headers):
        return None
    return JSONResponse(status_code=400, content=_length_required_payload())


def _oversized_response() -> JSONResponse:
    return JSONResponse(status_code=413, content=_oversized_payload())


def _invalid_length_response() -> JSONResponse:
    return JSONResponse(status_code=400, content=_invalid_length_payload())


def _length_required_response() -> JSONResponse:
    return JSONResponse(status_code=400, content=_length_required_payload())


def _check_content_length_header(request: Request, max_size: int) -> JSONResponse | None:
    headers = {k.lower(): v for k, v in request.headers.items()}
    status = _check_declared_content_length(headers, max_size)
    if status == 413:
        return _oversized_response()
    if status == 400:
        return _invalid_length_response()
    return None


def install_body_size_limit(request: Request, max_size: int) -> tuple[Request, dict]:
    """Wrap request.receive for unit tests (mirrors middleware byte cap)."""
    state = {"bytes": 0, "too_large": False}
    receive = request.receive

    async def limited_receive():
        if state["too_large"]:
            return {"type": "http.disconnect"}
        message = await receive()
        if message["type"] != "http.request":
            return message
        chunk = message.get("body", b"") or b""
        state["bytes"] += len(chunk)
        if state["bytes"] > max_size:
            state["too_large"] = True
            return {"type": "http.disconnect"}
        return message

    limited = Request(request.scope, limited_receive)
    return limited, state


async def _read_limited_body(
    receive: ReceiveCallable,
    send: SendCallable,
    max_body_size: int,
    headers: dict[str, str],
) -> bytes | None:
    """Read the request body up to max_body_size; return None when a 413 was sent."""
    body = b""
    while True:
        message = await receive()
        if message["type"] != "http.request":
            break
        body += message.get("body", b"") or b""
        if len(body) > max_body_size:
            await _send_json_response(send, 413, _oversized_payload())
            await _drain_receive(receive)
            return None
        if not message.get("more_body", False):
            break

    content_encoding = (headers.get("content-encoding") or "").lower()
    if content_encoding == "gzip" and body:
        try:
            body = gzip.decompress(body)
            if len(body) > max_body_size:
                await _send_json_response(send, 413, _oversized_payload())
                return None
        except Exception as exc:
            _log.debug("http_body_limit.py: {}", type(exc).__name__)

    return body


class BodySizeLimitMiddleware:
    """Pure ASGI middleware: caps body bytes before Starlette builds Request."""

    def __init__(self, app, max_body_size: int):
        self.app = app
        self.max_body_size = max_body_size

    async def __call__(self, scope: dict[str, Any], receive: ReceiveCallable, send: SendCallable):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "GET")
        if method not in JSON_BODY_METHODS:
            await self.app(scope, receive, send)
            return

        headers = _scope_headers(scope)
        declared_status = _check_declared_content_length(headers, self.max_body_size)
        if declared_status is not None:
            payload = _oversized_payload() if declared_status == 413 else _invalid_length_payload()
            await _send_json_response(send, declared_status, payload)
            await _drain_receive(receive)
            return

        if _needs_content_length(scope, headers):
            await _send_json_response(send, 400, _length_required_payload())
            await _drain_receive(receive)
            return

        body = await _read_limited_body(receive, send, self.max_body_size, headers)
        if body is None:
            return

        replayed = False

        async def replay_receive() -> dict[str, Any]:
            nonlocal replayed
            if not replayed:
                replayed = True
                return {"type": "http.request", "body": body, "more_body": False}
            message = await receive()
            if message["type"] == "http.request" and message.get("more_body", False):
                await _drain_receive(receive)
            return {"type": "http.disconnect"}

        await self.app(scope, replay_receive, send)


async def enforce_request_body_limit(
    request: Request,
    call_next,
    *,
    max_size: int,
):
    """Legacy HTTP middleware wrapper; prefer BodySizeLimitMiddleware on the app."""
    if request.method not in JSON_BODY_METHODS:
        return await call_next(request)

    header_error = _check_content_length_header(request, max_size)
    if header_error is not None:
        return header_error

    length_required = _require_content_length_for_json(request)
    if length_required is not None:
        return length_required

    limited_request, state = install_body_size_limit(request, max_size)
    response = await call_next(limited_request)
    if state["too_large"]:
        return _oversized_response()
    return response
