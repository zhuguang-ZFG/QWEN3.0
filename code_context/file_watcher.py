"""File change tracker using mtime + content hash for incremental re-indexing.

Detects which files have been created, modified, or deleted since last scan,
avoiding full re-indexing of unchanged files.
"""

from __future__ import annotations

import hashlib
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

_log = logging.getLogger(__name__)

_DEFAULT_EXTENSIONS = frozenset(
    {
        ".py",
        ".js",
        ".jsx",
        ".ts",
        ".tsx",
        ".go",
        ".rs",
        ".java",
        ".c",
        ".cpp",
        ".cc",
        ".h",
        ".hpp",
    }
)

_IGNORE_DIRS = frozenset(
    {
        ".git",
        "__pycache__",
        "node_modules",
        ".venv",
        "venv",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "site-packages",
    }
)


@dataclass
class FileChange:
    path: str
    change_type: str  # "created" | "modified" | "deleted"
    old_mtime: float = 0.0
    new_mtime: float = 0.0


@dataclass
class ScanManifest:
    scanned_at: float = 0.0
    total_files: int = 0
    file_hashes: dict[str, str] = field(default_factory=dict)  # path -> sha256[:16]
    file_mtimes: dict[str, float] = field(default_factory=dict)  # path -> mtime


class FileWatcher:
    """Tracks file changes between scans using mtime + content hash.

    Maintains a manifest of previously seen files. On each scan,
    returns only the files that have changed since the last scan.
    """

    def __init__(
        self,
        extensions: frozenset[str] | None = None,
        ignore_dirs: frozenset[str] | None = None,
        root_path: str | None = None,
    ) -> None:
        self._extensions = extensions or _DEFAULT_EXTENSIONS
        self._ignore_dirs = ignore_dirs or _IGNORE_DIRS
        self._root_path = root_path or os.getcwd()
        self._manifest = ScanManifest()

    def scan(self) -> tuple[list[str], list[FileChange]]:
        """Scan root_path and return (changed_paths, changes).

        Returns all file paths that should be (re)indexed, plus a list
        of individual changes for auditing.
        """
        current_mtimes: dict[str, float] = {}
        current_hashes: dict[str, str] = {}
        for path in self._walk_files():
            try:
                current_mtimes[path] = os.path.getmtime(path)
                current_hashes[path] = self.compute_content_hash(path)
            except OSError:
                continue

        changes: list[FileChange] = []
        changed_paths: list[str] = []

        for path, mtime in current_mtimes.items():
            old_mtime = self._manifest.file_mtimes.get(path, 0.0)
            if old_mtime == 0.0:
                changes.append(FileChange(path, "created", new_mtime=mtime))
                changed_paths.append(path)
            elif mtime > old_mtime:
                changes.append(FileChange(path, "modified", old_mtime, mtime))
                changed_paths.append(path)
            elif current_hashes.get(path, "") != self._manifest.file_hashes.get(path, ""):
                changes.append(FileChange(path, "modified", old_mtime, mtime))
                changed_paths.append(path)

        for old_path in self._manifest.file_mtimes:
            if old_path not in current_mtimes:
                changes.append(FileChange(old_path, "deleted", old_mtime=self._manifest.file_mtimes[old_path]))
                changed_paths.append(old_path)

        self._manifest = ScanManifest(
            scanned_at=time.time(),
            total_files=len(current_mtimes),
            file_hashes=current_hashes,
            file_mtimes=current_mtimes,
        )

        _log.info(
            "FileWatcher scan: %d files, %d changed",
            len(current_mtimes),
            len(changed_paths),
        )
        return changed_paths, changes

    def compute_content_hash(self, path: str) -> str:
        try:
            data = Path(path).read_bytes()
            return hashlib.sha256(data).hexdigest()[:16]
        except OSError:
            return ""

    def _walk_files(self) -> list[str]:
        result: list[str] = []
        root = Path(self._root_path)
        for entry in sorted(root.rglob("*")):
            if not entry.is_file():
                continue
            if any(part in self._ignore_dirs for part in entry.parts):
                continue
            if entry.suffix.lower() in self._extensions:
                result.append(str(entry))
        return result

    @property
    def manifest(self) -> ScanManifest:
        return self._manifest

    def has_file(self, path: str) -> bool:
        return path in self._manifest.file_mtimes
