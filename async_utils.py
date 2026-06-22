"""Async utility: run a coroutine synchronously, bridging sync/async boundaries.

Bridges the gap between FastAPI async handlers and sync routing code.
When an event loop is already running (pytest-asyncio / FastAPI), offloads
to a daemon thread so asyncio.run() can be called without nesting loops.
"""

from __future__ import annotations

import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor


def run_coro_sync(coro) -> object:
    """Run a coroutine synchronously, bridging sync/async boundaries.

    - No running loop → asyncio.run(coro)
    - Running loop → offload to daemon thread with asyncio.run
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()
