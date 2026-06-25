"""Tests for streaming_bridge synchronous helpers (CQ-099)."""

from __future__ import annotations

import asyncio
import queue as queue_mod
import threading

import pytest

import streaming_bridge


# ---------------------------------------------------------------------------
# _adaptive_timeout
# ---------------------------------------------------------------------------


class TestAdaptiveTimeout:
    def test_known_backend_returns_adaptive_value(self, monkeypatch):
        monkeypatch.setattr(streaming_bridge, "_STATIC_LATENCY_ESTIMATE", {"groq": 500.0})
        result = streaming_bridge._adaptive_timeout("groq")
        # max(3.0, 500/1000 + 1.5) = max(3.0, 2.0) = 3.0
        assert result == 3.0

    def test_known_backend_high_latency(self, monkeypatch):
        monkeypatch.setattr(streaming_bridge, "_STATIC_LATENCY_ESTIMATE", {"groq": 5000.0})
        result = streaming_bridge._adaptive_timeout("groq")
        # max(3.0, 5000/1000 + 1.5) = max(3.0, 6.5) = 6.5
        assert result == pytest.approx(6.5)

    def test_unknown_backend_returns_default(self, monkeypatch):
        monkeypatch.setattr(streaming_bridge, "_STATIC_LATENCY_ESTIMATE", {})
        result = streaming_bridge._adaptive_timeout("nonexistent")
        assert result == 3.0

    def test_custom_default(self, monkeypatch):
        monkeypatch.setattr(streaming_bridge, "_STATIC_LATENCY_ESTIMATE", {})
        result = streaming_bridge._adaptive_timeout("unknown", default=10.0)
        assert result == 10.0


# ---------------------------------------------------------------------------
# drain_queue
# ---------------------------------------------------------------------------


class TestDrainQueue:
    def test_drains_all_items(self):
        q = queue_mod.Queue()
        for i in range(5):
            q.put(i)
        streaming_bridge.drain_queue(q)
        assert q.empty()

    def test_empty_queue_no_error(self):
        q = queue_mod.Queue()
        streaming_bridge.drain_queue(q)
        assert q.empty()


# ---------------------------------------------------------------------------
# start_sync_stream_worker
# ---------------------------------------------------------------------------


class TestStartSyncStreamWorker:
    def test_happy_path_chunks_then_done(self):
        """Worker puts chunks then a done sentinel."""
        q = queue_mod.Queue()
        cancel = threading.Event()
        chunks = ["hello", " world"]

        def fake_stream(backend, messages, max_tokens, ide):
            return iter(chunks)

        thread = streaming_bridge.start_sync_stream_worker(
            q,
            cancel,
            backend="b",
            messages=[],
            max_tokens=100,
            ide="vscode",
            call_stream_fn=fake_stream,
        )
        thread.join(timeout=2.0)
        collected = []
        while not q.empty():
            typ, val = q.get_nowait()
            if typ == "chunk":
                collected.append(val)
        assert collected == chunks
        # The last item should be ("done", None)
        # We already drained chunks; re-check by re-running in order.
        q2 = queue_mod.Queue()
        streaming_bridge.start_sync_stream_worker(
            q2,
            cancel,
            backend="b",
            messages=[],
            max_tokens=100,
            ide="vscode",
            call_stream_fn=fake_stream,
        ).join(timeout=2.0)
        all_items = []
        while not q2.empty():
            all_items.append(q2.get_nowait())
        assert all_items[-1] == ("done", None)
        assert all_items[0] == ("chunk", "hello")

    def test_cancel_stops_worker(self):
        """Worker stops yielding when cancel event is set."""
        q = queue_mod.Queue()
        cancel = threading.Event()
        yielded = []

        def infinite_stream(backend, messages, max_tokens, ide):
            for i in range(10000):
                if cancel.is_set():
                    return
                yield f"chunk-{i}"

        # Set cancel after a short delay so the worker sees it soon.
        cancel.set()
        thread = streaming_bridge.start_sync_stream_worker(
            q,
            cancel,
            backend="b",
            messages=[],
            max_tokens=100,
            ide="vscode",
            call_stream_fn=infinite_stream,
        )
        thread.join(timeout=2.0)
        while not q.empty():
            typ, val = q.get_nowait()
            if typ == "chunk":
                yielded.append(val)
        # With cancel pre-set, no chunks should be produced.
        assert yielded == []

    def test_error_path(self):
        """Exception inside stream fn is surfaced as ("error", exc)."""
        q = queue_mod.Queue()
        cancel = threading.Event()

        def failing_stream(backend, messages, max_tokens, ide):
            raise RuntimeError("boom")
            yield  # make it a generator  # noqa: E501

        thread = streaming_bridge.start_sync_stream_worker(
            q,
            cancel,
            backend="b",
            messages=[],
            max_tokens=100,
            ide="vscode",
            call_stream_fn=failing_stream,
        )
        thread.join(timeout=2.0)
        items = []
        while not q.empty():
            items.append(q.get_nowait())
        assert items[-1] == ("done", None)
        error_items = [i for i in items if i[0] == "error"]
        assert len(error_items) == 1
        assert isinstance(error_items[0][1], RuntimeError)
        assert str(error_items[0][1]) == "boom"


# ---------------------------------------------------------------------------
# fallback_to_sync_call
# ---------------------------------------------------------------------------


class TestFallbackToSyncCall:
    @pytest.mark.asyncio
    async def test_success_returns_str(self):
        def ok_fn(backend, messages, max_tokens, ide):
            return "ok result"

        result = await streaming_bridge.fallback_to_sync_call(
            ok_fn,
            "b",
            [],
            100,
            "vscode",
            log_label="test",
        )
        assert result == "ok result"

    @pytest.mark.asyncio
    async def test_err_prefix_returns_none(self):
        def err_fn(backend, messages, max_tokens, ide):
            return "[ERR] something failed"

        result = await streaming_bridge.fallback_to_sync_call(
            err_fn,
            "b",
            [],
            100,
            "vscode",
            log_label="test",
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_exception_returns_none_and_logs(self, caplog):
        def exploding_fn(backend, messages, max_tokens, ide):
            raise ConnectionError("nope")

        import logging

        with caplog.at_level(logging.WARNING, logger="streaming_bridge"):
            result = await streaming_bridge.fallback_to_sync_call(
                exploding_fn,
                "b",
                [],
                100,
                "vscode",
                log_label="test",
            )
        assert result is None
        assert any("nope" not in r.message and "ConnectionError" in r.message for r in caplog.records)
