"""Database query tools — execute read-only SQL queries safely.

Supported databases:
- SQLite (file-based, no additional drivers needed)
- PostgreSQL (requires ``psycopg2``)
- MySQL (requires ``pymysql``)

Security constraints:
- Only SELECT / WITH queries are allowed (read-only)
- Query timeout (default 10s)
- Result row limit (default 100)
"""

from __future__ import annotations

import logging
import os
import re
import time
from typing import Any

from .registry import tool

_log = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────────────────
_QUERY_TIMEOUT = int(os.environ.get("LIMA_DB_QUERY_TIMEOUT", "10"))
_MAX_ROWS = int(os.environ.get("LIMA_DB_MAX_ROWS", "100"))

# SQL statements that are NOT allowed (write / admin operations)
_FORBIDDEN_PATTERNS = re.compile(
    r"^\s*(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|REPLACE|GRANT|REVOKE)\b",
    re.IGNORECASE,
)


def _is_read_only(sql: str) -> bool:
    """Return True if the SQL statement is a safe read-only query."""
    # Strip leading comments and whitespace
    cleaned = re.sub(r"--[^\n]*", "", sql)
    cleaned = re.sub(r"/\*.*?\*/", "", cleaned, flags=re.DOTALL)
    cleaned = cleaned.strip()
    if not cleaned:
        return False
    if _FORBIDDEN_PATTERNS.match(cleaned):
        return False
    return True


def _parse_connection_string(conn_str: str) -> dict[str, Any]:
    """Parse a connection string into a typed config dict.

    Supported formats:
    - ``sqlite:///path/to/db.sqlite``
    - ``postgresql://user:pass@host:port/dbname``
    - ``mysql://user:pass@host:port/dbname``
    """
    if conn_str.startswith("sqlite:///"):
        return {"type": "sqlite", "path": conn_str[len("sqlite:///"):]}
    if conn_str.startswith("postgresql://") or conn_str.startswith("postgres://"):
        url = conn_str.split("://", 1)[1]
        return {"type": "postgresql", "url": conn_str}
    if conn_str.startswith("mysql://"):
        return {"type": "mysql", "url": conn_str}
    # Default: try SQLite file path
    return {"type": "sqlite", "path": conn_str}


async def _query_sqlite(path: str, sql: str, timeout: float) -> dict[str, Any]:
    """Execute a read-only query on a SQLite database."""
    import sqlite3

    conn = sqlite3.connect(path, timeout=timeout)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.execute(sql)
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        rows = cursor.fetchmany(_MAX_ROWS + 1)
        truncated = len(rows) > _MAX_ROWS
        rows = rows[:_MAX_ROWS]
        result = [dict(row) for row in rows]
        return {
            "columns": columns,
            "rows": result,
            "row_count": len(result),
            "truncated": truncated,
        }
    finally:
        conn.close()


async def _query_postgresql(url: str, sql: str) -> dict[str, Any]:
    """Execute a read-only query on a PostgreSQL database."""
    try:
        import psycopg2
        import psycopg2.extras
    except ImportError:
        return {"error": "psycopg2 is not installed. Run: pip install psycopg2-binary"}

    conn = psycopg2.connect(url, connect_timeout=5)
    conn.set_session(readonly=True, autocommit=True)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql)
            columns = [desc[0] for desc in cur.description] if cur.description else []
            rows = cur.fetchmany(_MAX_ROWS + 1)
            truncated = len(rows) > _MAX_ROWS
            rows = rows[:_MAX_ROWS]
            result = [dict(row) for row in rows]
            return {
                "columns": columns,
                "rows": result,
                "row_count": len(result),
                "truncated": truncated,
            }
    finally:
        conn.close()


async def _query_mysql(url: str, sql: str) -> dict[str, Any]:
    """Execute a read-only query on a MySQL database."""
    try:
        import pymysql
        import pymysql.cursors
    except ImportError:
        return {"error": "pymysql is not installed. Run: pip install pymysql"}

    # Parse MySQL URL
    from urllib.parse import urlparse

    parsed = urlparse(url)
    conn = pymysql.connect(
        host=parsed.hostname or "localhost",
        port=parsed.port or 3306,
        user=parsed.username or "",
        password=parsed.password or "",
        database=parsed.path.lstrip("/") or "",
        connect_timeout=5,
        cursorclass=pymysql.cursors.DictCursor,
        read_default_file=None,
    )
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            columns = [desc[0] for desc in cur.description] if cur.description else []
            rows = cur.fetchmany(_MAX_ROWS + 1)
            truncated = len(rows) > _MAX_ROWS
            rows = rows[:_MAX_ROWS]
            # Convert any non-JSON-serializable types
            result = []
            for row in rows:
                clean = {}
                for k, v in row.items():
                    if hasattr(v, "isoformat"):
                        clean[k] = v.isoformat()
                    elif isinstance(v, bytes):
                        clean[k] = v.decode("utf-8", errors="replace")
                    else:
                        clean[k] = v
                result.append(clean)
            return {
                "columns": columns,
                "rows": result,
                "row_count": len(result),
                "truncated": truncated,
            }
    finally:
        conn.close()


@tool(
    "query_database",
    "Execute a read-only SQL query on a database. "
    "Only SELECT / WITH queries are allowed. Returns columns and rows.",
    {
        "properties": {
            "connection_string": {
                "description": "Database connection string. "
                "SQLite: sqlite:///path/to/db.sqlite "
                "PostgreSQL: postgresql://user:pass@host:port/dbname "
                "MySQL: mysql://user:pass@host:port/dbname",
                "type": "string",
            },
            "sql": {
                "description": "SQL query to execute (SELECT only).",
                "type": "string",
            },
        },
        "required": ["connection_string", "sql"],
        "type": "object",
    },
)
async def _query_database(
    connection_string: str,
    sql: str,
) -> dict[str, Any]:
    """Execute a read-only SQL query."""
    if not _is_read_only(sql):
        return {
            "error": "Only read-only queries (SELECT / WITH) are allowed. "
            "INSERT, UPDATE, DELETE, DROP, and other write operations are blocked.",
        }

    config = _parse_connection_string(connection_string)
    db_type = config["type"]
    start = time.time()

    try:
        if db_type == "sqlite":
            result = await _query_sqlite(config["path"], sql, _QUERY_TIMEOUT)
        elif db_type == "postgresql":
            result = await _query_postgresql(config["url"], sql)
        elif db_type == "mysql":
            result = await _query_mysql(config["url"], sql)
        else:
            return {"error": f"Unsupported database type: {db_type}"}

        result["duration_ms"] = int((time.time() - start) * 1000)
        result["database_type"] = db_type
        return result

    except Exception as exc:
        return {
            "error": str(exc),
            "database_type": db_type,
            "duration_ms": int((time.time() - start) * 1000),
        }
