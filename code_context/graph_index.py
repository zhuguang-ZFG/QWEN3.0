"""Graph Index - LiMa-owned interface for code relationship graphs.

Provides a stable, documented interface for structural code retrieval.
The default implementation is an in-memory adjacency-list graph.
External graph engines (LightRAG, GraphRAG) stay behind this boundary
and are not runtime dependencies.

Interface:
    GraphIndex: abstract base with add_relation, get_related, edge_count
    InMemoryGraphIndex: default implementation backed by context_pipeline.CodeGraph
"""

from __future__ import annotations

import logging
import os

_log = logging.getLogger(__name__)
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class GraphRelation:
    """A directional relationship between two code entities."""

    source: str
    target: str
    relation_type: str  # "imports" | "calls" | "extends" | "contains" | "defines"
    weight: float = 1.0


@dataclass
class GraphSearchResult:
    """A single result from graph traversal."""

    entity: str
    score: float
    relations: list[str] = field(default_factory=list)
    source: str = "graph"  # "graph" | "vector" | "both"


class GraphIndex(ABC):
    """Abstract interface for code relationship graphs.

    Implementations:
        InMemoryGraphIndex - default, backed by adjacency list
        (future) LightRAGGraphIndex - LightRAG-backed, gated
        (future) TreeSitterGraphIndex - tree-sitter AST, gated
    """

    @abstractmethod
    def add_relation(self, source: str, target: str, relation_type: str) -> None: ...

    @abstractmethod
    def get_related(self, entity: str, max_depth: int = 2) -> list[GraphRelation]: ...

    @abstractmethod
    def search(self, entities: list[str], max_depth: int = 2, max_results: int = 10) -> list[GraphSearchResult]: ...

    @property
    @abstractmethod
    def edge_count(self) -> int: ...


class InMemoryGraphIndex(GraphIndex):
    """Default in-memory implementation backed by adjacency list.

    Wraps context_pipeline.CodeGraph for backward compatibility while
    providing the formal GraphIndex interface.
    """

    def __init__(self) -> None:
        self._edges: list[GraphRelation] = []
        self._adjacency: dict[str, list[GraphRelation]] = {}

    def add_relation(self, source: str, target: str, relation_type: str) -> None:
        rel = GraphRelation(source=source, target=target, relation_type=relation_type)
        self._edges.append(rel)
        self._adjacency.setdefault(source, []).append(rel)
        # Bidirectional reverse edge
        self._adjacency.setdefault(target, []).append(
            GraphRelation(source=target, target=source, relation_type=f"rev_{relation_type}")
        )

    def get_related(self, entity: str, max_depth: int = 2) -> list[GraphRelation]:
        visited: set[str] = set()
        results: list[GraphRelation] = []
        queue: list[tuple[str, int]] = [(entity, 0)]
        while queue:
            current, depth = queue.pop(0)
            if current in visited or depth > max_depth:
                continue
            visited.add(current)
            for rel in self._adjacency.get(current, []):
                results.append(rel)
                if depth + 1 <= max_depth:
                    queue.append((rel.target, depth + 1))
        return results

    def search(self, entities: list[str], max_depth: int = 2, max_results: int = 10) -> list[GraphSearchResult]:
        seen: dict[str, GraphSearchResult] = {}
        for entity in entities:
            for rel in self.get_related(entity, max_depth=max_depth):
                path = rel.target
                if path in seen:
                    seen[path].score += 0.3
                    seen[path].source = "both"
                    seen[path].relations.append(f"{rel.relation_type}:{rel.source}")
                else:
                    seen[path] = GraphSearchResult(
                        entity=path, score=0.5,
                        relations=[f"{rel.relation_type}:{rel.source}"],
                    )
        ranked = sorted(seen.values(), key=lambda r: -r.score)
        return ranked[:max_results]

    @property
    def edge_count(self) -> int:
        return len(self._edges)


def build_graph_index() -> GraphIndex:
    """Factory: returns the best available GraphIndex implementation.

    Prefers SqliteGraphIndex (persistent) when LIMA_DATA_DIR is set.
    Falls back to InMemoryGraphIndex for zero-config usage.
    """
    data_dir = os.environ.get("LIMA_DATA_DIR", "")
    if data_dir:
        try:
            from code_context.sqlite_graph_store import SqliteGraphIndex

            return SqliteGraphIndex()
        except Exception as exc:
            _log.debug("graph_index: SqliteGraphIndex unavailable", exc_info=True)
    return InMemoryGraphIndex()
