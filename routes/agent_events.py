"""SSE event stream endpoint — real-time events for CLI/clients.

GET /agent/events — Server-Sent Events stream of routing decisions,
tool executions, and system events.
"""

from __future__ import annotations

import json
import logging
import time
from collections import deque

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/agent", tags=["agent-events"])
_log = logging.getLogger(__name__)

# In-memory ring buffer for recent events (last 200)
_events: deque = deque(maxlen=200)
_max_age = 3600  # 1 hour


def record_event(event_type: str, data: dict) -> None:
    """Record an event for SSE consumers."""
    _events.append({
        "type": event_type,
        "data": data,
        "timestamp": time.time(),
    })


def _event_generator(since: float = 0.0):
    """Generate SSE events from the ring buffer."""
    sent_ids = set()
    idx = 0
    events_list = list(_events)

    while True:
        # Check for new events
        for event in events_list[idx:]:
            if event["timestamp"] > since and id(event) not in sent_ids:
                sent_ids.add(id(event))
                yield f"data: {json.dumps(event)}\n\n"
            idx += 1

        # Check for new events added after our snapshot
        events_list = list(_events)
        time.sleep(1)

        # Timeout after 5 minutes of no new events
        if time.time() - since > 300:
            yield f"data: {json.dumps({'type': 'heartbeat', 'data': {'ts': time.time()}})}\n\n"
            since = time.time()


@router.get("/events")
async def stream_events(since: float = 0.0):
    """Stream real-time events via SSE.

    Query params:
      since: timestamp (float) to stream events after. Default: now.
    """
    if since <= 0:
        since = time.time()

    # Replay buffered events first
    async def replay_and_stream():
        for event in list(_events):
            if event["timestamp"] > since:
                yield f"data: {json.dumps(event)}\n\n"

        # Then stream new events
        last_count = len(_events)
        while True:
            time.sleep(1)
            current = list(_events)
            if len(current) > last_count:
                for event in current[last_count:]:
                    if event["timestamp"] > since:
                        yield f"data: {json.dumps(event)}\n\n"
                last_count = len(current)

            # Heartbeat every 30s
            if int(time.time()) % 30 == 0:
                yield f": heartbeat\n\n"

    return StreamingResponse(
        replay_and_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/events/recent")
async def recent_events(limit: int = 50):
    """Get recent events as JSON (non-streaming)."""
    events = list(_events)[-limit:]
    return {"events": events, "total": len(_events)}
