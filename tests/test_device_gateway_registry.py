"""Tests for device_gateway/registry.py: PII masking and pagination."""

from device_gateway.registry import get_device, get_all_devices
from device_gateway.sessions import registry
from device_logic.crud import list_device_rows
from device_logic.db import _schema_ready_paths, connect


def _seed_db(conn, count: int = 3) -> None:
    """Insert test accounts, devices, and bindings."""
    for i in range(count):
        aid = f"acc-{i}"
        conn.execute(
            "INSERT OR IGNORE INTO v2_account (id, phone, nickname) VALUES (?, ?, ?)",
            (aid, f"1{i:04d}999", f"user-{i}"),
        )
        did = f"dev-{i}"
        conn.execute(
            "INSERT OR IGNORE INTO v2_device (id, device_sn, model) VALUES (?, ?, 'test-model')",
            (did, f"SN-{i:04d}"),
        )
        conn.execute(
            "INSERT OR IGNORE INTO v2_device_binding (id, device_id, account_id, bind_mode, status) "
            "VALUES (?, ?, ?, 'owner', 'active')",
            (f"b-{i}", did, aid),
        )
    conn.commit()


class TestPagination:
    """list_device_rows pagination with limit/offset."""

    def test_list_device_rows_admin_default_limit(self, tmp_path, monkeypatch):
        monkeypatch.setenv("LIMA_DB_PATH", str(tmp_path / "pagination.db"))
        _schema_ready_paths.clear()
        with connect() as conn:
            _seed_db(conn, count=5)
            rows = list_device_rows(conn, account_id="", role="admin")
        # default limit=100 -> all 5 rows
        assert len(rows) == 5

    def test_list_device_rows_admin_limit_3(self, tmp_path, monkeypatch):
        monkeypatch.setenv("LIMA_DB_PATH", str(tmp_path / "pagination2.db"))
        _schema_ready_paths.clear()
        with connect() as conn:
            _seed_db(conn, count=10)
            rows = list_device_rows(conn, account_id="", role="admin", limit=3)
        assert len(rows) == 3

    def test_list_device_rows_admin_offset(self, tmp_path, monkeypatch):
        monkeypatch.setenv("LIMA_DB_PATH", str(tmp_path / "pagination3.db"))
        _schema_ready_paths.clear()
        with connect() as conn:
            _seed_db(conn, count=5)
            all_rows = list_device_rows(conn, account_id="", role="admin", limit=100)
            rows_page2 = list_device_rows(conn, account_id="", role="admin", limit=2, offset=2)
        assert len(rows_page2) == 2
        assert all_rows[2]["id"] == rows_page2[0]["id"]

    def test_get_all_devices_paginated(self, tmp_path, monkeypatch):
        monkeypatch.setenv("LIMA_DB_PATH", str(tmp_path / "pagination4.db"))
        _schema_ready_paths.clear()
        registry.clear()
        with connect() as conn:
            _seed_db(conn, count=10)
        devices = get_all_devices(limit=4, offset=0)
        assert len(devices) == 4


class TestPiiMasking:
    """phone field masking in get_device()."""

    def test_get_device_phone_masked(self, tmp_path, monkeypatch):
        monkeypatch.setenv("LIMA_DB_PATH", str(tmp_path / "pii.db"))
        _schema_ready_paths.clear()
        registry.clear()
        with connect() as conn:
            conn.execute("INSERT INTO v2_account (id, phone, nickname) VALUES ('acc-1', '13800138000', 'test-user')")
            conn.execute("INSERT INTO v2_device (id, device_sn, model) VALUES ('dev-1', 'SN-PII-01', 'test-model')")
            conn.execute(
                "INSERT INTO v2_device_binding (id, device_id, account_id, bind_mode, status) "
                "VALUES ('b-1', 'dev-1', 'acc-1', 'owner', 'active')"
            )
            conn.commit()

        result = get_device("dev-1")
        assert result is not None
        assert "owners" in result
        assert len(result["owners"]) == 1
        owner = result["owners"][0]
        # phone must be masked: first 3 digits + "****"
        assert owner["phone"] == "138****", f"expected masked phone, got {owner['phone']}"

    def test_get_device_phone_none(self, tmp_path, monkeypatch):
        """When owner has no phone, returned phone should be None (not crash)."""
        monkeypatch.setenv("LIMA_DB_PATH", str(tmp_path / "pii2.db"))
        _schema_ready_paths.clear()
        registry.clear()
        with connect() as conn:
            conn.execute("INSERT INTO v2_account (id, phone, nickname) VALUES ('acc-1', NULL, 'no-phone')")
            conn.execute("INSERT INTO v2_device (id, device_sn, model) VALUES ('dev-1', 'SN-PII-02', 'test-model')")
            conn.execute(
                "INSERT INTO v2_device_binding (id, device_id, account_id, bind_mode, status) "
                "VALUES ('b-1', 'dev-1', 'acc-1', 'owner', 'active')"
            )
            conn.commit()

        result = get_device("dev-1")
        assert result is not None
        assert result["owners"][0]["phone"] is None

    def test_get_device_no_owners(self, tmp_path, monkeypatch):
        """A device with no bindings should not have owners (empty list)."""
        monkeypatch.setenv("LIMA_DB_PATH", str(tmp_path / "pii3.db"))
        _schema_ready_paths.clear()
        registry.clear()
        with connect() as conn:
            conn.execute(
                "INSERT INTO v2_device (id, device_sn, model) VALUES ('dev-orphan', 'SN-ORPHAN', 'test-model')"
            )
            conn.commit()

        result = get_device("dev-orphan")
        assert result is not None
        assert result["owners"] == []
