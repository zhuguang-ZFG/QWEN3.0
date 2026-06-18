"""Voice/text transcript handling for text-chat capable device sessions."""

from __future__ import annotations

import logging
from typing import Any

from device_gateway.protocol import ProtocolError, audio_reply_frame, voice_status_frame
from device_gateway.sessions import DeviceSession
from routes.device_gateway_dispatch import send_ws_error

_log = logging.getLogger(__name__)


def _voice_enabled() -> bool:
    from device_voice import VOICE_ENABLED

    return VOICE_ENABLED


async def handle_voice_transcript(
    session: DeviceSession,
    device_id: str,
    text: str,
    request_id: str | None,
) -> bool:
    """Handle a text transcript for text-chat capable clients (e.g. digital human)."""
    if not text or not text.strip():
        await send_ws_error(
            session.websocket,
            ProtocolError("E_INVALID_MESSAGE", "transcript text must be non-empty", request_id),
        )
        return True

    if not _voice_enabled():
        await send_ws_error(
            session.websocket,
            ProtocolError("E_VOICE_DISABLED", "voice pipeline is not enabled", request_id),
        )
        return True

    await session.send_json(voice_status_frame(device_id, "thinking", transcript=text, request_id=request_id))
    try:
        from device_voice.dialogue import process_text_utterance

        result = await process_text_utterance(text, device_id)
    except Exception as exc:
        _log.warning("device=%s voice text dialogue failed: %s", device_id, type(exc).__name__, exc_info=True)
        await session.send_json(voice_status_frame(device_id, "idle", request_id=request_id))
        return True

    reply_text = result.get("reply_text", "")
    reply_audio = result.get("reply_audio", b"")
    if reply_text:
        await session.send_json(voice_status_frame(device_id, "speaking", transcript=reply_text, request_id=request_id))
    if reply_audio:
        await session.send_json(audio_reply_frame(device_id, request_id=request_id))
        await session.websocket.send_bytes(reply_audio)
    await session.send_json(voice_status_frame(device_id, "idle", request_id=request_id))
    return True
