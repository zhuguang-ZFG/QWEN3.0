"""Audit trail for approvals, executions, blocks, and queue events.

Records every decision point in a JSONL audit log. All values are redacted
before write. Supports query by event type, task_id, worker_id.
"""
from __future__ import annotations

import logging

_log = logging.getLogger(__name__)
import json
import os
import time
import uuid
from dataclasses import dataclass, field

from agent_runtime.contract import redact

_DEFAULT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"
)


def _audit_path() -> str:
    return os.environ.get(
        "LIMA_AUDIT_TRAIL",
        os.path.join(_DEFAULT_DIR, "audit_trail.jsonl"),
    )


@dataclass
class AuditEntry:
    event: str
    task_id: str = ""
    worker_id: str = ""
    request_id: str = ""
    approval_id: str = ""
    detail: str = ""
    timestamp: float = field(default_factory=time.time)
    audit_id: str = field(default_factory=lambda: f"audit-{uuid.uuid4().hex[:8]}")

    def to_dict(self) -> dict:
        return {
            "event": redact(self.event),
            "task_id": redact(self.task_id),
            "worker_id": redact(self.worker_id),
            "request_id": redact(self.request_id),
            "approval_id": redact(self.approval_id),
            "detail": redact(self.detail),
            "timestamp": self.timestamp, "audit_id": self.audit_id,
        }


class AuditTrail:
    def __init__(self, path: str = "") -> None:
        self._path = path or _audit_path()

    def record(self, event: str, task_id: str = "", worker_id: str = "",
               request_id: str = "", approval_id: str = "",
               detail: str = "") -> AuditEntry:
        entry = AuditEntry(
            event=event, task_id=task_id, worker_id=worker_id,
            request_id=request_id, approval_id=approval_id,
            detail=detail,
        )
        self._write(entry)
        return entry

    def query(self, event: str = "", task_id: str = "",
              limit: int = 50) -> list[AuditEntry]:
        results = []
        if not os.path.exists(self._path):
            return results
        with open(self._path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if event and d.get("event") != event:
                    continue
                if task_id and d.get("task_id") != task_id:
                    continue
                results.append(AuditEntry(
                    event=d.get("event", ""), task_id=d.get("task_id", ""),
                    worker_id=d.get("worker_id", ""),
                    request_id=d.get("request_id", ""),
                    approval_id=d.get("approval_id", ""),
                    detail=d.get("detail", ""),
                    timestamp=d.get("timestamp", 0),
                    audit_id=d.get("audit_id", ""),
                ))
                if len(results) >= limit:
                    break
        return results

    def count_by_event(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        if not os.path.exists(self._path):
            return counts
        with open(self._path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                    ev = d.get("event", "unknown")
                    counts[ev] = counts.get(ev, 0) + 1
                except json.JSONDecodeError:
                    continue
        return dict(sorted(counts.items()))

    def _write(self, entry: AuditEntry) -> None:
        d = os.path.dirname(self._path)
        if d:
            os.makedirs(d, exist_ok=True)
        with open(self._path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry.to_dict(), ensure_ascii=True) + "\n")

    def reset(self) -> None:
        try:
            os.remove(self._path)
        except OSError:
            _log.debug("audit_trail: optional dependency or operation failed", exc_info=True)
_global_trail: AuditTrail | None = None


def get_audit_trail(path: str = "") -> AuditTrail:
    global _global_trail
    desired_path = path or _audit_path()
    if _global_trail is None or _global_trail._path != desired_path:
        _global_trail = AuditTrail(desired_path)
    return _global_trail


def audit_event(event: str, task_id: str = "", worker_id: str = "",
                request_id: str = "", approval_id: str = "",
                detail: str = "") -> AuditEntry:
    return get_audit_trail().record(
        event=event, task_id=task_id, worker_id=worker_id,
        request_id=request_id, approval_id=approval_id, detail=detail,
    )
