"""Per-device family approval persistence.

Each protocol family (display, audio, speech, ocr, camera, perception) can be
approved independently per device. Approval records carry safety evidence and
can be revoked by an admin.
"""

from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass
from typing import Any


_DEFAULT_DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
_DEFAULT_DB_FILE = os.path.join(_DEFAULT_DB_DIR, "lima.db")
_DB_PATH = os.environ.get("LIMA_DB_PATH", _DEFAULT_DB_FILE)


@dataclass(frozen=True)
class FamilyApproval:
    device_id: str
    family: str
    status: str  # "approved" | "revoked"
    approved_by: str | None
    approved_at: str | None
    revoked_at: str | None
    evidence: dict[str, Any]


def get_db_path() -> str:
    """Resolve the active SQLite path at call time."""
    env_path = os.environ.get("LIMA_DB_PATH")
    if env_path:
        return env_path
    return _DB_PATH


def set_db_path(path: str) -> None:
    """Override the DB path, mainly for tests."""
    global _DB_PATH
    _DB_PATH = path


def _connect() -> sqlite3.Connection:
    db_path = get_db_path()
    if not os.environ.get("LIMA_DB_PATH"):
        os.makedirs(os.path.dirname(db_path) or _DEFAULT_DB_DIR, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS v2_family_approval (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT NOT NULL,
            family TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'approved'
                CHECK (status IN ('approved', 'revoked')),
            approved_by TEXT,
            approved_at TEXT NOT NULL DEFAULT (datetime('now')),
            revoked_at TEXT,
            evidence TEXT DEFAULT '{}',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_family_approval_device_family
        ON v2_family_approval(device_id, family)
        """
    )
    conn.commit()
    return conn


def _now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def approve_family(
    device_id: str,
    family: str,
    approved_by: str,
    evidence: dict[str, Any] | None = None,
) -> FamilyApproval:
    """Approve a protocol family for a device."""
    evidence = evidence or {}
    evidence_json = json.dumps(evidence, ensure_ascii=False, sort_keys=True)
    now = _now()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO v2_family_approval
                (device_id, family, status, approved_by, approved_at, revoked_at, evidence, updated_at)
            VALUES (?, ?, 'approved', ?, ?, NULL, ?, ?)
            ON CONFLICT(device_id, family) DO UPDATE SET
                status='approved',
                approved_by=excluded.approved_by,
                approved_at=excluded.approved_at,
                revoked_at=NULL,
                evidence=excluded.evidence,
                updated_at=excluded.updated_at
            """,
            (device_id, family, approved_by, now, evidence_json, now),
        )
        conn.commit()
    return FamilyApproval(
        device_id=device_id,
        family=family,
        status="approved",
        approved_by=approved_by,
        approved_at=now,
        revoked_at=None,
        evidence=evidence,
    )


def revoke_family(device_id: str, family: str, revoked_by: str) -> FamilyApproval | None:
    """Revoke a previous approval. Returns the updated record or None if no record exists."""
    now = _now()
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM v2_family_approval WHERE device_id=? AND family=?",
            (device_id, family),
        ).fetchone()
        if row is None:
            return None
        conn.execute(
            """
            UPDATE v2_family_approval
            SET status='revoked', revoked_at=?, updated_at=?
            WHERE device_id=? AND family=?
            """,
            (now, now, device_id, family),
        )
        conn.commit()
        evidence = json.loads(row["evidence"] or "{}")
        return FamilyApproval(
            device_id=device_id,
            family=family,
            status="revoked",
            approved_by=row["approved_by"],
            approved_at=row["approved_at"],
            revoked_at=now,
            evidence=evidence,
        )


def get_family_approval(device_id: str, family: str) -> FamilyApproval | None:
    """Return the latest approval record for a device/family, or None."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM v2_family_approval WHERE device_id=? AND family=?",
            (device_id, family),
        ).fetchone()
    if row is None:
        return None
    evidence = json.loads(row["evidence"] or "{}")
    return FamilyApproval(
        device_id=device_id,
        family=family,
        status=row["status"],
        approved_by=row["approved_by"],
        approved_at=row["approved_at"],
        revoked_at=row["revoked_at"],
        evidence=evidence,
    )


def list_family_approvals(device_id: str) -> list[FamilyApproval]:
    """Return all approval records for a device."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM v2_family_approval WHERE device_id=? ORDER BY family",
            (device_id,),
        ).fetchall()
    return [
        FamilyApproval(
            device_id=r["device_id"],
            family=r["family"],
            status=r["status"],
            approved_by=r["approved_by"],
            approved_at=r["approved_at"],
            revoked_at=r["revoked_at"],
            evidence=json.loads(r["evidence"] or "{}"),
        )
        for r in rows
    ]


def is_family_approved(device_id: str, family: str) -> bool:
    """Return True only if there is a current, non-revoked approval."""
    approval = get_family_approval(device_id, family)
    return approval is not None and approval.status == "approved"


def reset_family_approvals() -> None:
    """Clear all approval records. Use only in tests."""
    with _connect() as conn:
        conn.execute("DELETE FROM v2_family_approval")
        conn.commit()
