"""Local JSONL persistence for agent task and result records.

Zero external dependencies. Default path controlled by LIMA_AGENT_RUN_STORE.
All records are sanitized before write. Bad lines are skipped on read.
"""

from __future__ import annotations

import json
import logging
import os
from abc import ABC, abstractmethod

_log = logging.getLogger(__name__)

from agent_runtime.contract import AgentRunResult, AgentTask, redact


_DEFAULT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
)


def _store_path() -> str:
    return os.environ.get(
        "LIMA_AGENT_RUN_STORE",
        os.path.join(_DEFAULT_DIR, "agent_runs.jsonl"),
    )


class AgentRunStore(ABC):
    @abstractmethod
    def save_task(self, task: AgentTask) -> bool: ...

    @abstractmethod
    def save_result(self, result: AgentRunResult) -> bool: ...

    @abstractmethod
    def get_task(self, task_id: str) -> AgentTask | None: ...

    @abstractmethod
    def get_result(self, task_id: str) -> AgentRunResult | None: ...

    @abstractmethod
    def list_tasks(self, status: str = "", limit: int = 50) -> list[AgentTask]: ...

    @abstractmethod
    def list_results(
        self,
        status: str = "",
        limit: int = 50,
    ) -> list[AgentRunResult]: ...

    @abstractmethod
    def delete_task(self, task_id: str) -> bool: ...


class InMemoryAgentRunStore(AgentRunStore):
    def __init__(self) -> None:
        self._tasks: dict[str, AgentTask] = {}
        self._results: dict[str, AgentRunResult] = {}

    def save_task(self, task: AgentTask) -> bool:
        self._tasks[task.task_id] = _sanitize_task(task)
        return True

    def save_result(self, result: AgentRunResult) -> bool:
        self._results[result.task_id] = _sanitize_result(result)
        return True

    def get_task(self, task_id: str) -> AgentTask | None:
        return self._tasks.get(task_id)

    def get_result(self, task_id: str) -> AgentRunResult | None:
        return self._results.get(task_id)

    def list_tasks(self, status: str = "", limit: int = 50) -> list[AgentTask]:
        tasks = list(self._tasks.values())
        if status:
            tasks = [task for task in tasks if task.status.value == status]
        return sorted(tasks, key=lambda task: -task.created_at)[:limit]

    def list_results(
        self,
        status: str = "",
        limit: int = 50,
    ) -> list[AgentRunResult]:
        results = list(self._results.values())
        if status:
            results = [result for result in results if result.status.value == status]
        return results[-limit:]

    def delete_task(self, task_id: str) -> bool:
        removed = self._tasks.pop(task_id, None)
        self._results.pop(task_id, None)
        return removed is not None


class JsonlAgentRunStore(AgentRunStore):
    """JSONL-backed persistent store. One line per sanitized record."""

    def __init__(self, path: str = "") -> None:
        self._path = path or _store_path()
        self._ensure_dir()

    def _ensure_dir(self) -> None:
        store_dir = os.path.dirname(self._path)
        if store_dir:
            os.makedirs(store_dir, exist_ok=True)

    def save_task(self, task: AgentTask) -> bool:
        try:
            rec = {"_type": "task", **_sanitize_task(task).to_dict()}
            with open(self._path, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(rec, ensure_ascii=False) + "\n")
            return True
        except OSError:
            return False

    def save_result(self, result: AgentRunResult) -> bool:
        try:
            rec = {"_type": "result", **_sanitize_result(result).to_dict()}
            with open(self._path, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(rec, ensure_ascii=False) + "\n")
            return True
        except OSError:
            return False

    def get_task(self, task_id: str) -> AgentTask | None:
        for rec in reversed(self._read_all()):
            if rec.get("_type") == "task" and _matches_task_id(rec, task_id):
                return AgentTask.from_dict(rec)
        return None

    def get_result(self, task_id: str) -> AgentRunResult | None:
        for rec in reversed(self._read_all()):
            if rec.get("_type") == "result" and _matches_task_id(rec, task_id):
                return AgentRunResult.from_dict(rec)
        return None

    def list_tasks(self, status: str = "", limit: int = 50) -> list[AgentTask]:
        latest: dict[str, AgentTask] = {}
        for rec in self._read_all():
            if rec.get("_type") != "task":
                continue
            task = AgentTask.from_dict(rec)
            latest[task.task_id] = task

        tasks = list(latest.values())
        if status:
            tasks = [task for task in tasks if task.status.value == status]
        return sorted(tasks, key=lambda task: -task.created_at)[:limit]

    def list_results(
        self,
        status: str = "",
        limit: int = 50,
    ) -> list[AgentRunResult]:
        latest: dict[str, AgentRunResult] = {}
        for rec in self._read_all():
            if rec.get("_type") != "result":
                continue
            result = AgentRunResult.from_dict(rec)
            latest[result.task_id] = result

        results = list(latest.values())
        if status:
            results = [result for result in results if result.status.value == status]
        return results[-limit:]

    def delete_task(self, task_id: str) -> bool:
        records = self._read_all()
        filtered = [
            record
            for record in records
            if not _matches_task_id(record, task_id)
        ]
        if len(filtered) == len(records):
            return False
        self._write_all(filtered)
        return True

    def _read_all(self) -> list[dict]:
        if not os.path.exists(self._path):
            return []
        records = []
        with open(self._path, "r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return records

    def _write_all(self, records: list[dict]) -> None:
        tmp = self._path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            for rec in records:
                handle.write(json.dumps(rec, ensure_ascii=False) + "\n")
        os.replace(tmp, self._path)


def list_recent(store: AgentRunStore, limit: int = 20) -> list[AgentTask]:
    return store.list_tasks(status="", limit=limit)


def count_by_status(store: AgentRunStore) -> dict[str, int]:
    counts: dict[str, int] = {}
    for task in store.list_tasks(limit=10000):
        status = task.status.value
        counts[status] = counts.get(status, 0) + 1
    return dict(sorted(counts.items()))


def find_blocked(store: AgentRunStore, limit: int = 20) -> list[AgentTask]:
    blocked: list[AgentTask] = []
    for result in store.list_results(limit=10000):
        if not any(step.blocked for step in result.steps):
            continue
        task = store.get_task(result.task_id)
        if task is not None:
            blocked.append(task)
        if len(blocked) >= limit:
            break
    return blocked


def find_failed(store: AgentRunStore, limit: int = 20) -> list[AgentTask]:
    return store.list_tasks(status="failed", limit=limit)


def delete_older_than(store: AgentRunStore, cutoff_ts: float) -> int:
    deleted = 0
    for task in store.list_tasks(limit=10000):
        if task.created_at < cutoff_ts and store.delete_task(task.task_id):
            deleted += 1
    return deleted


def compact_jsonl(path: str = "") -> int:
    """Rewrite JSONL, keeping only the latest record per task_id and type."""
    target = path or _store_path()
    if not os.path.exists(target):
        return 0

    records = []
    seen: dict[str, int] = {}
    with open(target, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            task_id = rec.get("task_id", "")
            record_type = rec.get("_type", "")
            seen[f"{task_id}:{record_type}"] = len(records)
            records.append(rec)

    kept = [records[index] for index in sorted(set(seen.values()))]
    tmp = target + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        for rec in kept:
            handle.write(json.dumps(rec, ensure_ascii=False) + "\n")
    os.replace(tmp, target)
    return len(kept)


def reset_store_for_tests(path: str = "") -> None:
    target = path or _store_path()
    try:
        os.remove(target)
    except OSError:
        _log.debug("store: optional dependency or operation failed", exc_info=True)
def _sanitize_task(task: AgentTask) -> AgentTask:
    return AgentTask.from_dict(task.to_dict())


def _sanitize_result(result: AgentRunResult) -> AgentRunResult:
    return AgentRunResult.from_dict(result.to_dict())


def _matches_task_id(record: dict, task_id: str) -> bool:
    stored = str(record.get("task_id", ""))
    return stored == task_id or stored == redact(task_id)
