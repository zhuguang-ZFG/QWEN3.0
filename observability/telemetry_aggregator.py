"""In-memory aggregation for backend telemetry records.

AUDIT-5-O10：同类错误（如同一后端 quota/auth/timeout）在写入 jsonl 前按指纹聚合，
避免 500 条上限被重复记录刷掉，导致根因丢失。
"""

from __future__ import annotations

import atexit
import json
import threading
import time
from typing import Any, Callable

MAX_BUFFER_UNIQUE = 100
MAX_BUFFER_RECORDS = 500
_FLUSH_INTERVAL_SEC = 60


class BackendTelemetryAggregator:
    """Buffer telemetry records by fingerprint and flush aggregated records."""

    def __init__(self, flush_callback: Callable[[list[dict[str, Any]]], None]) -> None:
        self._flush_callback = flush_callback
        self._buffer: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._timer: threading.Timer | None = None
        self._schedule()
        atexit.register(self.flush)

    def _schedule(self) -> None:
        self._timer = threading.Timer(_FLUSH_INTERVAL_SEC, self._timed_flush)
        self._timer.daemon = True
        self._timer.start()

    def _timed_flush(self) -> None:
        self.flush()
        self._schedule()

    def record(self, record: dict[str, Any]) -> None:
        key = _fingerprint(record)
        records: list[dict[str, Any]] = []
        with self._lock:
            existing = self._buffer.get(key)
            if existing is not None:
                existing["count"] = existing.get("count", 1) + 1
                existing["ts"] = record.get("ts", existing["ts"])
                existing["latency_ms"] = max(
                    existing.get("latency_ms", 0),
                    record.get("latency_ms", 0),
                )
            else:
                copy = dict(record)
                copy.setdefault("count", 1)
                self._buffer[key] = copy
            buffered_records = sum(r.get("count", 1) for r in self._buffer.values())
            if len(self._buffer) >= MAX_BUFFER_UNIQUE or buffered_records >= MAX_BUFFER_RECORDS:
                records = list(self._buffer.values())
                self._buffer.clear()
        if records:
            self._flush_callback(records)

    def flush(self) -> list[dict[str, Any]]:
        with self._lock:
            records = list(self._buffer.values())
            self._buffer.clear()
        if records:
            self._flush_callback(records)
        return records


def _fingerprint(record: dict[str, Any]) -> str:
    fields = (
        record.get("backend"),
        record.get("scenario"),
        record.get("request_type"),
        record.get("phase"),
        record.get("attempt"),
        record.get("model"),
        record.get("success"),
        record.get("status_code"),
        record.get("error_class"),
        record.get("tools_requested"),
    )
    return json.dumps(fields, sort_keys=True, separators=(",", ":"), default=str)


_default_aggregator: BackendTelemetryAggregator | None = None


def install_default(
    flush_callback: Callable[[list[dict[str, Any]]], None],
) -> BackendTelemetryAggregator:
    """Install and return the module-level default aggregator."""
    global _default_aggregator
    _default_aggregator = BackendTelemetryAggregator(flush_callback)
    return _default_aggregator


def record(record: dict[str, Any]) -> None:
    """Record a telemetry item into the default aggregator."""
    if _default_aggregator is None:
        raise RuntimeError("telemetry aggregator has not been installed")
    _default_aggregator.record(record)


def flush() -> list[dict[str, Any]]:
    """Flush the default aggregator immediately."""
    if _default_aggregator is None:
        return []
    return _default_aggregator.flush()
