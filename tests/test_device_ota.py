"""Tests for OTA release gate and canary deployment."""
from device_ota.release import ReleaseGate
from device_ota.canary import CanaryDeployment


def test_release_gate_blocks_by_default():
    """Release gate blocks deployment until all criteria pass."""
    gate = ReleaseGate()
    assert gate.is_ready() is False


def test_release_gate_allows_when_ready():
    """Release gate allows deployment when all criteria pass."""
    gate = ReleaseGate()
    gate.set_criteria("tests_passing", True)
    gate.set_criteria("canary_verified", True)
    gate.set_criteria("safety_review", True)
    assert gate.is_ready() is True


def test_release_gate_status():
    """Release gate returns status."""
    gate = ReleaseGate()
    gate.set_criteria("tests_passing", True)
    status = gate.get_status()
    assert status["ready"] is False
    assert status["criteria"]["tests_passing"] is True


def test_release_gate_rejects_unknown_criterion():
    """Unknown criteria are rejected and state is unchanged."""
    gate = ReleaseGate()
    assert gate.set_criteria("unknown_criterion", True) is False
    assert gate.is_ready() is False


def test_canary_identifies_devices():
    """Canary deployment identifies canary devices."""
    canary = CanaryDeployment()
    canary.add_canary_device("dev_canary_1")
    assert canary.is_canary("dev_canary_1") is True
    assert canary.is_canary("dev_prod_1") is False


def test_canary_tracks_success_rate():
    """Canary tracks success/failure rate."""
    canary = CanaryDeployment()
    canary.add_canary_device("dev_1")
    canary.add_canary_device("dev_2")

    canary.record_success("dev_1")
    canary.record_success("dev_2")

    assert canary.is_healthy(threshold=0.9) is True


def test_canary_fails_on_low_success_rate():
    """Canary fails when success rate is too low."""
    canary = CanaryDeployment()
    canary.add_canary_device("dev_1")
    canary.add_canary_device("dev_2")

    canary.record_success("dev_1")
    canary.record_failure("dev_2")

    assert canary.is_healthy(threshold=0.9) is False  # 50% < 90%


def test_canary_not_healthy_without_data():
    """Canary is not healthy without deployment data."""
    canary = CanaryDeployment()
    canary.add_canary_device("dev_1")
    assert canary.is_healthy() is False  # No data yet


# ── Route tests ─────────────────────────────────────────────────────────


def test_ota_route_unknown_criterion_returns_400(monkeypatch):
    """Admin endpoint rejects unknown release criteria."""
    monkeypatch.setenv("LIMA_API_KEY", "test-private-token")

    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from routes.device_ota import router

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    response = client.post(
        "/device/v1/ota/release/criteria",
        headers={"Authorization": "Bearer test-private-token"},
        params={"name": "unknown_criterion", "passed": "true"},
    )
    assert response.status_code == 400
    assert "unknown_criterion" in response.json()["detail"]


def _ota_client(monkeypatch):
    monkeypatch.setenv("LIMA_API_KEY", "test-private-token")

    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from routes.device_ota import router, _gate, _canary

    # Reset shared state for test isolation
    _gate.criteria = {name: False for name in _gate.criteria}
    _canary.canary_devices.clear()
    _canary.deployed_version = ""
    _canary.success_count = 0
    _canary.failure_count = 0

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_ota_route_known_criterion_returns_200(monkeypatch):
    """Admin endpoint accepts known release criteria."""
    client = _ota_client(monkeypatch)

    response = client.post(
        "/device/v1/ota/release/criteria",
        headers={"Authorization": "Bearer test-private-token"},
        params={"name": "tests_passing", "passed": "true"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["name"] == "tests_passing"


def test_ota_deploy_blocked_until_gate_ready(monkeypatch):
    """Deploy is rejected until all release criteria pass."""
    client = _ota_client(monkeypatch)

    response = client.post(
        "/device/v1/ota/deploy/v2.0.0",
        headers={"Authorization": "Bearer test-private-token"},
    )
    assert response.status_code == 412
    assert "release gate not ready" in response.json()["detail"]


def test_ota_deploy_succeeds_when_gate_ready(monkeypatch):
    """Deploy succeeds once all release criteria pass."""
    client = _ota_client(monkeypatch)

    for name in ("tests_passing", "canary_verified", "safety_review"):
        r = client.post(
            "/device/v1/ota/release/criteria",
            headers={"Authorization": "Bearer test-private-token"},
            params={"name": name, "passed": "true"},
        )
        assert r.status_code == 200

    response = client.post(
        "/device/v1/ota/deploy/v2.0.0",
        headers={"Authorization": "Bearer test-private-token"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["version"] == "v2.0.0"


def test_ota_canary_success_failure_lifecycle(monkeypatch):
    """Canary success/failure endpoints update counters and health."""
    client = _ota_client(monkeypatch)

    client.post(
        "/device/v1/ota/canary/devices/dev-1",
        headers={"Authorization": "Bearer test-private-token"},
    )

    r1 = client.post(
        "/device/v1/ota/canary/record-success/dev-1",
        headers={"Authorization": "Bearer test-private-token"},
    )
    assert r1.status_code == 200
    assert r1.json()["success_count"] == 1

    r2 = client.post(
        "/device/v1/ota/canary/record-failure/dev-1",
        headers={"Authorization": "Bearer test-private-token"},
    )
    assert r2.status_code == 200
    assert r2.json()["failure_count"] == 1
    assert r2.json()["healthy"] is False

    r3 = client.delete(
        "/device/v1/ota/canary/devices/dev-1",
        headers={"Authorization": "Bearer test-private-token"},
    )
    assert r3.status_code == 200
    assert r3.json()["ok"] is True
