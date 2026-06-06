"""Reranking — LightRAG-inspired precision refinement after retrieval.

After dual-layer retrieval returns candidates, rerank for precision:
- Score by entity overlap (query entities vs result entities)
- Score by recency (recently modified files rank higher)
- Score by structural proximity (closer in graph = higher)
- Return top-K for context injection
"""

from dataclasses import dataclass

from context_pipeline.graph_retrieval import RetrievalResult


def rerank_results(
    results: list[RetrievalResult],
    query_entities: list[str],
    top_k: int = 5,
) -> list[RetrievalResult]:
    """Rerank retrieval results for precision.

    Scoring factors:
    - Base score from retrieval (vector/graph similarity)
    - Entity overlap bonus (+0.2 per matching entity)
    - Dual-source bonus (+0.3 if found by both vector and graph)
    - Relation count bonus (+0.1 per structural relation)
    """
    query_set = set(e.lower() for e in query_entities)

    for result in results:
        bonus = 0.0

        # Entity overlap (strong signal — user explicitly mentioned this file)
        path_parts = set(result.path.lower().replace("/", " ").replace("\\", " ").split())
        overlap = len(query_set & path_parts)
        bonus += overlap * 0.4

        # Dual-source bonus
        if result.source == "both":
            bonus += 0.3

        # Relation count bonus
        bonus += len(result.relations) * 0.1

        result.score += bonus

    results.sort(key=lambda r: -r.score)
    return results[:top_k]


def format_for_injection(results: list[RetrievalResult], max_chars: int = 800) -> str:
    """Format reranked results as compact context for prompt injection."""
    if not results:
        return ""

    lines = ["[代码上下文]"]
    total = len(lines[0])
    for r in results:
        source_tag = {"vector": "V", "graph": "G", "both": "VG"}[r.source]
        line = f"[{source_tag}] {r.path} (score:{r.score:.2f})"
        if r.snippet:
            line += f" | {r.snippet[:60]}"
        if total + len(line) + 1 > max_chars:
            break
        lines.append(line)
        total += len(line) + 1

    return "\n".join(lines)
