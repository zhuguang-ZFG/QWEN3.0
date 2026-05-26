"""MCP tool handlers — execute search_repo, search_memory, get_retrieval_trace."""

from __future__ import annotations
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_log = logging.getLogger(__name__)


def handle_tool_call(name: str, arguments: dict) -> dict:
    """Dispatch a tool call to the appropriate handler."""
    handlers = {
        "search_repo": _search_repo,
        "search_memory": _search_memory,
        "get_retrieval_trace": _get_retrieval_trace,
        "dev_search_docs": _dev_search_docs,
        "dev_search_error": _dev_search_error,
        "dev_read_url": _dev_read_url,
        "dev_fetch_github_file": _dev_fetch_github_file,
        "dev_search_gitee": _dev_search_gitee,
        "dev_fetch_gitee_file": _dev_fetch_gitee_file,
        "dev_search_codesearch": _dev_search_codesearch,
        "dev_summarize_sources": _dev_summarize_sources,
    }
    handler = handlers.get(name)
    if not handler:
        return {"error": f"Unknown tool: {name}"}
    try:
        return handler(arguments)
    except Exception as e:
        _log.warning("MCP tool %s failed: %s", name, type(e).__name__, exc_info=True)
        return {"ok": False, "error": "tool_failed", "error_code": "tool_failed", "detail": str(e)[:200]}


def _bounded_int(value, *, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, parsed))


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


def _dev_adapter():
    from search_gateway.dev_adapter import get_dev_search_adapter

    return get_dev_search_adapter()


def _dev_search_docs(args: dict) -> dict:
    from search_gateway.dev_tools import search_docs

    return search_docs(
        args.get("query", ""),
        args.get("domains") or None,
        adapter=_dev_adapter(),
        max_results=_bounded_int(args.get("max_results"), default=5, minimum=1, maximum=10),
    )


def _dev_search_error(args: dict) -> dict:
    from search_gateway.dev_tools import search_error

    return search_error(
        args.get("error_text", ""),
        language=args.get("language", ""),
        framework=args.get("framework", ""),
        adapter=_dev_adapter(),
        max_results=_bounded_int(args.get("max_results"), default=5, minimum=1, maximum=10),
    )


def _dev_read_url(args: dict) -> dict:
    from search_gateway.dev_tools import read_url

    return read_url(
        args.get("url", ""),
        adapter=_dev_adapter(),
        max_chars=_bounded_int(args.get("max_chars"), default=6000, minimum=1000, maximum=12000),
    )


def _dev_fetch_github_file(args: dict) -> dict:
    from search_gateway.dev_tools import fetch_github_file

    return fetch_github_file(
        args.get("repo", ""),
        args.get("path", ""),
        args.get("ref", "main"),
        adapter=_dev_adapter(),
        max_chars=_bounded_int(args.get("max_chars"), default=8000, minimum=1000, maximum=12000),
    )


def _dev_search_gitee(args: dict) -> dict:
    from search_gateway.dev_tools import search_gitee

    return search_gitee(
        args.get("query", ""),
        repo=args.get("repo") or None,
        max_results=_bounded_int(args.get("max_results"), default=5, minimum=1, maximum=10),
    )


def _dev_fetch_gitee_file(args: dict) -> dict:
    from search_gateway.dev_tools import fetch_gitee_file

    return fetch_gitee_file(
        args.get("repo", ""),
        args.get("path", ""),
        args.get("ref", "master"),
        max_chars=_bounded_int(args.get("max_chars"), default=8000, minimum=1000, maximum=12000),
    )


def _dev_search_codesearch(args: dict) -> dict:
    from search_gateway.dev_tools import search_codesearch

    return search_codesearch(
        args.get("query", ""),
        max_results=_bounded_int(args.get("max_results"), default=5, minimum=1, maximum=15),
        path_hint=args.get("path") or None,
    )


def _dev_summarize_sources(args: dict) -> dict:
    from search_gateway.dev_tools import summarize_sources

    return summarize_sources(
        args.get("sources", []),
        max_chars=_bounded_int(args.get("max_chars"), default=3000, minimum=1000, maximum=12000),
    )
