"""Sync-stream to async bridge helpers extracted from streaming.py (CQ-099)."""

from __future__ import annotations

import asyncio
import logging
import queue as queue_mod
import threading
import time
from collections.abc import AsyncIterator, Callable, Iterator

_log = logging.getLogger(__name__)

CallStreamFn = Callable[[str, list, int, str], Iterator[str]]
CallApiFn = Callable[[str, list, int, str], str]

# Static latency estimates imported from routing_selector (canonical source)
try:
    from routing_selector import _STATIC_LATENCY_ESTIMATE
except ImportError:
    _STATIC_LATENCY_ESTIMATE: dict[str, float] = {}


def _adaptive_timeout(backend: str, default: float = 3.0) -> float:
    est = _STATIC_LATENCY_ESTIMATE.get(backend)
    if est:
        return max(default, est / 1000 + 1.5)
    return default


def drain_queue(q: queue_mod.Queue) -> None:
    while not q.empty():
        try:
            q.get_nowait()
        except queue_mod.Empty:
            break


def start_sync_stream_worker(
    q: queue_mod.Queue,
    cancel: threading.Event,
    *,
    backend: str,
    messages: list,
    max_tokens: int,
    ide: str,
    call_stream_fn: CallStreamFn,
) -> threading.Thread:
    def _run() -> None:
        try:
            for chunk in call_stream_fn(backend, messages, max_tokens, ide):
                if cancel.is_set():
                    return
                q.put(("chunk", chunk))
        except Exception as exc:
            q.put(("error", exc))
        finally:
            q.put(("done", None))

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return thread


async def fallback_to_sync_call(
    call_fn: CallApiFn,
    backend: str,
    messages: list,
    max_tokens: int,
    ide: str,
    *,
    log_label: str,
) -> str | None:
    try:
        result = await asyncio.to_thread(call_fn, backend, messages, max_tokens, ide)
        if result and not str(result).startswith("[ERR]"):
            return str(result)
    except Exception as exc:
        _log.warning("%s backend=%s: %s", log_label, backend, type(exc).__name__)
    return None


async def bridge_stream(
    backend: str,
    messages: list,
    max_tokens: int,
    ide: str,
    call_stream_fn: CallStreamFn,
    call_fn: CallApiFn,
    first_chunk_timeout: float = 3.0,
) -> AsyncIterator[str]:
    """Bridge a blocking stream iterator into async yields with sync fallback."""
    timeout = _adaptive_timeout(backend, first_chunk_timeout)
    q: queue_mod.Queue = queue_mod.Queue()
    cancel = threading.Event()
    thread = start_sync_stream_worker(
        q,
        cancel,
        backend=backend,
        messages=messages,
        max_tokens=max_tokens,
        ide=ide,
        call_stream_fn=call_stream_fn,
    )

    first = False
    start = time.time()
    while True:
        remaining = timeout - (time.time() - start)
        if remaining <= 0:
            break
        try:
            typ, val = q.get(timeout=min(remaining, 0.5))
        except queue_mod.Empty:
            continue
        if typ == "done":
            if not first:
                cancel.set()
                thread.join(timeout=1.0)
                fallback = await fallback_to_sync_call(
                    call_fn, backend, messages, max_tokens, ide, log_label="stream fallback call failed"
                )
                if fallback:
                    yield fallback
            return
        if typ == "error":
            break
        if typ == "chunk":
            first = True
            yield val

    if not first:
        cancel.set()
        thread.join(timeout=2.0)
        if thread.is_alive():
            _log.warning("[STREAM] %s worker thread still alive after cancel+join", backend)
        drain_queue(q)
        fallback = await fallback_to_sync_call(
            call_fn, backend, messages, max_tokens, ide, log_label="stream empty fallback call failed"
        )
        if fallback:
            yield fallback
        return

    while True:
        try:
            typ, val = await asyncio.to_thread(q.get, timeout=30)
        except queue_mod.Empty:
            break
        if typ == "done":
            break
        if typ == "chunk":
            yield val
