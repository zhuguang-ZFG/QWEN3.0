"""Reranker protocol with deterministic fixture-backed implementations.

Allows retrieval tests to run with fixed scores instead of live model
calls. Hosted or model-backed rerankers must implement the same interface
and pass the fixture tests before admission.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, replace


@dataclass
class ScoredCandidate:
    path: str
    score: float
    source: str = ""
    snippet: str = ""
    relations: list[str] = field(default_factory=list)


class Reranker(ABC):
    @abstractmethod
    def rerank(
        self,
        candidates: list[ScoredCandidate],
        query_entities: list[str],
        top_k: int = 5,
    ) -> list[ScoredCandidate]: ...

    @abstractmethod
    def format_context(
        self,
        results: list[ScoredCandidate],
        max_chars: int = 800,
    ) -> str: ...


class LocalReranker(Reranker):
    """Deterministic rule-based reranker for the default retrieval path.

    Scoring factors:
    - Entity overlap bonus (+0.4 per matching entity)
    - Dual-source bonus (+0.3 if found by both vector and graph)
    - Relation count bonus (+0.1 per structural relation)
    """

    def rerank(
        self,
        candidates: list[ScoredCandidate],
        query_entities: list[str],
        top_k: int = 5,
    ) -> list[ScoredCandidate]:
        query_set = set(e.lower() for e in query_entities)

        scored: list[ScoredCandidate] = []
        for c in candidates:
            bonus = 0.0
            path_parts = set(
                c.path.lower().replace("/", " ").replace("\\", " ").replace(".", " ").split()
            )
            overlap = len(query_set & path_parts)
            bonus += overlap * 0.4
            if c.source == "both":
                bonus += 0.3
            bonus += len(c.relations) * 0.1
            scored.append(replace(c, score=c.score + bonus))

        scored.sort(key=lambda r: -r.score)
        return scored[:top_k]

    def format_context(
        self,
        results: list[ScoredCandidate],
        max_chars: int = 800,
    ) -> str:
        if not results:
            return ""
        source_tag = {"vector": "V", "graph": "G", "both": "VG"}
        lines = ["[code context]"]
        total = len(lines[0])
        for r in results:
            tag = source_tag.get(r.source, r.source[:2])
            line = f"[{tag}] {r.path} (score:{r.score:.2f})"
            if r.snippet:
                line += f" | {r.snippet[:60]}"
            if total + len(line) + 1 > max_chars:
                break
            lines.append(line)
            total += len(line) + 1
        return "\n".join(lines)


class FixtureReranker(Reranker):
    """Deterministic fixture reranker for retrieval tests.

    Accepts a pre-built mapping from query entity to candidate results,
    so tests can assert exact retrieval behavior without live indexes.
    """

    def __init__(
        self,
        fixture: dict[str, list[ScoredCandidate]] | None = None,
    ) -> None:
        self._fixture = dict(fixture or {})

    def rerank(
        self,
        candidates: list[ScoredCandidate],
        query_entities: list[str],
        top_k: int = 5,
    ) -> list[ScoredCandidate]:
        results: dict[str, ScoredCandidate] = {}
        for entity in query_entities:
            for entry in self._fixture.get(entity, []):
                if entry.path not in results or entry.score > results[entry.path].score:
                    results[entry.path] = entry
        ranked = sorted(results.values(), key=lambda r: -r.score)
        return ranked[:top_k] if ranked else candidates[:top_k]

    def format_context(
        self,
        results: list[ScoredCandidate],
        max_chars: int = 800,
    ) -> str:
        return LocalReranker().format_context(results, max_chars)
