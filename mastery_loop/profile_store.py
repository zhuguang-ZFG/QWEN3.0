"""SQLite-backed mastery profile store."""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from pathlib import Path

from .models import MasteryEvent, ModuleMastery, ReviewSchedule, WeakPoint, utc_now

DEFAULT_DB = Path("data/mastery_loop.db")
SECRET_PATTERN = re.compile(
    r"(sk-[A-Za-z0-9_-]{8,}|gh[pousr]_[A-Za-z0-9_]{12,}|token\s*=\s*[^,\s]+|password\s*=\s*[^,\s]+)",
    re.IGNORECASE,
)


def sanitize_text(text: str) -> str:
    return SECRET_PATTERN.sub("[REDACTED]", text or "")


def _event_id(event: MasteryEvent) -> str:
    raw = "|".join([
        event.source,
        event.project,
        event.outcome,
        event.summary,
        event.evidence_ref,
        event.created_at,
    ])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


class MasteryStore:
    def __init__(self, db_path: str | Path = DEFAULT_DB):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS mastery_events (
                    event_id TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    project TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    files_json TEXT NOT NULL,
                    modules_json TEXT NOT NULL,
                    score REAL NOT NULL,
                    severity TEXT NOT NULL,
                    evidence_ref TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS module_mastery (
                    project TEXT NOT NULL,
                    module TEXT NOT NULL,
                    stability_score REAL NOT NULL,
                    test_confidence REAL NOT NULL,
                    review_risk REAL NOT NULL,
                    deploy_risk REAL NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    next_review_at TEXT NOT NULL,
                    PRIMARY KEY(project, module)
                );
                CREATE TABLE IF NOT EXISTS weak_points (
                    project TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    target TEXT NOT NULL,
                    description TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    recurrence_count INTEGER NOT NULL,
                    last_evidence_ref TEXT NOT NULL,
                    status TEXT NOT NULL,
                    PRIMARY KEY(project, kind, target)
                );
                CREATE TABLE IF NOT EXISTS review_schedule (
                    target_type TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    due_at TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    interval_days INTEGER NOT NULL,
                    ease_factor REAL NOT NULL,
                    PRIMARY KEY(target_type, target_id)
                );
                """
            )

    def append_event(self, event: MasteryEvent) -> MasteryEvent:
        clean = MasteryEvent(
            source=event.source,
            project=event.project,
            outcome=event.outcome,
            summary=sanitize_text(event.summary)[:500],
            files=list(event.files),
            modules=list(event.modules),
            score=event.score,
            severity=event.severity,
            evidence_ref=sanitize_text(event.evidence_ref)[:300],
            event_id=event.event_id or _event_id(event),
            created_at=event.created_at,
        )
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO mastery_events
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    clean.event_id,
                    clean.source,
                    clean.project,
                    clean.outcome,
                    clean.summary,
                    json.dumps(clean.files),
                    json.dumps(clean.modules),
                    clean.score,
                    clean.severity,
                    clean.evidence_ref,
                    clean.created_at,
                ),
            )
        return clean

    def list_events(self, project: str = "", limit: int = 50) -> list[MasteryEvent]:
        query = "SELECT * FROM mastery_events"
        params: list[object] = []
        if project:
            query += " WHERE project = ?"
            params.append(project)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._row_event(row) for row in rows]

    def upsert_module(self, mastery: ModuleMastery) -> ModuleMastery:
        mastery.last_seen_at = mastery.last_seen_at or utc_now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO module_mastery
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    mastery.project,
                    mastery.module,
                    mastery.stability_score,
                    mastery.test_confidence,
                    mastery.review_risk,
                    mastery.deploy_risk,
                    mastery.last_seen_at,
                    mastery.next_review_at,
                ),
            )
        return mastery

    def get_module(self, project: str, module: str) -> ModuleMastery | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM module_mastery WHERE project = ? AND module = ?",
                (project, module),
            ).fetchone()
        if not row:
            return None
        return ModuleMastery(**dict(row))

    def list_modules(self, project: str = "") -> list[ModuleMastery]:
        query = "SELECT * FROM module_mastery"
        params: list[object] = []
        if project:
            query += " WHERE project = ?"
            params.append(project)
        query += " ORDER BY review_risk DESC, deploy_risk DESC, module ASC"
        with self._connect() as conn:
            return [ModuleMastery(**dict(row)) for row in conn.execute(query, params).fetchall()]

    def add_weak_point(self, weak: WeakPoint) -> WeakPoint:
        clean = WeakPoint(
            project=weak.project,
            kind=weak.kind,
            target=weak.target,
            description=sanitize_text(weak.description)[:500],
            severity=weak.severity,
            recurrence_count=weak.recurrence_count,
            last_evidence_ref=sanitize_text(weak.last_evidence_ref)[:300],
            status=weak.status,
        )
        with self._connect() as conn:
            existing = conn.execute(
                """
                SELECT * FROM weak_points
                WHERE project = ? AND kind = ? AND target = ?
                """,
                (clean.project, clean.kind, clean.target),
            ).fetchone()
            if existing:
                clean.recurrence_count = int(existing["recurrence_count"]) + 1
            conn.execute(
                """
                INSERT OR REPLACE INTO weak_points
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    clean.project,
                    clean.kind,
                    clean.target,
                    clean.description,
                    clean.severity,
                    clean.recurrence_count,
                    clean.last_evidence_ref,
                    clean.status,
                ),
            )
        return clean

    def list_weak_points(self, project: str = "", status: str = "open") -> list[WeakPoint]:
        query = "SELECT * FROM weak_points WHERE 1 = 1"
        params: list[object] = []
        if project:
            query += " AND project = ?"
            params.append(project)
        if status:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY recurrence_count DESC, severity DESC, target ASC"
        with self._connect() as conn:
            return [WeakPoint(**dict(row)) for row in conn.execute(query, params).fetchall()]

    def upsert_schedule(self, schedule: ReviewSchedule) -> ReviewSchedule:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO review_schedule
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    schedule.target_type,
                    schedule.target_id,
                    schedule.due_at,
                    schedule.reason,
                    schedule.interval_days,
                    schedule.ease_factor,
                ),
            )
        return schedule

    def list_schedules(self) -> list[ReviewSchedule]:
        with self._connect() as conn:
            return [
                ReviewSchedule(**dict(row))
                for row in conn.execute("SELECT * FROM review_schedule ORDER BY due_at ASC").fetchall()
            ]

    @staticmethod
    def _row_event(row: sqlite3.Row) -> MasteryEvent:
        return MasteryEvent(
            event_id=row["event_id"],
            source=row["source"],
            project=row["project"],
            outcome=row["outcome"],
            summary=row["summary"],
            files=json.loads(row["files_json"]),
            modules=json.loads(row["modules_json"]),
            score=row["score"],
            severity=row["severity"],
            evidence_ref=row["evidence_ref"],
            created_at=row["created_at"],
        )
