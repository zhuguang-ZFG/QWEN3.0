"""Tests for device_gateway/health_score.py and device_gateway/maintenance.py."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from device_gateway.health_score import DeviceHealthScore
from device_gateway.maintenance import PredictiveMaintenance
from device_ledger.events import LedgerEvent
from routes import device_admin


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@pytest.fixture
def score() -> DeviceHealthScore:
    return DeviceHealthScore()


@pytest.fixture
def maintenance() -> PredictiveMaintenance:
    return PredictiveMaintenance()


def _make_session(device_id: str, fw_rev: str = "") -> Any:
    session = MagicMock()
    session.device_id = device_id
    session.fw_rev = fw_rev
    return session


def _make_terminal_event(phase: str, created_at: str | None = None, error: str = "") -> LedgerEvent:
    terminal_event: dict[str, Any] = {"phase": phase}
    if error:
        terminal_event["error"] = error
    return LedgerEvent(
        event_id="evt-1",
        event_type="task_terminal",
        task_id="task-1",
        device_id="dev-1",
        payload={"terminal_event": terminal_event},
        created_at=created_at or _now_iso(),
    )


class TestDeviceHealthScore:
    def test_compute_returns_shape_and_status(self, score):
        with (
            patch("device_gateway.health_score.registry.get", return_value=None),
            patch("device_gateway.health_score.ledger_store.events_for_device", return_value=[]),
            patch.object(score, "_hardware_score", return_value=50),
            patch.object(score, "_device_firmware_version", return_value=""),
        ):
            result = score.compute("dev-1")
        assert set(result.keys()) == {"total", "dimensions", "status"}
        assert set(result["dimensions"].keys()) == set(DeviceHealthScore.DIMENSIONS)
        assert result["status"] in {"excellent", "good", "warning", "critical"}

    def test_offline_device_has_zero_connectivity(self, score):
        with (
            patch("device_gateway.health_score.registry.get", return_value=None),
            patch("device_gateway.health_score.ledger_store.events_for_device", return_value=[]),
            patch.object(score, "_hardware_score", return_value=50),
            patch.object(score, "_device_firmware_version", return_value=""),
        ):
            result = score.compute("dev-1")
        assert result["dimensions"]["connectivity"] == 0

    def test_online_device_has_full_connectivity(self, score):
        with (
            patch("device_gateway.health_score.registry.get", return_value=_make_session("dev-1")),
            patch("device_gateway.health_score.ledger_store.events_for_device", return_value=[]),
            patch.object(score, "_hardware_score", return_value=50),
        ):
            result = score.compute("dev-1")
        assert result["dimensions"]["connectivity"] == 100

    def test_task_success_rate(self, score):
        events = [
            _make_terminal_event("done"),
            _make_terminal_event("done"),
            _make_terminal_event("failed"),
        ]
        with (
            patch("device_gateway.health_score.registry.get", return_value=None),
            patch("device_gateway.health_score.ledger_store.events_for_device", return_value=events),
            patch.object(score, "_hardware_score", return_value=50),
            patch.object(score, "_device_firmware_version", return_value=""),
        ):
            result = score.compute("dev-1")
        assert result["dimensions"]["task_success"] == 66

    def test_firmware_version_mapping(self, score):
        with (
            patch("device_gateway.health_score.registry.get", return_value=_make_session("dev-1", "v1.3.0")),
            patch("device_gateway.health_score.ledger_store.events_for_device", return_value=[]),
            patch.object(score, "_hardware_score", return_value=50),
        ):
            assert score.compute("dev-1")["dimensions"]["firmware"] == 100

        with (
            patch("device_gateway.health_score.registry.get", return_value=_make_session("dev-1", "v1.0.0")),
            patch("device_gateway.health_score.ledger_store.events_for_device", return_value=[]),
            patch.object(score, "_hardware_score", return_value=50),
        ):
            assert score.compute("dev-1")["dimensions"]["firmware"] == 40

    def test_firmware_fallback_to_db(self, score):
        with (
            patch("device_gateway.health_score.registry.get", return_value=None),
            patch("device_gateway.health_score.ledger_store.events_for_device", return_value=[]),
            patch.object(score, "_hardware_score", return_value=50),
            patch.object(score, "_device_firmware_version", return_value="v1.2.0"),
        ):
            assert score.compute("dev-1")["dimensions"]["firmware"] == 80

    def test_hardware_score_from_self_check(self, score):
        conn = MagicMock()
        row_pass = {"result": "pass"}
        row_fail = {"result": "fail"}
        row_warn = {"result": "warning"}

        def _make_connect(row: dict[str, Any]):
            mock_conn = MagicMock()
            mock_conn.__enter__ = MagicMock(return_value=mock_conn)
            mock_conn.__exit__ = MagicMock(return_value=False)
            mock_conn.execute.return_value.fetchone.return_value = row
            return mock_conn

        with (
            patch("device_gateway.health_score.ledger_store.events_for_device", return_value=[]),
            patch("device_gateway.health_score.registry.get", return_value=None),
            patch("device_logic.db.connect", return_value=_make_connect(row_pass)),
        ):
            assert score.compute("dev-1")["dimensions"]["hardware"] == 100

        with (
            patch("device_gateway.health_score.ledger_store.events_for_device", return_value=[]),
            patch("device_gateway.health_score.registry.get", return_value=None),
            patch("device_logic.db.connect", return_value=_make_connect(row_warn)),
        ):
            assert score.compute("dev-1")["dimensions"]["hardware"] == 60

        with (
            patch("device_gateway.health_score.ledger_store.events_for_device", return_value=[]),
            patch("device_gateway.health_score.registry.get", return_value=None),
            patch("device_logic.db.connect", return_value=_make_connect(row_fail)),
        ):
            assert score.compute("dev-1")["dimensions"]["hardware"] == 20

    def test_status_thresholds(self, score):
        assert score._status(95) == "excellent"
        assert score._status(80) == "good"
        assert score._status(60) == "warning"
        assert score._status(30) == "critical"


class TestPredictiveMaintenance:
    def test_trend_analysis_shape(self, maintenance):
        events = [_make_terminal_event("done"), _make_terminal_event("done")]
        with patch("device_gateway.maintenance.ledger_store.events_for_device", return_value=events):
            result = maintenance.analyze_trend("dev-1")
        assert set(result.keys()) == {
            "trend",
            "predicted_failures",
            "recommended_actions",
            "next_maintenance",
            "window_days",
            "total_events",
            "terminal_events",
            "failure_count",
            "success_count",
        }
        assert result["trend"] == "improving"
        assert result["predicted_failures"] == 0
        assert result["recommended_actions"]

    def test_degrading_trend(self, maintenance):
        events = [
            _make_terminal_event("done"),
            _make_terminal_event("failed"),
            _make_terminal_event("done"),
            _make_terminal_event("done"),
        ]
        with patch("device_gateway.maintenance.ledger_store.events_for_device", return_value=events):
            result = maintenance.analyze_trend("dev-1")
        assert result["trend"] == "degrading"
        assert result["predicted_failures"] > 0
        assert any("维护" in action for action in result["recommended_actions"])
        assert result["next_maintenance"] is not None

    def test_critical_trend(self, maintenance):
        events = [
            _make_terminal_event("failed"),
            _make_terminal_event("failed"),
            _make_terminal_event("failed"),
            _make_terminal_event("done"),
        ]
        with patch("device_gateway.maintenance.ledger_store.events_for_device", return_value=events):
            result = maintenance.analyze_trend("dev-1")
        assert result["trend"] == "critical"
        assert any("检修" in action for action in result["recommended_actions"])

    def test_repeated_motion_timeout_recommends_check(self, maintenance):
        events = [
            _make_terminal_event("failed", error="motion_timeout"),
            _make_terminal_event("failed", error="motion_timeout"),
        ]
        with patch("device_gateway.maintenance.ledger_store.events_for_device", return_value=events):
            result = maintenance.analyze_trend("dev-1")
        assert any("机械传动" in action for action in result["recommended_actions"])

    def test_empty_events_returns_stable(self, maintenance):
        with patch("device_gateway.maintenance.ledger_store.events_for_device", return_value=[]):
            result = maintenance.analyze_trend("dev-1")
        assert result["trend"] == "stable"
        assert result["predicted_failures"] == 0
        assert result["next_maintenance"] is None


class TestDeviceAdminRoute:
    @pytest.fixture
    def client(self):
        app = FastAPI()
        app.include_router(device_admin.router)
        return TestClient(app)

    @pytest.fixture
    def admin_account(self):
        return {"id": "acc-admin", "role": "admin"}

    def _auth_header(self, role: str = "admin"):
        return {"Authorization": "Bearer dummy"}

    def test_health_route_requires_admin(self, client):
        with patch.object(device_admin, "authorize", return_value={"id": "acc-1", "role": "user"}):
            response = client.get("/admin/devices/dev-1/health", headers=self._auth_header())
        assert response.status_code == 403

    def test_health_route_returns_combined_payload(self, client, admin_account):
        conn = MagicMock()
        conn.__enter__ = MagicMock(return_value=conn)
        conn.__exit__ = MagicMock(return_value=False)
        conn.execute.return_value.fetchone.return_value = {"1": 1}

        with (
            patch.object(device_admin, "authorize", return_value=admin_account),
            patch.object(device_admin, "connect", return_value=conn),
            patch.object(DeviceHealthScore, "compute", return_value={"total": 85, "dimensions": {}, "status": "good"}),
            patch.object(PredictiveMaintenance, "analyze_trend", return_value={"trend": "stable"}),
        ):
            response = client.get("/admin/devices/dev-1/health", headers=self._auth_header())
        assert response.status_code == 200
        data = response.json()
        assert data["deviceId"] == "dev-1"
        assert data["health"]["total"] == 85
        assert data["maintenance"]["trend"] == "stable"

    def test_health_route_device_not_found(self, client, admin_account):
        conn = MagicMock()
        conn.__enter__ = MagicMock(return_value=conn)
        conn.__exit__ = MagicMock(return_value=False)
        conn.execute.return_value.fetchone.return_value = None

        with (
            patch.object(device_admin, "authorize", return_value=admin_account),
            patch.object(device_admin, "connect", return_value=conn),
        ):
            response = client.get("/admin/devices/dev-missing/health", headers=self._auth_header())
        assert response.status_code == 404
