"""MCP tool handlers — execute search_repo, search_memory, get_retrieval_trace."""

from __future__ import annotations
import logging
import os
import sys
from pathlib import Path

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
        "read_file": _read_file,
        "list_directory": _list_directory,
        "glob_search": _glob_search,
        "github_create_issue": _github_create_issue,
        "github_list_issues": _github_list_issues,
        "github_get_issue": _github_get_issue,
        "github_add_issue_comment": _github_add_issue_comment,
        "github_search_issues": _github_search_issues,
        "github_search_code": _github_search_code,
        "github_get_file_contents": _github_get_file_contents,
        "github_create_pull_request": _github_create_pull_request,
        "github_create_branch": _github_create_branch,
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


# ── Filesystem tools (default-off, path-allowlist gated) ──


def _read_file(args: dict) -> dict:
    """Read a file within allowed workspace roots."""
    path = args.get("path", "")
    max_chars = _bounded_int(args.get("max_chars"), default=8000, minimum=1000, maximum=20000)
    offset = _bounded_int(args.get("offset"), default=0, minimum=0, maximum=1000000)
    limit = _bounded_int(args.get("limit"), default=200, minimum=1, maximum=500)

    from lima_mcp.fs_allowlist import validate_path

    ok, result = validate_path(path)
    if not ok:
        return {"ok": False, "error": str(result)}
    assert isinstance(result, Path)

    try:
        text = result.read_text(encoding="utf-8", errors="replace")
    except (OSError, UnicodeDecodeError) as exc:
        return {"ok": False, "error": f"cannot read file: {exc}"}

    lines = text.split("\n")
    total_lines = len(lines)
    end = min(offset + limit, total_lines)
    selected = lines[offset:end]

    return {
        "ok": True,
        "path": str(result),
        "content": "\n".join(selected),
        "total_lines": total_lines,
        "offset": offset,
        "returned_lines": len(selected),
        "truncated": end < total_lines or len(text) > max_chars,
    }


def _list_directory(args: dict) -> dict:
    """List directory contents within allowed workspace roots."""
    path = args.get("path", ".")

    from lima_mcp.fs_allowlist import validate_path

    ok, result = validate_path(path, must_exist=True)
    if not ok:
        return {"ok": False, "error": str(result)}
    assert isinstance(result, Path)

    try:
        entries = []
        for child in sorted(result.iterdir()):
            try:
                is_dir = child.is_dir()
            except OSError:
                is_dir = False
            entries.append({
                "name": child.name,
                "type": "dir" if is_dir else "file",
            })
    except (OSError, PermissionError) as exc:
        return {"ok": False, "error": f"cannot list directory: {exc}"}

    return {
        "ok": True,
        "path": str(result),
        "entries": entries,
        "count": len(entries),
    }


def _glob_search(args: dict) -> dict:
    """Glob search for files within allowed workspace roots."""
    pattern = args.get("pattern", "*")
    path = args.get("path", ".")

    from lima_mcp.fs_allowlist import validate_path

    ok, result = validate_path(path, must_exist=True)
    if not ok:
        return {"ok": False, "error": str(result)}
    assert isinstance(result, Path)

    try:
        matches = sorted(result.glob(pattern))
    except (OSError, ValueError) as exc:
        return {"ok": False, "error": f"invalid glob pattern: {exc}"}

    return {
        "ok": True,
        "path": str(result),
        "pattern": pattern,
        "matches": [str(m.relative_to(result)) for m in matches[:200]],
        "count": min(len(matches), 200),
        "truncated": len(matches) > 200,
    }


# ── GitHub API tools (default-off, GITHUB_TOKEN gated) ──


def _github_create_issue(args: dict) -> dict:
    from lima_mcp.github_tools import create_issue

    return create_issue(
        owner=args.get("owner", ""),
        repo=args.get("repo", ""),
        title=args.get("title", ""),
        body=args.get("body", ""),
        labels=args.get("labels"),
        assignees=args.get("assignees"),
    )


def _github_list_issues(args: dict) -> dict:
    from lima_mcp.github_tools import list_issues

    return list_issues(
        owner=args.get("owner", ""),
        repo=args.get("repo", ""),
        state=args.get("state", "open"),
        labels=args.get("labels", ""),
        per_page=_bounded_int(args.get("per_page"), default=10, minimum=1, maximum=30),
    )


def _github_get_issue(args: dict) -> dict:
    from lima_mcp.github_tools import get_issue

    return get_issue(
        owner=args.get("owner", ""),
        repo=args.get("repo", ""),
        issue_number=_bounded_int(args.get("issue_number"), default=0, minimum=1, maximum=999999),
    )


def _github_add_issue_comment(args: dict) -> dict:
    from lima_mcp.github_tools import add_issue_comment

    return add_issue_comment(
        owner=args.get("owner", ""),
        repo=args.get("repo", ""),
        issue_number=_bounded_int(args.get("issue_number"), default=0, minimum=1, maximum=999999),
        body=args.get("body", ""),
    )


def _github_search_issues(args: dict) -> dict:
    from lima_mcp.github_tools import search_issues

    return search_issues(
        query=args.get("query", ""),
        per_page=_bounded_int(args.get("per_page"), default=10, minimum=1, maximum=20),
    )


def _github_search_code(args: dict) -> dict:
    from lima_mcp.github_tools import search_code

    return search_code(
        query=args.get("query", ""),
        per_page=_bounded_int(args.get("per_page"), default=10, minimum=1, maximum=20),
        language=args.get("language", ""),
    )


def _github_get_file_contents(args: dict) -> dict:
    from lima_mcp.github_tools import get_file_contents

    return get_file_contents(
        owner=args.get("owner", ""),
        repo=args.get("repo", ""),
        path=args.get("path", ""),
        ref=args.get("ref", "main"),
    )


def _github_create_pull_request(args: dict) -> dict:
    from lima_mcp.github_tools import create_pull_request

    return create_pull_request(
        owner=args.get("owner", ""),
        repo=args.get("repo", ""),
        title=args.get("title", ""),
        head=args.get("head", ""),
        base=args.get("base", "main"),
        body=args.get("body", ""),
    )


def _github_create_branch(args: dict) -> dict:
    from lima_mcp.github_tools import create_branch

    return create_branch(
        owner=args.get("owner", ""),
        repo=args.get("repo", ""),
        branch=args.get("branch", ""),
        from_ref=args.get("from", "main"),
    )
