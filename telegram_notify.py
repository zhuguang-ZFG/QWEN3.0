"""Telegram notification hooks for LiMa modules. Fire-and-forget, sync-safe."""

import asyncio
import logging
import threading
import time
from typing import Awaitable, Callable

import telegram_bot

logger = logging.getLogger(__name__)


def _prepare_push_text(summary: str) -> str:
    try:
        from telegram_push_translate import translate_push_text

        return translate_push_text(summary)
    except Exception:
        logger.warning("push translate skipped", exc_info=True)
        return summary


def _send_push_message(summary: str, *, parse_mode: str = "") -> None:
    _fire_and_forget(telegram_bot.send_message, _prepare_push_text(summary), parse_mode=parse_mode)

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
    _fire_and_forget(telegram_bot.send_alert, level, _prepare_push_text(msg))


def notify_task_ready(task_id: str, summary: str, changed_files: list[str]) -> None:
    if not telegram_bot.is_configured():
        return
    _fire_and_forget(telegram_bot.send_approval, task_id, summary, changed_files)


def notify_error_spike(error_rate: float, strategy: str) -> None:
    if not telegram_bot.is_configured():
        return
    msg = f"Error rate {error_rate:.0%} → strategy switched to `{strategy}`"
    _fire_and_forget(telegram_bot.send_alert, "warning", _prepare_push_text(msg))


def notify_github_event(summary: str) -> None:
    if not telegram_bot.is_configured():
        logger.debug("github event skipped: telegram not configured")
        return
    _send_push_message(summary)


def notify_gitee_event(summary: str) -> None:
    if not telegram_bot.is_configured():
        logger.debug("gitee event skipped: telegram not configured")
        return
    _send_push_message(summary)


def notify_ops_event(summary: str, level: str = "warning") -> None:
    """Ops/mirror/deploy events (TG-GH-1 / GI-G-1)."""
    if not telegram_bot.is_configured():
        logger.debug("ops event skipped: telegram not configured")
        return
    _fire_and_forget(telegram_bot.send_alert, level, _prepare_push_text(summary))


def notify_deploy_event(summary: str) -> None:
    """Deploy script success (TG-GH-6)."""
    if not telegram_bot.is_configured():
        logger.debug("deploy notify skipped: telegram not configured")
        return
    _send_push_message(summary)


def notify_smoke_event(summary: str) -> None:
    """Public smoke script success (TG-GH-6)."""
    if not telegram_bot.is_configured():
        logger.debug("smoke notify skipped: telegram not configured")
        return
    _send_push_message(summary)


_budget_last_notified: dict[str, float] = {}
_BUDGET_RATE_LIMIT_SECONDS = 300


def reset_budget_alerts_for_tests() -> None:
    _budget_last_notified.clear()


def notify_budget_threshold(
    *,
    backend: str,
    level: str,
    used: int,
    limit: int,
    pool_label: str = "",
) -> None:
    """Push budget warn/exhausted alerts to Telegram (rate-limited)."""
    if not telegram_bot.is_configured():
        return

    key = f"pool:{pool_label}" if pool_label else backend
    now = time.time()
    last = _budget_last_notified.get(key, 0.0)
    if now - last < _BUDGET_RATE_LIMIT_SECONDS:
        return
    _budget_last_notified[key] = now

    if pool_label:
        target = f"CF pool `{pool_label}`"
    else:
        target = f"`{backend}`"
    pct = int(100 * used / limit) if limit else 0
    if level == "exhausted":
        alert_level = "critical"
        headline = "Budget exhausted"
    elif level == "pool_warning":
        alert_level = "warning"
        headline = "CF account pool warning"
    else:
        alert_level = "warning"
        headline = "Budget warning"

    msg = f"{headline}: {target} {used}/{limit} ({pct}%)"
    _fire_and_forget(telegram_bot.send_alert, alert_level, _prepare_push_text(msg))
