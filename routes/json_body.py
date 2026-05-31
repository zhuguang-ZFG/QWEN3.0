"""Shared request JSON parsing helpers for explicit HTTP 400 contracts."""

from __future__ import annotations

import json
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse


def invalid_json_response(message: str, *, openai_error: bool = False) -> JSONResponse:
    if openai_error:
        return JSONResponse(
            status_code=400,
            content={"error": {"message": message, "type": "invalid_request_error"}},
        )
    return JSONResponse({"error": message}, status_code=400)


async def read_json_object(
    request: Request,
    *,
    openai_error: bool = False,
) -> dict[str, Any] | JSONResponse:
    try:
        body = await request.json()
    except (json.JSONDecodeError, ValueError):
        return invalid_json_response("valid JSON body required", openai_error=openai_error)
    if not isinstance(body, dict):
        return invalid_json_response("JSON object body required", openai_error=openai_error)
    return body
