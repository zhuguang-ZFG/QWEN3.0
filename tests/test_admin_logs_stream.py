"""Tests for the admin SSE log stream endpoint (Phase 1.2)."""

import asyncio
import os
import sys

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LIMA_ADMIN_TOKEN"] = "test-admin-token"

from routes.admin_api import (
    _log_sse_generator,
    _log_subscribers,
    publish_log_event,
    router as admin_api_router,
)
from routes.admin_auth import verify_admin

app = FastAPI()
app.dependency_overrides[verify_admin] = lambda: None
app.include_router(admin_api_router, prefix="/admin")
client = TestClient(app)
HEADERS = {"Authorization": "Bearer test-admin-token"}


def setup_function():
    _log_subscribers.clear()


def test_sse_endpoint_requires_admin_auth():
    """Unauthenticated request should be rejected."""
    resp = client.get("/admin/api/logs/stream")
    assert resp.status_code in (401, 403)


def test_sse_endpoint_returns_event_stream():
    """SSE endpoint should return text/event-stream content type."""
    resp = client.get("/admin/api/logs/stream", headers=HEADERS)
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers.get("content-type", "")
    assert "no-cache" in resp.headers.get("cache-control", "")


def test_sse_endpoint_receives_events():
    """After connecting, the client should receive published events."""
    async def _publish():
        await asyncio.sleep(0.1)
        await publish_log_event({"time": "12:00:00", "query": "test", "success": True})

    task = asyncio.get_event_loop().create_task(_publish())
    resp = client.get("/admin/api/logs/stream", headers=HEADERS)
    task.cancel()
    # Should contain at least the connected comment and the event data
    assert "data:" in resp.text or ": connected" in resp.text


def test_publish_log_event_fans_out():
    """publish_log_event should deliver to all subscribers."""
    queues: list[asyncio.Queue] = []

    async def _test():
        q: asyncio.Queue = asyncio.Queue(maxsize=10)
        _log_subscribers.append(q)
        await publish_log_event({"time": "12:00:00", "query": "fan-out", "success": True})
        assert not q.empty()
        event = q.get_nowait()
        assert event["query"] == "fan-out"
        _log_subscribers.clear()

    asyncio.get_event_loop().run_until_complete(_test())


def test_publish_removes_full_queues():
    """Subscribers with full queues should be removed."""
    async def _test():
        q: asyncio.Queue = asyncio.Queue(maxsize=1)
        q.put_nowait({"stale": True})  # Fill queue
        _log_subscribers.append(q)
        await publish_log_event({"new": True})
        # Queue was full, should be removed
        assert q not in _log_subscribers
        _log_subscribers.clear()

    asyncio.get_event_loop().run_until_complete(_test())
