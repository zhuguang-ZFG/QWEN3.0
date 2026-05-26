"""LiMa MCP Tools — expose knowledge and memory as tool endpoints.

Provides four tools for IDE/agent clients:
- search_repo: code graph + keyword search across the codebase
- search_memory: query typed memories by type/keyword
- get_retrieval_trace: view recent retrieval injection decisions
- ask_lima: natural language query combining memory + retrieval
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


TOOL_DEFINITIONS = [
    {
        "name": "search_repo",
        "description": "Search LiMa codebase by entity names, file paths, or keywords. Returns relevant code files with scores.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query (file names, function names, keywords)"},
                "max_results": {"type": "integer", "default": 5},
            },
            "required": ["query"],
        },
    },
    {
        "name": "search_memory",
        "description": "Query LiMa's typed memory store. Filter by memory type and/or keyword.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Keyword to search in memory summaries"},
                "memory_type": {"type": "string", "description": "Filter by type: project_fact, code_fact, ops_event, test_result, routing_lesson, security_lesson, reference_pattern, user_pref"},
                "limit": {"type": "integer", "default": 5},
            },
            "required": [],
        },
    },
    {
        "name": "get_retrieval_trace",
        "description": "View recent retrieval injection traces showing what code context was injected into prompts and why.",
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "default": 10},
            },
        },
    },
    {
        "name": "dev_search_docs",
        "description": "Search public programming documentation and return source-grounded results.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "domains": {"type": "array", "items": {"type": "string"}},
                "max_results": {"type": "integer"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "dev_search_error",
        "description": "Search public sources for a sanitized programming error or stack trace.",
        "parameters": {
            "type": "object",
            "properties": {
                "error_text": {"type": "string"},
                "language": {"type": "string"},
                "framework": {"type": "string"},
                "max_results": {"type": "integer"},
            },
            "required": ["error_text"],
        },
    },
    {
        "name": "dev_read_url",
        "description": "Read a public HTTP(S) URL and return extracted text.",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "max_chars": {"type": "integer"},
            },
            "required": ["url"],
        },
    },
    {
        "name": "dev_fetch_github_file",
        "description": "Fetch a public GitHub file through raw.githubusercontent.com.",
        "parameters": {
            "type": "object",
            "properties": {
                "repo": {"type": "string"},
                "path": {"type": "string"},
                "ref": {"type": "string"},
                "max_chars": {"type": "integer"},
            },
            "required": ["repo", "path"],
        },
    },
    {
        "name": "dev_search_gitee",
        "description": "Search Gitee repositories and issues scoped to the LiMa mirror repo.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "repo": {"type": "string", "description": "owner/name override; defaults to GITEE_SEARCH_REPO"},
                "max_results": {"type": "integer"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "dev_fetch_gitee_file",
        "description": "Fetch a file from a Gitee repository via OpenAPI (mirror read).",
        "parameters": {
            "type": "object",
            "properties": {
                "repo": {"type": "string"},
                "path": {"type": "string"},
                "ref": {"type": "string"},
                "max_chars": {"type": "integer"},
            },
            "required": ["repo", "path"],
        },
    },
    {
        "name": "dev_search_codesearch",
        "description": "Semantic/local code search via codesearch CLI (allowlisted repos, offline).",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "path": {"type": "string", "description": "Optional subpath within allowlist"},
                "max_results": {"type": "integer"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "dev_summarize_sources",
        "description": "Turn source dictionaries into a compact evidence block for LiMa Code.",
        "parameters": {
            "type": "object",
            "properties": {
                "sources": {"type": "array", "items": {"type": "object"}},
                "max_chars": {"type": "integer"},
            },
            "required": ["sources"],
        },
    },
]
