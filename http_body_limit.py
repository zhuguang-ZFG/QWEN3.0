"""ASGI-level request body size enforcement for LiMa JSON API routes."""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse

JSON_BODY_METHODS = frozenset({"POST", "PUT", "PATCH"})
JSON_BODY_PREFIXES = (
    "/v1/",
    "/admin/api/",
    "/mcp/",
    "/agent/",
    "/device/",
)


def _is_json_api_route(request: Request) -> bool:
    if request.method not in JSON_BODY_METHODS:
        return False
    path = request.url.path
    if not any(path.startswith(prefix) for prefix in JSON_BODY_PREFIXES):
        return False
    content_type = (request.headers.get("content-type") or "").lower()
    return "application/json" in content_type or path.startswith("/v1/")


def _oversized_response() -> JSONResponse:
    return JSONResponse(
        status_code=413,
        content={"error": {"message": "Request body too large"}},
    )


def _invalid_length_response() -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={"error": {"message": "Invalid Content-Length"}},
    )


def _length_required_response() -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={"error": {"message": "Content-Length required for JSON API requests"}},
    )


def _check_content_length_header(request: Request, max_size: int) -> JSONResponse | None:
    content_length = request.headers.get("content-length")
    if not content_length:
        return None
    try:
        if int(content_length) > max_size:
            return _oversized_response()
    except ValueError:
        return _invalid_length_response()
    return None


def _require_content_length_for_json(request: Request) -> JSONResponse | None:
    if not _is_json_api_route(request):
        return None
    if request.headers.get("content-length"):
        return None
    transfer_encoding = (request.headers.get("transfer-encoding") or "").lower()
    if "chunked" in transfer_encoding:
        return None
    return _length_required_response()


def install_body_size_limit(request: Request, max_size: int) -> tuple[Request, dict]:
    """Wrap request.receive to count bytes and block bodies over max_size."""
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
            return {"type": "http.request", "body": b"", "more_body": False}
        return message

    limited = Request(request.scope, limited_receive)
    return limited, state


async def enforce_request_body_limit(
    request: Request,
    call_next,
    *,
    max_size: int,
):
    """Middleware: header checks + ASGI receive byte cap for POST/PUT/PATCH."""
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
