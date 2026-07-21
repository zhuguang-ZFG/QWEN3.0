"""Production DLC token authentication fails closed when its DB is unavailable."""

from unittest.mock import patch

import pytest
from fastapi import HTTPException

from device_logic.device_token import DB_UNAVAILABLE
from dlc_api import deps


def test_production_db_failure_rejects_env_token_without_break_glass(monkeypatch) -> None:
    monkeypatch.setenv("LIMA_RUNTIME_ENV", "production")
    monkeypatch.setenv("LIMA_DEVICE_TOKENS", "legacy-token:dev-1")
    monkeypatch.delenv("LIMA_DLC_ALLOW_ENV_TOKEN_FALLBACK", raising=False)
    with patch("dlc_api.deps.lookup_device_id_by_token", return_value=DB_UNAVAILABLE):
        with pytest.raises(HTTPException) as exc_info:
            deps.verify_dlc_api_token("Bearer legacy-token")
    assert exc_info.value.status_code == 503


def test_production_break_glass_must_be_explicit(monkeypatch) -> None:
    monkeypatch.setenv("LIMA_RUNTIME_ENV", "production")
    monkeypatch.setenv("LIMA_DEVICE_TOKENS", "legacy-token:dev-1")
    monkeypatch.setenv("LIMA_DLC_ALLOW_ENV_TOKEN_FALLBACK", "1")
    with patch("dlc_api.deps.lookup_device_id_by_token", return_value=DB_UNAVAILABLE):
        assert deps.verify_dlc_api_token("Bearer legacy-token") == "dev-1"
