"""Unified Operator daily digest for Telegram (TG-GH-3)."""

from __future__ import annotations

import time

import health_tracker
from budget_cf_google import get_total_requests_today, get_usage_summary
from webhook_activity_buffer import format_activity_lines


def _health_counts() -> dict[str, int]:
    counts = {"healthy": 0, "degraded": 0, "dead": 0}
    for state in health_tracker.get_health_map().values():
        counts[state] = counts.get(state, 0) + 1
    return counts


def _task_summary() -> str:
    try:
        from routes.agent_task_service import task_counts

        counts = task_counts()
        return (
            f"Tasks: {counts.get('needs_review', 0)} needs_review, "
            f"{counts.get('running', 0)} running, "
            f"{counts.get('failed', 0)} failed"
        )
    except Exception:
        return "Tasks: (unavailable)"


def _budget_excerpt() -> str:
    try:
        grouped = get_usage_summary()
        cf_head = grouped.get("Cloudflare", "").splitlines()[0] if grouped.get("Cloudflare") else ""
        google_head = grouped.get("Google", "").splitlines()[0] if grouped.get("Google") else ""
        gitee_head = grouped.get("Gitee", "").splitlines()[0] if grouped.get("Gitee") else ""
        parts = [p for p in (cf_head, google_head, gitee_head) if p and not p.startswith("(none")]
        return "Budget: " + ("; ".join(parts) if parts else "(none)")
    except Exception:
        return "Budget: (unavailable)"


def _inventory_weekly_excerpt() -> str:
    try:
        from provider_inventory.weekly_diff import format_weekly_diff_digest, load_weekly_diff

        return format_weekly_diff_digest(load_weekly_diff())
    except Exception:
        return "Inventory 7d: (unavailable)"


def build_unified_digest_text(*, hours: float = 24.0) -> str:
    today = time.strftime("%Y-%m-%d")
    counts = _health_counts()
    lines = [
        f"*LiMa Daily · {today}*",
        (
            f"Backends: {counts['healthy']} healthy / "
            f"{counts['degraded']} degraded / {counts['dead']} dead"
        ),
        *format_activity_lines(hours),
        _task_summary(),
        _budget_excerpt(),
        _inventory_weekly_excerpt(),
        f"Requests today: {get_total_requests_today()}",
    ]
    dead_list = [b for b, s in health_tracker.get_health_map().items() if s == "dead"]
    if dead_list:
        lines.append(f"Dead: {', '.join(dead_list[:8])}")
    return "\n".join(lines)


async def send_unified_digest(*, hours: float = 24.0) -> bool:
    import telegram_bot

    if not telegram_bot.is_configured():
        return False
    text = build_unified_digest_text(hours=hours)
    try:
        from telegram_push_translate import translate_push_text

        text = translate_push_text(text)
    except Exception:
        pass
    return await telegram_bot.send_message(text)
