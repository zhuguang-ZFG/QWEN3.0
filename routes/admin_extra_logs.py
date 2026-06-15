"""Admin API: SSE live log stream."""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from routes.admin_auth import verify_admin

router = APIRouter()

_SSE_SUBSCRIBERS: list[asyncio.Queue] = []


def broadcast_log(entry: dict) -> None:
    """Push a log entry to all SSE subscribers."""
    dead: list[asyncio.Queue] = []
    for q in _SSE_SUBSCRIBERS:
        try:
            q.put_nowait(entry)
        except asyncio.QueueFull:
            dead.append(q)
    for q in dead:
        _SSE_SUBSCRIBERS.remove(q)


@router.get("/api/logs/stream", dependencies=[Depends(verify_admin)])
async def log_stream():
    """SSE endpoint: streams new log entries in real time."""
    queue: asyncio.Queue = asyncio.Queue(maxsize=200)
    _SSE_SUBSCRIBERS.append(queue)

    async def event_generator():
        try:
            while True:
                try:
                    entry = await asyncio.wait_for(queue.get(), timeout=30)
                    yield f"data: {json.dumps(entry)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            if queue in _SSE_SUBSCRIBERS:
                _SSE_SUBSCRIBERS.remove(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
