"""Async utility: run a coroutine synchronously, bridging sync/async boundaries.

Bridges the gap between FastAPI async handlers and sync routing code.
When an event loop is already running (pytest-asyncio / FastAPI), offloads
to a daemon thread so asyncio.run() can be called without nesting loops.
"""

from __future__ import annotations

import asyncio
import atexit
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Coroutine, TypeVar

T = TypeVar("T")

_sync_bridge_executor = ThreadPoolExecutor(
    max_workers=1,
    thread_name_prefix="sync_bridge",
)
atexit.register(_sync_bridge_executor.shutdown, wait=False)


def run_coro_sync(coro: Coroutine[Any, Any, T]) -> T:
    """Run a coroutine synchronously, bridging sync/async boundaries.

    - No running loop → asyncio.run(coro)
    - Running loop → offload to daemon thread with asyncio.run
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    return _sync_bridge_executor.submit(asyncio.run, coro).result()
