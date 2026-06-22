"""Tests for model_registry.py — version management."""

from model_registry import get_status, list_versions


class TestGetStatus:
    def test_empty_registry(self):
        status = get_status()
        assert "total_versions" in status
        assert "active_version" in status
        assert "latest_metrics" in status


class TestListVersions:
    def test_returns_list(self):
        versions = list_versions()
        assert isinstance(versions, list)
