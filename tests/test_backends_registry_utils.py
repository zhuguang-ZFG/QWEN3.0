"""Tests for backends_registry shared helpers."""

from __future__ import annotations

import logging

from backends_registry._utils import legacy_free_enabled
from backends_registry.coding_pool import community as community_pool


def test_legacy_free_enabled_honors_lima_env(monkeypatch):
    monkeypatch.setenv("LIMA_FREE_AJIAKESI_ENABLED", "1")
    monkeypatch.delenv("FREE_AJIAKESI_ENABLED", raising=False)
    assert legacy_free_enabled("AJIAKESI") is True


def test_legacy_free_enabled_defaults_false(monkeypatch):
    monkeypatch.delenv("LIMA_FREE_AJIAKESI_ENABLED", raising=False)
    monkeypatch.delenv("FREE_AJIAKESI_ENABLED", raising=False)
    assert legacy_free_enabled("AJIAKESI") is False


def test_legacy_free_enabled_warns_on_legacy_env(monkeypatch, caplog):
    monkeypatch.delenv("LIMA_FREE_AJIAKESI_ENABLED", raising=False)
    monkeypatch.setenv("FREE_AJIAKESI_ENABLED", "true")
    with caplog.at_level(logging.WARNING):
        assert legacy_free_enabled("AJIAKESI") is True
    assert "deprecated" in caplog.text
    assert "LIMA_FREE_AJIAKESI_ENABLED" in caplog.text


def test_log_insecure_backend_status_disabled_by_default(caplog):
    with caplog.at_level(logging.INFO):
        community_pool.log_insecure_backend_status()
    assert "disabled by default" in caplog.text


def test_log_insecure_backend_status_warns_when_enabled(monkeypatch, caplog):
    monkeypatch.setattr(community_pool, "_AJIAKESI_ENABLED", True)
    with caplog.at_level(logging.WARNING):
        community_pool.log_insecure_backend_status()
    assert "cleartext HTTP" in caplog.text
