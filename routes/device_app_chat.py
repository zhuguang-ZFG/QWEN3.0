"""LiMa native device app chat history and audio routes (voiceprint enrollment)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse

from device_logic.access import require_device_access
from device_logic.auth import authorize
from device_logic.chat_store import list_audio_history
from device_logic.db import connect
from device_logic.http import err

router = APIRouter(prefix="/device/v1/app", tags=["device-app-chat"])


@router.get("/devices/{device_id}/chat-history")
async def device_chat_history(device_id: str, authorization: str = Header(default="")) -> Any:
    """Return user audio chat messages for voiceprint vector selection."""
    account = authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    with connect() as conn:
        denied = require_device_access(conn, account, device_id)
        if denied:
            return denied
        rows = list_audio_history(conn, device_id)
    chat_history = [{"content": row["content"], "audioId": row["audio_id"]} for row in rows]
    return {"chatHistory": chat_history, "count": len(chat_history)}


@router.get("/audio/{audio_id}")
async def audio_download_meta(audio_id: str, authorization: str = Header(default="")) -> Any:
    """Return playback metadata for a stored audio clip."""
    account = authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM v2_audio_record WHERE audio_id=?",
            (audio_id,),
        ).fetchone()
        if row is None:
            return err(404, "audio not found", 404)
        denied = require_device_access(conn, account, row["device_id"])
        if denied:
            return denied
    # Playback URL is served when binary storage is wired; clients poll this meta first.
    return {
        "audioId": audio_id,
        "url": "",
        "contentType": "audio/mpeg",
    }
