"""Tests for device_logic shared layer (H2/H3/M1/M4/N1)."""

import pytest

from device_logic.activation import (
    ACTIVATION_TTL_SECONDS,
    check_activation_code,
    new_activation_code,
    reset_activation_store_for_tests,
)
from device_logic.crud import bind_device, manual_add_device
from device_logic.device_sn import validate_device_sn
from device_logic.errors import DeviceLogicError
from device_logic.updates import parse_device_updates, sql_set_clause


def test_sql_set_clause_rejects_disallowed_column():
    with pytest.raises(DeviceLogicError, match="Disallowed column"):
        sql_set_clause({"model": "x", "evil_col": "y"})


def test_parse_device_updates_accepts_firmware_fields():
    updates = parse_device_updates({"firmwareVer": "2.0.0", "hardwareVer": "rev-b"})
    assert updates == {"firmware_ver": "2.0.0", "hardware_ver": "rev-b"}


def test_bind_device_persists_firmware_fields(tmp_path, monkeypatch):
    monkeypatch.setenv("LIMA_DB_PATH", str(tmp_path / "logic.db"))
    from device_logic.db import _schema_ready_paths, connect
    from device_logic.http import new_id

    _schema_ready_paths.clear()
    reset_activation_store_for_tests()
    with connect() as conn:
        conn.execute("INSERT INTO v2_account (id, phone, nickname) VALUES ('acc-1', '10001', 'owner')")
        conn.commit()
        result = bind_device(
            conn,
            account_id="acc-1",
            device_sn="SN-LOGIC-1",
            model="esp32s3_xyz",
            firmware_ver="1.2.3",
            hardware_ver="rev-c",
            metadata={"lane": "A"},
            new_id=new_id,
        )
        row = conn.execute("SELECT * FROM v2_device WHERE id=?", (result["device_id"],)).fetchone()
    assert row["firmware_ver"] == "1.2.3"
    assert row["hardware_ver"] == "rev-c"


def test_activation_code_sqlite_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("LIMA_DB_PATH", str(tmp_path / "activation.db"))
    from device_logic.db import _schema_ready_paths

    _schema_ready_paths.clear()
    reset_activation_store_for_tests()
    code = new_activation_code("aa:bb:cc")
    assert len(code) == 6
    assert check_activation_code(code) is True
    assert check_activation_code("000000") is False


def test_activation_code_one_time_use(tmp_path, monkeypatch):
    """N1 fix: activation code must be consumed on first check — replay within TTL is blocked."""
    monkeypatch.setenv("LIMA_DB_PATH", str(tmp_path / "activation_otu.db"))
    from device_logic.db import _schema_ready_paths

    _schema_ready_paths.clear()
    reset_activation_store_for_tests()
    code = new_activation_code("dd:ee:ff")
    assert check_activation_code(code) is True  # first use → valid and consumed
    assert check_activation_code(code) is False  # replay → code deleted, blocked


def test_activation_ttl_constant():
    assert ACTIVATION_TTL_SECONDS == 600


def test_validate_device_sn_accepts_common_formats():
    assert validate_device_sn("SN-LOGIC-1") == "SN-LOGIC-1"
    assert validate_device_sn("  AA:BB:CC:DD:EE:FF  ") == "AA:BB:CC:DD:EE:FF"


def test_validate_device_sn_rejects_invalid():
    with pytest.raises(DeviceLogicError, match="invalid deviceSn"):
        validate_device_sn("")
    with pytest.raises(DeviceLogicError, match="invalid deviceSn"):
        validate_device_sn("'; DROP TABLE--")
    with pytest.raises(DeviceLogicError, match="invalid deviceSn"):
        validate_device_sn("x" * 65)


def test_bind_device_rejects_invalid_sn(tmp_path, monkeypatch):
    monkeypatch.setenv("LIMA_DB_PATH", str(tmp_path / "sn.db"))
    from device_logic.db import _schema_ready_paths, connect
    from device_logic.http import new_id

    _schema_ready_paths.clear()
    with connect() as conn:
        conn.execute("INSERT INTO v2_account (id, phone) VALUES ('acc-sn', '10002')")
        conn.commit()
        with pytest.raises(DeviceLogicError, match="invalid deviceSn"):
            bind_device(
                conn,
                account_id="acc-sn",
                device_sn="bad sn!",
                model="esp32s3_xyz",
                firmware_ver="",
                hardware_ver="",
                metadata=None,
                new_id=new_id,
            )


def test_manual_add_device_rejects_invalid_sn(tmp_path, monkeypatch):
    monkeypatch.setenv("LIMA_DB_PATH", str(tmp_path / "sn-manual.db"))
    from device_logic.db import _schema_ready_paths, connect
    from device_logic.http import new_id

    _schema_ready_paths.clear()
    with connect() as conn:
        with pytest.raises(DeviceLogicError, match="invalid deviceSn"):
            manual_add_device(
                conn,
                device_sn="",
                model="esp32s3_xyz",
                firmware_ver="",
                hardware_ver="",
                metadata=None,
                new_id=new_id,
            )
