"""Tests for MCP registry inventory (PE-A-1)."""

from __future__ import annotations

from provider_inventory.mcp_registries import (
    _glama_entry,
    _official_entry,
    infer_tags,
    merge_registry_entries,
)


def test_infer_tags_defaults_general():
    assert infer_tags("hello world") == ["general"]


def test_infer_tags_coding():
    assert "coding" in infer_tags("GitHub MCP server for repos")


def test_official_entry_shape():
    raw = {
        "server": {
            "name": "io.example/demo",
            "title": "Demo",
            "description": "Postgres SQL helper",
            "repository": {"url": "https://github.com/example/demo"},
        }
    }
    entry = _official_entry(raw)
    assert entry is not None
    assert entry["source"] == "official_registry"
    assert "data" in entry["tags"]


def test_glama_entry_shape():
    entry = _glama_entry(
        {
            "slug": "openproject-mcp",
            "namespace": "OliverRhyme",
            "name": "openproject-mcp",
            "description": "Git tools",
            "repository": {"url": "https://github.com/OliverRhyme/openproject-mcp"},
            "url": "https://glama.ai/mcp/servers/wqpopi4akg",
        }
    )
    assert entry is not None
    assert entry["source"] == "glama"
    assert "glama.ai" in entry["source_url"]
    assert entry["repository_url"].startswith("https://")


def test_fetch_glama_servers_paginates(monkeypatch):
    pages = [
        {
            "servers": [{"slug": "a", "namespace": "ns", "name": "A", "description": "one"}],
            "pageInfo": {"hasNextPage": True, "endCursor": "c1"},
        },
        {
            "servers": [{"slug": "b", "namespace": "ns", "name": "B", "description": "two"}],
            "pageInfo": {"hasNextPage": False, "endCursor": ""},
        },
    ]

    def fake_json(url, **kwargs):
        assert "cursor" in url or pages[0] is pages[0]
        return pages.pop(0)

    monkeypatch.setattr("provider_inventory.mcp_registries._fetch_json", fake_json)
    from provider_inventory.mcp_registries import fetch_glama_servers

    block = fetch_glama_servers(page_limit=5)
    assert block["pages_fetched"] == 2
    assert len(block["entries"]) == 2


def test_merge_deduplicates_by_key():
    a = {"entries": [{"key": "git", "name": "Git", "source": "official_registry", "description": "a"}]}
    b = {"entries": [{"key": "git", "name": "Git", "source": "glama", "description": ""}]}
    merged = merge_registry_entries(a, b)
    assert len(merged) == 1
    assert set(merged[0]["sources"]) == {"official_registry", "glama"}
