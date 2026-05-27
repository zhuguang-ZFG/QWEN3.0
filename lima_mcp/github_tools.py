"""GitHub REST API tools — facade for backward compatibility.

Split into lima_mcp/github/ package (issues, code, pull_requests, workflows).
This module re-exports all public names for existing imports.
"""

from lima_mcp.github import (  # noqa: F401
    _token, _is_configured, _api_request, GITHUB_API_BASE, _TIMEOUT,
    create_issue, list_issues, get_issue, add_issue_comment, search_issues,
    search_code, get_file_contents, create_branch,
    list_workflow_runs, get_workflow_run, list_workflow_jobs,
    list_workflow_artifacts, get_combined_status, list_check_runs,
    create_pull_request, get_pull_request, get_pull_request_files,
    get_pull_request_diff, create_review,
)
