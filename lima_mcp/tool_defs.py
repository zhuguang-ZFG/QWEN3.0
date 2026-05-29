"""MCP Tool Definitions — auto-generated from lima_mcp/__init__.py"""
from __future__ import annotations

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
    {
        "name": "read_file",
        "description": "Read a file within allowed workspace roots. Default-off; requires LIMA_FILESYSTEM_ALLOWED_ROOTS.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute or relative path to the file"},
                "offset": {"type": "integer", "description": "Line offset to start reading from (0-based)"},
                "limit": {"type": "integer", "description": "Maximum lines to return"},
                "max_chars": {"type": "integer", "description": "Maximum characters to read"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "list_directory",
        "description": "List directory contents within allowed workspace roots. Default-off; requires LIMA_FILESYSTEM_ALLOWED_ROOTS.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Directory path (defaults to workspace root)"},
            },
            "required": [],
        },
    },
    {
        "name": "glob_search",
        "description": "Glob search for files within allowed workspace roots. Default-off; requires LIMA_FILESYSTEM_ALLOWED_ROOTS.",
        "parameters": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Glob pattern (e.g. '**/*.py', 'src/*.ts')"},
                "path": {"type": "string", "description": "Search root directory"},
            },
            "required": ["pattern"],
        },
    },
    {
        "name": "github_create_issue",
        "description": "Create a GitHub issue. Requires GITHUB_TOKEN in environment.",
        "parameters": {
            "type": "object",
            "properties": {
                "owner": {"type": "string"},
                "repo": {"type": "string"},
                "title": {"type": "string", "description": "Issue title (max 256 chars)"},
                "body": {"type": "string", "description": "Issue body (markdown)"},
                "labels": {"type": "array", "items": {"type": "string"}},
                "assignees": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["owner", "repo", "title"],
        },
    },
    {
        "name": "github_list_issues",
        "description": "List issues in a GitHub repository. Requires GITHUB_TOKEN.",
        "parameters": {
            "type": "object",
            "properties": {
                "owner": {"type": "string"},
                "repo": {"type": "string"},
                "state": {"type": "string", "description": "open, closed, or all"},
                "labels": {"type": "string", "description": "Filter by label name"},
                "per_page": {"type": "integer"},
            },
            "required": ["owner", "repo"],
        },
    },
    {
        "name": "github_get_issue",
        "description": "Get a single GitHub issue by number. Requires GITHUB_TOKEN.",
        "parameters": {
            "type": "object",
            "properties": {
                "owner": {"type": "string"},
                "repo": {"type": "string"},
                "issue_number": {"type": "integer"},
            },
            "required": ["owner", "repo", "issue_number"],
        },
    },
    {
        "name": "github_add_issue_comment",
        "description": "Add a comment to a GitHub issue. Requires GITHUB_TOKEN.",
        "parameters": {
            "type": "object",
            "properties": {
                "owner": {"type": "string"},
                "repo": {"type": "string"},
                "issue_number": {"type": "integer"},
                "body": {"type": "string", "description": "Comment body (markdown)"},
            },
            "required": ["owner", "repo", "issue_number", "body"],
        },
    },
    {
        "name": "github_search_issues",
        "description": "Search GitHub issues (across repos). Requires GITHUB_TOKEN.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "GitHub issue search query"},
                "per_page": {"type": "integer"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "github_search_code",
        "description": "Search GitHub code across public repositories. Requires GITHUB_TOKEN.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "GitHub code search query"},
                "language": {"type": "string", "description": "Filter by language (e.g. python, typescript)"},
                "per_page": {"type": "integer"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "github_get_file_contents",
        "description": "Read file contents from a GitHub repository. Requires GITHUB_TOKEN.",
        "parameters": {
            "type": "object",
            "properties": {
                "owner": {"type": "string"},
                "repo": {"type": "string"},
                "path": {"type": "string", "description": "File path within the repo"},
                "ref": {"type": "string", "description": "Branch or tag (default: main)"},
            },
            "required": ["owner", "repo", "path"],
        },
    },
    {
        "name": "github_create_pull_request",
        "description": "Create a GitHub pull request. Requires GITHUB_TOKEN with repo scope.",
        "parameters": {
            "type": "object",
            "properties": {
                "owner": {"type": "string"},
                "repo": {"type": "string"},
                "title": {"type": "string", "description": "PR title"},
                "head": {"type": "string", "description": "Source branch name"},
                "base": {"type": "string", "description": "Target branch (default: main)"},
                "body": {"type": "string", "description": "PR description (markdown)"},
            },
            "required": ["owner", "repo", "title", "head"],
        },
    },
    {
        "name": "github_create_branch",
        "description": "Create a new branch in a GitHub repository. Requires GITHUB_TOKEN.",
        "parameters": {
            "type": "object",
            "properties": {
                "owner": {"type": "string"},
                "repo": {"type": "string"},
                "branch": {"type": "string", "description": "New branch name"},
                "from": {"type": "string", "description": "Source branch (default: main)"},
            },
            "required": ["owner", "repo", "branch"],
        },
    },
    {
        "name": "github_list_workflow_runs",
        "description": "List recent GitHub Actions workflow runs. Requires GITHUB_TOKEN.",
        "parameters": {
            "type": "object",
            "properties": {
                "owner": {"type": "string"}, "repo": {"type": "string"},
                "branch": {"type": "string"}, "status": {"type": "string"},
                "per_page": {"type": "integer"},
            }, "required": ["owner", "repo"],
        },
    },
    {
        "name": "github_get_workflow_run",
        "description": "Get a specific workflow run by ID. Requires GITHUB_TOKEN.",
        "parameters": {
            "type": "object",
            "properties": {
                "owner": {"type": "string"}, "repo": {"type": "string"},
                "run_id": {"type": "integer"},
            }, "required": ["owner", "repo", "run_id"],
        },
    },
    {
        "name": "github_list_workflow_jobs",
        "description": "List jobs for a workflow run with step-level details. Requires GITHUB_TOKEN.",
        "parameters": {
            "type": "object",
            "properties": {
                "owner": {"type": "string"}, "repo": {"type": "string"},
                "run_id": {"type": "integer"}, "per_page": {"type": "integer"},
            }, "required": ["owner", "repo", "run_id"],
        },
    },
    {
        "name": "github_list_workflow_artifacts",
        "description": "List CI artifacts (coverage, SBOM, etc). Requires GITHUB_TOKEN.",
        "parameters": {
            "type": "object",
            "properties": {
                "owner": {"type": "string"}, "repo": {"type": "string"},
                "per_page": {"type": "integer"},
            }, "required": ["owner", "repo"],
        },
    },
    {
        "name": "github_get_combined_status",
        "description": "Get combined commit status (CI checks summary) for a ref. Requires GITHUB_TOKEN.",
        "parameters": {
            "type": "object",
            "properties": {
                "owner": {"type": "string"}, "repo": {"type": "string"},
                "ref": {"type": "string", "description": "Branch name or commit SHA"},
            }, "required": ["owner", "repo", "ref"],
        },
    },
    {
        "name": "github_list_check_runs",
        "description": "List check runs for a commit ref. Requires GITHUB_TOKEN.",
        "parameters": {
            "type": "object",
            "properties": {
                "owner": {"type": "string"}, "repo": {"type": "string"},
                "ref": {"type": "string"}, "per_page": {"type": "integer"},
            }, "required": ["owner", "repo", "ref"],
        },
    },
    {
        "name": "memory_stats",
        "description": "Return memory store statistics: total entries, embedding coverage, per-type counts, session count.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "outcome_ledger_stats",
        "description": "Return Outcome Ledger stats: total events by source, unlearned/rejected/applied counts.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
]
