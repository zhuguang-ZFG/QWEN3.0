"""In-memory artifact store for device task previews and terminal results."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import threading
from typing import Any


@dataclass(frozen=True)
class ArtifactRecord:
    task_id: str
    artifact_type: str
    content: Any
    content_hash: str
    retention_days: int = 30
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"))

    def __post_init__(self) -> None:
        if not self.task_id:
            raise ValueError("task_id is required")
        if not self.artifact_type:
            raise ValueError("artifact_type is required")
        if self.retention_days < 1:
            raise ValueError("retention_days must be positive")
        object.__setattr__(self, "content", deepcopy(self.content))

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "artifact_type": self.artifact_type,
            "content": deepcopy(self.content),
            "content_hash": self.content_hash,
            "retention_days": self.retention_days,
            "created_at": self.created_at,
        }


class InMemoryArtifactStore:
    backend_name = "memory"

    def __init__(self) -> None:
        self._records: list[ArtifactRecord] = []
        self._lock = threading.RLock()

    def reset(self) -> None:
        with self._lock:
            self._records.clear()

    def put_artifact(
        self,
        *,
        task_id: str,
        artifact_type: str,
        content: Any,
        retention_days: int = 30,
    ) -> ArtifactRecord:
        record = ArtifactRecord(
            task_id=task_id,
            artifact_type=artifact_type,
            content=content,
            content_hash=_content_hash(content),
            retention_days=retention_days,
        )
        with self._lock:
            self._records.append(deepcopy(record))
        return deepcopy(record)

    def artifacts_for_task(self, task_id: str, artifact_type: str | None = None) -> list[ArtifactRecord]:
        with self._lock:
            return [
                deepcopy(record)
                for record in self._records
                if record.task_id == task_id and (artifact_type is None or record.artifact_type == artifact_type)
            ]


def _content_hash(content: Any) -> str:
    if isinstance(content, bytes):
        raw = content
    elif isinstance(content, str):
        raw = content.encode("utf-8")
    else:
        raw = json.dumps(content, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


artifact_store = InMemoryArtifactStore()


def artifacts_for_device(
    device_id: str,
    artifact_type: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> list[ArtifactRecord]:
    """Query artifacts by device_id with pagination."""
    limit = max(1, min(int(limit), 100))
    offset = max(0, int(offset))
    with artifact_store._lock:
        records = []
        for record in artifact_store._records:
            # Check if content is a dict and has device_id
            if isinstance(record.content, dict):
                if record.content.get("device_id") != device_id:
                    continue
            else:
                # If content is not a dict, skip device_id check
                continue

            if artifact_type is not None and record.artifact_type != artifact_type:
                continue

            records.append(record)

        # Sort by created_at descending
        records.sort(key=lambda r: r.created_at, reverse=True)
        return [deepcopy(r) for r in records[offset : offset + limit]]
