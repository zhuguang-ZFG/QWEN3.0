"""Admin SSE log stream — real-time log fan-out (extracted from admin_api)."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import AsyncGenerator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from routes.admin_auth import verify_admin

router = APIRouter()
_log = logging.getLogger(__name__)

# ── SSE log stream ─────────────────────────────────────────────────────────
# A simple in-process pub-sub for log events.  Each SSE client gets an
# ``asyncio.Queue``.  When a new log entry arrives the dispatcher fans
# it out to every queue.

_log_subscribers: list[asyncio.Queue[dict | None]] = []
_log_subscribers_lock = asyncio.Lock()

# Stored main event-loop reference for SSE fan-out from non-async paths.
_main_sse_loop: asyncio.AbstractEventLoop | None = None


def _set_sse_event_loop(loop: asyncio.AbstractEventLoop) -> None:
    """Called once at startup to capture the asyncio event loop."""
    global _main_sse_loop
    _main_sse_loop = loop


async def publish_log_event(event: dict) -> None:
    """Push *event* to every active SSE subscriber (fire-and-forget)."""
    async with _log_subscribers_lock:
        dead: list[int] = []
        for idx, q in enumerate(_log_subscribers):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                dead.append(idx)
        for idx in reversed(dead):
            _log_subscribers.pop(idx)


async def _log_sse_generator(
    queue: asyncio.Queue[dict | None],
) -> AsyncGenerator[str, None]:
    """Yield SSE-formatted strings for every log event in *queue*."""
    try:
        yield ": connected\n\n"
        while True:
            event: dict | None = await queue.get()
            if event is None:
                break
            data = json.dumps(event, ensure_ascii=False)
            yield f"data: {data}\n\n"
    except asyncio.CancelledError:
        pass


@router.get("/api/logs/stream", dependencies=[Depends(verify_admin)])
async def admin_logs_stream():
    """SSE endpoint that streams log events in real time."""
    queue: asyncio.Queue[dict | None] = asyncio.Queue(maxsize=256)
    async with _log_subscribers_lock:
        _log_subscribers.append(queue)

    async def _cleanup():
        async with _log_subscribers_lock:
            if queue in _log_subscribers:
                _log_subscribers.remove(queue)

    async def _wrapped():
        try:
            async for chunk in _log_sse_generator(queue):
                yield chunk
        finally:
            await _cleanup()

    return StreamingResponse(
        _wrapped(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
