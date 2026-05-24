"""Unified eval registry linking model, route, fixture, score, and promotion.

Provides a single source of truth for what was evaluated, when, against
which fixtures, with what score, and whether it was promoted into routing.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field


@dataclass
class EvalEntry:
    model: str
    backend: str
    fixture: str
    timestamp: float = field(default_factory=time.time)
    score: float = 0.0
    passed: bool = False
    latency_ms: float = 0.0
    cost_tokens: int = 0
    cost_estimated_usd: float = 0.0
    promoted_to: str = ""  # "strong" | "medium" | "floor" | ""
    fail_reason: str = ""
    evidence_file: str = ""

    def to_dict(self) -> dict:
        return {
            "model": self.model, "backend": self.backend,
            "fixture": self.fixture, "timestamp": self.timestamp,
            "score": self.score, "passed": self.passed,
            "latency_ms": self.latency_ms,
            "cost_tokens": self.cost_tokens,
            "cost_estimated_usd": self.cost_estimated_usd,
            "promoted_to": self.promoted_to,
            "fail_reason": self.fail_reason,
            "evidence_file": self.evidence_file,
        }


_EVAL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
_EVAL_PATH = os.environ.get(
    "LIMA_EVAL_REGISTRY",
    os.path.join(_EVAL_DIR, "eval_registry.jsonl"),
)


def record_eval(entry: EvalEntry) -> None:
    os.makedirs(os.path.dirname(_EVAL_PATH), exist_ok=True)
    with open(_EVAL_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")


def query_evals(
    backend: str = "",
    fixture: str = "",
    promoted: bool | None = None,
    limit: int = 50,
) -> list[EvalEntry]:
    if not os.path.exists(_EVAL_PATH):
        return []
    results = []
    with open(_EVAL_PATH, "r", encoding="utf-8") as f:
        for line in f:
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            if backend and d.get("backend") != backend:
                continue
            if fixture and d.get("fixture") != fixture:
                continue
            if promoted is True and not d.get("promoted_to"):
                continue
            if promoted is False and d.get("promoted_to"):
                continue
            results.append(EvalEntry(
                model=d.get("model", ""),
                backend=d.get("backend", ""),
                fixture=d.get("fixture", ""),
                timestamp=d.get("timestamp", 0),
                score=d.get("score", 0),
                passed=d.get("passed", False),
                latency_ms=d.get("latency_ms", 0),
                cost_tokens=d.get("cost_tokens", 0),
                cost_estimated_usd=d.get("cost_estimated_usd", 0),
                promoted_to=d.get("promoted_to", ""),
                fail_reason=d.get("fail_reason", ""),
                evidence_file=d.get("evidence_file", ""),
            ))
    return results[-limit:]


def latest_promoted(limit: int = 20) -> list[EvalEntry]:
    return query_evals(promoted=True, limit=limit)


def summary() -> dict:
    entries = query_evals(limit=1000)
    passed = [e for e in entries if e.passed]
    promoted = [e for e in entries if e.promoted_to]
    total_cost = sum(e.cost_estimated_usd for e in entries)
    return {
        "total_evals": len(entries),
        "passed": len(passed),
        "failed": len(entries) - len(passed),
        "promoted": len(promoted),
        "total_cost_estimated_usd": round(total_cost, 6),
        "latest_eval_at": max((e.timestamp for e in entries), default=0),
    }
