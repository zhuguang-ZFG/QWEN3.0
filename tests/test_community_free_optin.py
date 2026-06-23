"""Tests for community free backend opt-in gating (SEC-005)."""

import importlib

import pytest

import backends_registry
import backends_registry.coding_pool.community as coding_community
import backends_registry.community_free as community_free


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Remove opt-in env vars before each test."""
    keys = [
        "LIMA_FREE_AJIAKESI_ENABLED",
        "LIMA_FREE_TEAM_SPEED_ENABLED",
        "FREE_AJIAKESI_ENABLED",
        "FREE_TEAM_SPEED_ENABLED",
    ]
    for k in keys:
        monkeypatch.delenv(k, raising=False)


def _reload_registry_modules():
    importlib.reload(community_free)
    importlib.reload(coding_community)
    importlib.reload(backends_registry.coding_pool)
    importlib.reload(backends_registry)


@pytest.mark.parametrize("enabled", ["1", "true", "True", "yes", "on"])
def test_ajiakesi_enabled_with_truthy_values(enabled, monkeypatch):
    monkeypatch.setenv("LIMA_FREE_AJIAKESI_ENABLED", enabled)
    _reload_registry_modules()
    assert "free_ajiakesi_gpt54" in backends_registry.BACKENDS
    assert "free_ajiakesi_gpt55" in backends_registry.BACKENDS
    assert "free_ajiakesi_gpt54_code" in backends_registry.BACKENDS


@pytest.mark.parametrize("disabled", ["0", "false", "False", "no", "off", ""])
def test_ajiakesi_disabled_with_falsy_values(disabled, monkeypatch):
    monkeypatch.setenv("LIMA_FREE_AJIAKESI_ENABLED", disabled)
    _reload_registry_modules()
    assert "free_ajiakesi_gpt54" not in backends_registry.BACKENDS
    assert "free_ajiakesi_gpt54_code" not in backends_registry.BACKENDS


def test_team_speed_enabled(monkeypatch):
    monkeypatch.setenv("LIMA_FREE_TEAM_SPEED_ENABLED", "1")
    _reload_registry_modules()
    assert "free_team_speed_gpt55" in backends_registry.BACKENDS


def test_team_speed_disabled_by_default():
    _reload_registry_modules()
    assert "free_team_speed_gpt55" not in backends_registry.BACKENDS


def test_ajiakesi_legacy_env_still_works_with_warning(caplog, monkeypatch):
    monkeypatch.setenv("FREE_AJIAKESI_ENABLED", "1")
    with caplog.at_level("WARNING"):
        _reload_registry_modules()
    assert "free_ajiakesi_gpt54" in backends_registry.BACKENDS
    assert "FREE_AJIAKESI_ENABLED is deprecated" in caplog.text


def test_ajiakesi_lima_env_takes_precedence_over_legacy(monkeypatch):
    monkeypatch.setenv("LIMA_FREE_AJIAKESI_ENABLED", "0")
    monkeypatch.setenv("FREE_AJIAKESI_ENABLED", "1")
    _reload_registry_modules()
    assert "free_ajiakesi_gpt54" not in backends_registry.BACKENDS


def test_coding_pool_ajiakesi_blocks_private_code(monkeypatch):
    monkeypatch.setenv("LIMA_FREE_AJIAKESI_ENABLED", "1")
    importlib.reload(coding_community)
    cfg54 = coding_community.BACKENDS["free_ajiakesi_gpt54_code"]
    cfg55 = coding_community.BACKENDS["free_ajiakesi_gpt55_code"]
    assert cfg54["private_code_allowed"] is False
    assert cfg55["private_code_allowed"] is False


def test_team_speed_has_no_tool_calls_cap(monkeypatch):
    monkeypatch.setenv("LIMA_FREE_TEAM_SPEED_ENABLED", "1")
    importlib.reload(community_free)
    cfg = community_free.BACKENDS["free_team_speed_gpt55"]
    assert "tool_calls" not in cfg.get("caps", [])


def test_https_backends_always_registered():
    _reload_registry_modules()
    assert "free_muyuan_gpt54" in backends_registry.BACKENDS
    assert "free_muyuan_gpt55_code" in backends_registry.BACKENDS
    assert "free_openai_next_gpt4" in backends_registry.BACKENDS
