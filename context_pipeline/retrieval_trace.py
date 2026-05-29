"""Retrieval trace — records what was retrieved, why, and what was injected.

Ring buffer of recent traces for admin diagnostics.
"""

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

MAX_TRACES = 50


@dataclass
class RetrievalTrace:
    timestamp: float = 0.0
    query_entities: list[str] = field(default_factory=list)
    candidates_searched: int = 0
    reranked_results: list[dict] = field(default_factory=list)
    injected_text: str = ""
    injected_chars: int = 0
    backend: str = ""
    scenario: str = ""
    request_type: str = ""
    # Source-quality scoring
    source_quality_score: float = 0.0
    retrieval_precision: float = 0.0
    injection_useful: bool = False

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "query_entities": self.query_entities,
            "candidates_searched": self.candidates_searched,
            "reranked_results": self.reranked_results,
            "injected_text": self.injected_text,
            "injected_chars": self.injected_chars,
            "backend": self.backend,
            "scenario": self.scenario,
            "request_type": self.request_type,
            "source_quality_score": self.source_quality_score,
            "retrieval_precision": self.retrieval_precision,
            "injection_useful": self.injection_useful,
        }


_traces: deque = deque(maxlen=MAX_TRACES)


def record_trace(trace: RetrievalTrace) -> None:
    if not trace.timestamp:
        trace.timestamp = time.time()
    _traces.append(trace)


def get_recent_traces(limit: int = 20) -> list[dict]:
    items = list(_traces)[-limit:]
    items.reverse()
    return [t.to_dict() for t in items]
