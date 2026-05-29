"""Graph/vector index protocol with deterministic in-memory fixtures.

Defines the stable interface the retrieval pipeline depends on, so
graph and vector index implementations can be swapped without changing
the hot-path routing code.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class IndexEntry:
    path: str
    content: str = ""
    symbols: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


class GraphIndex(ABC):
    @abstractmethod
    def add_relation(self, source: str, target: str, relation_type: str) -> None: ...

    @abstractmethod
    def get_related(self, entity: str, max_depth: int = 2) -> list: ...

    @property
    @abstractmethod
    def edge_count(self) -> int: ...


class VectorIndex(ABC):
    @abstractmethod
    def add(self, entry: IndexEntry) -> None: ...

    @abstractmethod
    def search(self, query: str, limit: int = 5) -> list[IndexEntry]: ...

    @property
    @abstractmethod
    def entry_count(self) -> int: ...


class InMemoryVectorIndex(VectorIndex):
    """Deterministic in-memory vector index backed by a fixture map.

    Accepts a pre-built mapping from query terms to IndexEntry lists, so
    tests can assert exactly which results are returned for each query.
    """

    def __init__(self, fixture: dict[str, list[IndexEntry]] | None = None) -> None:
        self._fixture = dict(fixture or {})
        self._entries: list[IndexEntry] = []

    def add(self, entry: IndexEntry) -> None:
        self._entries.append(entry)

    def search(self, query: str, limit: int = 5) -> list[IndexEntry]:
        results: list[IndexEntry] = []
        query_lower = query.lower()
        for term, entries in self._fixture.items():
            if term.lower() in query_lower:
                results.extend(entries)
        if not results:
            return self._entries[:limit]
        return results[:limit]

    @property
    def entry_count(self) -> int:
        return len(self._entries)
