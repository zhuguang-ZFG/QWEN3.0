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
    cmd_eval, cmd_task, cmd_tasks, cmd_cache, cmd_stop, start_probe_loop,
    cmd_voice, cmd_voicechat, start_broadcast_loop, _operator_error,
    cmd_github, cmd_device,
)
from routes.telegram_eval_tools import cmd_evalslice, cmd_evalreport, cmd_archiveeval
from routes.telegram_diag_tools import cmd_oldllm
from routes.telegram_public_tools import (
    cmd_hot,
    cmd_news,
    cmd_public_tool,
    cmd_tools,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/telegram")

_WEBHOOK_SECRET = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "")
_voicechat_enabled: dict[str, bool] = {}


async def _handle_voice_message(chat_id: str, voice: dict) -> None:
    """STT: 用户发语音 → 转文字 → 当作文字消息处理。"""
    try:
        import stt
        file_id = voice.get("file_id", "")
        text = await stt.voice_to_text(file_id)
        if not text:
            await telegram_bot.send_message("(语音识别失败)", chat_id=chat_id)
            return
        await telegram_bot.send_message(f"🎤 {text}", chat_id=chat_id)
        await cmd_chat(chat_id, text)
    except Exception:
        logger.exception("Voice STT failed")
        await telegram_bot.send_message(_operator_error("voice_stt"), chat_id=chat_id)


async def _send_voicechat_reply(chat_id: str, user_text: str) -> None:
    """voicechat 模式：对最后一条 AI 回复生成语音。"""
    try:
        from routes.telegram_commands import _get_history
        history = _get_history(chat_id)
        if not history:
            return
        last_msg = history[-1]
        if last_msg.get("role") != "assistant":
            return
        reply_text = last_msg.get("content", "")[:500]
        if not reply_text:
            return
        from routes.telegram_commands import _optional_import
        mimo_tts = _optional_import("mimo_tts")
        if mimo_tts is None:
            return
        ogg = await mimo_tts.tts_ogg(reply_text)
        if ogg:
            await telegram_bot.send_voice(ogg, chat_id=chat_id)
    except Exception as exc:
        logger.warning("Voicechat TTS failed: %s", type(exc).__name__)


def _get_webhook_secret() -> str:
    return os.environ.get("TELEGRAM_WEBHOOK_SECRET", "") or _WEBHOOK_SECRET


_ADMIN_TOKEN = os.environ.get("LIMA_ADMIN_TOKEN", "")


def _get_admin_token() -> str:
    return os.environ.get("LIMA_ADMIN_TOKEN", "") or _ADMIN_TOKEN


async def _require_admin(authorization: str = Header(default="")) -> None:
    token_expected = _get_admin_token()
    if not token_expected:
        raise HTTPException(503, "LIMA_ADMIN_TOKEN not configured")
    from access_guard import extract_bearer_token, constant_time_equals
    presented = extract_bearer_token(authorization)
    if not presented or not constant_time_equals(presented, token_expected):
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
    blocks = []
    for group, body in summary.items():
        blocks.append(f"*{group}*\n{body}")
    await telegram_bot.send_message(
        "\n\n".join(blocks) or "No usage data",
        parse_mode="Markdown",
        chat_id=chat_id,
    )


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
    except Exception:
        logger.exception("cmd_logs failed")
        await telegram_bot.send_message(_operator_error("logs"), chat_id=chat_id)


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


async def _dispatch_command_lines(chat_id: str, text: str) -> None:
    """Run each slash-command line in a multi-line Telegram message."""
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip().startswith("/")]
    if not lines:
        await _dispatch_command(chat_id, text)
        return
    for line in lines:
        await _dispatch_command(chat_id, line)


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
    elif cmd == "/stop":
        await cmd_stop(chat_id, arg.strip())
    elif cmd == "/cache":
        await cmd_cache(chat_id)
    elif cmd == "/voice":
        await cmd_voice(chat_id, arg)
    elif cmd == "/voicechat":
        await cmd_voicechat(chat_id, arg)
    elif cmd == "/logs":
        await _cmd_logs(chat_id, arg.strip())
    elif cmd == "/restart":
        await _cmd_restart(chat_id)
    elif cmd == "/github":
        await cmd_github(chat_id, arg)
    elif cmd == "/device":
        await cmd_device(chat_id, arg)
    elif cmd == "/news":
        await cmd_news(chat_id, arg)
    elif cmd == "/hot":
        await cmd_hot(chat_id, arg)
    elif cmd == "/tools":
        await cmd_tools(chat_id)
    elif cmd == "/weather":
        await cmd_public_tool(chat_id, "weather", arg)
    elif cmd == "/wiki":
        await cmd_public_tool(chat_id, "wiki", arg)
    elif cmd == "/exchange":
        await cmd_public_tool(chat_id, "exchange", arg)
    elif cmd == "/calc":
        await cmd_public_tool(chat_id, "calc", arg)
    elif cmd == "/time":
        await cmd_public_tool(chat_id, "time", arg)
    elif cmd == "/translate":
        await cmd_public_tool(chat_id, "translate", arg)
    elif cmd == "/stock":
        await cmd_public_tool(chat_id, "stock", arg)
    elif cmd == "/holiday":
        await cmd_public_tool(chat_id, "holiday", arg)
    elif cmd == "/ip":
        await cmd_public_tool(chat_id, "ip", arg)
    elif cmd == "/earthquake":
        await cmd_public_tool(chat_id, "earthquake", arg)
    elif cmd == "/dict":
        await cmd_public_tool(chat_id, "dict", arg)
    elif cmd == "/whois":
        await cmd_public_tool(chat_id, "whois", arg)
    elif cmd == "/qr":
        await cmd_public_tool(chat_id, "qr", arg)
    elif cmd == "/geocode":
        await cmd_public_tool(chat_id, "geocode", arg)
    elif cmd == "/random":
        await cmd_public_tool(chat_id, "randomuser", arg)
    elif cmd == "/ssl":
        await cmd_public_tool(chat_id, "ssl", arg)
    elif cmd == "/regex":
        await cmd_public_tool(chat_id, "regex", arg)
    elif cmd == "/image":
        await cmd_public_tool(chat_id, "image", arg)
    elif cmd == "/uuid":
        await cmd_public_tool(chat_id, "uuid", arg)
    elif cmd == "/evalslice":
        await cmd_evalslice(chat_id, arg)
    elif cmd == "/evalreport":
        await cmd_evalreport(chat_id, arg)
    elif cmd == "/archiveeval":
        await cmd_archiveeval(chat_id, arg)
    elif cmd == "/oldllm":
        await cmd_oldllm(chat_id, arg)
    elif cmd == "/start":
        await telegram_bot.send_message(
            "LiMa Bot ready.\n/status /health /budget /top /uptime\n"
            "/chat /clear /code /eval /evalslice /evalreport /archiveeval /oldllm /voice\n"
            "/github /device status\n"
            "/tools /news /hot /weather /wiki /exchange\n"
            "/dict /whois /qr /geocode /random /ssl /regex /image /uuid\n"
            "/logs /restart /task /tasks",
            chat_id=chat_id,
        )
    else:
        await telegram_bot.send_message("Unknown command", chat_id=chat_id)


def _review_callback_notice(status_code: int, task_id: str, decision: str) -> str:
    if status_code == 200:
        return f"Task {task_id} {decision}"
    if status_code == 409:
        return f"Task {task_id} 已审批，无需重复操作"
    return f"Review failed: {status_code}"


async def _handle_callback(callback_query: dict) -> None:
    cb_id = callback_query.get("id", "")
    data = callback_query.get("data", "")

    if data.startswith("approve:") or data.startswith("reject:"):
        action, task_id = data.split(":", 1)
        import httpx
        try:
            admin = os.environ.get("LIMA_ADMIN_TOKEN", "")
            decision = "approved" if action == "approve" else "rejected"
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.post(
                    f"http://127.0.0.1:8080/agent/tasks/{task_id}/review",
                    headers={"Authorization": f"Bearer {admin}"},
                    json={"decision": decision, "reviewer": "telegram"},
                )
                await telegram_bot.answer_callback(
                    cb_id,
                    _review_callback_notice(r.status_code, task_id, decision),
                )
        except Exception:
            logger.exception("telegram task review callback failed")
            await telegram_bot.answer_callback(cb_id, _operator_error("task_review"))
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

def _verify_webhook_secret(secret: str) -> None:
    """Fail closed when Telegram is configured but webhook auth is missing or wrong."""
    if not telegram_bot.is_configured():
        return
    expected = _get_webhook_secret()
    if not expected:
        raise HTTPException(503, "TELEGRAM_WEBHOOK_SECRET not configured")
    from access_guard import constant_time_equals
    if not constant_time_equals(secret, expected):
        raise HTTPException(403, "Forbidden")


@router.post("/webhook")
async def webhook(request: Request):
    secret = request.headers.get("x-telegram-bot-api-secret-token", "")
    _verify_webhook_secret(secret)

    body = await request.json()
    message = body.get("message")
    callback_query = body.get("callback_query")
    inline_query = body.get("inline_query")

    if inline_query:
        from telegram_inline import handle_inline_query

        await handle_inline_query(inline_query)
        return {"ok": True}

    if message:
        from telegram_b2b import handle_inbound_b2b

        handled, reply_chat, ack = await handle_inbound_b2b(message)
        if handled:
            if reply_chat and ack:
                await telegram_bot.send_message(ack, chat_id=reply_chat, parse_mode="")
            return {"ok": True}

    if message and message.get("text", "").startswith("/"):
        chat_id = str(message["chat"]["id"])
        if not telegram_bot.is_authorized(chat_id):
            logger.warning("Unauthorized chat_id: %s", chat_id)
            return {"ok": True}
        await _dispatch_command_lines(chat_id, message["text"])
    elif message and message.get("text"):
        chat_id = str(message["chat"]["id"])
        if telegram_bot.is_authorized(chat_id):
            text = message["text"]
            await cmd_chat(chat_id, text)
            if _voicechat_enabled.get(chat_id):
                await _send_voicechat_reply(chat_id, text)
    elif message and message.get("voice"):
        chat_id = str(message["chat"]["id"])
        if telegram_bot.is_authorized(chat_id):
            await _handle_voice_message(chat_id, message["voice"])
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
_startup_started = False


async def _send_daily_digest() -> None:
    from telegram_digest import send_unified_digest

    await send_unified_digest()


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


async def start_telegram_webhook() -> None:
    global _startup_started
    if _startup_started or not telegram_bot.is_configured():
        return
    _startup_started = True
    asyncio.create_task(_digest_loop())
    await start_probe_loop()
    await start_broadcast_loop()
