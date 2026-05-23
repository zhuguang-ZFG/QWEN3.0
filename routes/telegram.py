"""Telegram webhook and command router for LiMa."""

import asyncio
import logging
import os
import re
import subprocess
import time

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel

import health_tracker
import budget_manager
import telegram_bot
from routes.telegram_commands import (
    cmd_chat, cmd_clear, cmd_code, cmd_top, cmd_uptime,
    cmd_eval, cmd_task, cmd_tasks, start_probe_loop,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/telegram")

_WEBHOOK_SECRET = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "")


def _get_webhook_secret() -> str:
    return os.environ.get("TELEGRAM_WEBHOOK_SECRET", "") or _WEBHOOK_SECRET


_ADMIN_TOKEN = os.environ.get("LIMA_ADMIN_TOKEN", "")


def _get_admin_token() -> str:
    return os.environ.get("LIMA_ADMIN_TOKEN", "") or _ADMIN_TOKEN


async def _require_admin(authorization: str = Header(default="")) -> None:
    token_expected = _get_admin_token()
    if not token_expected:
        raise HTTPException(503, "LIMA_ADMIN_TOKEN not configured")
    token = authorization.replace("Bearer ", "").strip()
    if token != token_expected:
        raise HTTPException(401, "Unauthorized")


class SetupBody(BaseModel):
    url: str


# --- Command handlers ---

async def _cmd_status(chat_id: str) -> None:
    hmap = health_tracker.get_health_map()
    counts = {"healthy": 0, "degraded": 0, "dead": 0}
    for state in hmap.values():
        counts[state] = counts.get(state, 0) + 1
    text = (
        f"Backends: {counts['healthy']} healthy, "
        f"{counts['degraded']} degraded, {counts['dead']} dead"
    )
    await telegram_bot.send_message(text, chat_id=chat_id)


async def _cmd_health(chat_id: str, name: str) -> None:
    if not name:
        await telegram_bot.send_message("Usage: /health <backend_name>", chat_id=chat_id)
        return
    state = health_tracker.get_backend_state(name)
    if not state:
        await telegram_bot.send_message(f"Unknown backend: {name}", chat_id=chat_id)
        return
    await telegram_bot.send_message(f"`{name}`: {state}", parse_mode="Markdown", chat_id=chat_id)


async def _cmd_budget(chat_id: str) -> None:
    summary = budget_manager.get_usage_summary()
    lines = [f"{k}: {v}" for k, v in summary.items()]
    await telegram_bot.send_message("\n".join(lines) or "No usage data", chat_id=chat_id)


async def _cmd_chat(chat_id: str, message: str) -> None:
    await cmd_chat(chat_id, message)


_REDACT_PATTERNS = [
    (re.compile(r'(sk-|ak_|gho_|Bearer\s+)[A-Za-z0-9_\-]{8,}'), r'\1***REDACTED***'),
    (re.compile(r'(key|token|password|secret)=[^\s&]+', re.IGNORECASE), r'\1=***'),
    (re.compile(r'https?://[^\s]*[?&](key|token)=[^\s&]+'), '[URL_REDACTED]'),
]


def _redact_logs(text: str) -> str:
    for pattern, replacement in _REDACT_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


async def _cmd_logs(chat_id: str, arg: str) -> None:
    n = int(arg) if arg.isdigit() else 10
    n = min(n, 30)
    try:
        result = subprocess.run(
            ["journalctl", "-u", "lima-router", "--no-pager", "-n", str(n),
             "--output=short-iso"],
            capture_output=True, text=True, timeout=15,
        )
        text = result.stdout.strip() or "No logs"
        text = _redact_logs(text)
        if len(text) > 3500:
            text = text[-3500:]
        await telegram_bot.send_message(f"```\n{text}\n```", chat_id=chat_id)
    except Exception as e:
        await telegram_bot.send_message(f"Error: {e}", chat_id=chat_id)


async def _cmd_restart(chat_id: str) -> None:
    keyboard = {
        "inline_keyboard": [[
            {"text": "Confirm restart", "callback_data": "restart:confirm"},
            {"text": "Cancel", "callback_data": "restart:cancel"},
        ]]
    }
    await telegram_bot._api_call("sendMessage", {
        "chat_id": chat_id,
        "text": "Restart lima-router?",
        "reply_markup": keyboard,
    })


async def _dispatch_command(chat_id: str, text: str) -> None:
    parts = text.strip().split(maxsplit=1)
    cmd = parts[0].lower().split("@")[0]
    arg = parts[1] if len(parts) > 1 else ""

    if cmd == "/status":
        await _cmd_status(chat_id)
    elif cmd == "/health":
        await _cmd_health(chat_id, arg.strip())
    elif cmd == "/budget":
        await _cmd_budget(chat_id)
    elif cmd == "/chat":
        await cmd_chat(chat_id, arg)
    elif cmd == "/clear":
        await cmd_clear(chat_id)
    elif cmd == "/code":
        await cmd_code(chat_id, arg)
    elif cmd == "/top":
        await cmd_top(chat_id)
    elif cmd == "/uptime":
        await cmd_uptime(chat_id)
    elif cmd == "/eval":
        await cmd_eval(chat_id, arg.strip())
    elif cmd == "/task":
        await cmd_task(chat_id, arg)
    elif cmd == "/tasks":
        await cmd_tasks(chat_id)
    elif cmd == "/logs":
        await _cmd_logs(chat_id, arg.strip())
    elif cmd == "/restart":
        await _cmd_restart(chat_id)
    elif cmd == "/start":
        await telegram_bot.send_message(
            "LiMa Bot ready.\n/status /health /budget /top /uptime\n"
            "/chat /clear /code /eval\n/logs /restart /task /tasks",
            chat_id=chat_id,
        )
    else:
        await telegram_bot.send_message("Unknown command", chat_id=chat_id)


async def _handle_callback(callback_query: dict) -> None:
    cb_id = callback_query.get("id", "")
    data = callback_query.get("data", "")

    if data.startswith("approve:") or data.startswith("reject:"):
        action, task_id = data.split(":", 1)
        import httpx
        try:
            admin = os.environ.get("LIMA_ADMIN_TOKEN", "")
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.post(
                    f"http://127.0.0.1:8080/agent/tasks/{task_id}/review",
                    headers={"Authorization": f"Bearer {admin}"},
                    json={"approved": action == "approve"},
                )
                if r.status_code == 200:
                    result_text = "approved" if action == "approve" else "rejected"
                    await telegram_bot.answer_callback(cb_id, f"Task {task_id} {result_text}")
                else:
                    await telegram_bot.answer_callback(cb_id, f"Review failed: {r.status_code}")
        except Exception as e:
            await telegram_bot.answer_callback(cb_id, f"Error: {e}")
    elif data == "restart:confirm":
        await telegram_bot.answer_callback(cb_id, "Restarting...")
        subprocess.Popen(
            ["systemctl", "restart", "lima-router"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    elif data == "restart:cancel":
        await telegram_bot.answer_callback(cb_id, "Cancelled")
    else:
        await telegram_bot.answer_callback(cb_id, "Unknown action")


# --- Endpoints ---

@router.post("/webhook")
async def webhook(request: Request):
    secret = request.headers.get("x-telegram-bot-api-secret-token", "")
    expected = _get_webhook_secret()
    if expected and secret != expected:
        logger.warning("Webhook secret mismatch")
        return {"ok": True}

    body = await request.json()
    message = body.get("message")
    callback_query = body.get("callback_query")

    if message and message.get("text", "").startswith("/"):
        chat_id = str(message["chat"]["id"])
        if not telegram_bot.is_authorized(chat_id):
            logger.warning("Unauthorized chat_id: %s", chat_id)
            return {"ok": True}
        await _dispatch_command(chat_id, message["text"])
    elif message and message.get("text"):
        chat_id = str(message["chat"]["id"])
        if telegram_bot.is_authorized(chat_id):
            await cmd_chat(chat_id, message["text"])
    elif callback_query:
        cb_chat_id = str(callback_query.get("message", {}).get("chat", {}).get("id", ""))
        if not telegram_bot.is_authorized(cb_chat_id):
            logger.warning("Unauthorized callback from chat_id: %s", cb_chat_id)
            return {"ok": True}
        await _handle_callback(callback_query)

    return {"ok": True}


@router.post("/setup", dependencies=[Depends(_require_admin)])
async def setup_webhook(body: SetupBody):
    result = await telegram_bot._api_call("setWebhook", {
        "url": body.url,
        "secret_token": _get_webhook_secret(),
    })
    return {"ok": True, "result": result}


# --- Daily digest ---

_DIGEST_HOUR = int(os.environ.get("TELEGRAM_DIGEST_HOUR", "9"))
_last_digest_day: str = ""


async def _send_daily_digest() -> None:
    hmap = health_tracker.get_health_map()
    counts = {"healthy": 0, "degraded": 0, "dead": 0}
    for state in hmap.values():
        counts[state] = counts.get(state, 0) + 1
    summary = budget_manager.get_usage_summary()
    total_reqs = sum(v for v in summary.values() if isinstance(v, (int, float)))
    text = (
        f"*Daily Digest*\n"
        f"Backends: {counts['healthy']} healthy, {counts['degraded']} degraded, {counts['dead']} dead\n"
        f"Requests today: {total_reqs}\n"
    )
    dead_list = [b for b, s in hmap.items() if s == "dead"]
    if dead_list:
        text += f"Dead: {', '.join(dead_list[:10])}"
    await telegram_bot.send_message(text)


async def _digest_loop() -> None:
    global _last_digest_day
    while True:
        await asyncio.sleep(60)
        now = time.localtime()
        today = time.strftime("%Y-%m-%d")
        if now.tm_hour == _DIGEST_HOUR and _last_digest_day != today:
            _last_digest_day = today
            try:
                await _send_daily_digest()
            except Exception:
                logger.exception("Daily digest failed")


@router.on_event("startup")
async def _start_digest_task():
    if telegram_bot.is_configured():
        asyncio.create_task(_digest_loop())
        await start_probe_loop()
