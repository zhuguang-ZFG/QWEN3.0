import pytest

from tool_gateway.auth import SecretStore
from tool_gateway.executor import ToolExecutor
from tool_gateway.registry import (
    ToolDefinition, ToolRegistry, AuthorityClass, RiskClass,
    DANGEROUS_AUTHORITIES, requires_approval, build_default_registry,
)
from tool_gateway.audit import (
    audit_event, get_recent_events, query_events, count_events, reset_audit,
)
from tool_gateway.governance import (
    register_worker, heartbeat, get_worker, list_workers,
    quarantine_worker, mark_offline_stale, reset_for_tests,
)


@pytest.fixture(autouse=True)
def isolated_gateway_storage(tmp_path, monkeypatch):
    monkeypatch.setenv("LIMA_AUDIT_DB", str(tmp_path / "tool_audit.db"))
    monkeypatch.setenv("LIMA_WORKER_DB", str(tmp_path / "worker_registry.db"))
    reset_audit()
    reset_for_tests()
    yield
    reset_audit()
    reset_for_tests()


def test_tool_registry_searches_by_intent():
    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="git_status",
            description="Show local git status",
            tags=("git", "repo", "status"),
            requires_secret=False,
        )
    )

    matches = registry.search("repo status")

    assert [tool.name for tool in matches] == ["git_status"]


def test_secret_store_returns_presence_without_revealing_value(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "secret-value")
    store = SecretStore()

    assert store.has("GITHUB_TOKEN") is True
    assert store.describe("GITHUB_TOKEN") == {"name": "GITHUB_TOKEN", "configured": True}


def test_executor_rejects_unregistered_tool():
    executor = ToolExecutor(ToolRegistry())

    result = executor.execute("missing", {})

    assert result["ok"] is False
    assert result["error"] == "tool_not_registered"


def test_default_registry_includes_lima_code_dev_search_tools():
    registry = build_default_registry()

    matches = registry.search("programming docs error url gitee mirror")
    names = {tool.name for tool in matches}

    assert "dev_search_docs" in names
    assert "dev_search_error" in names
    assert "dev_read_url" in names
    assert "dev_search_gitee" in names


# ── M7: Authority class ──────────────────────────────────────────────────────

def test_authority_enum_values():
    assert AuthorityClass.READ_ONLY == "read_only"
    assert AuthorityClass.DEPLOYMENT == "deployment"


def test_dangerous_authorities():
    assert AuthorityClass.DEPLOYMENT in DANGEROUS_AUTHORITIES
    assert AuthorityClass.READ_ONLY not in DANGEROUS_AUTHORITIES


def test_requires_approval():
    assert requires_approval(AuthorityClass.DEPLOYMENT) is True
    assert requires_approval(AuthorityClass.READ_ONLY) is False


def test_tool_definition_authority_defaults():
    t = ToolDefinition(name="test", description="a test tool")
    assert t.authority == AuthorityClass.READ_ONLY
    assert t.requires_approval is False


def test_tool_definition_dangerous_authority_auto_requires_approval():
    t = ToolDefinition(
        name="deploy", description="deploy", authority=AuthorityClass.DEPLOYMENT,
        risk_class=RiskClass.HIGH, rollback_owner="admin",
    )
    assert t.requires_approval is True


# ── M7: Executor authority enforcement ──────────────────────────────────────

def test_executor_enforces_allowed_tools():
    r = build_default_registry()
    exc = ToolExecutor(r)
    exc.set_allowed_tools({"dev_search_docs"})
    result = exc.execute("dev_read_url", {})
    assert result["ok"] is False
    assert result["error"] == "tool_not_allowed"


def test_executor_rejects_approval_required():
    r = ToolRegistry()
    r.register(ToolDefinition(
        name="dangerous_deploy", description="deploy",
        authority=AuthorityClass.DEPLOYMENT,
        risk_class=RiskClass.HIGH, rollback_owner="admin",
        requires_approval=True,
    ))
    exc = ToolExecutor(r)
    exc.register_handler("dangerous_deploy", kind="python", target=lambda a: "done")
    result = exc.execute("dangerous_deploy", {})
    assert result["ok"] is False
    assert "requires_approval" in result["error"]


def test_executor_rejects_dangerous_authority_without_explicit_flag():
    r = ToolRegistry()
    r.register(ToolDefinition(
        name="shell_tool", description="shell",
        authority=AuthorityClass.SHELL_EXEC,
        risk_class=RiskClass.HIGH, rollback_owner="admin",
    ))
    exc = ToolExecutor(r)
    exc.register_handler("shell_tool", kind="python", target=lambda a: "done")
    result = exc.execute("shell_tool", {})
    assert result["ok"] is False
    assert result["error"] == "tool_requires_approval"


def test_dangerous_tool_fails_closed_without_risk_class():
    with pytest.raises(ValueError, match="risk_class"):
        ToolDefinition(
            name="bad_tool", description="no risk class",
            authority=AuthorityClass.DEPLOYMENT,
        )


def test_dangerous_tool_fails_closed_without_rollback_owner():
    with pytest.raises(ValueError, match="rollback_owner"):
        ToolDefinition(
            name="bad_tool", description="no owner",
            authority=AuthorityClass.SHELL_EXEC,
            risk_class=RiskClass.HIGH,
        )


def test_executor_rejects_too_many_args():
    r = ToolRegistry()
    r.register(ToolDefinition(name="small", description="small", max_args=1))
    exc = ToolExecutor(r)
    exc.register_handler("small", kind="python", target=lambda a: "done")
    result = exc.execute("small", {"a": 1, "b": 2})
    assert result["ok"] is False
    assert result["error"] == "too_many_args"


def test_executor_allows_readonly_python():
    r = ToolRegistry()
    r.register(ToolDefinition(name="safe_search", description="search"))
    exc = ToolExecutor(r)
    exc.register_handler("safe_search", kind="python", target=lambda a: "found")
    result = exc.execute("safe_search", {})
    assert result["ok"] is True


# ── M7: Audit persistence ────────────────────────────────────────────────────

def test_audit_event_records_and_retrieves():
    audit_event("execute_start", tool="test_tool")
    events = get_recent_events(10)
    assert len(events) >= 1


def test_count_events_by_type():
    reset_audit()
    for _ in range(3):
        audit_event("execute_rejected", tool="bad", reason="not_allowed")
    assert count_events(event_type="execute_rejected") == 3


def test_count_events_by_tool():
    reset_audit()
    audit_event("execute_start", tool="tool_a")
    audit_event("execute_start", tool="tool_b")
    assert count_events(tool="tool_a") == 1


def test_audit_event_redacts_secret_values_from_memory_and_sqlite():
    audit_event(
        "execute_start",
        tool="secret_tool",
        api_key="sk-abcdefghijklmnopqrstuvwxyz123456",
        details={"authorization": "Bearer abcdefghijklmnopqrstuvwxyz123456"},
    )

    memory_text = str(get_recent_events(1))
    sqlite_text = str(query_events(tool="secret_tool", limit=1))
    assert "sk-abcdefghijklmnopqrstuvwxyz123456" not in memory_text
    assert "Bearer abcdefghijklmnopqrstuvwxyz123456" not in memory_text
    assert "sk-abcdefghijklmnopqrstuvwxyz123456" not in sqlite_text
    assert "Bearer abcdefghijklmnopqrstuvwxyz123456" not in sqlite_text
    assert "[REDACTED]" in memory_text
    assert "[REDACTED]" in sqlite_text


# ── M7: Worker governance ────────────────────────────────────────────────────

def test_register_and_get_worker():
    register_worker("worker-001", version="1.0", capacity=2)
    w = get_worker("worker-001")
    assert w is not None
    assert w.worker_id == "worker-001"
    assert w.capacity == 2


def test_heartbeat_updates_status():
    register_worker("worker-002")
    assert heartbeat("worker-002", status="busy", active_tasks=["t1"]) is True
    w = get_worker("worker-002")
    assert w.status == "busy"
    assert "t1" in w.active_tasks


def test_heartbeat_unknown_worker():
    assert heartbeat("nonexistent", status="idle") is False


def test_list_workers_by_status():
    register_worker("w1")
    register_worker("w2")
    heartbeat("w1", status="busy")
    busy = list_workers(status="busy")
    assert len(busy) == 1
    assert busy[0].worker_id == "w1"


def test_quarantine_worker():
    register_worker("w3")
    assert quarantine_worker("w3") is True
    w = get_worker("w3")
    assert w.status == "quarantined"


def test_mark_offline_stale():
    import time
    register_worker("stale_worker")
    from tool_gateway.governance import _get_conn
    conn = _get_conn()
    conn.execute("UPDATE workers SET last_heartbeat = ? WHERE worker_id = ?",
                 (time.time() - 1000, "stale_worker"))
    conn.commit()
    conn.close()
    count = mark_offline_stale(timeout_sec=300)
    assert count >= 1
    w = get_worker("stale_worker")
    assert w.status == "offline"


def test_list_workers_all():
    register_worker("w_a")
    register_worker("w_b")
    assert len(list_workers()) >= 2
