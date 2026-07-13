"""Tests for dlc_api/deps.py — S3 per-device token DB lookup + env fallback."""

from __future__ import annotations

import hashlib
import sqlite3
from unittest.mock import patch, MagicMock

import pytest
from fastapi import HTTPException

from dlc_api.deps import verify_dlc_api_token, _token_hash, _lookup_token_from_db, _DB_UNAVAILABLE


# --- _token_hash ---


def test_token_hash_sha256():
    token = "my-secret-token"
    expected = hashlib.sha256(token.encode("utf-8")).hexdigest()
    assert _token_hash(token) == expected


def test_token_hash_deterministic():
    assert _token_hash("abc") == _token_hash("abc")


# --- _lookup_token_from_db ---


def test_lookup_token_from_db_returns_device_id_when_found():
    token = "device-token-123"
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()

    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchone.return_value = {"device_id": "dev-42"}
    mock_ctx = MagicMock()
    mock_ctx.__enter__ = MagicMock(return_value=mock_conn)
    mock_ctx.__exit__ = MagicMock(return_value=False)

    with patch("dlc_api.deps._db_connect") as mock_connect:
        mock_connect.return_value = mock_ctx
        result = _lookup_token_from_db(token)

    assert result == "dev-42"
    mock_conn.execute.assert_called_once_with(
        "SELECT device_id FROM v2_device_token WHERE token_hash=? LIMIT 1",
        (token_hash,),
    )


def test_lookup_token_from_db_returns_none_when_not_found():
    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchone.return_value = None
    mock_ctx = MagicMock()
    mock_ctx.__enter__ = MagicMock(return_value=mock_conn)
    mock_ctx.__exit__ = MagicMock(return_value=False)

    with patch("dlc_api.deps._db_connect") as mock_connect:
        mock_connect.return_value = mock_ctx
        result = _lookup_token_from_db("unknown-token")

    assert result is None


def test_lookup_token_from_db_returns_sentinel_on_exception():
    """DB errors → _DB_UNAVAILABLE (env fallback path)."""
    with patch("dlc_api.deps._db_connect", side_effect=Exception("DB unavailable")):
        result = _lookup_token_from_db("any-token")

    assert result is _DB_UNAVAILABLE


def test_lookup_token_from_db_returns_sentinel_when_table_missing():
    """OperationalError (no such table) → _DB_UNAVAILABLE."""
    with patch("dlc_api.deps._db_connect", side_effect=sqlite3.OperationalError("no such table: v2_device_token")):
        result = _lookup_token_from_db("any-token")

    assert result is _DB_UNAVAILABLE


# --- verify_dlc_api_token (integration of DB + env fallback) ---


def test_verify_prefers_db_over_env(monkeypatch):
    """DB hit should return device_id even if env also has a matching token."""
    monkeypatch.setenv("LIMA_DEVICE_TOKENS", "my-token:env-device")

    with patch("dlc_api.deps._lookup_token_from_db", return_value="db-device"):
        result = verify_dlc_api_token("Bearer my-token")

    assert result == "db-device"


def test_verify_falls_back_to_env_when_db_unavailable(monkeypatch):
    """When DB returns _DB_UNAVAILABLE, env var should still work."""
    monkeypatch.setenv("LIMA_DEVICE_TOKENS", "fallback-token:env-dev-1")

    with patch("dlc_api.deps._lookup_token_from_db", return_value=_DB_UNAVAILABLE):
        result = verify_dlc_api_token("Bearer fallback-token")

    assert result == "env-dev-1"


def test_verify_rejects_invalid_token_not_in_db_or_env(monkeypatch):
    """Token not in DB and not in env → 401."""
    monkeypatch.setenv("LIMA_DEVICE_TOKENS", "good-token:dev-1")

    with patch("dlc_api.deps._lookup_token_from_db", return_value=None):
        with pytest.raises(HTTPException) as exc_info:
            verify_dlc_api_token("Bearer bad-token")

    assert exc_info.value.status_code == 401


def test_verify_rejects_missing_bearer():
    with pytest.raises(HTTPException) as exc_info:
        verify_dlc_api_token("Basic abc123")

    assert exc_info.value.status_code == 401


def test_verify_rejects_empty_token():
    with pytest.raises(HTTPException) as exc_info:
        verify_dlc_api_token("Bearer ")

    assert exc_info.value.status_code == 401


def test_verify_works_with_only_env_when_db_unavailable(monkeypatch):
    """Full graceful degradation: DB unavailable, env has the token."""
    monkeypatch.setenv("LIMA_DEVICE_TOKENS", "env-only-token:dev-env")

    with patch("dlc_api.deps._lookup_token_from_db", return_value=_DB_UNAVAILABLE):
        result = verify_dlc_api_token("Bearer env-only-token")

    assert result == "dev-env"


def test_verify_accepts_equals_format_env(monkeypatch):
    """device_id=token format (VPS device-gateway compatible)."""
    monkeypatch.setenv("LIMA_DEVICE_TOKENS", "dev-test-1=secret-token-abc")

    with patch("dlc_api.deps._lookup_token_from_db", return_value=_DB_UNAVAILABLE):
        result = verify_dlc_api_token("Bearer secret-token-abc")

    assert result == "dev-test-1"


def test_verify_accepts_mixed_formats_env(monkeypatch):
    """Both token:device_id and device_id=token in same env var."""
    monkeypatch.setenv("LIMA_DEVICE_TOKENS", "tok1:dev-a,dev-b=tok2")

    with patch("dlc_api.deps._lookup_token_from_db", return_value=_DB_UNAVAILABLE):
        assert verify_dlc_api_token("Bearer tok1") == "dev-a"
        assert verify_dlc_api_token("Bearer tok2") == "dev-b"


def test_verify_rejects_when_no_tokens_at_all(monkeypatch):
    """No DB, no env → 401."""
    monkeypatch.delenv("LIMA_DEVICE_TOKENS", raising=False)

    with patch("dlc_api.deps._lookup_token_from_db", return_value=_DB_UNAVAILABLE):
        with pytest.raises(HTTPException) as exc_info:
            verify_dlc_api_token("Bearer anything")

    assert exc_info.value.status_code == 401


def test_verify_rejects_token_not_in_db_even_if_in_env(monkeypatch):
    """DB OK but token not found → 401, even if token exists in env."""
    monkeypatch.setenv("LIMA_DEVICE_TOKENS", "env-token:env-dev")

    with patch("dlc_api.deps._lookup_token_from_db", return_value=None):
        with pytest.raises(HTTPException) as exc_info:
            verify_dlc_api_token("Bearer env-token")

    assert exc_info.value.status_code == 401


def test_verify_accepts_double_space_bearer(monkeypatch):
    """Bearer<2spaces>token should be accepted (strip fix)."""
    monkeypatch.setenv("LIMA_DEVICE_TOKENS", "my-token:dev-double")

    with patch("dlc_api.deps._lookup_token_from_db", return_value=_DB_UNAVAILABLE):
        result = verify_dlc_api_token("Bearer  my-token")

    assert result == "dev-double"
