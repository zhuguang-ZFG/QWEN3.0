"""Chat session/message persistence for the native device app."""

from __future__ import annotations

import logging
import sqlite3
from typing import Any

from device_logic.http import new_id, now

_log = logging.getLogger(__name__)


ROLES = frozenset({"user", "assistant", "system"})


def _owner_account_id(conn: sqlite3.Connection, device_id: str) -> str | None:
    """Return the owner account for a device, or any active binder as fallback."""
    row = conn.execute(
        """
        SELECT account_id FROM v2_device_binding
        WHERE device_id=? AND bind_mode='owner' AND status='active'
        LIMIT 1
        """,
        (device_id,),
    ).fetchone()
    if row is not None:
        return row["account_id"]
    row = conn.execute(
        """
        SELECT account_id FROM v2_device_binding
        WHERE device_id=? AND status='active'
        LIMIT 1
        """,
        (device_id,),
    ).fetchone()
    return row["account_id"] if row is not None else None


def create_session(conn: sqlite3.Connection, device_id: str, account_id: str, title: str = "") -> str:
    """Create a new chat session and return its id."""
    session_id = new_id()
    conn.execute(
        """
        INSERT INTO v2_chat_session (id, device_id, account_id, title, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (session_id, device_id, account_id, title, now()),
    )
    conn.commit()
    return session_id


def list_sessions(
    conn: sqlite3.Connection, device_id: str, account_id: str, status: str = "active"
) -> list[sqlite3.Row]:
    """Return sessions for a device, optionally filtered by account and status."""
    rows = conn.execute(
        """
        SELECT * FROM v2_chat_session
        WHERE device_id=? AND account_id=? AND status=?
        ORDER BY last_message_at IS NULL, last_message_at DESC, created_at DESC
        """,
        (device_id, account_id, status),
    ).fetchall()
    return rows


def session_exists(conn: sqlite3.Connection, session_id: str, account_id: str) -> bool:
    """Check whether a session is owned by the given account."""
    row = conn.execute(
        "SELECT 1 FROM v2_chat_session WHERE id=? AND account_id=? AND status='active'",
        (session_id, account_id),
    ).fetchone()
    return row is not None


def soft_delete_session(conn: sqlite3.Connection, session_id: str, account_id: str) -> bool:
    """Soft-delete a session if it belongs to the account. Returns True if a row was updated."""
    cursor = conn.execute(
        "UPDATE v2_chat_session SET status='deleted' WHERE id=? AND account_id=? AND status='active'",
        (session_id, account_id),
    )
    conn.commit()
    return cursor.rowcount > 0


def get_messages(
    conn: sqlite3.Connection, session_id: str, limit: int = 50, offset: int = 0
) -> list[sqlite3.Row]:
    """Return paginated messages for a session."""
    rows = conn.execute(
        """
        SELECT * FROM v2_chat_message
        WHERE session_id=?
        ORDER BY created_at ASC
        LIMIT ? OFFSET ?
        """,
        (session_id, limit, offset),
    ).fetchall()
    return rows


def ensure_active_session(conn: sqlite3.Connection, device_id: str) -> str | None:
    """Return the latest active session for a device, creating one implicitly if needed."""
    row = conn.execute(
        """
        SELECT id FROM v2_chat_session
        WHERE device_id=? AND status='active'
        ORDER BY last_message_at IS NULL, last_message_at DESC, created_at DESC
        LIMIT 1
        """,
        (device_id,),
    ).fetchone()
    if row is not None:
        return row["id"]
    account_id = _owner_account_id(conn, device_id)
    if account_id is None:
        _log.warning("device=%s has no bound account; skipping implicit session creation", device_id)
        return None
    return create_session(conn, device_id, account_id)


def insert_message(
    conn: sqlite3.Connection,
    session_id: str,
    role: str,
    content: str,
    *,
    audio_id: str | None = None,
    voiceprint_id: str | None = None,
) -> str:
    """Insert a chat message and update session's last_message_at."""
    if role not in ROLES:
        raise ValueError(f"invalid role: {role}")
    message_id = new_id()
    created = now()
    conn.execute(
        """
        INSERT INTO v2_chat_message (id, session_id, role, content, audio_id, voiceprint_id, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (message_id, session_id, role, content, audio_id, voiceprint_id, created),
    )
    conn.execute(
        "UPDATE v2_chat_session SET last_message_at=? WHERE id=?",
        (created, session_id),
    )
    conn.commit()
    return message_id


def list_audio_history(conn: sqlite3.Connection, device_id: str) -> list[sqlite3.Row]:
    """Return user messages with an audio_id, joined with audio record metadata."""
    rows = conn.execute(
        """
        SELECT
            m.id AS message_id,
            m.session_id,
            m.role,
            m.content,
            m.audio_id,
            m.voiceprint_id,
            m.created_at,
            a.duration_ms
        FROM v2_chat_message m
        JOIN v2_audio_record a ON a.audio_id = m.audio_id
        WHERE m.role='user' AND a.device_id=? AND m.audio_id IS NOT NULL
        ORDER BY m.created_at DESC
        """,
        (device_id,),
    ).fetchall()
    return rows


def session_payload(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "sessionId": row["id"],
        "id": row["id"],
        "deviceId": row["device_id"],
        "accountId": row["account_id"],
        "title": row["title"] or "",
        "lastMessageAt": row["last_message_at"] or "",
        "createdAt": row["created_at"],
        "status": row["status"],
    }


def message_payload(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "messageId": row["id"],
        "id": row["id"],
        "sessionId": row["session_id"],
        "role": row["role"],
        "content": row["content"],
        "audioId": row["audio_id"] or "",
        "voiceprintId": row["voiceprint_id"] or "",
        "createdAt": row["created_at"],
    }


def audio_history_payload(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "messageId": row["message_id"],
        "sessionId": row["session_id"],
        "role": row["role"],
        "content": row["content"],
        "audioId": row["audio_id"],
        "voiceprintId": row["voiceprint_id"] or "",
        "durationMs": row["duration_ms"],
        "createdAt": row["created_at"],
    }


def persist_user_transcript(conn: sqlite3.Connection, device_id: str, content: str) -> str | None:
    """Persist a user transcript into the device's latest active session.

    If no active session exists, one is created implicitly using the device's
    bound account. Returns the message id, or None if persistence was skipped.
    """
    session_id = ensure_active_session(conn, device_id)
    if session_id is None:
        return None
    return insert_message(conn, session_id, "user", content)
