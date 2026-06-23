"""Per-device family approval persistence and gating.

Each protocol family (display, audio, speech, ocr, camera, perception) can be
approved independently per device. Approval records carry safety evidence and
can be revoked by an admin.
"""

from __future__ import annotations

import json
import os
import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

from config import db_config
from config.sqlite_pool import pooled_sqlite_conn
from device_gateway.protocol_families import (
    FAMILY_ALLOWLISTS,
    GATED_FAMILIES,
    ProtocolFamily,
    family_is_active,
)

_DEFAULT_DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
_DEFAULT_DB_FILE = os.path.join(_DEFAULT_DB_DIR, "lima.db")
_DB_PATH = db_config.get_lima_db_path()

GATE_HARDCODED_APPROVAL_FAMILIES: frozenset[str] = frozenset()


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
    return db_config.get_lima_db_path()


def set_db_path(path: str) -> None:
    """Override the DB path, mainly for tests."""
    global _DB_PATH
    _DB_PATH = path
    db_config.LIMA_DB_PATH = path


def _ensure_schema(conn: sqlite3.Connection) -> None:
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


@contextmanager
def _connect() -> Generator[sqlite3.Connection, None, None]:
    db_path = get_db_path()
    os.makedirs(os.path.dirname(db_path) or _DEFAULT_DB_DIR, exist_ok=True)
    with pooled_sqlite_conn(db_path) as conn:
        conn.row_factory = sqlite3.Row
        _ensure_schema(conn)
        yield conn


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


def _family_value(family: str | ProtocolFamily) -> str:
    return family.value if isinstance(family, ProtocolFamily) else family


def family_requires_approval(family: str | ProtocolFamily) -> bool:
    """Return True if the family is gated and requires per-device approval."""
    return _family_value(family) in GATED_FAMILIES


def validate_family_capability(
    device_id: str,
    family: str | ProtocolFamily,
    capability: str,
) -> tuple[bool, str | None]:
    """Validate that a capability is allowed for a device.

    Returns (allowed, error).
    - Gated families (display/audio/speech/ocr/camera/perception) are enabled
      per-device by explicit approval, independent of the global ACTIVE_FAMILIES.
    - Non-gated active families (e.g. motion) use the global allowlist.
    """
    value = _family_value(family)
    allowed = FAMILY_ALLOWLISTS.get(value)
    if allowed is None or capability not in allowed:
        return False, f"Capability '{capability}' not in family '{value}'"

    if value in GATED_FAMILIES:
        if value in GATE_HARDCODED_APPROVAL_FAMILIES:
            return True, None
        if not is_family_approved(device_id, value):
            return False, f"Family '{value}' is not approved for device '{device_id}'"
        return True, None

    if not family_is_active(value):
        return False, f"Family '{value}' is not active"

    return True, None


__all__ = [
    "FamilyApproval",
    "approve_family",
    "family_requires_approval",
    "get_family_approval",
    "is_family_approved",
    "list_family_approvals",
    "reset_family_approvals",
    "revoke_family",
    "validate_family_capability",
]
