"""FIX-N: dead-code deprecation + silent-degradation warning logs.

Covers 4 points:
1. device_logic.sms emits DeprecationWarning on import.
2. device_gateway.auth logs a warning when the registered-device fallback fires.
3. device_gateway.store_utils logs a warning on non-redis backend selection.
4. device_intelligence.maintenance logs a warning when the ledger lookup fails.
"""

from __future__ import annotations

import importlib
import logging

import pytest


def test_sms_module_import_emits_deprecation_warning():
    import device_logic.sms as sms

    with pytest.warns(DeprecationWarning, match="device_logic.sms is deprecated"):
        importlib.reload(sms)


def test_auth_fallback_logs_warning(monkeypatch, caplog):
    import device_gateway.auth as auth

    monkeypatch.setattr(auth, "_WS_REGISTERED_DEVICE_FALLBACK", True)
    monkeypatch.setattr(auth, "_is_registered_device", lambda device_id: True)
    monkeypatch.setattr(auth, "configured_device_tokens", lambda: {})

    with caplog.at_level(logging.WARNING, logger="device_gateway.auth"):
        assert auth.validate_device_token("dev-registered", "") is True

    assert any("device auth fallback activated" in r.message for r in caplog.records)


def test_store_manager_non_redis_backend_logs_warning(monkeypatch, caplog):
    from device_gateway import store_utils
    from device_gateway.store_utils import StoreManager

    monkeypatch.setattr(store_utils.settings, "get_env", lambda name, default="": "sqlite")

    class _Dummy:
        backend_name = "memory"
        shared_across_processes = False

    manager = StoreManager(_Dummy)

    with caplog.at_level(logging.WARNING, logger="device_gateway.store_utils"):
        manager.configure_from_env(
            "LIMA_DUMMY_STORE",
            redis_url=None,
            redis_factory=lambda url: _Dummy(),
        )

    assert any("non-redis backend" in r.message for r in caplog.records)


def test_maintenance_ledger_failure_logs_warning(monkeypatch, caplog):
    from device_gateway import maintenance

    def _boom(device_id):
        raise RuntimeError("ledger down")

    monkeypatch.setattr(maintenance.ledger_store, "events_for_device", _boom)

    pm = maintenance.PredictiveMaintenance()

    with caplog.at_level(logging.WARNING, logger="device_gateway.maintenance"):
        result = pm.analyze_trend("dev-x")

    assert result["total_events"] == 0
    assert any("events_for_device failed" in r.message for r in caplog.records)
