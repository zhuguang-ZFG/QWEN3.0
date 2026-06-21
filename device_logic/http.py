"""HTTP helpers shared by native device app and compat routes."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from fastapi import Request
from fastapi.responses import JSONResponse


def ok(data: Any) -> JSONResponse:
    return JSONResponse({"code": 0, "data": data})


def err(code: int, message: str, status_code: int = 400) -> JSONResponse:
    return JSONResponse({"code": code, "message": message}, status_code=status_code)


async def read_body(request: Request) -> dict[str, Any] | JSONResponse:
    try:
        body = await request.json()
    except (json.JSONDecodeError, ValueError):
        return err(400, "valid JSON body required", 400)
    if not isinstance(body, dict):
        return err(400, "JSON object body required", 400)
    return body


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def new_id() -> str:
    return str(uuid4())


def str_field(body: dict[str, Any], *names: str) -> str:
    for name in names:
        value = body.get(name)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def query_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, parsed))


def json_params(value: Any) -> str:
    return json.dumps(value if isinstance(value, dict) else {}, ensure_ascii=False, sort_keys=True)


def loads_json(value: Any) -> dict[str, Any]:
    if not isinstance(value, str) or not value:
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def expires_at(seconds: int) -> str:
    return (
        (datetime.now(timezone.utc) + timedelta(seconds=seconds))
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )
