"""LiMa native device app chat history and audio routes (voiceprint enrollment)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, Request
from fastapi.responses import FileResponse, JSONResponse

from device_logic.access import require_device_access
from device_logic.audio_store import resolve_storage_path
from device_logic.auth import authorize
from device_logic.chat_store import list_audio_history
from device_logic.db import connect
from device_logic.http import err

router = APIRouter(prefix="/device/v1/app", tags=["device-app-chat"])


def _audio_content_url(request: Request, audio_id: str) -> str:
    base = str(request.base_url).rstrip("/")
    return f"{base}/device/v1/app/audio/{audio_id}/content"


def _load_audio_row(conn, audio_id: str):
    return conn.execute(
        "SELECT * FROM v2_audio_record WHERE audio_id=?",
        (audio_id,),
    ).fetchone()


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
async def audio_download_meta(
    audio_id: str,
    request: Request,
    authorization: str = Header(default=""),
) -> Any:
    """Return playback metadata for a stored audio clip."""
    account = authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    with connect() as conn:
        row = _load_audio_row(conn, audio_id)
        if row is None:
            return err(404, "audio not found", 404)
        denied = require_device_access(conn, account, row["device_id"])
        if denied:
            return denied
    storage_path = str(row["storage_path"] or "")
    content_type = str(row["content_type"] or "audio/mpeg")
    url = _audio_content_url(request, audio_id) if resolve_storage_path(storage_path) else ""
    return {"audioId": audio_id, "url": url, "contentType": content_type}


@router.get("/audio/{audio_id}/content")
async def audio_download_content(audio_id: str, authorization: str = Header(default="")) -> Any:
    """Stream a stored audio clip after device-access authorization."""
    account = authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    with connect() as conn:
        row = _load_audio_row(conn, audio_id)
        if row is None:
            return err(404, "audio not found", 404)
        denied = require_device_access(conn, account, row["device_id"])
        if denied:
            return denied
    path = resolve_storage_path(str(row["storage_path"] or ""))
    if path is None:
        return err(404, "audio content is not available", 404)
    media_type = str(row["content_type"] or "audio/mpeg")
    return FileResponse(path, media_type=media_type, filename=path.name)
