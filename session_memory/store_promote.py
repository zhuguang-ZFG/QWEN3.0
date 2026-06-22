"""Typed memory, promotion, and audit."""

from __future__ import annotations

import json
import os
import time

from session_memory.store_db import (
    MEMORY_TYPES,
    MemoryEntry,
    get_db_path,
    _sanitize_storage_text,
)
from session_memory import store_db
from session_memory.store_crud import save_memory


def save_typed_memory(
    memory_type: str,
    summary: str,
    detail: str = "",
    session_id: str = "_global",
) -> int:
    """Save a typed memory (not tied to a single exchange)."""
    if memory_type not in MEMORY_TYPES:
        detail = f"[original_type={memory_type}] {detail}".strip()
        memory_type = "project_fact"
    return save_memory(
        session_id=session_id,
        role="system",
        summary=summary,
        detail=detail,
        memory_type=memory_type,
    )


def query_by_type(memory_type: str, limit: int = 10, session_id: str | None = None) -> list[MemoryEntry]:
    """Query memories by type, optionally scoped to a session."""
    conn = store_db._get_conn()
    if session_id:
        rows = conn.execute(
            "SELECT id, session_id, timestamp, role, summary, detail, embedding, memory_type "
            "FROM memories WHERE memory_type = ? AND session_id = ? "
            "ORDER BY timestamp DESC, id DESC LIMIT ?",
            (memory_type, session_id, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, session_id, timestamp, role, summary, detail, embedding, memory_type "
            "FROM memories WHERE memory_type = ? "
            "ORDER BY timestamp DESC, id DESC LIMIT ?",
            (memory_type, limit),
        ).fetchall()
    conn.close()
    return [
        MemoryEntry(
            id=r[0],
            session_id=r[1],
            timestamp=r[2],
            role=r[3],
            summary=r[4],
            detail=r[5],
            embedding=json.loads(r[6]),
            memory_type=r[7] if len(r) > 7 else "exchange",
        )
        for r in rows
    ]


# Promotion

_PROMOTION_RULES: dict[str, dict[str, list[str]]] = {
    "exchange": {
        "reference_pattern": ["pattern", "reference", "reusable"],
        "routing_lesson": ["route", "backend", "fallback"],
        "code_fact": ["def ", "class ", "import "],
        "ops_event": ["deploy", "restart", "server"],
        "test_result": ["test", "passed", "failed", "coverage"],
        "security_lesson": ["vuln", "auth", "token", "secret"],
        "user_pref": ["prefer", "user", "style"],
    },
}


def promote_memory(
    memory_id: int,
    new_type: str,
    evidence: str = "",
    auto: bool = False,
) -> bool:
    """Promote a memory from one type to another with evidence.

    Returns True if promotion succeeded, False if rejected.
    """
    if new_type not in MEMORY_TYPES or new_type == "exchange":
        return False

    conn = store_db._get_conn()
    row = conn.execute(
        "SELECT id, session_id, timestamp, role, summary, detail, embedding, memory_type FROM memories WHERE id = ?",
        (memory_id,),
    ).fetchone()
    if not row:
        conn.close()
        return False

    old_type = row[7] if len(row) > 7 else "exchange"
    detail = row[5] or ""
    evidence = _sanitize_storage_text(evidence)
    if evidence and "[REDACTED]" in evidence:
        return False  # evidence contained secrets, reject promotion
    evidence_line = f"[promoted from {old_type}]" + (f" evidence={evidence}" if evidence else "")
    new_detail = f"{evidence_line}\n{detail}" if detail else evidence_line

    conn.execute(
        "UPDATE memories SET memory_type = ?, detail = ? WHERE id = ?",
        (new_type, new_detail, memory_id),
    )
    conn.commit()
    conn.close()
    _record_promotion_audit(memory_id, old_type, new_type, evidence, auto)
    return True


def auto_promote_candidates(session_id: str, limit: int = 50) -> list[int]:
    """Find exchange memories that match promotion rule keywords.

    Returns list of memory IDs that are candidates for promotion.
    Does NOT perform the promotion - caller decides.
    """
    conn = store_db._get_conn()
    rows = conn.execute(
        "SELECT id, summary FROM memories "
        "WHERE session_id = ? AND memory_type = 'exchange' "
        "ORDER BY timestamp DESC LIMIT ?",
        (session_id, limit),
    ).fetchall()
    conn.close()

    candidates = []
    for mem_id, summary in rows:
        text = (summary or "").lower()
        for _new_type, rule_set in _PROMOTION_RULES.get("exchange", {}).items():
            for keywords in [rule_set]:
                if any(kw in text for kw in keywords):
                    if mem_id not in candidates:
                        candidates.append(mem_id)
    return candidates


def _record_promotion_audit(
    memory_id: int,
    old_type: str,
    new_type: str,
    evidence: str,
    auto: bool,
) -> None:
    """Record promotion in audit log (lightweight JSONL)."""
    audit_dir = os.path.dirname(get_db_path())
    audit_path = os.path.join(audit_dir, "memory_promotions.jsonl")
    try:
        entry = {
            "memory_id": memory_id,
            "old_type": old_type,
            "new_type": new_type,
            "evidence": evidence,
            "auto": auto,
            "timestamp": time.time(),
        }
        with open(audit_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass
