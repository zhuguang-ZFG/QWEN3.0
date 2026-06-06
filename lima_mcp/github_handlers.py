"""GitHub MCP tool handlers — issue/PR/code/CI evidence."""
from __future__ import annotations

from lima_mcp.tools import _bounded_int  # shared utility

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


# ── CI Evidence handlers ──


def _github_list_workflow_runs(args: dict) -> dict:
    from lima_mcp.github_tools import list_workflow_runs
    return list_workflow_runs(
        owner=args.get("owner", ""), repo=args.get("repo", ""),
        branch=args.get("branch", ""),
        per_page=_bounded_int(args.get("per_page"), default=10, minimum=1, maximum=20),
        status=args.get("status", ""),
    )


def _github_get_workflow_run(args: dict) -> dict:
    from lima_mcp.github_tools import get_workflow_run
    return get_workflow_run(
        owner=args.get("owner", ""), repo=args.get("repo", ""),
        run_id=_bounded_int(args.get("run_id"), default=0, minimum=1, maximum=999999999),
    )


def _github_list_workflow_jobs(args: dict) -> dict:
    from lima_mcp.github_tools import list_workflow_jobs
    return list_workflow_jobs(
        owner=args.get("owner", ""), repo=args.get("repo", ""),
        run_id=_bounded_int(args.get("run_id"), default=0, minimum=1, maximum=999999999),
        per_page=_bounded_int(args.get("per_page"), default=20, minimum=1, maximum=30),
    )


def _github_list_workflow_artifacts(args: dict) -> dict:
    from lima_mcp.github_tools import list_workflow_artifacts
    return list_workflow_artifacts(
        owner=args.get("owner", ""), repo=args.get("repo", ""),
        per_page=_bounded_int(args.get("per_page"), default=10, minimum=1, maximum=20),
    )


def _github_get_combined_status(args: dict) -> dict:
    from lima_mcp.github_tools import get_combined_status
    return get_combined_status(
        owner=args.get("owner", ""), repo=args.get("repo", ""),
        ref=args.get("ref", ""),
    )


def _github_list_check_runs(args: dict) -> dict:
    from lima_mcp.github_tools import list_check_runs
    return list_check_runs(
        owner=args.get("owner", ""), repo=args.get("repo", ""),
        ref=args.get("ref", ""),
        per_page=_bounded_int(args.get("per_page"), default=10, minimum=1, maximum=20),
    )


def _memory_stats(args: dict) -> dict:
    """Return memory store statistics."""
    from session_memory.store_db import memory_stats
    return memory_stats()


def _outcome_ledger_stats(args: dict) -> dict:
    """Return Outcome Ledger statistics."""
    from session_memory.outcome_ledger import stats as ledger_stats
    return ledger_stats()


# ── PR Review handlers ──


def _github_get_pull_request(args: dict) -> dict:
    from lima_mcp.github_tools import get_pull_request
    return get_pull_request(
        owner=args.get("owner", ""), repo=args.get("repo", ""),
        pr_number=_bounded_int(args.get("pr_number"), default=0, minimum=1, maximum=999999),
    )


def _github_get_pr_files(args: dict) -> dict:
    from lima_mcp.github_tools import get_pull_request_files
    return get_pull_request_files(
        owner=args.get("owner", ""), repo=args.get("repo", ""),
        pr_number=_bounded_int(args.get("pr_number"), default=0, minimum=1, maximum=999999),
        per_page=_bounded_int(args.get("per_page"), default=20, minimum=1, maximum=50),
    )


def _github_get_pr_diff(args: dict) -> dict:
    from lima_mcp.github_tools import get_pull_request_diff
    return get_pull_request_diff(
        owner=args.get("owner", ""), repo=args.get("repo", ""),
        pr_number=_bounded_int(args.get("pr_number"), default=0, minimum=1, maximum=999999),
    )


def _github_create_review(args: dict) -> dict:
    from lima_mcp.github_tools import create_review
    return create_review(
        owner=args.get("owner", ""), repo=args.get("repo", ""),
        pr_number=_bounded_int(args.get("pr_number"), default=0, minimum=1, maximum=999999),
        body=args.get("body", ""), event=args.get("event", "COMMENT"),
    )
