"""Shadow Mode v0.2 — persistent improvement proposals with state machine.

States: proposed → approved → applied | rejected
NEVER auto-applies. Every proposal requires:
  1. >= MIN_EVIDENCE successful outcomes
  2. Eval pass (if applicable)
  3. Human approval via /learn approve
  4. Rollback notes
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path

_log = logging.getLogger(__name__)

MIN_EVIDENCE = 3
MIN_CONFIDENCE = 0.5

_DB_PATH = os.environ.get("LIMA_OUTCOME_DB", str(Path(__file__).resolve().parent.parent / "data" / "outcome_ledger.db"))


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS candidates (
            id TEXT PRIMARY KEY,
            category TEXT NOT NULL,
            summary TEXT NOT NULL,
            evidence_ids TEXT DEFAULT '[]',
            evidence_count INTEGER DEFAULT 0,
            confidence REAL DEFAULT 0.0,
            proposed_at REAL NOT NULL,
            status TEXT DEFAULT 'proposed',
            rollback_notes TEXT DEFAULT '',
            applied_at REAL DEFAULT 0,
            notes TEXT DEFAULT ''
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_candidates_status ON candidates(status, proposed_at DESC)")
    conn.commit()
    return conn


def save_candidate(c: CandidateImprovement) -> None:
    conn = _get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO candidates (id, category, summary, evidence_ids, evidence_count, confidence, proposed_at, status, rollback_notes) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (c.id, c.category, c.summary, json.dumps(c.evidence_ids), c.evidence_count,
         c.confidence, c.proposed_at, c.status, c.rollback_notes),
    )
    conn.commit()
    conn.close()


def update_candidate(candidate_id: str, status: str, *, notes: str = "") -> bool:
    conn = _get_conn()
    applied_at = time.time() if status == "applied" else 0
    conn.execute(
        "UPDATE candidates SET status=?, applied_at=?, notes=? WHERE id=?",
        (status, applied_at, notes[:200], candidate_id),
    )
    conn.commit()
    affected = conn.total_changes
    conn.close()
    return affected > 0


def list_candidates(*, status: str = "proposed", limit: int = 20) -> list[dict]:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT id, category, summary, evidence_count, confidence, proposed_at, status, rollback_notes, notes "
        "FROM candidates WHERE status=? ORDER BY confidence DESC LIMIT ?",
        (status, limit),
    ).fetchall()
    conn.close()
    return [
        {"id": r[0], "category": r[1], "summary": r[2], "evidence_count": r[3],
         "confidence": r[4], "proposed_at": r[5], "status": r[6],
         "rollback_notes": r[7], "notes": r[8]}
        for r in rows
    ]


@dataclass
class CandidateImprovement:
    id: str
    category: str  # routing_weight | prompt_suggestion | backend_promotion | pattern
    summary: str
    evidence_ids: list[str] = field(default_factory=list)
    evidence_count: int = 0
    confidence: float = 0.0
    proposed_at: float = 0.0
    status: str = "proposed"  # proposed | approved | rejected | applied
    rollback_notes: str = ""


def scan_for_candidates() -> list[CandidateImprovement]:
    """Scan outcome ledger for patterns, persist new candidates. Returns all proposed."""
    candidates: list[CandidateImprovement] = []

    try:
        from session_memory.outcome_ledger import query

        outcomes = query(limit=100)

        # Pattern: Backend+scenario success/failure aggregation
        backend_scene: dict[str, dict] = {}
        for o in outcomes:
            backend = o.get("backend", "")
            scenario = o.get("scenario", "")
            if not backend or not scenario:
                continue
            key = f"{backend}:{scenario}"
            if key not in backend_scene:
                backend_scene[key] = {"success": 0, "total": 0, "ids": []}
            backend_scene[key]["total"] += 1
            if o["outcome"] == "success":
                backend_scene[key]["success"] += 1
            backend_scene[key]["ids"].append(o["event_id"])

        existing = {c["id"] for c in list_candidates(status="proposed")}

        for key, stats in backend_scene.items():
            if stats["total"] >= MIN_EVIDENCE:
                rate = stats["success"] / stats["total"]
                if rate >= 0.8:
                    cid = f"boost:{key}:{int(time.time() // 3600)}"
                    if cid not in existing:
                        c = CandidateImprovement(
                            id=cid, category="routing_weight",
                            summary=f"Boost {key}: {stats['success']}/{stats['total']} ok",
                            evidence_ids=stats["ids"][-5:], evidence_count=stats["total"],
                            confidence=round(rate, 2), proposed_at=time.time(),
                            rollback_notes="Set weight back to 1.0 if failure rate exceeds 30%",
                        )
                        save_candidate(c)
                        candidates.append(c)

                elif rate <= 0.3:
                    cid = f"degrade:{key}:{int(time.time() // 3600)}"
                    if cid not in existing:
                        c = CandidateImprovement(
                            id=cid, category="routing_weight",
                            summary=f"Degrade {key}: {stats['success']}/{stats['total']} ok",
                            evidence_ids=stats["ids"][-5:], evidence_count=stats["total"],
                            confidence=round(1 - rate, 2), proposed_at=time.time(),
                            rollback_notes="Restore weight if subsequent 3 outcomes succeed",
                        )
                        save_candidate(c)
                        candidates.append(c)

    except Exception:
        _log.debug("shadow scan failed", exc_info=True)

    # Return ALL proposed (including previously persisted)
    all_proposed = list_candidates(status="proposed")
    return [
        CandidateImprovement(
            id=c["id"], category=c["category"], summary=c["summary"],
            evidence_ids=[], evidence_count=c["evidence_count"],
            confidence=c["confidence"], proposed_at=c["proposed_at"],
            status=c["status"], rollback_notes=c.get("rollback_notes", ""),
        )
        for c in all_proposed
    ]


def format_digest(candidates: list[CandidateImprovement] | None = None) -> str:
    """Generate a human-readable learning digest.

    Returns markdown text suitable for Telegram or daily report.
    """
    if candidates is None:
        candidates = scan_for_candidates()

    try:
        from session_memory.outcome_ledger import stats as ledger_stats
        from session_memory.store_db import memory_stats

        lstats = ledger_stats()
        mstats = memory_stats()
    except Exception:
        lstats = {"total": 0, "unlearned": 0}
        mstats = {"total": 0, "embedding_pct": 0}

    lines = [
        "*LiMa Learning Digest*",
        f"`{time.strftime('%Y-%m-%d %H:%M')}`",
        "",
        "*Outcomes*",
        f"  Total recorded: {lstats.get('total', 0)}",
        f"  Awaiting review: {lstats.get('unlearned', 0)}",
        "",
        "*Memory*",
        f"  Total entries: {mstats.get('total', 0)}",
        f"  Embedding coverage: {mstats.get('embedding_pct', 0)}%",
        "",
    ]

    if candidates:
        lines.append("*Improvement Candidates*")
        for c in candidates[:8]:
            icon = "\U0001f7e2" if c.confidence >= 0.8 else "\U0001f7e1"
            lines.append(
                f"{icon} [{c.category}] {c.summary}\n"
                f"  evidence={c.evidence_count} confidence={c.confidence}\n"
                f"  `/learn approve {c.id[:40]}`"
            )
        lines.append("")
    else:
        lines.append("No improvement candidates. System is stable.")

    lines.append("")

    # Show applied candidates
    try:
        applied = list_candidates(status="applied")
        if applied:
            lines.append("*Recently Applied*")
            for c in applied[:5]:
                lines.append(f"  ✅ {c['summary'][:100]}")
            lines.append("")
    except Exception:
        pass

    # Show routing weight effects
    try:
        from context_pipeline.routing_weights import get_routing_weights
        rw = get_routing_weights()
        lines.append("*Routing Effects*")
        for scenario in ["coding", "chat"]:
            stats_items = []
            for key, w in rw._weights.items():
                if key.endswith(f":{scenario}") and (w.successes + w.failures) >= 1:
                    stats_items.append((w.weight, w.success_rate, key.split(":")[0], w.successes + w.failures))
            stats_items.sort(key=lambda x: -x[0])
            for weight, rate, backend, total in stats_items[:3]:
                icon = "\U0001f7e2" if rate >= 0.8 else ("\U0001f7e1" if rate >= 0.5 else "\U0001f534")
                lines.append(f"  {icon} {backend}:{scenario} w={weight:.2f} rate={rate:.0%} n={total}")
        lines.append("")
    except Exception:
        pass

    lines.append("/learn to review  /outcome for ledger  /memstats for memory")

    return "\n".join(lines)
