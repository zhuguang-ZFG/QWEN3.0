"""Telegram Bot core library for LiMa project notifications and approvals."""

import logging
import os

import httpx

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.telegram.org/bot{token}/{method}"


def _bot_token() -> str:
    return os.getenv("TELEGRAM_BOT_TOKEN", "")


def _chat_id() -> str:
    return os.getenv("TELEGRAM_CHAT_ID", "")


def _gfw_proxy() -> str:
    return os.getenv("GFW_PROXY", "http://127.0.0.1:7897")


def is_configured() -> bool:
    return bool(_bot_token() and _chat_id())


def is_authorized(chat_id: int | str) -> bool:
    return str(chat_id) == _chat_id()


def parse_approval_callback(data: str) -> dict:
    if not data or ":" not in data:
        return {"ok": False, "error": "Invalid callback payload"}
    action, task_id = data.split(":", 1)
    task_id = task_id.strip()
    if action == "approve" and task_id:
        return {"ok": True, "decision": "approved", "task_id": task_id}
    if action == "reject" and task_id:
        return {"ok": True, "decision": "rejected", "task_id": task_id}
    return {"ok": False, "error": "Unsupported callback payload"}


def _gfw_proxy() -> str:
    return os.getenv("GFW_PROXY", "http://127.0.0.1:7897")


def _telegram_proxy_candidates() -> list[str | None]:
    """Prefer configured proxy for local dev; fall back to direct on VPS."""
    if os.getenv("TELEGRAM_NO_PROXY", "").strip().lower() in {"1", "true", "yes"}:
        return [None]
    explicit = os.getenv("TELEGRAM_PROXY", "").strip()
    if explicit:
        return [explicit, None]
    gfw = os.getenv("GFW_PROXY", "").strip() or _gfw_proxy()
    return [gfw, None]


async def _api_call(method: str, data: dict) -> dict | None:
    url = _BASE_URL.format(token=_bot_token(), method=method)
    last_error: Exception | None = None
    for proxy in _telegram_proxy_candidates():
        try:
            async with httpx.AsyncClient(proxy=proxy, timeout=10.0) as client:
                resp = await client.post(url, json=data)
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPError as exc:
            last_error = exc
            if proxy is not None:
                logger.debug(
                    "Telegram API %s via proxy failed, trying next transport: %s",
                    method,
                    type(exc).__name__,
                )
                continue
            logger.warning("Telegram API %s failed: %s", method, exc)
            return None
        except Exception as exc:
            last_error = exc
            logger.warning("Telegram API %s unexpected error: %s", method, exc)
            return None
    if last_error is not None:
        logger.warning("Telegram API %s failed after transport attempts: %s", method, last_error)
    return None


async def send_message(
    text: str, parse_mode: str = "Markdown", chat_id: str = ""
) -> bool:
    if not is_configured():
        return False
    target = chat_id or _chat_id()
    if len(text) > 4000:
        text = text[:3997] + "..."
    result = await _api_call("sendMessage", {
        "chat_id": target,
        "text": text,
        "parse_mode": parse_mode,
    })
    if result is not None and result.get("ok", False):
        return True
    if parse_mode and parse_mode != "":
        result = await _api_call("sendMessage", {
            "chat_id": target,
            "text": text,
        })
        return result is not None and result.get("ok", False)
    return False


async def send_approval(
    task_id: str, summary: str, changed_files: list[str]
) -> bool:
    if not is_configured():
        return False
    files_text = "\n".join(f"- `{f}`" for f in changed_files[:20])
    text = f"*Task {task_id}*\n{summary}\n\n*Changed files:*\n{files_text}"
    keyboard = {
        "inline_keyboard": [[
            {"text": "Approve", "callback_data": f"approve:{task_id}"},
            {"text": "Reject", "callback_data": f"reject:{task_id}"},
        ]]
    }
    result = await _api_call("sendMessage", {
        "chat_id": _chat_id(),
        "text": text,
        "parse_mode": "Markdown",
        "reply_markup": keyboard,
    })
    return result is not None and result.get("ok", False)


_LEVEL_EMOJI = {
    "critical": "\U0001f534",
    "warning": "\U0001f7e1",
    "info": "\U0001f535",
}


async def send_alert(level: str, text: str) -> bool:
    emoji = _LEVEL_EMOJI.get(level.lower(), "\u26a0\ufe0f")
    return await send_message(f"{emoji} *[{level.upper()}]* {text}")


async def answer_callback(callback_query_id: str, text: str) -> bool:
    result = await _api_call("answerCallbackQuery", {
        "callback_query_id": callback_query_id,
        "text": text,
    })
    return result is not None and result.get("ok", False)


async def send_voice(audio_bytes: bytes, chat_id: str = "", caption: str = "") -> bool:
    """发送 OGG Opus 语音消息到 Telegram。"""
    if not is_configured():
        return False
    target = chat_id or _chat_id()
    url = _BASE_URL.format(token=_bot_token(), method="sendVoice")
    data = {"chat_id": target}
    if caption:
        data["caption"] = caption
    files = {"voice": ("voice.ogg", audio_bytes, "audio/ogg")}
    for proxy in _telegram_proxy_candidates():
        try:
            async with httpx.AsyncClient(proxy=proxy, timeout=30.0) as client:
                resp = await client.post(url, data=data, files=files)
                resp.raise_for_status()
                result = resp.json()
                return result.get("ok", False)
        except Exception as exc:
            if proxy is not None:
                logger.debug(
                    "Telegram sendVoice via proxy failed, trying direct: %s",
                    type(exc).__name__,
                )
                continue
            logger.warning("Telegram sendVoice failed: %s", exc)
            return False
    return False
