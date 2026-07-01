"""SQLite metadata store for the Telegram-backed image gallery.

Actual image bytes are stored on Telegram; this module only keeps file IDs,
names, sizes, and tags so the mini-program can list and select them.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from device_logic.db import connect

_log = logging.getLogger(__name__)


def _new_id() -> str:
    return uuid.uuid4().hex


def add_image(
    account_id: str,
    file_id: str,
    filename: str,
    size_bytes: int,
    mime_type: str = "image/jpeg",
    thumb_url: str | None = None,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    """Add a gallery image record and return its metadata."""
    image_id = _new_id()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO v2_gallery_image
                (id, account_id, file_id, filename, mime_type, size_bytes, thumb_url, tags, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active')
            """,
            (
                image_id,
                account_id,
                file_id,
                filename,
                mime_type,
                size_bytes,
                thumb_url,
                json.dumps(tags or [], ensure_ascii=False),
            ),
        )
        conn.commit()
    return {
        "id": image_id,
        "accountId": account_id,
        "fileId": file_id,
        "filename": filename,
        "mimeType": mime_type,
        "sizeBytes": size_bytes,
        "thumbUrl": thumb_url,
        "tags": tags or [],
        "status": "active",
    }


def list_images(
    account_id: str,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """List active gallery images for an account, newest first."""
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, account_id, file_id, filename, mime_type, size_bytes, thumb_url, tags, status, created_at
            FROM v2_gallery_image
            WHERE account_id = ? AND status = 'active'
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            (account_id, limit, offset),
        ).fetchall()
    return [_row_to_dict(row) for row in rows]


def get_image(image_id: str, account_id: str) -> dict[str, Any] | None:
    """Get a single gallery image if it belongs to the account and is active."""
    with connect() as conn:
        row = conn.execute(
            """
            SELECT id, account_id, file_id, filename, mime_type, size_bytes, thumb_url, tags, status, created_at
            FROM v2_gallery_image
            WHERE id = ? AND account_id = ? AND status = 'active'
            """,
            (image_id, account_id),
        ).fetchone()
    return _row_to_dict(row) if row else None


def delete_image(image_id: str, account_id: str) -> bool:
    """Soft-delete a gallery image. Returns True if a row was affected."""
    with connect() as conn:
        cursor = conn.execute(
            "UPDATE v2_gallery_image SET status = 'deleted' WHERE id = ? AND account_id = ? AND status = 'active'",
            (image_id, account_id),
        )
        conn.commit()
        affected = cursor.rowcount
    if affected:
        _log.info("soft-deleted gallery image %s for account %s", image_id, account_id)
    return bool(affected)


def _row_to_dict(row: Any) -> dict[str, Any]:
    tags_raw = row["tags"] or "[]"
    try:
        tags = json.loads(tags_raw)
    except json.JSONDecodeError:
        tags = []
    return {
        "id": row["id"],
        "accountId": row["account_id"],
        "fileId": row["file_id"],
        "filename": row["filename"],
        "mimeType": row["mime_type"],
        "sizeBytes": row["size_bytes"],
        "thumbUrl": row["thumb_url"],
        "tags": tags,
        "status": row["status"],
        "createdAt": row["created_at"],
    }
