"""Single authoritative retrieval injection path for LiMa requests."""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class RetrievalPayload:
    query_terms: list[str]
    candidates_searched: int
    reranked_results: list
    text: str


def _normalize_messages(messages: list) -> list[dict]:
    return [
        {"role": m.get("role", ""), "content": m.get("content", "")}
        if isinstance(m, dict)
        else {"role": getattr(m, "role", ""), "content": getattr(m, "content", "")}
        for m in messages
    ]


def run_retrieval(messages: list[dict]) -> RetrievalPayload | None:
    """Extract entities, search graph/vector layers, rerank, and format context."""
    try:
        from context_pipeline.entity_extraction import extract_entities
        from context_pipeline.code_scanner import get_code_graph
        from context_pipeline.graph_retrieval import dual_layer_search, RetrievalResult
        from context_pipeline.production_index import search_production_corpus
        from context_pipeline.reranking import rerank_results, format_for_injection
    except ImportError as exc:
        logger.warning("context_pipeline modules not installed; retrieval injection disabled: %s", exc)
        return None

    try:
        raw_msgs = _normalize_messages(messages)
        entities = extract_entities(raw_msgs)
        terms = entities.to_query_terms()
        if not terms:
            return None

        graph = get_code_graph()
        query = " ".join(terms)
        vector_results = search_production_corpus(query, top_k=8)
        if not vector_results:
            vector_results = [RetrievalResult(path=term, score=0.7, source="vector") for term in terms[:5]]
        merged = dual_layer_search(terms, vector_results, graph, max_results=8)
        reranked = rerank_results(merged, terms, top_k=5)
        if not reranked:
            return None

        text = format_for_injection(reranked)
        if not text:
            return None

        return RetrievalPayload(
            query_terms=terms,
            candidates_searched=len(merged),
            reranked_results=reranked,
            text=text,
        )
    except Exception as exc:
        logger.warning("retrieval pipeline failed: %s", exc, exc_info=True)
        return None


def build_retrieval_text(messages: list[dict]) -> str:
    """Return formatted retrieval text without mutating messages."""
    payload = run_retrieval(messages)
    return payload.text if payload else ""


def _record_trace(payload: RetrievalPayload) -> None:
    from context_pipeline.retrieval_trace import record_trace, RetrievalTrace

    record_trace(
        RetrievalTrace(
            query_entities=payload.query_terms,
            candidates_searched=payload.candidates_searched,
            reranked_results=[
                {"path": r.path, "score": round(r.score, 2), "source": r.source} for r in payload.reranked_results
            ],
            injected_text=payload.text,
            injected_chars=len(payload.text),
            injection_useful=bool(payload.text and len(payload.text) > 50),
        )
    )


def inject_retrieval_context(messages: list[dict]) -> tuple[list[dict], str]:
    """Inject formatted retrieval context into messages and record trace evidence."""
    payload = run_retrieval(messages)
    if not payload:
        return messages, ""

    retrieval_msg = {"role": "system", "content": payload.text}
    result = list(messages)
    if result and result[0].get("role") == "system":
        result.insert(1, retrieval_msg)
    else:
        result.insert(0, retrieval_msg)

    try:
        _record_trace(payload)
    except Exception as exc:
        logger.warning("retrieval trace record failed: %s", exc, exc_info=True)

    return result, payload.text
