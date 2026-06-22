"""Lessons learned — persistent experience from routing failures and successes."""

import json
import time
from dataclasses import dataclass, asdict
from pathlib import Path

from config.db_config import LESSONS_DIR


LESSONS_DIR = Path(LESSONS_DIR)


@dataclass
class Lesson:
    """A single learned experience."""

    domain: str
    content: str
    learned_at: float
    times_applied: int = 0
    session_id: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Lesson":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


def _lessons_path(session_id: str) -> Path:
    LESSONS_DIR.mkdir(parents=True, exist_ok=True)
    return LESSONS_DIR / f"{session_id}_lessons.json"


def add_lesson(session_id: str, domain: str, content: str) -> Lesson:
    """Record a new lesson learned."""
    lesson = Lesson(
        domain=domain,
        content=content,
        learned_at=time.time(),
        session_id=session_id,
    )
    lessons = get_lessons(session_id)
    lessons.append(lesson)
    _save_lessons(session_id, lessons)
    return lesson


def get_lessons(session_id: str, domain: str = "") -> list[Lesson]:
    """Get all lessons for a session, optionally filtered by domain."""
    path = _lessons_path(session_id)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        lessons = [Lesson.from_dict(d) for d in data]
    except (json.JSONDecodeError, KeyError):
        return []
    if domain:
        lessons = [l for l in lessons if l.domain == domain]
    return lessons


def apply_lesson(session_id: str, domain: str) -> Lesson | None:
    """Find and mark a lesson as applied. Returns the most relevant lesson."""
    lessons = get_lessons(session_id, domain=domain)
    if not lessons:
        return None
    lesson = lessons[-1]
    lesson.times_applied += 1
    _save_lessons(session_id, get_lessons(session_id))
    return lesson


def get_routing_lessons(session_id: str) -> list[Lesson]:
    """Get lessons specifically about routing failures."""
    return get_lessons(session_id, domain="routing")


def _save_lessons(session_id: str, lessons: list[Lesson]) -> None:
    path = _lessons_path(session_id)
    path.write_text(
        json.dumps([l.to_dict() for l in lessons], ensure_ascii=False),
        encoding="utf-8",
    )
