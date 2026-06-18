from pathlib import Path

from device_ota.canary import CanaryDeployment
from device_ota.release import ReleaseGate


def _ota_client_with_state(monkeypatch, path: Path):
    monkeypatch.setenv("LIMA_API_KEY", "test-private-token")
    monkeypatch.setenv("LIMA_DEVICE_TOKENS", "dev-1=device-token,dev-2=other-token")
    monkeypatch.setenv("LIMA_DEVICE_OTA_STATE_PATH", str(path))

    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from routes.device_ota import reset_ota_state_for_tests, router

    reset_ota_state_for_tests()
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def _deploy_firmware(client) -> None:
    admin_headers = {"Authorization": "Bearer test-private-token"}
    for name in ("tests_passing", "canary_verified", "safety_review"):
        assert (
            client.post(
                "/device/v1/ota/release/criteria",
                headers=admin_headers,
                params={"name": name, "passed": "true"},
            ).status_code
            == 200
        )
    assert client.post("/device/v1/ota/canary/devices/dev-1", headers=admin_headers).status_code == 200
    assert (
        client.post(
            "/device/v1/ota/deploy/v2.0.0",
            headers=admin_headers,
            json={"url": "https://cdn.example.com/fw.bin", "sha256": "a" * 64, "signature": "YWJj"},
        ).status_code
        == 200
    )


def test_ota_state_round_trips_to_json(tmp_path):
    path = tmp_path / "ota_state.json"
    gate = ReleaseGate(path)
    canary = CanaryDeployment(path)
    gate.set_criteria("tests_passing", True)
    canary.add_canary_device("dev-1")
    canary.deploy_version("v2.0.0")
    canary.record_success("dev-1")

    assert ReleaseGate(path).get_status()["criteria"]["tests_passing"] is True
    reloaded_canary = CanaryDeployment(path)
    assert reloaded_canary.canary_devices == ["dev-1"]
    assert reloaded_canary.deployed_version == "v2.0.0"
    assert reloaded_canary.success_count == 1


def test_device_ota_upgrade_plan_contract(monkeypatch, tmp_path):
    client = _ota_client_with_state(monkeypatch, tmp_path / "ota_state.json")
    _deploy_firmware(client)

    response = client.post(
        "/device/v1/ota/upgrade-plan",
        headers={"Authorization": "Bearer device-token"},
        json={"device_id": "dev-1", "current_version": "v1.0.0"},
    )

    assert response.status_code == 200
    assert response.json()["firmware"]["version"] == "v2.0.0"
    assert response.json()["firmware"]["url"] == "https://cdn.example.com/fw.bin"


def test_device_ota_upgrade_plan_rejects_admin_key_for_device(monkeypatch, tmp_path):
    client = _ota_client_with_state(monkeypatch, tmp_path / "ota_state.json")
    response = client.post(
        "/device/v1/ota/upgrade-plan",
        headers={"Authorization": "Bearer test-private-token"},
        json={"device_id": "dev-1", "current_version": "v1.0.0"},
    )
    assert response.status_code == 401


def test_device_ota_upgrade_plan_skips_non_canary_device(monkeypatch, tmp_path):
    client = _ota_client_with_state(monkeypatch, tmp_path / "ota_state.json")
    _deploy_firmware(client)

    response = client.post(
        "/device/v1/ota/upgrade-plan",
        headers={"Authorization": "Bearer other-token"},
        json={"device_id": "dev-2", "current_version": "v1.0.0"},
    )

    assert response.status_code == 200
    assert response.json() == {"firmware": None}


def test_device_ota_install_result_contract(monkeypatch, tmp_path):
    client = _ota_client_with_state(monkeypatch, tmp_path / "ota_state.json")
    client.post("/device/v1/ota/canary/devices/dev-1", headers={"Authorization": "Bearer test-private-token"})

    response = client.post(
        "/device/v1/ota/install-result",
        headers={"Authorization": "Bearer device-token"},
        json={"device_id": "dev-1", "release_id": "v2.0.0", "success": True},
    )

    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_device_ota_install_result_rejects_device_token_mismatch(monkeypatch, tmp_path):
    client = _ota_client_with_state(monkeypatch, tmp_path / "ota_state.json")
    response = client.post(
        "/device/v1/ota/install-result",
        headers={"Authorization": "Bearer other-token"},
        json={"device_id": "dev-1", "release_id": "v2.0.0", "success": True},
    )
    assert response.status_code == 401
