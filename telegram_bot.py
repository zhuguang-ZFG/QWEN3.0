"""Telegram Bot core library for LiMa project notifications and approvals."""

import logging
import os

import httpx

logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")
GFW_PROXY: str = os.getenv("GFW_PROXY", "http://127.0.0.1:7897")

_BASE_URL = "https://api.telegram.org/bot{token}/{method}"


def is_configured() -> bool:
    return bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)


def is_authorized(chat_id: int | str) -> bool:
    return str(chat_id) == TELEGRAM_CHAT_ID


async def _api_call(method: str, data: dict) -> dict | None:
    url = _BASE_URL.format(token=TELEGRAM_BOT_TOKEN, method=method)
    try:
        async with httpx.AsyncClient(proxy=GFW_PROXY, timeout=10.0) as client:
            resp = await client.post(url, json=data)
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPError as e:
        logger.warning("Telegram API %s failed: %s", method, e)
        return None
    except Exception as e:
        logger.warning("Telegram API %s unexpected error: %s", method, e)
        return None


async def send_message(
    text: str, parse_mode: str = "Markdown", chat_id: str = ""
) -> bool:
    if not is_configured():
        return False
    target = chat_id or TELEGRAM_CHAT_ID
    result = await _api_call("sendMessage", {
        "chat_id": target,
        "text": text,
        "parse_mode": parse_mode,
    })
    return result is not None and result.get("ok", False)


async def send_approval(
    task_id: str, summary: str, changed_files: list[str]
) -> bool:
    if not is_configured():
        return False
    files_text = "\n".join(f"• `{f}`" for f in changed_files[:20])
    text = f"*Task {task_id}*\n{summary}\n\n*Changed files:*\n{files_text}"
    keyboard = {
        "inline_keyboard": [[
            {"text": "✅ Approve", "callback_data": f"approve:{task_id}"},
            {"text": "❌ Reject", "callback_data": f"reject:{task_id}"},
        ]]
    }
    result = await _api_call("sendMessage", {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
        "reply_markup": keyboard,
    })
    return result is not None and result.get("ok", False)


_LEVEL_EMOJI = {"critical": "🔴", "warning": "🟡", "info": "🟢"}


async def send_alert(level: str, text: str) -> bool:
    emoji = _LEVEL_EMOJI.get(level.lower(), "⚪")
    return await send_message(f"{emoji} *[{level.upper()}]* {text}")


async def answer_callback(callback_query_id: str, text: str) -> bool:
    result = await _api_call("answerCallbackQuery", {
        "callback_query_id": callback_query_id,
        "text": text,
    })
    return result is not None and result.get("ok", False)
