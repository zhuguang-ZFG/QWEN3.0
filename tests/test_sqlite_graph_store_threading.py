"""Regression tests for code_context/sqlite_graph_store.py thread safety (P1-1)."""

from __future__ import annotations

import threading

from code_context.sqlite_graph_store import SqliteGraphIndex


THREADS = 10
OPS_PER_THREAD = 50


def test_concurrent_add_relation_is_consistent(tmp_path):
    """Multiple threads writing via the same connection must not corrupt the database."""
    db_path = tmp_path / "graph_threading.db"
    index = SqliteGraphIndex(str(db_path))
    errors: list[Exception] = []

    def worker(tid: int) -> None:
        try:
            for i in range(OPS_PER_THREAD):
                index.add_relation(f"src_{tid}_{i}", f"tgt_{tid}_{i}", "calls")
        except Exception as exc:  # pragma: no cover - indicates a thread-safety bug
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(tid,)) for tid in range(THREADS)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"concurrent add_relation raised: {errors[:3]}"
    assert index.edge_count == THREADS * OPS_PER_THREAD * 2
    index.close()


def test_concurrent_mixed_read_write(tmp_path):
    """Concurrent reads and writes must stay consistent."""
    db_path = tmp_path / "graph_mixed.db"
    index = SqliteGraphIndex(str(db_path))
    errors: list[Exception] = []

    def writer(tid: int) -> None:
        try:
            for i in range(20):
                index.add_relation("common", f"node_{tid}_{i}", "uses")
        except Exception as exc:  # pragma: no cover
            errors.append(exc)

    def reader() -> None:
        try:
            for _ in range(20):
                index.get_related("common", max_depth=1)
                index.edge_count
        except Exception as exc:  # pragma: no cover
            errors.append(exc)

    threads = [threading.Thread(target=writer, args=(tid,)) for tid in range(THREADS)]
    threads.append(threading.Thread(target=reader))
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"mixed read/write raised: {errors[:3]}"
    assert index.edge_count == THREADS * 20 * 2
    index.close()
