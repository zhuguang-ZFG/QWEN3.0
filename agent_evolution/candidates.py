"""Candidate skill extraction and storage."""

import hashlib
import json
import os
import threading
import time
from dataclasses import dataclass, asdict
from pathlib import Path

_PERSIST_DIR = Path(os.environ.get(
    "LIMA_DATA_DIR", os.path.join(os.path.dirname(__file__), "..", "data")
))
_PERSIST_FILE = _PERSIST_DIR / "candidate_store.json"


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


def extract_candidate_from_task_evidence(
    task_id: str,
    goal: str,
    result: dict,
) -> CandidateSkill:
    changed_files = list(result.get("changed_files", []))
    test_commands = list(result.get("test_commands", []))
    summary = str(result.get("summary", ""))
    risks = " ".join(str(item) for item in result.get("risks", []))
    trigger = " ".join(part for part in [goal, summary, risks] if part).strip()
    return extract_candidate(
        task_id=task_id,
        failure_reason=trigger or "approved_task_evidence",
        commands=test_commands,
        files=changed_files,
    )


class CandidateStore:
    """Persistent store for candidate skills (JSON-backed)."""

    def __init__(self, persist_path: Path | None = None) -> None:
        self._path = persist_path or _PERSIST_FILE
        self._store: dict[str, CandidateSkill] = {}
        self._lock = threading.Lock()
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            for item in data:
                self._store[item["skill_id"]] = CandidateSkill(**item)
        except (json.JSONDecodeError, KeyError, TypeError):
            pass

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = [asdict(c) for c in self._store.values()]
        self._path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def add(self, candidate: CandidateSkill) -> None:
        with self._lock:
            self._store[candidate.skill_id] = candidate
            self._save()

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
