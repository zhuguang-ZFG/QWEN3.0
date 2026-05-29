"""checkpoint.py — File snapshot & rollback for safe vibecode editing.

Every write_file tool call creates a checkpoint. If things go wrong,
the agent (or user) can rollback to any previous checkpoint.

Storage: ~/.lima/checkpoints/<session_id>/<checkpoint_id>/
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path

_log = logging.getLogger(__name__)

CHECKPOINT_DIR = Path.home() / ".lima" / "checkpoints"
MAX_CHECKPOINTS_PER_SESSION = 50
MAX_SESSIONS = 20


@dataclass
class Snapshot:
    source: str  # original file path
    backup: str  # snapshot path
    size: int = 0
    timestamp: float = 0.0


@dataclass
class Checkpoint:
    id: str
    timestamp: float
    reason: str  # e.g. "write_file: cli.py", "pre_test", "manual"
    files: list[Snapshot] = field(default_factory=list)

    def rollback(self) -> list[str]:
        """Restore all files to this checkpoint. Returns list of restored paths."""
        restored = []
        for snap in self.files:
            try:
                shutil.copy2(snap.backup, snap.source)
                restored.append(snap.source)
            except OSError as e:
                _log.warning("Rollback failed: %s → %s: %s", snap.backup, snap.source, e)
        return restored


class CheckpointManager:
    """Manages checkpoints for a session. Thread-safe."""

    def __init__(self, session_id: str = ""):
        self.session_id = session_id or f"session_{int(time.time())}"
        self.session_dir = CHECKPOINT_DIR / self.session_id
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.checkpoints: list[Checkpoint] = []
        self._counter = 0
        self._load_existing()
        self._prune_old_sessions()

    def _load_existing(self) -> None:
        index_file = self.session_dir / "index.json"
        if index_file.exists():
            try:
                with open(index_file) as f:
                    data = json.load(f)
                for cp_data in data.get("checkpoints", []):
                    cp = Checkpoint(
                        id=cp_data["id"],
                        timestamp=cp_data["timestamp"],
                        reason=cp_data["reason"],
                    )
                    for s in cp_data.get("files", []):
                        cp.files.append(Snapshot(
                            source=s["source"], backup=s["backup"],
                            size=s.get("size", 0), timestamp=s.get("timestamp", 0),
                        ))
                    self.checkpoints.append(cp)
                self._counter = len(self.checkpoints)
            except (json.JSONDecodeError, KeyError, OSError):
                self.checkpoints = []

    def create(self, reason: str, files: list[str]) -> Checkpoint | None:
        """Snapshot files before making changes. Call before write_file."""
        if len(self.checkpoints) >= MAX_CHECKPOINTS_PER_SESSION:
            self._prune_checkpoints()

        cp_id = f"cp_{self._counter:04d}"
        cp_dir = self.session_dir / cp_id
        cp_dir.mkdir(exist_ok=True)

        snapshots = []
        for fpath in files:
            src = Path(fpath).resolve()
            if not src.exists():
                continue
            backup = cp_dir / src.name
            try:
                shutil.copy2(str(src), str(backup))
                snapshots.append(Snapshot(
                    source=str(src), backup=str(backup),
                    size=src.stat().st_size, timestamp=time.time(),
                ))
            except OSError as e:
                _log.warning("Snapshot failed: %s: %s", fpath, e)

        if not snapshots:
            shutil.rmtree(cp_dir, ignore_errors=True)
            return None

        cp = Checkpoint(
            id=cp_id, timestamp=time.time(), reason=reason, files=snapshots,
        )
        self.checkpoints.append(cp)
        self._counter += 1
        self._save_index()
        return cp

    def rollback_to(self, cp_id: str | None = None) -> list[str]:
        """Rollback to a specific checkpoint (default: last)."""
        if not self.checkpoints:
            return []
        cp = None
        if cp_id:
            for c in self.checkpoints:
                if c.id == cp_id:
                    cp = c
                    break
        else:
            cp = self.checkpoints[-1]

        if not cp:
            return []
        restored = cp.rollback()
        _log.info("Rolled back to %s: %d files restored", cp.id, len(restored))
        return restored

    def list_checkpoints(self) -> list[dict]:
        return [
            {"id": c.id, "time": c.timestamp, "reason": c.reason,
             "files": [s.source for s in c.files]}
            for c in self.checkpoints
        ]

    def cleanup(self) -> None:
        """Remove all checkpoints for this session."""
        shutil.rmtree(self.session_dir, ignore_errors=True)

    def _save_index(self) -> None:
        data = {
            "session_id": self.session_id,
            "checkpoints": [
                {
                    "id": c.id, "timestamp": c.timestamp, "reason": c.reason,
                    "files": [
                        {"source": s.source, "backup": s.backup,
                         "size": s.size, "timestamp": s.timestamp}
                        for s in c.files
                    ],
                }
                for c in self.checkpoints
            ],
        }
        index_file = self.session_dir / "index.json"
        tmp = index_file.with_suffix(".tmp")
        with open(tmp, "w") as f:
            json.dump(data, f, indent=2)
        tmp.replace(index_file)

    def _prune_checkpoints(self) -> None:
        """Keep only the latest 20 checkpoints."""
        to_remove = self.checkpoints[:-20]
        self.checkpoints = self.checkpoints[-20:]
        for cp in to_remove:
            cp_dir = self.session_dir / cp.id
            shutil.rmtree(cp_dir, ignore_errors=True)

    def _prune_old_sessions(self) -> None:
        sessions = sorted(CHECKPOINT_DIR.iterdir(), key=lambda p: p.stat().st_mtime)
        while len(sessions) > MAX_SESSIONS:
            old = sessions.pop(0)
            shutil.rmtree(old, ignore_errors=True)


# ── Global session ────────────────────────────────────────────────────────────

_current: CheckpointManager | None = None


def get_checkpoint_manager() -> CheckpointManager:
    global _current
    if _current is None:
        sid = f"vibecode_{int(time.time())}"
        _current = CheckpointManager(sid)
    return _current


def checkpoint_files(files: list[str], reason: str = "pre_edit") -> Checkpoint | None:
    """Snapshot files before editing. Thread-safe convenience function."""
    return get_checkpoint_manager().create(reason, files)


def rollback(reason: str = "manual") -> list[str]:
    """Rollback to last checkpoint."""
    return get_checkpoint_manager().rollback_to()
