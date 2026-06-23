"""Tests for routes/admin_extra_logs.py."""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest

from routes import admin_extra_logs


@pytest.fixture(autouse=True)
def _clean_subscribers():
    with patch.object(admin_extra_logs, "_SSE_SUBSCRIBERS", []):
        yield


@pytest.mark.asyncio
async def test_log_stream_returns_streaming_response():
    with patch("asyncio.wait_for", side_effect=asyncio.CancelledError):
        response = await admin_extra_logs.log_stream()
    assert response.media_type == "text/event-stream"
    assert response.headers["Cache-Control"] == "no-cache"
    assert response.headers["X-Accel-Buffering"] == "no"


@pytest.mark.asyncio
async def test_log_stream_registers_subscriber():
    with patch("asyncio.wait_for", side_effect=asyncio.CancelledError):
        await admin_extra_logs.log_stream()
    assert len(admin_extra_logs._SSE_SUBSCRIBERS) == 1


@pytest.mark.asyncio
async def test_log_stream_yields_event():
    async def _fake_wait_for(coro, timeout):
        return {"message": "hello"}

    with patch("asyncio.wait_for", side_effect=_fake_wait_for):
        response = await admin_extra_logs.log_stream()
        gen = response.body_iterator
        chunks = []
        async for chunk in gen:
            chunks.append(chunk)
            await gen.aclose()
            break
    assert any('"message": "hello"' in (c.decode() if isinstance(c, bytes) else c) for c in chunks)


def test_broadcast_log_delivers_to_subscriber():
    queue = asyncio.Queue(maxsize=200)
    admin_extra_logs._SSE_SUBSCRIBERS.append(queue)
    admin_extra_logs.broadcast_log({"message": "hello"})
    assert queue.get_nowait() == {"message": "hello"}


def test_broadcast_log_removes_full_queues():
    full_queue = asyncio.Queue(maxsize=1)
    full_queue.put_nowait({"first": "item"})
    admin_extra_logs._SSE_SUBSCRIBERS.append(full_queue)
    admin_extra_logs.broadcast_log({"message": "hello"})
    assert full_queue not in admin_extra_logs._SSE_SUBSCRIBERS
