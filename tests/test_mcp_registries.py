"""Tests for MCP registry inventory (PE-A-1)."""

from __future__ import annotations

from provider_inventory.mcp_registries import (
    infer_tags,
    merge_registry_entries,
    _official_entry,
    _glama_entry,
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
    entry = _glama_entry({"slug": "owner/repo", "name": "Repo MCP", "description": "Git tools"})
    assert entry is not None
    assert entry["source"] == "glama"
    assert "glama.ai" in entry["source_url"]


def test_merge_deduplicates_by_key():
    a = {"entries": [{"key": "git", "name": "Git", "source": "official_registry", "description": "a"}]}
    b = {"entries": [{"key": "git", "name": "Git", "source": "glama", "description": ""}]}
    merged = merge_registry_entries(a, b)
    assert len(merged) == 1
    assert set(merged[0]["sources"]) == {"official_registry", "glama"}
