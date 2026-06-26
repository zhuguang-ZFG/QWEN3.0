"""Tests for the F1 OTA enhancement suite."""

from __future__ import annotations

import base64
import math
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from device_ota.canary import CanaryDeployment
from device_ota.gradual import GradualRollout
from device_ota.rollback_monitor import RollbackMonitor
from device_ota.signature import FirmwareSignatureError, FirmwareVerifier

_URL = "https://cdn.example.com/fw.bin"
_SHA256 = "a" * 64


def _key_pair():
    private_key = Ed25519PrivateKey.generate()
    public_pem = (
        private_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode("utf-8")
    )
    return private_key, public_pem


def _sign(private_key, url: str, sha256: str) -> str:
    return base64.b64encode(private_key.sign((url + sha256).encode("utf-8"))).decode("utf-8")


def _ota_client(monkeypatch, public_key_pem: str):
    monkeypatch.setenv("LIMA_API_KEY", "test-private-token")
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    import access_guard
    from routes import device_ota
    from routes import device_ota_helpers

    monkeypatch.setattr(access_guard, "_API_KEYS", {"test-private-token"})
    monkeypatch.setattr(device_ota_helpers, "ota_signing_public_key", lambda: public_key_pem)
    device_ota.reset_ota_state_for_tests()
    app = FastAPI()
    app.include_router(device_ota.router)
    return TestClient(app)


def _start(client, private_key, devices):
    return client.post(
        "/device/v1/ota/gradual/start/v1.0.0",
        headers={"Authorization": "Bearer test-private-token"},
        json={"devices": devices, "url": _URL, "sha256": _SHA256, "signature": _sign(private_key, _URL, _SHA256)},
    )


def test_stage_selection_is_deterministic():
    rollout = GradualRollout()
    devices = [f"dev-{i:03d}" for i in range(100)]
    rollout.start("v1.0.0", devices, {})
    selected = rollout.select_devices_for_stage()
    assert len(selected) == max(1, math.ceil(100 * 0.05))
    assert rollout.select_devices_for_stage() == selected
    reloaded = GradualRollout()
    reloaded.start("v1.0.0", devices, {})
    assert reloaded.select_devices_for_stage() == selected


def test_stage_ratios_progress():
    rollout = GradualRollout()
    rollout.start("v1", [f"dev-{i}" for i in range(100)], {})
    counts = []
    for _ in range(len(rollout.STAGES)):
        counts.append(len(rollout.select_devices_for_stage()))
        rollout.promote()
    assert counts == [5, 20, 50, 100]


def test_promote_threshold():
    rollout = GradualRollout(min_samples=5, promote_threshold=0.9)
    rollout.start("v1", ["dev-1"], {})
    for _ in range(4):
        rollout.record_success("dev-1")
    assert rollout.should_promote() is False
    rollout.record_success("dev-1")
    assert rollout.should_promote() is True
    assert rollout.promote() is True
    assert rollout.status_dict()["stage"] == "early"


def test_rollback_threshold():
    rollout = GradualRollout(min_samples=5, rollback_threshold=0.15)
    rollout.start("v1", ["dev-1"], {})
    rollout.promote()
    for _ in range(5):
        rollout.record_failure("dev-1")
    assert rollout.should_rollback() is True
    assert rollout.rollback() is True
    assert rollout.status_dict()["stage"] == "canary"
    assert rollout.stage_success == rollout.stage_failure == 0


def test_state_round_trips_to_json(tmp_path: Path):
    path = tmp_path / "gradual.json"
    rollout = GradualRollout(path)
    rollout.start("v1", [f"dev-{i}" for i in range(20)], {"url": _URL})
    rollout.record_success("dev-1")
    rollout.record_success("dev-2")
    rollout.promote()
    reloaded = GradualRollout(path)
    assert reloaded.version == "v1"
    assert reloaded.stage_index == 1
    assert reloaded.stage_success == 0
    assert reloaded.firmware["url"] == _URL


def test_rollback_monitor_promotes_when_healthy():
    gradual = GradualRollout(min_samples=1, promote_threshold=0.0)
    canary = CanaryDeployment()
    monitor = RollbackMonitor(gradual, canary)
    canary.add_canary_device("dev-1")
    canary.record_success("dev-1")
    gradual.record_success("dev-1")
    assert monitor.check_and_act() == "promoted"
    assert gradual.status_dict()["stage"] == "early"


def test_rollback_monitor_rolls_back_after_three_unhealthy_checks():
    gradual = GradualRollout()
    canary = CanaryDeployment()
    monitor = RollbackMonitor(gradual, canary)
    canary.add_canary_device("dev-1")
    canary.add_canary_device("dev-2")
    canary.record_failure("dev-1")
    canary.record_failure("dev-2")
    assert monitor.check_and_act() == "unhealthy"
    assert monitor.check_and_act() == "unhealthy"
    assert monitor.check_and_act() == "rolled_back"
    assert gradual.status_dict()["stage"] == "canary"


def test_signature_accepts_valid_and_rejects_tampered():
    private_key, public_pem = _key_pair()
    signature = _sign(private_key, _URL, _SHA256)
    verifier = FirmwareVerifier(public_pem)
    assert verifier.verify(_URL, _SHA256, signature) is True
    assert verifier.verify(_URL, "b" * 64, signature) is False
    assert verifier.verify("https://evil.com/fw.bin", _SHA256, signature) is False


def test_signature_rejects_invalid_base64():
    _, public_pem = _key_pair()
    assert FirmwareVerifier(public_pem).verify(_URL, _SHA256, "not-valid-base64!!!") is False


def test_signature_raises_on_missing_or_invalid_key():
    with pytest.raises(FirmwareSignatureError, match="not configured"):
        FirmwareVerifier(None)
    with pytest.raises(FirmwareSignatureError, match="not configured"):
        FirmwareVerifier("")
    with pytest.raises(FirmwareSignatureError, match="invalid"):
        FirmwareVerifier("not-a-pem-key")


def test_gradual_start_endpoint_verifies_signature(monkeypatch):
    private_key, public_pem = _key_pair()
    client = _ota_client(monkeypatch, public_pem)
    response = _start(client, private_key, [f"dev-{i}" for i in range(20)])
    assert response.status_code == 200
    data = response.json()
    assert data["stage"] == "canary"
    assert len(data["selected_devices"]) == max(1, math.ceil(20 * 0.05))


def test_gradual_start_rejects_bad_signature(monkeypatch):
    _, public_pem = _key_pair()
    client = _ota_client(monkeypatch, public_pem)
    response = client.post(
        "/device/v1/ota/gradual/start/v1.0.0",
        headers={"Authorization": "Bearer test-private-token"},
        json={
            "devices": ["dev-1"],
            "url": _URL,
            "sha256": _SHA256,
            "signature": base64.b64encode(b"bad").decode("utf-8"),
        },
    )
    assert response.status_code == 400
    assert "signature" in response.json()["detail"].lower()


def test_gradual_start_rejects_missing_devices(monkeypatch):
    private_key, public_pem = _key_pair()
    client = _ota_client(monkeypatch, public_pem)
    response = _start(client, private_key, [])
    assert response.status_code == 400
    assert "devices" in response.json()["detail"].lower()


def test_gradual_record_success_failure_and_status(monkeypatch):
    private_key, public_pem = _key_pair()
    client = _ota_client(monkeypatch, public_pem)
    _start(client, private_key, ["dev-1", "dev-2"])
    headers = {"Authorization": "Bearer test-private-token"}
    client.post("/device/v1/ota/gradual/record-success/dev-1", headers=headers)
    status = client.get("/device/v1/ota/gradual/status", headers=headers).json()
    assert status["stage_success"] == 1
    client.post("/device/v1/ota/gradual/record-failure/dev-2", headers=headers)
    status = client.get("/device/v1/ota/gradual/status", headers=headers).json()
    assert status["stage_success"] == 1
    assert status["stage_failure"] == 1


def test_gradual_promote_and_rollback_endpoints(monkeypatch):
    private_key, public_pem = _key_pair()
    client = _ota_client(monkeypatch, public_pem)
    _start(client, private_key, ["dev-1"])
    headers = {"Authorization": "Bearer test-private-token"}
    for _ in range(5):
        client.post("/device/v1/ota/gradual/record-success/dev-1", headers=headers)
    promote = client.post("/device/v1/ota/gradual/promote", headers=headers).json()
    assert promote["promoted"] is True
    assert promote["status"]["stage"] == "early"
    rollback = client.post("/device/v1/ota/gradual/rollback", headers=headers).json()
    assert rollback["rolled_back"] is True
    assert rollback["status"]["stage"] == "canary"


def test_verify_signature_endpoint(monkeypatch):
    private_key, public_pem = _key_pair()
    client = _ota_client(monkeypatch, public_pem)
    headers = {"Authorization": "Bearer test-private-token"}
    valid = client.post(
        "/device/v1/ota/verify-signature",
        headers=headers,
        json={"url": _URL, "sha256": _SHA256, "signature": _sign(private_key, _URL, _SHA256)},
    ).json()
    assert valid["valid"] is True
    invalid = client.post(
        "/device/v1/ota/verify-signature",
        headers=headers,
        json={"url": _URL, "sha256": "b" * 64, "signature": _sign(private_key, _URL, _SHA256)},
    ).json()
    assert invalid["valid"] is False
