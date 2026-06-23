"""Auto-indexer: detects file changes and updates SQLite graph + ChromaDB.

Runs on startup and periodically to keep code context indexes fresh.
Uses file_watcher for change detection, tree-sitter for extraction,
sqlite_graph_store and chroma_vector_store for persistence.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from pathlib import Path

from config.settings import PATHS

_log = logging.getLogger(__name__)

_DEFAULT_SCAN_INTERVAL = 300  # 5 minutes


class AutoIndexer:
    """Monitors file changes and updates code context indexes."""

    def __init__(
        self,
        root_path: str | None = None,
        scan_interval: int = _DEFAULT_SCAN_INTERVAL,
    ) -> None:
        self._root = root_path or PATHS.project_root or os.getcwd()
        self._interval = scan_interval
        self._last_scan = 0.0
        self._graph = None
        self._vector = None
        self._watcher = None

    def _init_components(self) -> None:
        try:
            from code_context.file_watcher import FileWatcher

            self._watcher = FileWatcher(root_path=self._root)
        except Exception as exc:
            _log.warning("FileWatcher init failed: %s", exc)

        try:
            from code_context.graph_index import build_graph_index

            self._graph = build_graph_index()
        except Exception as exc:
            _log.warning("GraphIndex init failed: %s", exc)

        try:
            from code_context.chroma_vector_store import ChromaCodeIndex

            self._vector = ChromaCodeIndex()
        except Exception as exc:
            _log.warning("ChromaCodeIndex init failed: %s", exc)

    def _process_changes(self, changed_paths: list[str]) -> tuple[int, int, int]:
        """Index new files and remove deleted ones. Returns (indexed, deleted_count, errors)."""
        indexed = 0
        deleted_count = 0
        errors = 0
        for path in changed_paths:
            if not os.path.exists(path):
                try:
                    self._delete_file(path)
                    deleted_count += 1
                except Exception as exc:
                    _log.warning("delete %s failed: %s", path, exc)
                    errors += 1
                continue
            try:
                self._index_file(path)
                indexed += 1
            except Exception as exc:
                _log.warning("index %s failed: %s", path, exc)
                errors += 1
        return indexed, deleted_count, errors


    def _build_stats(
        self,
        watcher,
        changed_paths: list[str],
        changes: list,
        indexed: int,
        deleted_count: int,
        errors: int,
        duration: float,
    ) -> dict:
        """Assemble the scan stats dict."""
        return {
            "scanned": watcher.manifest.total_files,
            "changed": len(changed_paths),
            "indexed": indexed,
            "deleted_count": deleted_count,
            "errors": errors,
            "duration_ms": round(duration, 1),
            "created": sum(1 for c in changes if c.change_type == "created"),
            "modified": sum(1 for c in changes if c.change_type == "modified"),
            "deleted": sum(1 for c in changes if c.change_type == "deleted"),
        }


    def scan_once(self) -> dict:
        """Run a single scan and update indexes. Returns stats."""
        if not self._watcher:
            self._init_components()
        if not self._watcher:
            return {"error": "watcher not available"}

        watcher = self._watcher
        t0 = time.time()
        changed_paths, changes = watcher.scan()
        indexed, deleted_count, errors = self._process_changes(changed_paths)
        duration = (time.time() - t0) * 1000
        self._last_scan = time.time()

        stats = self._build_stats(watcher, changed_paths, changes, indexed, deleted_count, errors, duration)
        if indexed > 0 or deleted_count > 0:
            _log.info(
                "AutoIndexer: %d indexed, %d deleted, %d changed in %.0fms",
                indexed,
                deleted_count,
                len(changed_paths),
                duration,
            )
        return stats

    def _delete_file(self, path: str) -> None:
        if self._vector is not None:
            try:
                self._vector.delete_file(path)
            except Exception as exc:
                _log.warning("vector delete %s failed: %s", path, exc)
        if self._graph is not None:
            try:
                self._graph.delete_file(path)
            except Exception as exc:
                _log.warning("graph delete %s failed: %s", path, exc)

    def _index_file(self, path: str) -> None:
        p = Path(path)
        suffix = p.suffix.lower()
        if suffix not in (".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java", ".c", ".cpp"):
            return

        try:
            from code_context.ast_adapter import get_extractor

            lang_map = {
                ".py": "python",
                ".js": "javascript",
                ".ts": "typescript",
                ".tsx": "typescript",
                ".jsx": "javascript",
                ".go": "go",
                ".rs": "rust",
                ".java": "java",
            }
            lang = lang_map.get(suffix, "python")
            extractor = get_extractor(lang)
            if not extractor:
                return

            file_ast = extractor.scan_file(p)

            if self._graph and file_ast.relations:
                for rel in file_ast.relations:
                    self._graph.add_relation(rel.source, rel.target, rel.relation_type)

            if self._vector:
                content = ""
                try:
                    content = p.read_text(encoding="utf-8", errors="replace")[:5000]
                except Exception as exc:
                    _log.warning("auto_indexer read failed: %s", exc)
                symbols_data = [
                    type("S", (), {"name": s.name, "kind": s.kind, "line": s.line})() for s in file_ast.symbols
                ]
                imports_data = [(r.target, r.line) for r in file_ast.relations if r.relation_type == "imports"]
                self._vector.upsert_file(
                    path=str(p),
                    symbols=symbols_data,
                    imports=imports_data,
                    mtime=p.stat().st_mtime if p.exists() else 0,
                    content=content,
                )
        except Exception as exc:
            _log.warning("auto_indexer index_file failed: %s", exc)

    @property
    def last_scan(self) -> float:
        return self._last_scan

    def should_scan(self) -> bool:
        return time.time() - self._last_scan >= self._interval


_indexer: AutoIndexer | None = None


def get_auto_indexer() -> AutoIndexer:
    global _indexer
    if _indexer is None:
        _indexer = AutoIndexer()
    return _indexer


def run_indexer_scan() -> dict:
    """Convenience: get indexer, run scan, return stats."""
    return get_auto_indexer().scan_once()


# ── Background loop for server lifespan ───────────────────────────────────────

_indexer_thread: threading.Thread | None = None
_indexer_stop = threading.Event()


def start_auto_indexer(interval_sec: int = 300) -> None:
    """Start background periodic scan in a daemon thread. Non-blocking."""
    global _indexer_thread, _indexer_stop
    if _indexer_thread and _indexer_thread.is_alive():
        return
    _indexer_stop.clear()
    _indexer_thread = threading.Thread(
        target=_indexer_loop,
        args=(interval_sec, _indexer_stop),
        daemon=True,
        name="lima-auto-indexer",
    )
    _indexer_thread.start()
    _log.info("auto_indexer started (interval=%ds)", interval_sec)


def _indexer_loop(interval_sec: int, stop_event: threading.Event) -> None:
    while not stop_event.is_set():
        try:
            run_indexer_scan()
        except Exception as exc:
            _log.warning("auto_indexer cleanup failed: %s", exc)
        stop_event.wait(timeout=interval_sec)


def stop_auto_indexer() -> None:
    global _indexer_thread
    _indexer_stop.set()
    if _indexer_thread and _indexer_thread.is_alive():
        _indexer_thread.join(timeout=5)
    _indexer_thread = None
