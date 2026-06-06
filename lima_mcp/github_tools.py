"""GitHub REST API tools — facade for backward compatibility.

Split into lima_mcp/github/ package (issues, code, pull_requests, workflows).
This module re-exports all public names for existing imports.
"""

from lima_mcp.github import (
    _TIMEOUT,
    GITHUB_API_BASE,
    _api_request,
    _is_configured,
    _token,
    add_issue_comment,
    create_branch,
    create_issue,
    create_pull_request,
    create_review,
    get_combined_status,
    get_file_contents,
    get_issue,
    get_pull_request,
    get_pull_request_diff,
    get_pull_request_files,
    get_workflow_run,
    list_check_runs,
    list_issues,
    list_workflow_artifacts,
    list_workflow_jobs,
    list_workflow_runs,
    search_code,
    search_issues,
)
