"""LiMa native device app chat history and audio routes (manager-mobile)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse

from device_logic.access import require_device_access
from device_logic.auth import authorize
from device_logic.db import connect
from device_logic.http import err

router = APIRouter(prefix="/device/v1/app", tags=["device-app-chat"])


@router.get("/devices/{device_id}/chat-sessions")
async def list_chat_sessions(device_id: str, authorization: str = Header(default="")) -> Any:
    """List chat sessions for a device.

    Currently returns an empty list; future implementation can persist
    conversation summaries from device voice transcripts.
    """
    account = authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    with connect() as conn:
        denied = require_device_access(conn, account, device_id)
        if denied:
            return denied
    return {"sessions": [], "total": 0, "count": 0}


@router.get("/devices/{device_id}/chat-sessions/{session_id}/messages")
async def get_chat_messages(device_id: str, session_id: str, authorization: str = Header(default="")) -> Any:
    """Get messages for a chat session.

    Currently returns an empty list; future implementation can persist
    transcript messages from device voice interactions.
    """
    account = authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    with connect() as conn:
        denied = require_device_access(conn, account, device_id)
        if denied:
            return denied
    return {"messages": [], "sessionId": session_id, "count": 0}


@router.get("/devices/{device_id}/chat-history")
async def list_chat_history(device_id: str, authorization: str = Header(default="")) -> Any:
    """List audio-capable chat history entries for voiceprint vector selection.

    Currently returns an empty list; future implementation can persist
    voice transcripts and filter entries that have an associated audio_id.
    """
    account = authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    with connect() as conn:
        denied = require_device_access(conn, account, device_id)
        if denied:
            return denied
    return {"chatHistory": [], "count": 0}


@router.get("/devices/{device_id}/audio/{audio_id}")
async def get_audio_info(device_id: str, audio_id: str, authorization: str = Header(default="")) -> Any:
    """Return metadata for an audio recording tied to a device."""
    account = authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    if not audio_id:
        return err(400, "audio_id is required", 400)
    with connect() as conn:
        denied = require_device_access(conn, account, device_id)
        if denied:
            return denied
    from routes.upload import _AUDIO_EXTENSIONS, _safe_upload_path
    from routes.upload_tokens import upload_access_token

    if _safe_upload_path(audio_id, allowed_extensions=_AUDIO_EXTENSIONS) is None:
        return err(404, "audio not found", 404)
    token = upload_access_token(audio_id)
    return {
        "audioId": audio_id,
        "url": f"/uploads/{audio_id}?token={token}",
        "contentType": "audio/wav",
    }
