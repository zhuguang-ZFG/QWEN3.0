"""Tests for per-device DLC API token issuance."""

from __future__ import annotations

import hashlib

from device_logic.crud import bind_device
from device_logic.device_token import ensure_device_token
from device_logic.db import _schema_ready_paths, connect


def test_ensure_device_token_issues_once(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LIMA_DB_PATH", str(tmp_path / "token.db"))
    _schema_ready_paths.clear()
    with connect() as conn:
        conn.execute("INSERT INTO v2_device (id, device_sn, model) VALUES ('dev-1', 'SN1', 'm')")
        conn.commit()
        token, issued = ensure_device_token(conn, "dev-1")
        conn.commit()
        assert issued is True
        assert token
        row = conn.execute("SELECT token_hash FROM v2_device_token WHERE device_id='dev-1'").fetchone()
        assert row["token_hash"] == hashlib.sha256(token.encode("utf-8")).hexdigest()
        again, issued_again = ensure_device_token(conn, "dev-1")
        assert again is None
        assert issued_again is False


def test_bind_device_returns_token_on_first_bind(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LIMA_DB_PATH", str(tmp_path / "bind.db"))
    from device_logic.activation import reset_activation_store_for_tests
    from device_logic.http import new_id

    _schema_ready_paths.clear()
    reset_activation_store_for_tests()
    with connect() as conn:
        conn.execute("INSERT INTO v2_account (id, phone, nickname) VALUES ('acc-1', '10001', 'owner')")
        conn.commit()
        first = bind_device(
            conn,
            account_id="acc-1",
            device_sn="SN-BIND-1",
            model="esp32s3_xyz",
            firmware_ver="1.0.0",
            hardware_ver="rev-a",
            metadata=None,
            new_id=new_id,
        )
        second = bind_device(
            conn,
            account_id="acc-1",
            device_sn="SN-BIND-1",
            model="esp32s3_xyz",
            firmware_ver="1.0.0",
            hardware_ver="rev-a",
            metadata=None,
            new_id=new_id,
        )
    assert first["dlc_api_token_issued"] is True
    assert first["dlc_api_token"]
    assert second["dlc_api_token_issued"] is False
    assert second["dlc_api_token"] is None
