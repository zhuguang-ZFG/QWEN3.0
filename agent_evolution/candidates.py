"""Candidate skill extraction and storage."""

import hashlib
import threading
import time
from dataclasses import dataclass


@dataclass
class CandidateSkill:
    skill_id: str
    name: str
    source_task_id: str
    trigger_pattern: str
    backend: str
    commands: list[str]
    file_categories: list[str]
    created_at: float
    active: bool = False
    eval_passed: bool = False
    promoted: bool = False


def extract_candidate(
    task_id: str,
    failure_reason: str,
    commands: list[str],
    files: list[str],
) -> CandidateSkill:
    """Create an inactive candidate from task results."""
    skill_id = hashlib.sha256(
        f"{task_id}:{failure_reason}".encode()
    ).hexdigest()[:12]
    name = f"skill_{skill_id}"
    categories = list({f.rsplit(".", 1)[-1] for f in files if "." in f})
    return CandidateSkill(
        skill_id=skill_id,
        name=name,
        source_task_id=task_id,
        trigger_pattern=failure_reason,
        backend="auto",
        commands=commands,
        file_categories=categories,
        created_at=time.time(),
        active=False,
        eval_passed=False,
        promoted=False,
    )


class CandidateStore:
    """In-memory store for candidate skills."""

    def __init__(self) -> None:
        self._store: dict[str, CandidateSkill] = {}
        self._lock = threading.Lock()

    def add(self, candidate: CandidateSkill) -> None:
        with self._lock:
            self._store[candidate.skill_id] = candidate

    def get(self, skill_id: str) -> CandidateSkill | None:
        with self._lock:
            return self._store.get(skill_id)

    def list_pending(self) -> list[CandidateSkill]:
        with self._lock:
            return [c for c in self._store.values() if not c.promoted]


_global_store: CandidateStore | None = None


def get_candidate_store() -> CandidateStore:
    global _global_store
    if _global_store is None:
        _global_store = CandidateStore()
    return _global_store
