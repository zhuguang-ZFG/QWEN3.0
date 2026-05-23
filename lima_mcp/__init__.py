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
]
