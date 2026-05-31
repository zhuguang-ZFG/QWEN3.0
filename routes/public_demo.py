"""Bounded public website demo routes."""

from __future__ import annotations

import os
import time
from collections import defaultdict, deque
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from chat_models import ChatRequest
from chat_request_utils import extract_system_preview
from routes.json_body import read_json_object

router = APIRouter()

_deps: dict[str, Any] = {}
_PUBLIC_DEMO_WINDOW_SECONDS = 60
_PUBLIC_DEMO_DEFAULT_LIMIT = 6
_PUBLIC_DEMO_MAX_TOKENS = 200
_PUBLIC_DEMO_MAX_CHARS = 1200
_public_demo_hits: defaultdict[str, deque[float]] = defaultdict(deque)


def inject_deps(**kwargs: Any) -> None:
    _deps.update(kwargs)


def _dep(name: str) -> Any:
    try:
        return _deps[name]
    except KeyError as exc:
        raise RuntimeError(f"routes.public_demo missing dependency: {name}") from exc


def _model_id() -> str:
    return str(_dep("model_id"))


def _public_demo_enabled() -> bool:
    return os.environ.get("LIMA_PUBLIC_DEMO_ENABLED", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _public_demo_limit() -> int:
    raw_limit = os.environ.get("LIMA_PUBLIC_DEMO_MAX_PER_MINUTE", "").strip()
    try:
        limit = int(raw_limit) if raw_limit else _PUBLIC_DEMO_DEFAULT_LIMIT
    except ValueError:
        limit = _PUBLIC_DEMO_DEFAULT_LIMIT
    return max(1, min(60, limit))


def _public_demo_client_key(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    if forwarded_for:
        return forwarded_for
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _check_public_demo_rate_limit(key: str, now: float | None = None) -> bool:
    current = time.time() if now is None else now
    hits = _public_demo_hits[key]
    while hits and current - hits[0] >= _PUBLIC_DEMO_WINDOW_SECONDS:
        hits.popleft()
    if len(hits) >= _public_demo_limit():
        return False
    hits.append(current)
    return True


def _message_text_length(message: Any) -> int:
    content = message.get("content") if isinstance(message, dict) else None
    if isinstance(content, str):
        return len(content)
    if not isinstance(content, list):
        return 0

    total = 0
    for part in content:
        if isinstance(part, str):
            total += len(part)
        elif isinstance(part, dict):
            text = part.get("text")
            if isinstance(text, str):
                total += len(text)
            image_url = part.get("image_url")
            if isinstance(image_url, dict) and isinstance(image_url.get("url"), str):
                total += len(image_url["url"])
            source = part.get("source")
            if isinstance(source, dict) and isinstance(source.get("data"), str):
                total += len(source["data"])
    return total


def _validate_public_demo_body(body: dict[str, Any]) -> dict[str, Any]:
    if body.get("tools") or body.get("tool_choice") or body.get("stream"):
        raise HTTPException(status_code=400, detail="Unsupported public demo request")

    messages = body.get("messages")
    if not isinstance(messages, list) or not messages:
        raise HTTPException(status_code=400, detail="Public demo requires messages")

    total_chars = sum(_message_text_length(message) for message in messages)
    if total_chars <= 0 or total_chars > _PUBLIC_DEMO_MAX_CHARS:
        raise HTTPException(
            status_code=400,
            detail="Public demo message is empty or too long",
        )

    try:
        max_tokens = int(body.get("max_tokens", _PUBLIC_DEMO_MAX_TOKENS))
    except (TypeError, ValueError):
        max_tokens = _PUBLIC_DEMO_MAX_TOKENS
    max_tokens = max(1, min(_PUBLIC_DEMO_MAX_TOKENS, max_tokens))

    sanitized: dict[str, Any] = {
        "model": str(body.get("model") or _model_id()),
        "messages": messages,
        "stream": False,
        "max_tokens": max_tokens,
    }
    if isinstance(body.get("temperature"), (int, float)):
        sanitized["temperature"] = body["temperature"]
    return sanitized


@router.post("/public/demo/chat")
async def public_demo_chat(request: Request):
    """Website demo endpoint; private API routes remain key-protected."""
    if not _public_demo_enabled():
        raise HTTPException(status_code=503, detail="LiMa public demo is disabled.")

    client_key = _public_demo_client_key(request)
    if not _check_public_demo_rate_limit(client_key):
        raise HTTPException(status_code=429, detail="Public demo rate limit exceeded.")

    body = await read_json_object(request)
    if isinstance(body, JSONResponse):
        return body
    sanitized = _validate_public_demo_body(body)
    chat_req = ChatRequest(**sanitized)
    return await _dep("handle_chat")(
        chat_req,
        fmt="openai",
        client_ip=client_key,
        ide_source="public_demo",
        sys_prompt_preview=extract_system_preview(sanitized["messages"]),
        request_headers=dict(request.headers),
    )
