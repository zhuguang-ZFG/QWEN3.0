"""Auto-indexer: detects file changes and updates SQLite graph + ChromaDB.

Runs on startup and periodically to keep code context indexes fresh.
Uses file_watcher for change detection, tree-sitter for extraction,
sqlite_graph_store and chroma_vector_store for persistence.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from pathlib import Path

_log = logging.getLogger(__name__)

_DEFAULT_SCAN_INTERVAL = 300  # 5 minutes


class AutoIndexer:
    """Monitors file changes and updates code context indexes."""

    def __init__(
        self,
        root_path: str | None = None,
        scan_interval: int = _DEFAULT_SCAN_INTERVAL,
    ) -> None:
        self._root = root_path or os.environ.get(
            "LIMA_PROJECT_ROOT", os.getcwd(),
        )
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
            _log.debug("FileWatcher init failed: %s", exc)

        try:
            from code_context.graph_index import build_graph_index
            self._graph = build_graph_index()
        except Exception as exc:
            _log.debug("GraphIndex init failed: %s", exc)

        try:
            from code_context.chroma_vector_store import ChromaCodeIndex
            self._vector = ChromaCodeIndex()
        except Exception as exc:
            _log.debug("ChromaCodeIndex init failed: %s", exc)

    def scan_once(self) -> dict:
        """Run a single scan and update indexes. Returns stats."""
        if not self._watcher:
            self._init_components()
        if not self._watcher:
            return {"error": "watcher not available"}

        t0 = time.time()
        changed_paths, changes = self._watcher.scan()

        indexed = 0
        errors = 0
        for path in changed_paths:
            if not os.path.exists(path):
                continue
            try:
                self._index_file(path)
                indexed += 1
            except Exception as exc:
                _log.debug("index %s failed: %s", path, exc)
                errors += 1

        duration = (time.time() - t0) * 1000
        self._last_scan = time.time()

        stats = {
            "scanned": self._watcher.manifest.total_files,
            "changed": len(changed_paths),
            "indexed": indexed,
            "errors": errors,
            "duration_ms": round(duration, 1),
            "created": sum(1 for c in changes if c.change_type == "created"),
            "modified": sum(1 for c in changes if c.change_type == "modified"),
            "deleted": sum(1 for c in changes if c.change_type == "deleted"),
        }

        if indexed > 0:
            _log.info(
                "AutoIndexer: %d files indexed, %d changed in %.0fms",
                indexed, len(changed_paths), duration,
            )

        return stats

    def _index_file(self, path: str) -> None:
        p = Path(path)
        suffix = p.suffix.lower()
        if suffix not in (".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java", ".c", ".cpp"):
            return

        try:
            from code_context.ast_adapter import get_extractor
            lang_map = {
                ".py": "python", ".js": "javascript", ".ts": "typescript",
                ".tsx": "typescript", ".jsx": "javascript",
                ".go": "go", ".rs": "rust", ".java": "java",
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
                    _log.debug("auto_indexer: optional dependency or operation failed", exc_info=True)
                symbols_data = [
                    type("S", (), {"name": s.name, "kind": s.kind, "line": s.line})()
                    for s in file_ast.symbols
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
            _log.debug("index_file %s failed: %s", path, exc)

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

_INDEXER_TASK = None


def start_auto_indexer(interval_sec: int = 300) -> None:
    """Start background periodic scan. Non-blocking."""
    global _INDEXER_TASK
    try:
        import asyncio
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    _INDEXER_TASK = loop.create_task(_indexer_loop(interval_sec))
    _log.info("auto_indexer started (interval=%ds)", interval_sec)


async def _indexer_loop(interval_sec: int) -> None:
    while True:
        try:
            run_indexer_scan()
        except Exception as exc:
            _log.debug("auto_indexer: optional dependency or operation failed", exc_info=True)
        await asyncio.sleep(interval_sec)


def stop_auto_indexer() -> None:
    global _INDEXER_TASK
    if _INDEXER_TASK and not _INDEXER_TASK.done():
        _INDEXER_TASK.cancel()
        _INDEXER_TASK = None
