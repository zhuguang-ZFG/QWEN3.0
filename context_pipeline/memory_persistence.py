"""SQLite-backed persistence for HierarchicalMemory L0-L4 layers.

Saves/loads memory state to survive process restarts. Auto-saves on
significant changes (L1 perf updates, L3 skill crystallization).
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import time
from pathlib import Path

_log = logging.getLogger(__name__)

_DEFAULT_DB_DIR = os.environ.get("LIMA_DATA_DIR", ".lima-data")


class MemoryPersistence:
    """SQLite persistence for hierarchical memory layers."""

    def __init__(self, db_path: str | None = None) -> None:
        resolved = db_path or str(Path(_DEFAULT_DB_DIR) / "context_memory.db")
        Path(resolved).parent.mkdir(parents=True, exist_ok=True)
        self._db_path = resolved
        self._conn = sqlite3.connect(resolved, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS memory_entries (
                layer INTEGER NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                updated_at REAL NOT NULL,
                PRIMARY KEY (layer, key)
            )
        """)
        self._conn.commit()

    def save_layer(self, layer: int, entries: dict) -> None:
        now = time.time()
        for key, value in entries.items():
            self._conn.execute(
                "INSERT OR REPLACE INTO memory_entries (layer, key, value, updated_at) "
                "VALUES (?, ?, ?, ?)",
                (layer, key, json.dumps(value, ensure_ascii=False, default=str), now),
            )
        self._conn.commit()

    def load_layer(self, layer: int) -> dict:
        rows = self._conn.execute(
            "SELECT key, value FROM memory_entries WHERE layer = ?",
            (layer,),
        ).fetchall()
        result = {}
        for key, value_json in rows:
            try:
                result[key] = json.loads(value_json)
            except (json.JSONDecodeError, TypeError):
                result[key] = value_json
        return result

    def snapshot_all(self) -> dict[int, dict]:
        result = {}
        for layer in range(5):
            result[layer] = self.load_layer(layer)
        return result

    def clear_layer(self, layer: int) -> None:
        self._conn.execute("DELETE FROM memory_entries WHERE layer = ?", (layer,))
        self._conn.commit()

    def layer_stats(self) -> dict[int, int]:
        rows = self._conn.execute(
            "SELECT layer, COUNT(*) FROM memory_entries GROUP BY layer",
        ).fetchall()
        return {layer: count for layer, count in rows}

    def close(self) -> None:
        self._conn.close()


def save_hierarchical_memory(hmem, persistence: MemoryPersistence | None = None) -> None:
    """Save all layers of a HierarchicalMemory instance."""
    p = persistence or MemoryPersistence()
    for layer in [hmem.L0, hmem.L1, hmem.L2, hmem.L3, hmem.L4]:
        if layer.entries:
            p.save_layer(layer.level, layer.entries)


def load_hierarchical_memory(hmem, persistence: MemoryPersistence | None = None) -> None:
    """Load persisted state into a HierarchicalMemory instance."""
    p = persistence or MemoryPersistence()
    for layer in [hmem.L0, hmem.L1, hmem.L2, hmem.L3, hmem.L4]:
        entries = p.load_layer(layer.level)
        layer.entries.update(entries)
