from tool_gateway.auth import SecretStore
from tool_gateway.executor import ToolExecutor
from tool_gateway.registry import ToolDefinition, ToolRegistry, build_default_registry


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

    matches = registry.search("programming docs error url")
    names = {tool.name for tool in matches}

    assert "dev_search_docs" in names
    assert "dev_search_error" in names
    assert "dev_read_url" in names
