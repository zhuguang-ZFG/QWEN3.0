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
        conn.execute(
            "CREATE TABLE IF NOT EXISTS channel_tool_usage ("
            " channel_user_id_hash TEXT NOT NULL,"
            " tool TEXT NOT NULL,"
            " day TEXT NOT NULL,"
            " count INTEGER NOT NULL DEFAULT 0,"
            " PRIMARY KEY (channel_user_id_hash, tool, day)"
            ")"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS channel_chat_turns ("
            " id INTEGER PRIMARY KEY AUTOINCREMENT,"
            " channel_user_id_hash TEXT NOT NULL,"
            " role TEXT NOT NULL,"
            " content TEXT NOT NULL,"
            " created_at INTEGER NOT NULL"
            ")"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_chat_turns_user_time"
            " ON channel_chat_turns(channel_user_id_hash, created_at)"
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

    def ensure_guest_binding(
        self,
        channel: str,
        channel_user_id_raw: str,
        *,
        display_name: str = "",
    ) -> tuple[Optional[ChannelBinding], bool]:
        """Create or return an active guest binding. Returns (binding, created_new)."""
        existing = self.get_binding_by_channel_user(channel, channel_user_id_raw)
        if existing and existing.status in (
            BindingStatus.ACTIVE,
            BindingStatus.PAUSED,
        ):
            return existing, False
        if existing and existing.status == BindingStatus.REVOKED:
            self.set_binding_status(existing.binding_id, BindingStatus.ACTIVE)
            rebound = self.get_binding_by_channel_user(channel, channel_user_id_raw)
            return rebound, True

        user_hash = self._hash_id(channel_user_id_raw)
        binding_id = f"guest_{user_hash[:16]}"
        lima_user_id = f"wechat_guest_{user_hash[:12]}"
        ok = self.create_binding(
            binding_id=binding_id,
            channel=channel,
            channel_user_id_raw=channel_user_id_raw,
            display_name=display_name or channel_user_id_raw[:20],
            lima_user_id=lima_user_id,
        )
        if not ok:
            existing = self.get_binding_by_channel_user(channel, channel_user_id_raw)
            if existing and existing.status in (
                BindingStatus.ACTIVE,
                BindingStatus.PAUSED,
            ):
                return existing, False
            return None, False
        return self.get_binding_by_channel_user(channel, channel_user_id_raw), True

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
            role=row["role"] if "role" in row else BindingRole.GUEST,
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

    # -- Tool quotas ---------------------------------------------------------

    def consume_tool_quota(
        self, channel_user_id_hash: str, tool: str, limit: int, *, day: str
    ) -> tuple[bool, int]:
        """Increment usage if under limit. Returns (allowed, count_after)."""
        if limit <= 0:
            return False, 0
        with self._lock:
            conn = self._get_conn()
            row = conn.execute(
                "SELECT count FROM channel_tool_usage"
                " WHERE channel_user_id_hash = ? AND tool = ? AND day = ?",
                (channel_user_id_hash, tool, day),
            ).fetchone()
            current = int(row["count"]) if row else 0
            if current >= limit:
                return False, current
            new_count = current + 1
            conn.execute(
                "INSERT INTO channel_tool_usage"
                " (channel_user_id_hash, tool, day, count)"
                " VALUES (?, ?, ?, ?)"
                " ON CONFLICT(channel_user_id_hash, tool, day)"
                " DO UPDATE SET count = ?",
                (channel_user_id_hash, tool, day, new_count, new_count),
            )
            conn.commit()
            return True, new_count

    # -- Chat session (G3 multi-turn) ----------------------------------------

    def append_chat_turn(
        self, channel_user_id_hash: str, role: str, content: str
    ) -> None:
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                "INSERT INTO channel_chat_turns"
                " (channel_user_id_hash, role, content, created_at)"
                " VALUES (?, ?, ?, ?)",
                (channel_user_id_hash, role, content, int(time.time())),
            )
            conn.commit()

    def get_chat_history(
        self, channel_user_id_hash: str, *, max_messages: int = 12
    ) -> list[dict[str, str]]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT role, content FROM channel_chat_turns"
            " WHERE channel_user_id_hash = ?"
            " ORDER BY created_at DESC, id DESC LIMIT ?",
            (channel_user_id_hash, max_messages),
        ).fetchall()
        out: list[dict[str, str]] = []
        for row in reversed(rows):
            role = row["role"]
            if role in ("user", "assistant"):
                out.append({"role": role, "content": row["content"]})
        return out

    def trim_chat_history(
        self, channel_user_id_hash: str, *, max_messages: int = 12
    ) -> None:
        with self._lock:
            conn = self._get_conn()
            rows = conn.execute(
                "SELECT id FROM channel_chat_turns"
                " WHERE channel_user_id_hash = ?"
                " ORDER BY created_at DESC, id DESC",
                (channel_user_id_hash,),
            ).fetchall()
            if len(rows) <= max_messages:
                return
            drop_ids = [r["id"] for r in rows[max_messages:]]
            placeholders = ",".join("?" * len(drop_ids))
            conn.execute(
                f"DELETE FROM channel_chat_turns WHERE id IN ({placeholders})",
                drop_ids,
            )
            conn.commit()

    def clear_chat_history(self, channel_user_id_hash: str) -> None:
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                "DELETE FROM channel_chat_turns WHERE channel_user_id_hash = ?",
                (channel_user_id_hash,),
            )
            conn.commit()

    def count_chat_turns(self, channel_user_id_hash: str) -> int:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT COUNT(*) AS cnt FROM channel_chat_turns"
            " WHERE channel_user_id_hash = ?",
            (channel_user_id_hash,),
        ).fetchone()
        return int(row["cnt"]) if row else 0

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
