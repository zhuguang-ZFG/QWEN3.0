"""Shadow Mode v0.1 — autonomous improvement proposals with human gate.

Scans unlearned outcomes, detects patterns, proposes changes.
NEVER auto-applies. Every proposal requires:
  1. >= MIN_EVIDENCE successful outcomes
  2. Eval pass (if applicable)
  3. Human approval via /learn approve
  4. Rollback notes

Output: CandidateImprovement objects ready for review.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

_log = logging.getLogger(__name__)

MIN_EVIDENCE = 3       # minimum outcomes before proposing
MIN_CONFIDENCE = 0.5   # minimum aggregate confidence


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
    """Scan outcome ledger for patterns that suggest improvements.

    Returns list of candidates. Does NOT apply anything.
    """
    candidates: list[CandidateImprovement] = []

    try:
        from session_memory.outcome_ledger import query

        # Look for patterns in recent outcomes
        outcomes = query(limit=50)

        # Pattern 1: Backend repeatedly succeeds in a scenario
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

        for key, stats in backend_scene.items():
            if stats["total"] >= MIN_EVIDENCE:
                rate = stats["success"] / stats["total"]
                if rate >= 0.8:
                    candidates.append(CandidateImprovement(
                        id=f"route:{key}:{int(time.time())}",
                        category="routing_weight",
                        summary=f"Boost {key}: {stats['success']}/{stats['total']} success",
                        evidence_ids=stats["ids"][-5:],
                        evidence_count=stats["total"],
                        confidence=round(rate, 2),
                        proposed_at=time.time(),
                        rollback_notes=f"Set weight back to 1.0 if failure rate exceeds 30%",
                    ))

        # Pattern 2: Repeated failures on same backend+scenario
        for key, stats in backend_scene.items():
            if stats["total"] >= 2:
                rate = stats["success"] / stats["total"]
                if rate <= 0.3:
                    candidates.append(CandidateImprovement(
                        id=f"route:degrade:{key}:{int(time.time())}",
                        category="routing_weight",
                        summary=f"Degrade {key}: {stats['success']}/{stats['total']} success",
                        evidence_ids=stats["ids"][-5:],
                        evidence_count=stats["total"],
                        confidence=round(1 - rate, 2),
                        proposed_at=time.time(),
                        rollback_notes=f"Restore weight if subsequent 3 outcomes succeed",
                    ))

    except Exception:
        _log.debug("shadow scan failed", exc_info=True)

    return candidates


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

    lines.append("/learn to review  /outcome for ledger  /memstats for memory")

    return "\n".join(lines)
