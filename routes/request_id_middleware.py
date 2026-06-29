"""Middleware that ensures every HTTP response carries an X-Request-Id header."""

from __future__ import annotations

import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Inject X-Request-Id into every response.

    Reuses the existing X-LiMa-Trace-Id when present (e.g. chat endpoints) so
    clients can correlate logs/traces with a single id. Falls back to a random
    UUID for routes that do not create a LiMa trace.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        if not response.headers.get("X-Request-Id"):
            request_id = response.headers.get("X-LiMa-Trace-Id") or str(uuid.uuid4())
            response.headers["X-Request-Id"] = request_id
        return response
