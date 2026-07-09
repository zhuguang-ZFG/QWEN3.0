"""Device app voice routes — ASR transcription + intent resolution."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, File, Form, Header, UploadFile
from fastapi.responses import JSONResponse

import voice_app_ws_ticket
from routes.rate_limit_helper import check_key_limit
from device_gateway.intent import resolve_voice_task
from device_logic.access import require_device_control
from device_logic.audio_clips import save_device_audio_clip
from device_logic.auth import authorize
from device_logic.db import connect
from device_logic.http import err, new_id
from device_voice.asr import (
    AsrNotConfiguredError,
    content_type_for_audio,
    transcribe_audio,
)
from config.voice_settings import VOICE

_log = logging.getLogger(__name__)
router = APIRouter(prefix="/device/v1/app", tags=["device-app-voice"])


@router.post("/voice/transcribe")
async def transcribe_voice(
    authorization: str = Header(default=""),
    audio: UploadFile = File(...),
    device_id: str = Form(default=""),
) -> Any:
    """Transcribe uploaded audio and resolve a motion intent without creating a task."""
    account = authorize(authorization)
    if isinstance(account, JSONResponse):
        return account

    limited = check_key_limit(
        f"device_app_voice:{account['id']}",
        VOICE.transcribe_per_min,
    )
    if limited is not None:
        return limited

    audio_data = await audio.read()
    if not audio_data:
        return err(400, "audio file is empty", 400)
    if len(audio_data) > VOICE.max_audio_bytes:
        return err(413, "audio file is too large", 413)

    device_id = device_id.strip()
    if device_id:
        with connect() as conn:
            denied = require_device_control(conn, account, device_id)
            if denied:
                return denied

    try:
        text = await transcribe_audio(audio_data)
    except ValueError as exc:
        return err(400, str(exc), 400)
    except AsrNotConfiguredError as exc:
        _log.warning("voice transcribe unavailable: %s", exc)
        return err(503, "ASR is not configured", 503)
    except Exception as exc:
        _log.warning("voice transcribe failed: %s", type(exc).__name__, exc_info=True)
        return err(503, "ASR failed", 503)

    intent = resolve_voice_task(text)
    audio_id = new_id()
    persisted: dict[str, str] | None = None
    if device_id:
        with connect() as conn:
            persisted = save_device_audio_clip(
                conn,
                device_id,
                text,
                audio_data,
                content_type=content_type_for_audio(audio_data),
                audio_id=audio_id,
            )
        if persisted is None:
            return err(503, "device has no bound account for chat persistence", 503)

    payload: dict[str, Any] = {"text": text, "intent": intent}
    if persisted is not None:
        payload["audioId"] = persisted["audioId"]
    return payload


@router.post("/voice/ticket")
async def issue_voice_ticket(authorization: str = Header(default="")) -> Any:
    """Issue a one-time ticket for legacy /v1/voice WebSocket connections."""
    account = authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    return {
        "ticket": voice_app_ws_ticket.issue(account["id"]),
        "expires_in": voice_app_ws_ticket.TTL_SECONDS,
    }
