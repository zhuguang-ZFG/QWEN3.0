r"""TG-S3 v0.2 — Telegram as unlimited cold storage backend.

Stores files as Telegram documents with metadata in SQLite.
Operations: put (upload), list (catalog), get (retrieve by key).

Storage model:
  - Files uploaded via sendDocument to the operator chat
  - Metadata stored in data/tg_s3_store.db
  - Keys are auto-generated: tg3:<timestamp>:<filename>
  - Max file size: 50MB (Telegram bot limit)

Usage:
  from routes.telegram_tgs3 import tg_s3_put, tg_s3_list, tg_s3_get

  key = await tg_s3_put("eval_results.json", json_bytes)
  files = await tg_s3_list(prefix="eval")
  data = await tg_s3_get(key)
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import time
from pathlib import Path

import telegram_bot

_log = logging.getLogger(__name__)

_DB_PATH = os.environ.get("LIMA_TGS3_DB", str(Path(__file__).resolve().parent.parent / "data" / "tg_s3_store.db"))


def _get_conn() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(_DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tg_s3_objects (
            key TEXT PRIMARY KEY,
            filename TEXT NOT NULL,
            message_id INTEGER NOT NULL,
            file_id TEXT NOT NULL,
            size_bytes INTEGER DEFAULT 0,
            content_type TEXT DEFAULT 'application/octet-stream',
            tags TEXT DEFAULT '[]',
            stored_at REAL NOT NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tgs3_tags ON tg_s3_objects(tags)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tgs3_stored ON tg_s3_objects(stored_at DESC)")
    conn.commit()
    return conn


def _make_key(filename: str) -> str:
    ts = int(time.time() * 1000)
    safe = filename.replace(" ", "_").replace("/", "_")[:80]
    return f"tg3:{ts}:{safe}"


async def tg_s3_put(
    file_path: str | Path,
    *,
    filename: str = "",
    tags: list[str] | None = None,
    chat_id: str = "",
) -> str | None:
    """Upload a file to TG-S3. Returns the storage key, or None on failure."""
    path = Path(file_path)
    if not path.is_file():
        _log.warning("tg_s3_put: file not found %s", path)
        return None

    name = filename or path.name
    size = path.stat().st_size
    if size > 50 * 1024 * 1024:
        _log.warning("tg_s3_put: file too large %s (%d bytes)", name, size)
        return None

    # Detect content type
    ct = "application/octet-stream"
    ext = path.suffix.lower()
    ct_map = {
        ".json": "application/json", ".md": "text/markdown",
        ".txt": "text/plain", ".csv": "text/csv",
        ".py": "text/x-python", ".log": "text/plain",
        ".svg": "image/svg+xml", ".png": "image/png",
        ".jpg": "image/jpeg", ".gif": "image/gif",
        ".zip": "application/zip", ".tar": "application/x-tar",
        ".gz": "application/gzip", ".bin": "application/octet-stream",
    }
    ct = ct_map.get(ext, ct)

    # Upload via Telegram
    sent = await telegram_bot.send_document(str(path), chat_id=chat_id, caption=f"[tg-s3] {name}", filename=name)
    if not sent:
        return None

    key = _make_key(name)
    conn = _get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO tg_s3_objects (key, filename, message_id, file_id, size_bytes, content_type, tags, stored_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (key, name, 0, "", size, ct, json.dumps(tags or []), time.time()),
    )
    conn.commit()
    conn.close()
    _log.info("tg_s3_put: %s -> %s (%d bytes)", key, name, size)
    return key


def tg_s3_list(*, prefix: str = "", tag: str = "", limit: int = 20) -> list[dict]:
    """List stored objects, optionally filtered by prefix or tag."""
    conn = _get_conn()
    if tag:
        rows = conn.execute(
            "SELECT key, filename, size_bytes, content_type, tags, stored_at FROM tg_s3_objects "
            "WHERE tags LIKE ? ORDER BY stored_at DESC LIMIT ?",
            (f'%"{tag}"%', limit),
        ).fetchall()
    elif prefix:
        rows = conn.execute(
            "SELECT key, filename, size_bytes, content_type, tags, stored_at FROM tg_s3_objects "
            "WHERE filename LIKE ? ORDER BY stored_at DESC LIMIT ?",
            (f"{prefix}%", limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT key, filename, size_bytes, content_type, tags, stored_at FROM tg_s3_objects "
            "ORDER BY stored_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    conn.close()
    return [
        {
            "key": r[0], "filename": r[1], "size_bytes": r[2],
            "content_type": r[3], "tags": json.loads(r[4]),
            "stored_at": r[5],
        }
        for r in rows
    ]


def tg_s3_stats() -> dict:
    """Return storage statistics."""
    conn = _get_conn()
    total = conn.execute("SELECT COUNT(*) FROM tg_s3_objects").fetchone()[0] or 0
    size = conn.execute("SELECT COALESCE(SUM(size_bytes), 0) FROM tg_s3_objects").fetchone()[0] or 0
    conn.close()
    return {"total_objects": total, "total_bytes": size, "db_path": _DB_PATH}
