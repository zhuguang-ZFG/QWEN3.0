"""Tests for routes/admin_extra_logs.py — SSE log broadcast."""

import asyncio

from routes.admin_extra_logs import broadcast_log, _SSE_SUBSCRIBERS


class TestBroadcastLog:
    def test_broadcasts_to_subscriber(self):
        queue = asyncio.Queue(maxsize=10)
        _SSE_SUBSCRIBERS.append(queue)
        try:
            broadcast_log({"msg": "hello"})
            assert queue.get_nowait() == {"msg": "hello"}
        finally:
            _SSE_SUBSCRIBERS.remove(queue)

    def test_removes_full_queues(self):
        queue = asyncio.Queue(maxsize=0)
        _SSE_SUBSCRIBERS.append(queue)
        try:
            broadcast_log({"msg": "hello"})
            assert queue not in _SSE_SUBSCRIBERS
        finally:
            if queue in _SSE_SUBSCRIBERS:
                _SSE_SUBSCRIBERS.remove(queue)

    def test_no_subscribers(self):
        broadcast_log({"msg": "hello"})  # should not raise
