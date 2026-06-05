"""Observable trace for retrieval / memory / skills / code context injection."""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

MAX_TRACES = 50


@dataclass
class ContextInjectionTrace:
    timestamp: float = 0.0
    scenario: str = ""
    backend: str = ""
    retrieval_chars: int = 0
    web_search_chars: int = 0
    code_context_chars: int = 0
    memory_items: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    request_type: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "scenario": self.scenario,
            "backend": self.backend,
            "retrieval_chars": self.retrieval_chars,
            "web_search_chars": self.web_search_chars,
            "code_context_chars": self.code_context_chars,
            "memory_items": list(self.memory_items),
            "skills": list(self.skills),
            "request_type": self.request_type,
            "injection_summary": self.summary(),
        }

    def summary(self) -> str:
        parts: list[str] = []
        if self.retrieval_chars:
            parts.append(f"retrieval={self.retrieval_chars}c")
        if self.web_search_chars:
            parts.append(f"web={self.web_search_chars}c")
        if self.code_context_chars:
            parts.append(f"code={self.code_context_chars}c")
        if self.memory_items:
            parts.append(f"memory={len(self.memory_items)}")
        if self.skills:
            parts.append(f"skills={len(self.skills)}")
        return ", ".join(parts) or "none"

    def to_meta(self) -> dict[str, Any]:
        """Compact payload for x_lima_meta (no secrets / no full prompt)."""
        return {
            "retrieval_chars": self.retrieval_chars,
            "web_search_chars": self.web_search_chars,
            "code_context_chars": self.code_context_chars,
            "memory_count": len(self.memory_items),
            "memory_types": [m.split("]", 1)[0].strip("[") for m in self.memory_items[:5]],
            "skills": self.skills[:10],
            "summary": self.summary(),
        }


_traces: deque[ContextInjectionTrace] = deque(maxlen=MAX_TRACES)
_active: ContextInjectionTrace | None = None


def begin_trace(*, scenario: str = "", request_type: str = "") -> ContextInjectionTrace:
    global _active
    _active = ContextInjectionTrace(
        timestamp=time.time(),
        scenario=scenario,
        request_type=request_type,
    )
    return _active


def get_active_trace() -> ContextInjectionTrace | None:
    return _active


def record_retrieval(text: str) -> None:
    if _active and text:
        _active.retrieval_chars += len(text)


def record_web_search(text: str) -> None:
    if _active and text:
        _active.web_search_chars += len(text)


def record_code_context(text: str) -> None:
    if _active and text:
        _active.code_context_chars += len(text)


def record_memory_item(label: str) -> None:
    if _active and label:
        _active.memory_items.append(label[:120])


def record_skills(skill_ids: list[str]) -> None:
    if _active and skill_ids:
        _active.skills = list(skill_ids)


def finish_trace(*, backend: str = "") -> ContextInjectionTrace | None:
    global _active
    if not _active:
        return None
    if backend:
        _active.backend = backend
    if not _active.timestamp:
        _active.timestamp = time.time()
    _traces.append(_active)
    finished = _active
    _active = None
    return finished


def get_recent_traces(limit: int = 20) -> list[dict]:
    items = list(_traces)[-limit:]
    items.reverse()
    return [t.to_dict() for t in items]
