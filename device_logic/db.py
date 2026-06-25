"""SQLite connection and schema bootstrap for LiMa device app data."""

from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from config.db_config import get_lima_db_path
from config.sqlite_pool import pooled_sqlite_conn

_schema_lock = threading.Lock()
_schema_ready_paths: set[str] = set()


def db_path() -> Path:
    return Path(get_lima_db_path())


def _run_migrations(conn: sqlite3.Connection) -> None:
    columns = {row[1] for row in conn.execute("PRAGMA table_info(v2_account)")}
    if "password_hash" not in columns:
        conn.execute("ALTER TABLE v2_account ADD COLUMN password_hash TEXT")
    if "email" not in columns:
        conn.execute("ALTER TABLE v2_account ADD COLUMN email TEXT")
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_v2_account_email ON v2_account(email)")

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS v2_captcha (
            id              TEXT PRIMARY KEY,
            code            TEXT NOT NULL,
            expires_at      TEXT NOT NULL,
            created_at      TEXT DEFAULT (datetime('now'))
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_v2_captcha_expires ON v2_captcha(expires_at)")

    voiceprint_columns = {row[1] for row in conn.execute("PRAGMA table_info(v2_voiceprint)")}
    if "label" not in voiceprint_columns:
        conn.execute("ALTER TABLE v2_voiceprint ADD COLUMN label TEXT")
    if "introduce" not in voiceprint_columns:
        conn.execute("ALTER TABLE v2_voiceprint ADD COLUMN introduce TEXT")
    if "audio_id" not in voiceprint_columns:
        conn.execute("ALTER TABLE v2_voiceprint ADD COLUMN audio_id TEXT")

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS v2_pair_request (
            id              TEXT PRIMARY KEY,
            pair_token      TEXT UNIQUE NOT NULL,
            device_sn       TEXT NOT NULL,
            account_id      TEXT NOT NULL REFERENCES v2_account(id),
            wifi_ssid       TEXT,
            server_url      TEXT,
            status          TEXT DEFAULT 'pending'
                CHECK (status IN ('pending', 'completed', 'expired')),
            created_at      TEXT DEFAULT (datetime('now')),
            expires_at      TEXT NOT NULL
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_v2_pair_token ON v2_pair_request(pair_token)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_v2_pair_status ON v2_pair_request(status)")

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS v2_chat_session (
            id              TEXT PRIMARY KEY,
            device_id       TEXT NOT NULL REFERENCES v2_device(id),
            account_id      TEXT NOT NULL REFERENCES v2_account(id),
            title           TEXT DEFAULT '',
            last_message_at TEXT,
            created_at      TEXT NOT NULL,
            status          TEXT DEFAULT 'active'
                CHECK (status IN ('active', 'deleted'))
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_v2_chat_session_device_status ON v2_chat_session(device_id, status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_v2_chat_session_account ON v2_chat_session(account_id)")

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS v2_chat_message (
            id              TEXT PRIMARY KEY,
            session_id      TEXT NOT NULL REFERENCES v2_chat_session(id),
            role            TEXT NOT NULL
                CHECK (role IN ('user', 'assistant', 'system')),
            content         TEXT NOT NULL,
            audio_id        TEXT,
            voiceprint_id   TEXT,
            created_at      TEXT NOT NULL
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_v2_chat_message_session ON v2_chat_message(session_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_v2_chat_message_audio ON v2_chat_message(audio_id)")

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS v2_audio_record (
            id              TEXT PRIMARY KEY,
            device_id       TEXT NOT NULL REFERENCES v2_device(id),
            session_id      TEXT REFERENCES v2_chat_session(id),
            audio_id        TEXT NOT NULL,
            duration_ms     INTEGER,
            created_at      TEXT NOT NULL
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_v2_audio_record_device ON v2_audio_record(device_id)")

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS v2_task_template (
            id              TEXT PRIMARY KEY,
            account_id      TEXT NOT NULL,
            device_id       TEXT,
            name            TEXT NOT NULL,
            capability      TEXT NOT NULL,
            params          TEXT NOT NULL,
            category        TEXT DEFAULT 'custom'
                CHECK (category IN ('recent', 'favorite', 'custom')),
            use_count       INTEGER DEFAULT 0,
            created_at      TEXT NOT NULL,
            updated_at      TEXT NOT NULL
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_v2_task_template_account ON v2_task_template(account_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_v2_task_template_device ON v2_task_template(device_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_v2_task_template_category ON v2_task_template(category)")

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS v2_notification_subscription (
            id              TEXT PRIMARY KEY,
            account_id      TEXT NOT NULL REFERENCES v2_account(id),
            openid          TEXT NOT NULL,
            template_ids    TEXT NOT NULL,
            device_ids      TEXT,
            created_at      TEXT NOT NULL,
            updated_at      TEXT NOT NULL,
            status          TEXT DEFAULT 'active'
                CHECK (status IN ('active', 'unsubscribed'))
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_v2_notification_subscription_account ON v2_notification_subscription(account_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_v2_notification_subscription_status ON v2_notification_subscription(status)"
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS v2_notification_log (
            id              TEXT PRIMARY KEY,
            account_id      TEXT NOT NULL,
            device_id       TEXT,
            event_type      TEXT NOT NULL,
            template_id     TEXT NOT NULL,
            payload         TEXT NOT NULL,
            sent_at         TEXT NOT NULL,
            status          TEXT NOT NULL
                CHECK (status IN ('sent', 'failed', 'pending')),
            error           TEXT,
            wx_response     TEXT
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_v2_notification_log_account ON v2_notification_log(account_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_v2_notification_log_device ON v2_notification_log(device_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_v2_notification_log_sent_at ON v2_notification_log(sent_at)")

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS v2_device_share (
            id              TEXT PRIMARY KEY,
            device_id       TEXT NOT NULL REFERENCES v2_device(id),
            owner_account_id TEXT NOT NULL REFERENCES v2_account(id),
            share_token     TEXT UNIQUE NOT NULL,
            permission      TEXT DEFAULT 'view'
                CHECK (permission IN ('view', 'control')),
            status          TEXT DEFAULT 'pending'
                CHECK (status IN ('pending', 'accepted', 'revoked', 'expired')),
            guest_account_id TEXT REFERENCES v2_account(id),
            expires_at      TEXT NOT NULL,
            accepted_at     TEXT,
            revoked_at      TEXT,
            created_at      TEXT DEFAULT (datetime('now')),
            updated_at      TEXT DEFAULT (datetime('now'))
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_v2_share_token ON v2_device_share(share_token)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_v2_share_device ON v2_device_share(device_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_v2_share_guest ON v2_device_share(guest_account_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_v2_share_status ON v2_device_share(status)")

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS v2_asset_library (
            id              TEXT PRIMARY KEY,
            title           TEXT NOT NULL,
            category        TEXT NOT NULL
                CHECK (category IN ('text', 'image', 'svg', 'template')),
            content         TEXT NOT NULL,
            preview_url     TEXT,
            tags            TEXT,
            difficulty      TEXT DEFAULT 'easy'
                CHECK (difficulty IN ('easy', 'medium', 'hard')),
            use_count       INTEGER DEFAULT 0,
            created_at      TEXT NOT NULL,
            status          TEXT DEFAULT 'active'
                CHECK (status IN ('active', 'inactive', 'deleted'))
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_v2_asset_category ON v2_asset_library(category)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_v2_asset_difficulty ON v2_asset_library(difficulty)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_v2_asset_status ON v2_asset_library(status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_v2_asset_use_count ON v2_asset_library(use_count DESC)")

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS v2_api_key (
            id              TEXT PRIMARY KEY,
            account_id      TEXT NOT NULL REFERENCES v2_account(id),
            name            TEXT NOT NULL,
            key_prefix      TEXT NOT NULL,
            key_hash        TEXT NOT NULL,
            status          TEXT DEFAULT 'active'
                CHECK (status IN ('active', 'revoked', 'deleted')),
            created_at      TEXT NOT NULL,
            expires_at      TEXT,
            daily_limit     INTEGER
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_v2_api_key_account ON v2_api_key(account_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_v2_api_key_status ON v2_api_key(status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_v2_api_key_hash ON v2_api_key(key_hash)")

    conn.commit()


def ensure_schema(conn: sqlite3.Connection, resolved_path: str) -> None:
    with _schema_lock:
        if resolved_path in _schema_ready_paths:
            return
        schema_path = Path(__file__).resolve().parent.parent / "migrations" / "xiaozhi_schema.sql"
        if not schema_path.exists():
            raise RuntimeError(f"xiaozhi schema missing: {schema_path}")
        conn.executescript(schema_path.read_text(encoding="utf-8"))
        _run_migrations(conn)
        _schema_ready_paths.add(resolved_path)


@contextmanager
def connect() -> Generator[sqlite3.Connection, None, None]:
    """Yield a SQLite connection from the thread-local pool.

    The connection is automatically returned to the pool after the context.
    """
    path = db_path()
    if path.parent != Path(""):
        path.parent.mkdir(parents=True, exist_ok=True)
    with pooled_sqlite_conn(str(path), check_same_thread=False) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        ensure_schema(conn, str(path.resolve()))
        try:
            yield conn
        finally:
            conn.row_factory = None
