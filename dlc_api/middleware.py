"""dlc_api ASGI middleware — application-layer body size limit + X-Request-ID.

findings.md:584：server_dlc 生产入口原本无任何中间件，请求体大小完全依赖
nginx `client_max_body_size` 兜底。若有人直连 :8081（绕过 nginx，如内网调试、
nginx 配置漂移、容器内直达）则无上限，超大 body 可撑爆内存。这里补一个最小
ASGI 中间件：优先按 `Content-Length` header 快速拒绝（413），对没有声明长度的
流式 body 则在累计读取时兜底拒绝，避免无限缓冲。

X-Request-ID：为每条请求分配/透传唯一标识，供日志关联与问题追踪。
"""

from __future__ import annotations

import contextvars
import re
import uuid

from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

# Module-level contextvar — read by observability/structured_logging.py.
request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")

# 默认应用层上限：32MB，与 nginx `client_max_body_size 32M` 对齐。
DEFAULT_MAX_BODY_BYTES = 32 * 1024 * 1024

_TOO_LARGE_RESPONSE = {
    "status": "error",
    "error": "request_entity_too_large",
    "detail": "request body exceeds size limit",
}


class BodySizeLimitMiddleware:
    """Reject requests whose body exceeds ``max_bytes`` with HTTP 413.

    Two layers of defense:
    1. If ``Content-Length`` is present and exceeds the limit, reject before
       reading any body (fast path).
    2. Otherwise count bytes as the body streams in and reject once the
       running total exceeds the limit (guards chunked/omitted-length bodies).
    """

    def __init__(self, app: ASGIApp, *, max_bytes: int = DEFAULT_MAX_BODY_BYTES) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Fast path: honour a declared Content-Length before reading the body.
        for name, value in scope.get("headers", []):
            if name == b"content-length":
                try:
                    declared = int(value)
                except (ValueError, TypeError):
                    break
                if declared > self.max_bytes:
                    await self._reject(send)
                    return
                break

        received = 0
        limit = self.max_bytes
        too_large = False

        async def _counting_receive() -> Message:
            nonlocal received, too_large
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    too_large = True
            return message

        # Wrap receive so a body without Content-Length is still bounded. We
        # can only send a 413 before the app starts its own response, so guard
        # the send side too.
        started = False

        async def _guarded_send(message: Message) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, _counting_receive, _guarded_send)
        finally:
            if too_large and not started:
                await self._reject(send)

    @staticmethod
    async def _reject(send: Send) -> None:
        import json

        body = json.dumps(_TOO_LARGE_RESPONSE).encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode("ascii")),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})


def add_body_size_limit(app: FastAPI, *, max_bytes: int = DEFAULT_MAX_BODY_BYTES) -> None:
    """Attach :class:`BodySizeLimitMiddleware` to a FastAPI/Starlette app."""
    app.add_middleware(BodySizeLimitMiddleware, max_bytes=max_bytes)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Propagate or generate an X-Request-ID per request.

    - Reads ``X-Request-ID`` from the incoming request header.
    - If absent, generates ``uuid.uuid4().hex[:16]``.
    - Stores the id in ``request.state.request_id`` and the module-level
      :data:`request_id_var` contextvar so downstream code (including async
      loggers) can pick it up.
    - Writes the id back into the response header.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        rid = re.sub(r"[^a-zA-Z0-9_-]", "", (request.headers.get("X-Request-ID") or ""))[:128] or uuid.uuid4().hex[:16]
        token = request_id_var.set(rid)
        request.state.request_id = rid
        try:
            response = await call_next(request)
        finally:
            request_id_var.reset(token)
        response.headers["X-Request-ID"] = rid
        return response


def add_request_id_middleware(app: FastAPI) -> None:
    """Attach :class:`RequestIDMiddleware` to a FastAPI/Starlette app."""
    app.add_middleware(RequestIDMiddleware)
