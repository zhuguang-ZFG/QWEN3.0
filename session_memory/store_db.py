"""Session memory schema and SQLite connection."""
from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass


@dataclass
class MemoryEntry:
    id: int
    session_id: str
    timestamp: float
    role: str
    summary: str
    detail: str
    embedding: list[float]
    memory_type: str = "exchange"



_DEFAULT_DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
_DEFAULT_DB_FILE = os.path.join(_DEFAULT_DB_DIR, "lima_sessions.db")
_DB_PATH = os.environ.get("LIMA_SESSION_DB", _DEFAULT_DB_FILE)


def get_db_path() -> str:
    """Resolve the active SQLite path at call time (env, facade patch, or module default)."""
    env_path = os.environ.get("LIMA_SESSION_DB")
    if env_path:
        return env_path
    try:
        import session_memory.store as store_facade

        facade_path = getattr(store_facade, "_DB_PATH", None)
        if isinstance(facade_path, str) and facade_path:
            return facade_path
    except ImportError:
        pass
    return _DB_PATH


def set_db_path(path: str) -> None:
    """Set DB path for runtime/tests; keeps facade and module globals aligned."""
    global _DB_PATH
    _DB_PATH = path
    try:
        import session_memory.store as store_facade

        store_facade._DB_PATH = path
    except ImportError:
        pass


def _get_conn() -> sqlite3.Connection:
    db_path = get_db_path()
    if not os.environ.get("LIMA_SESSION_DB"):
        os.makedirs(os.path.dirname(db_path) or _DEFAULT_DB_DIR, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            timestamp REAL NOT NULL,
            role TEXT NOT NULL,
            summary TEXT NOT NULL,
            detail TEXT DEFAULT '',
            embedding TEXT DEFAULT '[]',
            memory_type TEXT DEFAULT 'exchange'
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_session
        ON memories(session_id, timestamp DESC)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_memory_type
        ON memories(memory_type, timestamp DESC)
    """)
    # Migration: add memory_type column to existing DBs
    try:
        conn.execute("SELECT memory_type FROM memories LIMIT 1")
    except sqlite3.OperationalError:
        conn.execute("ALTER TABLE memories ADD COLUMN memory_type TEXT DEFAULT 'exchange'")
    conn.commit()
    return conn


MEMORY_TYPES = (
    "exchange", "compacted", "project_fact", "code_fact",
    "ops_event", "test_result", "routing_lesson",
    "security_lesson", "reference_pattern", "user_pref",
)


def _sanitize_storage_text(text: str) -> str:
    """Return text safe enough for memory storage without falling back to raw secrets."""
    try:
        from session_memory.redact import sanitize_for_memory

        cleaned = sanitize_for_memory(text)
    except ImportError:
        return text
    if cleaned is None:
        return "[REDACTED]" if text and text.strip() else ""
    return cleaned


def memory_stats() -> dict:
    """Return aggregate statistics about the memory store."""
    conn = _get_conn()
    total = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0] or 0
    by_type = conn.execute(
        "SELECT memory_type, COUNT(*) FROM memories GROUP BY memory_type ORDER BY COUNT(*) DESC"
    ).fetchall()
    with_emb = conn.execute(
        "SELECT COUNT(*) FROM memories WHERE embedding != '[]'"
    ).fetchone()[0] or 0
    sessions = conn.execute(
        "SELECT COUNT(DISTINCT session_id) FROM memories"
    ).fetchone()[0] or 0
    conn.close()
    return {
        "total": total,
        "with_embeddings": with_emb,
        "embedding_pct": round(with_emb / total * 100, 1) if total else 0,
        "sessions": sessions,
        "by_type": {t: c for t, c in by_type},
    }


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
            "SELECT sample_count FROM v2_voiceprint WHERE id = ? AND status != 'disabled'",
            (voiceprint_id,)
        ).fetchone()

        if existing:
            new_sample_count = existing["sample_count"] + 1
            conn.execute(
                "UPDATE v2_voiceprint SET sample_count = ?, embedding = ?, embedding_dim = ? WHERE id = ? AND status != 'disabled'",
                (new_sample_count, audio_data, len(audio_data) // 4, voiceprint_id)
            )
        else:
            conn.execute(
                "INSERT INTO v2_voiceprint (id, member_id, device_id, embedding, embedding_dim, sample_count, confidence, status) VALUES (?, ?, ?, ?, ?, 1, 0.0, 'enrolled')",
                (voiceprint_id, member_id, device_id, audio_data, len(audio_data) // 4, 1)
            )
        conn.commit()
    except Exception as exc:
        _log().debug("failed to upsert voiceprint sample voiceprint_id=%s err=%s", voiceprint_id, type(exc).__name__)
    finally:
        conn.close()


# ── 3D-Speaker embedding storage ───────────────────────────────────────────


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
    """Store a 3D-Speaker embedding vector for a voiceprint entry.

    Unlike upsert_voiceprint_sample (which stores raw audio), this stores
    the actual 512-dim embedding vector as a JSON string for fast cosine
    similarity matching.

    Args:
        voiceprint_id: Voiceprint enrollment ID.
        member_id: Family member identifier.
        device_id: Device that collected the sample.
        embedding: 3D-Speaker embedding vector (list of floats).
        speaker_ref: Speaker reference string for matching.
        display_name: Human-readable display name.
        member_type: Member type (owner/child/adult).
    """
    import json

    conn = _get_conn()
    try:
        _ensure_voiceprint_table(conn)

        embedding_json = json.dumps(embedding)
        embedding_dim = len(embedding)

        existing = conn.execute(
            "SELECT id FROM v2_voiceprint WHERE id = ? AND status != 'disabled'",
            (voiceprint_id,)
        ).fetchone()

        if existing:
            conn.execute(
                """UPDATE v2_voiceprint
                   SET embedding_vec = ?, embedding_dim = ?, speaker_ref = ?,
                       display_name = ?, member_type = ?
                   WHERE id = ?""",
                (embedding_json, embedding_dim, speaker_ref, display_name, member_type, voiceprint_id)
            )
        else:
            conn.execute(
                """INSERT INTO v2_voiceprint
                   (id, member_id, device_id, embedding_vec, embedding_dim,
                    speaker_ref, display_name, member_type, sample_count, confidence, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, 0.0, 'active')""",
                (voiceprint_id, member_id, device_id, embedding_json, embedding_dim,
                 speaker_ref, display_name, member_type)
            )
        conn.commit()
        _log().info("voiceprint embedding stored voiceprint_id=%s dim=%d", voiceprint_id, embedding_dim)
    except Exception as exc:
        _log().debug("failed to store voiceprint embedding voiceprint_id=%s err=%s", voiceprint_id, type(exc).__name__)
    finally:
        conn.close()


def get_voiceprint_embeddings(device_id: str) -> list[dict]:
    """Retrieve voiceprint entries with embedding vectors for a device.

    Returns list of dicts with keys: member_id, display_name, member_type,
    speaker_ref, embedding_hash, embedding (list[float]), status, expires_at.
    """
    import json

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
                (device_id,)
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
            (device_id,)
        ).fetchall()
        return [_row_to_entry_fallback(row) for row in rows]
    except Exception as exc:
        _log().debug("failed to get voiceprint embeddings device_id=%s err=%s", device_id, type(exc).__name__)
        return []
    finally:
        conn.close()


def _row_to_entry(row: sqlite3.Row) -> dict:
    """Convert a db row (new schema) to a voiceprint entry dict."""
    import json

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


def _log():
    """Get logger for store_db module."""
    import logging
    return logging.getLogger(__name__)

