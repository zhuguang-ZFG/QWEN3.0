"""Tests for database query tools (Phase 4.2)."""

import os
import sqlite3
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lima_fc_tools.db_tools import (
    _is_read_only,
    _parse_connection_string,
    _query_database,
)


def test_is_read_only_select():
    assert _is_read_only("SELECT * FROM users") is True
    assert _is_read_only("  SELECT 1") is True
    assert _is_read_only("WITH cte AS (SELECT 1) SELECT * FROM cte") is True


def test_is_read_only_rejects_writes():
    assert _is_read_only("INSERT INTO users VALUES (1)") is False
    assert _is_read_only("DELETE FROM users") is False
    assert _is_read_only("DROP TABLE users") is False
    assert _is_read_only("UPDATE users SET name='x'") is False
    assert _is_read_only("CREATE TABLE test (id INT)") is False
    assert _is_read_only("TRUNCATE TABLE users") is False
    assert _is_read_only("") is False


def test_is_read_only_rejects_comments_before_write():
    # SQL with a comment before the write statement should still be rejected
    assert _is_read_only("-- comment\nDELETE FROM users") is False


def test_parse_connection_string_sqlite():
    config = _parse_connection_string("sqlite:///data/test.db")
    assert config["type"] == "sqlite"
    assert config["path"] == "data/test.db"


def test_parse_connection_string_postgresql():
    config = _parse_connection_string("postgresql://user:pass@localhost/mydb")
    assert config["type"] == "postgresql"
    assert "url" in config


def test_parse_connection_string_mysql():
    config = _parse_connection_string("mysql://user:pass@localhost/mydb")
    assert config["type"] == "mysql"
    assert "url" in config


def test_parse_connection_string_default():
    config = _parse_connection_string("data/test.db")
    assert config["type"] == "sqlite"
    assert config["path"] == "data/test.db"


@pytest.mark.asyncio
async def test_query_sqlite():
    """Test SQLite query execution."""
    # Create a temporary SQLite database
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE users (id INTEGER, name TEXT)")
        conn.execute("INSERT INTO users VALUES (1, 'Alice')")
        conn.execute("INSERT INTO users VALUES (2, 'Bob')")
        conn.commit()
        conn.close()

        conn_str = f"sqlite:///{db_path}"
        result = await _query_database(conn_str, "SELECT * FROM users ORDER BY id")

        assert "error" not in result
        assert result["row_count"] == 2
        assert result["rows"][0]["name"] == "Alice"
        assert result["rows"][1]["name"] == "Bob"
        assert "duration_ms" in result
        assert result["database_type"] == "sqlite"
    finally:
        os.unlink(db_path)


@pytest.mark.asyncio
async def test_query_database_rejects_write():
    result = await _query_database("sqlite:///test.db", "DELETE FROM users")
    assert "error" in result
    assert "read-only" in result["error"].lower()


@pytest.mark.asyncio
async def test_query_database_empty_sql():
    result = await _query_database("sqlite:///test.db", "")
    assert "error" in result
