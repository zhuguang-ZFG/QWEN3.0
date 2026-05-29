"""Shared fire-and-forget asyncio helpers for Telegram modules."""

from __future__ import annotations

import asyncio
import logging
import threading
from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)


def fire_and_forget(awaitable_factory: Callable[[], Awaitable[object]]) -> None:
    """Schedule a coroutine on the running loop, or run it in a daemon thread."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(awaitable_factory())
            return
    except RuntimeError:
        pass
    except Exception:
        logger.exception("fire_and_forget schedule failed")
        return

    threading.Thread(
        target=asyncio.run,
        args=(awaitable_factory(),),
        daemon=True,
    ).start()


def fire_and_forget_call(
    async_fn: Callable[..., Awaitable[object]],
    *args: object,
    **kwargs: object,
) -> None:
    """Fire-and-forget wrapper for async callables with positional/kw args."""
    fire_and_forget(lambda: async_fn(*args, **kwargs))
