"""MCP Access Plane connector governance and least-privilege enablement.

Every MCP connector must declare: owner, allowlist, credential boundary,
timeout, audit event, and failure mode before it can be enabled. Tools are
default-off; the access plane enforces read-only-safe defaults.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ConnectorStatus(str, Enum):
    OFF = "off"
    READ_ONLY = "read_only"
    FULL = "full"


VALID_FAILURE_MODES = frozenset({"deny", "warn", "allow_degraded"})


@dataclass
class ConnectorPolicy:
    name: str
    description: str = ""
    status: ConnectorStatus = ConnectorStatus.OFF
    owner: str = ""
    allowlist: list[str] = field(default_factory=list)
    credential_env: str = ""
    timeout_sec: float = 30.0
    failure_mode: str = "deny"  # deny | warn | allow_degraded
    audit_events: bool = True

    def is_enabled(self) -> bool:
        return self.status != ConnectorStatus.OFF

    def is_read_only(self) -> bool:
        return self.status == ConnectorStatus.READ_ONLY


FOUNDATION_CONNECTORS: dict[str, ConnectorPolicy] = {
    "filesystem_read": ConnectorPolicy(
        name="filesystem_read",
        description="Read files and directories within workspace boundaries.",
        status=ConnectorStatus.READ_ONLY,
        owner="lima-server",
        allowlist=["read_file", "list_directory", "glob_search"],
        timeout_sec=10.0,
        failure_mode="deny",
    ),
    "git_read": ConnectorPolicy(
        name="git_read",
        description="Read git history, status, and diffs.",
        status=ConnectorStatus.READ_ONLY,
        owner="lima-server",
        allowlist=["git_log", "git_diff", "git_status", "git_show"],
        timeout_sec=15.0,
        failure_mode="deny",
    ),
    "docs_lookup": ConnectorPolicy(
        name="docs_lookup",
        description="Search and read public documentation.",
        status=ConnectorStatus.READ_ONLY,
        owner="lima-server",
        allowlist=["search_docs", "read_docs", "resolve_library"],
        timeout_sec=20.0,
        failure_mode="warn",
    ),
    "memory_query": ConnectorPolicy(
        name="memory_query",
        description="Read typed session memories for context recall.",
        status=ConnectorStatus.READ_ONLY,
        owner="lima-server",
        allowlist=["query_memory", "list_memory_types", "get_recall_context"],
        credential_env="",
        timeout_sec=10.0,
        failure_mode="warn",
    ),
}

GATED_CONNECTORS: dict[str, ConnectorPolicy] = {
    "filesystem_write": ConnectorPolicy(
        name="filesystem_write",
        description="Write and modify files on disk.",
        status=ConnectorStatus.OFF,
        owner="",
        allowlist=[],
        credential_env="",
        timeout_sec=15.0,
        failure_mode="deny",
    ),
    "git_write": ConnectorPolicy(
        name="git_write",
        description="Commit, push, and manage branches.",
        status=ConnectorStatus.OFF,
        owner="",
        allowlist=[],
        credential_env="",
        timeout_sec=30.0,
        failure_mode="deny",
    ),
    "database_read": ConnectorPolicy(
        name="database_read",
        description="Read from connected databases.",
        status=ConnectorStatus.OFF,
        owner="",
        allowlist=[],
        credential_env="LIMA_MCP_DB_URL",
        timeout_sec=30.0,
        failure_mode="deny",
    ),
    "cloud_api": ConnectorPolicy(
        name="cloud_api",
        description="Call cloud provider APIs.",
        status=ConnectorStatus.OFF,
        owner="",
        allowlist=[],
        credential_env="LIMA_MCP_CLOUD_CREDENTIALS",
        timeout_sec=60.0,
        failure_mode="deny",
    ),
}


def connector_catalog() -> dict[str, ConnectorPolicy]:
    return {**FOUNDATION_CONNECTORS, **GATED_CONNECTORS}


def enabled_connectors() -> list[ConnectorPolicy]:
    return [c for c in connector_catalog().values() if c.is_enabled()]


def validate_connector_policy(name: str) -> ConnectorPolicy | None:
    catalog = connector_catalog()
    policy = catalog.get(name)
    if policy is None:
        return None
    if not policy.owner:
        return None  # unowned connector is not valid
    if policy.is_enabled() and not policy.allowlist:
        return None  # enabled connector without allowlist is broken
    if policy.is_enabled() and not policy.audit_events:
        return None
    if policy.failure_mode not in VALID_FAILURE_MODES:
        return None
    if policy.timeout_sec <= 0:
        return None
    return policy
