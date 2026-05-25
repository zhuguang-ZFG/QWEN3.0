"""Channel Gateway SQLite store - binding, session, and audit persistence."""

import hashlib
import os
import secrets
import sqlite3
import threading
import time
from typing import Optional

from channel_gateway.models import (
    BindingRole,
    BindingStatus,
    ChannelBinding,
    ChannelBindingCode,
    ChannelMessage,
)


class ChannelStore:
    """SQLite-backed persistence for channel bindings, codes, and message audit."""

    def __init__(self, db_path: str):
        self._db_path = db_path
        self._salt = os.environ.get("LIMA_CHANNEL_ID_SALT", "")
        self._lock = threading.Lock()
        self._conn: Optional[sqlite3.Connection] = None

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            if self._db_path == ":memory:":
                self._conn = sqlite3.connect(":memory:", check_same_thread=False)
            else:
                os.makedirs(os.path.dirname(self._db_path) or ".", exist_ok=True)
                self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def _create_tables(self) -> None:
        conn = self._get_conn()
        conn.execute(
            "CREATE TABLE IF NOT EXISTS channel_bindings ("
            " binding_id TEXT PRIMARY KEY,"
            " channel TEXT NOT NULL,"
            " channel_user_id_hash TEXT NOT NULL,"
            " display_name TEXT NOT NULL DEFAULT '',"
            " lima_user_id TEXT NOT NULL,"
            " role TEXT NOT NULL DEFAULT 'guest',"
            " status TEXT NOT NULL DEFAULT 'pending',"
            " created_at INTEGER NOT NULL,"
            " updated_at INTEGER NOT NULL"
            ")"
        )
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_bindings_channel_user"
            " ON channel_bindings(channel, channel_user_id_hash)"
            " WHERE status IN ('active', 'paused')"
        )
        columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(channel_bindings)").fetchall()
        }
        if "role" not in columns:
            conn.execute(
                "ALTER TABLE channel_bindings"
                " ADD COLUMN role TEXT NOT NULL DEFAULT 'guest'"
            )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS channel_binding_codes ("
            " code_hash TEXT PRIMARY KEY,"
            " lima_user_id TEXT NOT NULL,"
            " expires_at INTEGER NOT NULL,"
            " used_at INTEGER,"
            " created_at INTEGER NOT NULL"
            ")"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS channel_messages ("
            " message_id TEXT PRIMARY KEY,"
            " channel TEXT NOT NULL,"
            " channel_user_id_hash TEXT NOT NULL,"
            " conversation_id_hash TEXT NOT NULL,"
            " direction TEXT NOT NULL,"
            " intent TEXT NOT NULL DEFAULT 'chat',"
            " task_id TEXT,"
            " device_id TEXT,"
            " summary TEXT NOT NULL DEFAULT '',"
            " created_at INTEGER NOT NULL"
            ")"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_messages_channel_user"
            " ON channel_messages(channel, channel_user_id_hash)"
        )
        conn.commit()

    # -- ID Hashing ----------------------------------------------------------

    def _hash_id(self, raw_id: str) -> str:
        if not self._salt:
            raise RuntimeError("LIMA_CHANNEL_ID_SALT is required for id hashing")
        return hashlib.sha256(f"{self._salt}:{raw_id}".encode()).hexdigest()

    def _is_owner_hash(self, user_hash: str) -> bool:
        raw = os.environ.get("LIMA_CHANNEL_OWNER_HASHES", "")
        if not raw:
            return False
        return user_hash in set(h.strip() for h in raw.split(",") if h.strip())

    # -- Binding Codes -------------------------------------------------------

    def create_binding_code(self, lima_user_id: str, ttl_seconds: int = 300) -> str:
        code = f"{secrets.randbelow(900000) + 100000:06d}"
        code_hash = hashlib.sha256(
            f"{self._salt}:{code}".encode()
        ).hexdigest()
        expires_at = int(time.time()) + ttl_seconds
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                "INSERT INTO channel_binding_codes (code_hash, lima_user_id, expires_at, created_at)"
                " VALUES (?, ?, ?, ?)",
                (code_hash, lima_user_id, expires_at, int(time.time())),
            )
            conn.commit()
        return code

    def validate_binding_code(self, code: str) -> bool:
        """Validate a binding code. Returns True on first successful use (one-time)."""
        code_hash = hashlib.sha256(
            f"{self._salt}:{code}".encode()
        ).hexdigest()
        with self._lock:
            conn = self._get_conn()
            row = conn.execute(
                "SELECT code_hash, expires_at, used_at FROM channel_binding_codes"
                " WHERE code_hash = ?",
                (code_hash,),
            ).fetchone()
            if row is None:
                return False
            if row["used_at"] is not None:
                return False
            if int(time.time()) > row["expires_at"]:
                return False
            conn.execute(
                "UPDATE channel_binding_codes SET used_at = ? WHERE code_hash = ?",
                (int(time.time()), code_hash),
            )
            conn.commit()
            return True

    # -- Bindings ------------------------------------------------------------

    def create_binding(
        self,
        binding_id: str,
        channel: str,
        channel_user_id_raw: str,
        display_name: str,
        lima_user_id: str,
    ) -> bool:
        """Create an active binding. Defaults to guest role unless owner allowlist matches."""
        user_hash = self._hash_id(channel_user_id_raw)
        role = BindingRole.OWNER if self._is_owner_hash(user_hash) else BindingRole.GUEST
        now = int(time.time())
        with self._lock:
            conn = self._get_conn()
            try:
                conn.execute(
                    "INSERT INTO channel_bindings"
                    " (binding_id, channel, channel_user_id_hash, display_name,"
                    "  lima_user_id, role, status, created_at, updated_at)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (binding_id, channel, user_hash, display_name,
                     lima_user_id, role, BindingStatus.ACTIVE, now, now),
                )
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False

    def get_binding_by_channel_user(
        self, channel: str, channel_user_id_raw: str
    ) -> Optional[ChannelBinding]:
        user_hash = self._hash_id(channel_user_id_raw)
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM channel_bindings"
            " WHERE channel = ? AND channel_user_id_hash = ?"
            " ORDER BY created_at DESC, rowid DESC LIMIT 1",
            (channel, user_hash),
        ).fetchone()
        if row is None:
            return None
        return ChannelBinding(
            binding_id=row["binding_id"],
            channel=row["channel"],
            channel_user_id_hash=row["channel_user_id_hash"],
            display_name=row["display_name"],
            lima_user_id=row["lima_user_id"],
            role=row["role"] if "role" in row.keys() else BindingRole.GUEST,
            status=row["status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def set_binding_status(self, binding_id: str, status: str) -> bool:
        with self._lock:
            conn = self._get_conn()
            cur = conn.execute(
                "UPDATE channel_bindings SET status = ?, updated_at = ?"
                " WHERE binding_id = ?",
                (status, int(time.time()), binding_id),
            )
            conn.commit()
            return cur.rowcount > 0

    def get_binding_count(self) -> int:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM channel_bindings WHERE status IN ('active', 'paused')"
        ).fetchone()
        return row["cnt"] if row else 0

    # -- Messages ------------------------------------------------------------

    def record_message(
        self,
        message_id: str,
        channel: str,
        channel_user_id_raw: str,
        conversation_id_raw: str,
        direction: str,
        intent: str,
        summary: str,
        task_id: Optional[str] = None,
        device_id: Optional[str] = None,
    ) -> bool:
        """Record a message. Returns False if message_id already exists (dedupe)."""
        user_hash = self._hash_id(channel_user_id_raw)
        conv_hash = self._hash_id(conversation_id_raw)
        with self._lock:
            conn = self._get_conn()
            try:
                conn.execute(
                    "INSERT INTO channel_messages"
                    " (message_id, channel, channel_user_id_hash, conversation_id_hash,"
                    "  direction, intent, task_id, device_id, summary, created_at)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (message_id, channel, user_hash, conv_hash,
                     direction, intent, task_id, device_id,
                     summary[:500], int(time.time())),
                )
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False

    def get_recent_message_count(self, limit: int = 100) -> int:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM ("
            " SELECT 1 FROM channel_messages ORDER BY created_at DESC LIMIT ?"
            ")",
            (limit,),
        ).fetchone()
        return row["cnt"] if row else 0
