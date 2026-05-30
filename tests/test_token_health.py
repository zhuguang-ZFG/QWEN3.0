"""Tests for token_health.py — token validation module."""

import os
import tempfile

os.environ["LIMA_TOKEN_HEALTH_DB"] = os.path.join(tempfile.gettempdir(), "test_token_health.db")
os.environ["LIMA_BACKEND_PROFILE_DB"] = os.path.join(tempfile.gettempdir(), "test_th_profiles.db")

import token_health as th


def test_check_token_no_key():
    result = th.check_token("nonexistent_backend")
    assert result["status"] == "unknown"


def test_save_token_status():
    results = [
        {"backend": "test1", "status": "valid", "ok": True},
        {"backend": "test2", "status": "expired", "ok": False, "error": "401"},
    ]
    th.save_token_status(results)
    # Verify no exception raised


def test_check_all_tokens_no_import():
    # Test graceful handling when backends_registry not available
    results = th.check_all_tokens()
    assert isinstance(results, list)
