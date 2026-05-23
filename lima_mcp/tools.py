"""MCP tool handlers — execute search_repo, search_memory, get_retrieval_trace."""

from __future__ import annotations
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def handle_tool_call(name: str, arguments: dict) -> dict:
    """Dispatch a tool call to the appropriate handler."""
    handlers = {
        "search_repo": _search_repo,
        "search_memory": _search_memory,
        "get_retrieval_trace": _get_retrieval_trace,
    }
    handler = handlers.get(name)
    if not handler:
        return {"error": f"Unknown tool: {name}"}
    try:
        return handler(arguments)
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


def _search_repo(args: dict) -> dict:
    """Search codebase via entity extraction + graph retrieval."""
    query = args.get("query", "")
    max_results = args.get("max_results", 5)
    if not query:
        return {"error": "query is required"}

    try:
        from context_pipeline.entity_extraction import extract_entities
        from context_pipeline.code_scanner import get_code_graph
        from context_pipeline.graph_retrieval import dual_layer_search, RetrievalResult
        from context_pipeline.reranking import rerank_results
    except ImportError as e:
        return {"error": f"Missing module: {e}"}

    entities_input = [{"role": "user", "content": query}]
    extracted = extract_entities(entities_input)
    terms = extracted.to_query_terms()
    if not terms:
        terms = query.split()[:5]

    graph = get_code_graph()
    vector_results = [RetrievalResult(path=t, score=0.7, source="vector") for t in terms[:5]]
    merged = dual_layer_search(terms, vector_results, graph, max_results=max_results + 3)
    reranked = rerank_results(merged, terms, top_k=max_results)

    return {
        "results": [
            {"path": r.path, "score": round(r.score, 2), "source": r.source, "snippet": r.snippet}
            for r in reranked
        ],
        "query_entities": terms,
    }


def _search_memory(args: dict) -> dict:
    """Search typed memory store by type and/or keyword."""
    query = args.get("query", "")
    memory_type = args.get("memory_type", "")
    limit = args.get("limit", 5)

    try:
        from session_memory.store import query_by_type, search_memories_keyword
    except ImportError as e:
        return {"error": f"Missing module: {e}"}

    results = []
    if memory_type:
        entries = query_by_type(memory_type, limit=limit)
        if query:
            entries = [e for e in entries if query.lower() in e.summary.lower()]
        results = [{"id": e.id, "type": memory_type, "summary": e.summary,
                    "timestamp": e.timestamp} for e in entries[:limit]]
    elif query:
        entries = search_memories_keyword("_global", query, limit=limit)
        results = [{"id": e.id, "summary": e.summary,
                    "timestamp": e.timestamp} for e in entries]
    else:
        from session_memory.store import MEMORY_TYPES
        return {"available_types": list(MEMORY_TYPES), "hint": "Provide query or memory_type"}

    return {"results": results, "count": len(results)}


def _get_retrieval_trace(args: dict) -> dict:
    """Return recent retrieval injection traces."""
    limit = args.get("limit", 10)

    try:
        from context_pipeline.retrieval_trace import get_recent_traces
    except ImportError as e:
        return {"error": f"Missing module: {e}"}

    traces = get_recent_traces(limit=limit)
    return {"traces": traces, "count": len(traces)}
