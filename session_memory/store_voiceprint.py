"""Voiceprint sample and embedding storage in SQLite."""

from __future__ import annotations

import json
import logging
import os
import sqlite3

from session_memory.store_db import get_db_path, _get_conn

_log = logging.getLogger(__name__)


def upsert_voiceprint_sample(
    *,
    voiceprint_id: str,
    member_id: str,
    device_id: str,
    sample_index: int,
    audio_data: str,
    format: str,
) -> None:
    """Update or insert a voiceprint sample record.

    Updates the sample_count for an existing voiceprint record, or creates
    a new one if it doesn't exist. This ensures the device gateway can track
    the number of samples collected for each voiceprint.
    """
    conn = _get_conn()

    try:
        _ensure_voiceprint_table(conn)

        existing = conn.execute(
            "SELECT sample_count FROM v2_voiceprint WHERE id = ? AND status != 'disabled'", (voiceprint_id,)
        ).fetchone()

        if existing:
            new_sample_count = existing["sample_count"] + 1
            conn.execute(
                "UPDATE v2_voiceprint SET sample_count = ?, embedding = ?, embedding_dim = ? WHERE id = ? AND status != 'disabled'",
                (new_sample_count, audio_data, len(audio_data) // 4, voiceprint_id),
            )
        else:
            conn.execute(
                "INSERT INTO v2_voiceprint (id, member_id, device_id, embedding, embedding_dim, sample_count, confidence, status) VALUES (?, ?, ?, ?, ?, 1, 0.0, 'enrolled')",
                (voiceprint_id, member_id, device_id, audio_data, len(audio_data) // 4, 1),
            )
        conn.commit()
    except Exception as exc:
        _log.warning("failed to upsert voiceprint sample voiceprint_id=%s err=%s", voiceprint_id, exc)
    finally:
        conn.close()


def store_voiceprint_embedding(
    *,
    voiceprint_id: str,
    member_id: str,
    device_id: str,
    embedding: list[float],
    speaker_ref: str = "",
    display_name: str = "",
    member_type: str = "",
) -> None:
    """Store a 3D-Speaker embedding vector for a voiceprint entry."""
    conn = _get_conn()
    try:
        _ensure_voiceprint_table(conn)

        embedding_json = json.dumps(embedding)
        embedding_dim = len(embedding)

        existing = conn.execute(
            "SELECT id FROM v2_voiceprint WHERE id = ? AND status != 'disabled'", (voiceprint_id,)
        ).fetchone()

        if existing:
            conn.execute(
                """UPDATE v2_voiceprint
                   SET embedding_vec = ?, embedding_dim = ?, speaker_ref = ?,
                       display_name = ?, member_type = ?
                   WHERE id = ?""",
                (embedding_json, embedding_dim, speaker_ref, display_name, member_type, voiceprint_id),
            )
        else:
            conn.execute(
                """INSERT INTO v2_voiceprint
                   (id, member_id, device_id, embedding_vec, embedding_dim,
                    speaker_ref, display_name, member_type, sample_count, confidence, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, 0.0, 'active')""",
                (
                    voiceprint_id,
                    member_id,
                    device_id,
                    embedding_json,
                    embedding_dim,
                    speaker_ref,
                    display_name,
                    member_type,
                ),
            )
        conn.commit()
        _log.info("voiceprint embedding stored voiceprint_id=%s dim=%d", voiceprint_id, embedding_dim)
    except Exception as exc:
        _log.warning("failed to store voiceprint embedding voiceprint_id=%s err=%s", voiceprint_id, exc)
    finally:
        conn.close()


def get_voiceprint_embeddings(device_id: str) -> list[dict]:
    """Retrieve voiceprint entries with embedding vectors for a device."""
    conn = _get_conn()
    try:
        _ensure_voiceprint_table(conn)

        # Try new schema with embedding_vec first
        try:
            rows = conn.execute(
                """SELECT id, member_id, device_id, speaker_ref, display_name,
                          member_type, embedding_vec, confidence, status, created_at
                   FROM v2_voiceprint
                   WHERE device_id = ? AND status != 'disabled' AND embedding_vec IS NOT NULL""",
                (device_id,),
            ).fetchall()
            if rows:
                return [_row_to_entry(row) for row in rows]
        except sqlite3.OperationalError:
            pass  # embedding_vec column may not exist yet

        # Fallback: use base64 embedding field
        rows = conn.execute(
            """SELECT id, member_id, device_id, speaker_ref, display_name,
                      member_type, embedding, confidence, status, created_at
               FROM v2_voiceprint
               WHERE device_id = ? AND status != 'disabled'""",
            (device_id,),
        ).fetchall()
        return [_row_to_entry_fallback(row) for row in rows]
    except Exception as exc:
        _log.warning("failed to get voiceprint embeddings device_id=%s err=%s", device_id, exc)
        return []
    finally:
        conn.close()


def _row_to_entry(row: sqlite3.Row) -> dict:
    """Convert a db row (new schema) to a voiceprint entry dict."""
    entry = {
        "member_id": row["member_id"],
        "display_name": row["display_name"] or "",
        "member_type": row["member_type"] or "",
        "speaker_ref": row["speaker_ref"] or "",
        "embedding_hash": "",
        "embedding": None,
        "status": row["status"] or "active",
    }

    embedding_vec = row["embedding_vec"]
    if embedding_vec:
        try:
            entry["embedding"] = json.loads(embedding_vec)
        except (json.JSONDecodeError, TypeError):
            pass

    return entry


def _row_to_entry_fallback(row: sqlite3.Row) -> dict:
    """Convert a db row (fallback schema) to a voiceprint entry dict."""
    return {
        "member_id": row["member_id"],
        "display_name": row.get("display_name") or "",
        "member_type": row.get("member_type") or "",
        "speaker_ref": row.get("speaker_ref") or "",
        "embedding_hash": row["embedding"] or "",
        "embedding": None,
        "status": row["status"] or "active",
    }


def _ensure_voiceprint_table(conn: sqlite3.Connection) -> None:
    """Ensure the v2_voiceprint table and new columns exist."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS v2_voiceprint (
            id TEXT PRIMARY KEY,
            member_id TEXT,
            device_id TEXT,
            embedding TEXT DEFAULT '',
            embedding_vec TEXT DEFAULT '',
            embedding_dim INTEGER DEFAULT 0,
            speaker_ref TEXT DEFAULT '',
            display_name TEXT DEFAULT '',
            member_type TEXT DEFAULT '',
            sample_count INTEGER DEFAULT 0,
            confidence REAL DEFAULT 0.0,
            status TEXT DEFAULT 'enrolled',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """)
    # Add new columns if upgrading from older schema
    for col, col_type in [
        ("embedding_vec", "TEXT DEFAULT ''"),
        ("speaker_ref", "TEXT DEFAULT ''"),
        ("display_name", "TEXT DEFAULT ''"),
        ("member_type", "TEXT DEFAULT ''"),
        ("updated_at", "TEXT DEFAULT (datetime('now'))"),
    ]:
        try:
            conn.execute(f"ALTER TABLE v2_voiceprint ADD COLUMN {col} {col_type}")
        except sqlite3.OperationalError:
            pass  # Column already exists
    conn.commit()


__all__ = [
    "upsert_voiceprint_sample",
    "store_voiceprint_embedding",
    "get_voiceprint_embeddings",
]
