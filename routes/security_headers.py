"""Global security headers middleware for LiMa HTTP responses.

AUDIT fix: nginx (the production edge) already sets X-Frame-Options,
X-Content-Type-Options, Referrer-Policy, and Strict-Transport-Security via
``add_header ... always``. Setting them here too produces duplicate headers
with conflicting values (e.g. X-Frame-Options: DENY + SAMEORIGIN). This
middleware now only sets headers that nginx does NOT configure: CSP,
Permissions-Policy, and X-XSS-Protection. The four overlap headers are left
to nginx.
"""

from __future__ import annotations

import os

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add HTTP response security headers not covered by the nginx edge."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        # Only set headers that nginx does NOT already configure, to avoid
        # duplicate/conflicting values (nginx add_header always appends).
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        response.headers["X-XSS-Protection"] = "0"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; font-src 'self' data:; connect-src 'self'; "
            "frame-ancestors 'none'; form-action 'self'"
        )
        # When running without nginx (local dev / Docker direct), the four
        # baseline headers are not set by an edge proxy — add them here so
        # dev mode still has baseline protection. Detected via LIMA_BEHIND_NGINX.
        if os.environ.get("LIMA_BEHIND_NGINX", "1") != "1":
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
            forwarded_proto = request.headers.get("x-forwarded-proto", "").lower()
            if request.url.scheme == "https" or forwarded_proto == "https":
                response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response
