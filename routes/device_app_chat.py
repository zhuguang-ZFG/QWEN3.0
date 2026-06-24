"""LiMa native device app chat history and audio routes (manager-mobile)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, Query, Request
from fastapi.responses import JSONResponse

from device_logic.access import require_device_access
from device_logic.auth import authorize
from device_logic.chat_store import (
    create_session,
    get_messages,
    list_audio_history,
    list_sessions,
    session_payload,
    message_payload,
    audio_history_payload,
    soft_delete_session,
)
from device_logic.db import connect
from device_logic.http import err, read_body, str_field

router = APIRouter(prefix="/device/v1/app", tags=["device-app-chat"])


def _not_found(message: str = "session not found") -> JSONResponse:
    return err(404, message, 404)


@router.post("/devices/{device_id}/chat-sessions")
async def create_chat_session(
    device_id: str, request: Request, authorization: str = Header(default="")
) -> Any:
    """Create a chat session for a device."""
    account = authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    body = await read_body(request)
    if isinstance(body, JSONResponse):
        return body
    with connect() as conn:
        denied = require_device_access(conn, account, device_id)
        if denied:
            return denied
        session_id = create_session(conn, device_id, account["id"], str_field(body, "title"))
        row = conn.execute("SELECT * FROM v2_chat_session WHERE id=?", (session_id,)).fetchone()
    return session_payload(row)


@router.get("/devices/{device_id}/chat-sessions")
async def list_chat_sessions(
    device_id: str, authorization: str = Header(default="")
) -> Any:
    """List active chat sessions for a device."""
    account = authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    with connect() as conn:
        denied = require_device_access(conn, account, device_id)
        if denied:
            return denied
        rows = list_sessions(conn, device_id, account["id"])
    return {"sessions": [session_payload(row) for row in rows], "count": len(rows)}


@router.get("/devices/{device_id}/chat-sessions/{session_id}/messages")
async def get_chat_messages(
    device_id: str,
    session_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    authorization: str = Header(default=""),
) -> Any:
    """Get paginated messages for a chat session."""
    account = authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    with connect() as conn:
        denied = require_device_access(conn, account, device_id)
        if denied:
            return denied
        row = conn.execute(
            "SELECT device_id FROM v2_chat_session WHERE id=? AND account_id=? AND status='active'",
            (session_id, account["id"]),
        ).fetchone()
        if row is None or row["device_id"] != device_id:
            return _not_found()
        rows = get_messages(conn, session_id, limit=limit, offset=offset)
    return {"messages": [message_payload(row) for row in rows], "sessionId": session_id, "count": len(rows)}


@router.delete("/chat-sessions/{session_id}")
async def delete_chat_session(session_id: str, authorization: str = Header(default="")) -> Any:
    """Soft-delete a chat session if the caller owns it."""
    account = authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    with connect() as conn:
        deleted = soft_delete_session(conn, session_id, account["id"])
    if not deleted:
        return _not_found()
    return {"sessionId": session_id, "status": "deleted"}


@router.get("/devices/{device_id}/chat-history")
async def list_chat_history(device_id: str, authorization: str = Header(default="")) -> Any:
    """List user messages that have an associated audio_id (for voiceprint selection)."""
    account = authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    with connect() as conn:
        denied = require_device_access(conn, account, device_id)
        if denied:
            return denied
        rows = list_audio_history(conn, device_id)
    return {"chatHistory": [audio_history_payload(row) for row in rows], "count": len(rows)}


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
