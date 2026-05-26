"""Telegram notification hooks for LiMa modules. Fire-and-forget, sync-safe."""

import asyncio
import logging
import threading
import time
from typing import Awaitable, Callable

import telegram_bot

logger = logging.getLogger(__name__)

_health_last_notified: dict[str, float] = {}
_RATE_LIMIT_SECONDS = 60


def _fire_and_forget(async_fn: Callable[..., Awaitable], *args, **kwargs) -> None:
    def make_coro() -> Awaitable:
        return async_fn(*args, **kwargs)

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(make_coro())
        else:
            t = threading.Thread(target=asyncio.run, args=(make_coro(),), daemon=True)
            t.start()
    except RuntimeError:
        t = threading.Thread(target=asyncio.run, args=(make_coro(),), daemon=True)
        t.start()
    except Exception:
        logger.exception("_fire_and_forget failed")


def notify_health_change(backend: str, old_state: str, new_state: str) -> None:
    if not telegram_bot.is_configured():
        return
    if new_state == "dead":
        level = "critical"
    elif new_state == "degraded" and old_state == "healthy":
        level = "warning"
    else:
        return

    now = time.time()
    last = _health_last_notified.get(backend, 0.0)
    if now - last < _RATE_LIMIT_SECONDS:
        return
    _health_last_notified[backend] = now

    msg = f"Backend `{backend}` → {new_state}"
    _fire_and_forget(telegram_bot.send_alert, level, msg)


def notify_task_ready(task_id: str, summary: str, changed_files: list[str]) -> None:
    if not telegram_bot.is_configured():
        return
    _fire_and_forget(telegram_bot.send_approval, task_id, summary, changed_files)


def notify_error_spike(error_rate: float, strategy: str) -> None:
    if not telegram_bot.is_configured():
        return
    msg = f"Error rate {error_rate:.0%} → strategy switched to `{strategy}`"
    _fire_and_forget(telegram_bot.send_alert, "warning", msg)


def notify_github_event(summary: str) -> None:
    if not telegram_bot.is_configured():
        logger.debug("github event skipped: telegram not configured")
        return
    _fire_and_forget(telegram_bot.send_message, summary)
