"""Graph-aware Retrieval — LightRAG-inspired dual-layer code search.

Combines two retrieval channels:
1. Vector retrieval: semantic similarity (existing code_context)
2. Graph retrieval: structural relationships (caller/callee/module)

Results are merged and deduplicated before reranking.
"""

from dataclasses import dataclass, field


@dataclass
class CodeRelation:
    """A structural relationship between code entities."""

    source: str
    target: str
    relation_type: str  # "imports", "calls", "extends", "contains"
    weight: float = 1.0


@dataclass
class RetrievalResult:
    """A single retrieval result from dual-layer search."""

    path: str
    score: float
    source: str  # "vector" | "graph" | "both"
    snippet: str = ""
    relations: list[str] = field(default_factory=list)


class CodeGraph:
    """In-memory code relationship graph for structural retrieval."""

    def __init__(self) -> None:
        self._edges: list[CodeRelation] = []
        self._adjacency: dict[str, list[CodeRelation]] = {}

    def add_relation(self, source: str, target: str, relation_type: str) -> None:
        rel = CodeRelation(source=source, target=target, relation_type=relation_type)
        self._edges.append(rel)
        self._adjacency.setdefault(source, []).append(rel)
        self._adjacency.setdefault(target, []).append(
            CodeRelation(source=target, target=source, relation_type=f"rev_{relation_type}")
        )

    def get_related(self, entity: str, max_depth: int = 2) -> list[CodeRelation]:
        """Get all entities related to the given entity within max_depth hops."""
        visited = set()
        results = []
        queue = [(entity, 0)]
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

    @property
    def edge_count(self) -> int:
        return len(self._edges)


def dual_layer_search(
    query_entities: list[str],
    vector_results: list[RetrievalResult],
    graph: CodeGraph,
    max_results: int = 10,
) -> list[RetrievalResult]:
    """Merge vector and graph retrieval results."""
    merged: dict[str, RetrievalResult] = {}

    for vr in vector_results:
        merged[vr.path] = vr

    for entity in query_entities:
        relations = graph.get_related(entity, max_depth=2)
        for rel in relations:
            path = rel.target
            if path in merged:
                merged[path].score += 0.3
                merged[path].source = "both"
                merged[path].relations.append(f"{rel.relation_type}:{rel.source}")
            else:
                merged[path] = RetrievalResult(
                    path=path, score=0.5, source="graph",
                    relations=[f"{rel.relation_type}:{rel.source}"],
                )

    ranked = sorted(merged.values(), key=lambda r: -r.score)
    return ranked[:max_results]
