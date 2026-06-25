"""DDL statements and column-add migrations for the device app schema.

Kept as data so `db.py::_run_migrations` stays a small orchestrator instead of
a 229-line sequence of `conn.execute` calls.
"""

from __future__ import annotations

import sqlite3

# CREATE TABLE / CREATE INDEX statements, executed in order on every bootstrap.
# Idempotent via IF NOT EXISTS.
_DDL_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS v2_captcha (
        id              TEXT PRIMARY KEY,
        code            TEXT NOT NULL,
        expires_at      TEXT NOT NULL,
        created_at      TEXT DEFAULT (datetime('now'))
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_v2_captcha_expires ON v2_captcha(expires_at)",
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
    """,
    "CREATE INDEX IF NOT EXISTS idx_v2_pair_token ON v2_pair_request(pair_token)",
    "CREATE INDEX IF NOT EXISTS idx_v2_pair_status ON v2_pair_request(status)",
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
    """,
    "CREATE INDEX IF NOT EXISTS idx_v2_chat_session_device_status ON v2_chat_session(device_id, status)",
    "CREATE INDEX IF NOT EXISTS idx_v2_chat_session_account ON v2_chat_session(account_id)",
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
    """,
    "CREATE INDEX IF NOT EXISTS idx_v2_chat_message_session ON v2_chat_message(session_id)",
    "CREATE INDEX IF NOT EXISTS idx_v2_chat_message_audio ON v2_chat_message(audio_id)",
    """
    CREATE TABLE IF NOT EXISTS v2_audio_record (
        id              TEXT PRIMARY KEY,
        device_id       TEXT NOT NULL REFERENCES v2_device(id),
        session_id      TEXT REFERENCES v2_chat_session(id),
        audio_id        TEXT NOT NULL,
        duration_ms     INTEGER,
        created_at      TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_v2_audio_record_device ON v2_audio_record(device_id)",
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
    """,
    "CREATE INDEX IF NOT EXISTS idx_v2_task_template_account ON v2_task_template(account_id)",
    "CREATE INDEX IF NOT EXISTS idx_v2_task_template_device ON v2_task_template(device_id)",
    "CREATE INDEX IF NOT EXISTS idx_v2_task_template_category ON v2_task_template(category)",
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
    """,
    "CREATE INDEX IF NOT EXISTS idx_v2_notification_subscription_account ON v2_notification_subscription(account_id)",
    "CREATE INDEX IF NOT EXISTS idx_v2_notification_subscription_status ON v2_notification_subscription(status)",
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
    """,
    "CREATE INDEX IF NOT EXISTS idx_v2_notification_log_account ON v2_notification_log(account_id)",
    "CREATE INDEX IF NOT EXISTS idx_v2_notification_log_device ON v2_notification_log(device_id)",
    "CREATE INDEX IF NOT EXISTS idx_v2_notification_log_sent_at ON v2_notification_log(sent_at)",
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
    """,
    "CREATE INDEX IF NOT EXISTS idx_v2_share_token ON v2_device_share(share_token)",
    "CREATE INDEX IF NOT EXISTS idx_v2_share_device ON v2_device_share(device_id)",
    "CREATE INDEX IF NOT EXISTS idx_v2_share_guest ON v2_device_share(guest_account_id)",
    "CREATE INDEX IF NOT EXISTS idx_v2_share_status ON v2_device_share(status)",
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
    """,
    "CREATE INDEX IF NOT EXISTS idx_v2_asset_category ON v2_asset_library(category)",
    "CREATE INDEX IF NOT EXISTS idx_v2_asset_difficulty ON v2_asset_library(difficulty)",
    "CREATE INDEX IF NOT EXISTS idx_v2_asset_status ON v2_asset_library(status)",
    "CREATE INDEX IF NOT EXISTS idx_v2_asset_use_count ON v2_asset_library(use_count DESC)",
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
    """,
    "CREATE INDEX IF NOT EXISTS idx_v2_api_key_account ON v2_api_key(account_id)",
    "CREATE INDEX IF NOT EXISTS idx_v2_api_key_status ON v2_api_key(status)",
    "CREATE INDEX IF NOT EXISTS idx_v2_api_key_hash ON v2_api_key(key_hash)",
)

# (table, column, sql) for additive ALTER TABLE migrations. Skipped if column exists.
_ADD_COLUMN_MIGRATIONS: tuple[tuple[str, str, str], ...] = (
    ("v2_account", "password_hash", "ALTER TABLE v2_account ADD COLUMN password_hash TEXT"),
    ("v2_account", "email", "ALTER TABLE v2_account ADD COLUMN email TEXT"),
    ("v2_voiceprint", "label", "ALTER TABLE v2_voiceprint ADD COLUMN label TEXT"),
    ("v2_voiceprint", "introduce", "ALTER TABLE v2_voiceprint ADD COLUMN introduce TEXT"),
    ("v2_voiceprint", "audio_id", "ALTER TABLE v2_voiceprint ADD COLUMN audio_id TEXT"),
)

# Extra statements to run after a specific column add (e.g. unique index).
_POST_COLUMN_ADD: dict[str, tuple[str, ...]] = {
    "email": ("CREATE UNIQUE INDEX IF NOT EXISTS idx_v2_account_email ON v2_account(email)",),
}


def apply_migrations(conn: sqlite3.Connection) -> None:
    """Run all additive column migrations then all DDL statements."""
    existing_columns: dict[str, set[str]] = {}

    def columns_of(table: str) -> set[str]:
        if table not in existing_columns:
            existing_columns[table] = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
        return existing_columns[table]

    for table, column, sql in _ADD_COLUMN_MIGRATIONS:
        if column not in columns_of(table):
            conn.execute(sql)
            for extra in _POST_COLUMN_ADD.get(column, ()):
                conn.execute(extra)

    for ddl in _DDL_STATEMENTS:
        conn.execute(ddl)

    conn.commit()
