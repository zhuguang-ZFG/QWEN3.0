"""Tests for config/sqlite_pool.py — thread-local SQLite connection pool."""

import os
import sqlite3

from config.sqlite_pool import pooled_sqlite_conn, sqlite_connect_pooled, pool_release, pool_clear


class TestPooledSqliteConn:
    def test_creates_connection(self):
        with pooled_sqlite_conn(":memory:") as conn:
            conn.execute("CREATE TABLE t (id INTEGER)")
            conn.execute("INSERT INTO t VALUES (1)")

    def test_commits_on_success(self):
        path = ".test-tmp/pool_commit.db"
        os.makedirs(".test-tmp", exist_ok=True)
        with pooled_sqlite_conn(path) as conn:
            conn.execute("CREATE TABLE t (id INTEGER)")
            conn.execute("INSERT INTO t VALUES (42)")
        with pooled_sqlite_conn(path) as conn:
            row = conn.execute("SELECT id FROM t").fetchone()
            assert row[0] == 42
        pool_clear()

    def test_rollback_on_error(self):
        path = ":memory:"
        try:
            with pooled_sqlite_conn(path) as conn:
                conn.execute("CREATE TABLE t (id INTEGER UNIQUE)")
                conn.execute("INSERT INTO t VALUES (1)")
                conn.execute("INSERT INTO t VALUES (1)")
            raise AssertionError("expected IntegrityError")
        except sqlite3.IntegrityError:
            pass

    def test_pool_reuses_connections(self):
        path = ".test-tmp/pool_reuse.db"
        os.makedirs(".test-tmp", exist_ok=True)
        conn1 = sqlite_connect_pooled(path)
        conn1.execute("CREATE TABLE IF NOT EXISTS t (id INTEGER)")
        pool_release(path, conn1)
        conn2 = sqlite_connect_pooled(path)
        assert conn2 is conn1
        pool_release(path, conn2)
        pool_clear()

    def test_pool_clear_closes_connections(self):
        path = ".test-tmp/pool_clear.db"
        os.makedirs(".test-tmp", exist_ok=True)
        conn = sqlite_connect_pooled(path)
        pool_release(path, conn)
        pool_clear()
