"""Tests for firmware remote attestation (F5)."""

from __future__ import annotations

import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import WebSocket

from device_gateway.attestation import (
    AttestationResult,
    AttestationVerifier,
    compute_firmware_hash,
    verifier as attestation_verifier,
)
from device_gateway.protocol import attestation_failed_frame, attestation_warning_frame
from device_gateway.sessions import DeviceSession
from routes import device_ota
from routes import device_gateway_ws_handlers as handlers


@pytest.fixture
def clean_verifier(tmp_path):
    """Provide an isolated verifier backed by a temporary JSON file."""
    path = tmp_path / "firmware_hashes.json"
    v = AttestationVerifier(str(path))
    v.register("v1.3.0", "sha256:" + "0" * 64)
    v.register("v2.0.0", "sha256:" + "a" * 64)
    return v, path


@pytest.fixture
def websocket():
    ws = MagicMock(spec=WebSocket)
    ws.scope = {}
    ws.query_params = MagicMock()
    ws.query_params.get.return_value = ""
    ws.headers = {"authorization": "Bearer token-1"}
    ws.send_json = AsyncMock()
    ws.close = AsyncMock()
    return ws


@pytest.fixture(autouse=True)
def _reset_state(monkeypatch):
    handlers.registry.clear()
    handlers.shadow_store.reset()
    # Ensure device token is configured for hello tests.
    monkeypatch.setenv("LIMA_DEVICE_TOKENS", "dev-1=token-1")
    yield
    handlers.registry.clear()
    handlers.shadow_store.reset()


# ── AttestationVerifier unit tests ─────────────────────────────────────────


def test_unknown_version_quarantine(clean_verifier):
    v, _ = clean_verifier
    result = v.verify("dev-1", "sha256:" + "0" * 64, "v9.9.9")
    assert result.action == "quarantine"
    assert "unknown" in result.reason.lower()


def test_hash_mismatch_read_only(clean_verifier):
    v, _ = clean_verifier
    result = v.verify("dev-1", "sha256:" + "b" * 64, "v1.3.0")
    assert result.action == "read_only"
    assert "mismatch" in result.reason.lower()


def test_known_hash_full_access(clean_verifier):
    v, _ = clean_verifier
    result = v.verify("dev-1", "sha256:" + "0" * 64, "v1.3.0")
    assert result.action == "full_access"


def test_reload_hashes_persists_and_loads(clean_verifier):
    v, path = clean_verifier
    # Persist in-memory hashes to disk, then reload into a fresh verifier.
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(v.list_hashes(), fh)
    fresh = AttestationVerifier(str(path))
    fresh.reload_hashes()
    assert fresh.list_hashes().get("v1.3.0") == "sha256:" + "0" * 64


def test_compute_firmware_hash():
    data = b"hello firmware"
    expected = "sha256:" + __import__("hashlib").sha256(data).hexdigest()
    assert compute_firmware_hash(data) == expected


# ── WebSocket hello integration tests ──────────────────────────────────────


@pytest.mark.asyncio
async def test_hello_quarantine_unknown_version(websocket, monkeypatch):
    monkeypatch.setattr(handlers, "attestation_verifier", _isolated_verifier())
    message = {
        "type": "hello",
        "protocol": "lima-device-v1",
        "device_id": "dev-1",
        "firmwareVersion": "v9.9.9",
        "firmwareHash": "sha256:" + "0" * 64,
    }
    device_id, session, keep_open = await handlers.handle_hello(websocket, message, request_id="r1")
    assert device_id is None
    assert session is None
    assert keep_open is False
    websocket.close.assert_awaited_once_with(code=1008)
    sent = websocket.send_json.await_args.args[0]
    assert sent["type"] == "attestation_failed"


@pytest.mark.asyncio
async def test_hello_read_only_hash_mismatch(websocket, monkeypatch):
    monkeypatch.setattr(handlers, "attestation_verifier", _isolated_verifier())
    message = {
        "type": "hello",
        "protocol": "lima-device-v1",
        "device_id": "dev-1",
        "firmwareVersion": "v1.3.0",
        "firmwareHash": "sha256:" + "b" * 64,
    }
    with patch.object(handlers, "drain_pending_tasks", new_callable=AsyncMock, return_value=True):
        device_id, session, keep_open = await handlers.handle_hello(websocket, message, request_id="r1")
    assert device_id == "dev-1"
    assert isinstance(session, DeviceSession)
    assert session.attestation_action == "read_only"
    assert keep_open is True
    sent_types = [call.args[0]["type"] for call in websocket.send_json.await_args_list]
    assert "attestation_warning" in sent_types


@pytest.mark.asyncio
async def test_hello_full_access_known_hash(websocket, monkeypatch):
    monkeypatch.setattr(handlers, "attestation_verifier", _isolated_verifier())
    message = {
        "type": "hello",
        "protocol": "lima-device-v1",
        "device_id": "dev-1",
        "firmwareVersion": "v1.3.0",
        "firmwareHash": "sha256:" + "0" * 64,
    }
    with patch.object(handlers, "drain_pending_tasks", new_callable=AsyncMock, return_value=True):
        device_id, session, keep_open = await handlers.handle_hello(websocket, message, request_id="r1")
    assert device_id == "dev-1"
    assert isinstance(session, DeviceSession)
    assert session.attestation_action == "full_access"
    assert keep_open is True


@pytest.mark.asyncio
async def test_hello_without_attestation_fields_quarantine(websocket, monkeypatch):
    monkeypatch.setattr(handlers, "attestation_verifier", _isolated_verifier())
    message = {
        "type": "hello",
        "protocol": "lima-device-v1",
        "device_id": "dev-1",
    }
    device_id, session, keep_open = await handlers.handle_hello(websocket, message, request_id="r1")
    assert device_id is None
    assert keep_open is False
    websocket.close.assert_awaited_once_with(code=1008)


# ── Admin whitelist endpoints ──────────────────────────────────────────────


@pytest.fixture
def admin_client(monkeypatch):
    monkeypatch.setenv("LIMA_API_KEY", "admin-key")
    from fastapi import APIRouter, FastAPI
    from fastapi.testclient import TestClient

    router = APIRouter(prefix="/device/v1/ota")
    router.get("/firmware-hashes")(device_ota.list_firmware_hashes)
    router.post("/firmware-hashes")(device_ota.register_firmware_hash)
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_admin_register_and_list_firmware_hash(admin_client, tmp_path, monkeypatch):
    fresh_path = tmp_path / "firmware_hashes.json"
    monkeypatch.setattr(device_ota, "_FIRMWARE_HASHES_PATH", str(fresh_path))
    fresh_verifier = AttestationVerifier(str(fresh_path))
    monkeypatch.setattr(device_ota, "attestation_verifier", fresh_verifier)
    new_hash = "sha256:" + "c" * 64
    response = admin_client.post(
        "/device/v1/ota/firmware-hashes",
        json={"version": "v9.9.9", "hash": "c" * 64},
        headers={"authorization": "Bearer admin-key"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["version"] == "v9.9.9"
    assert body["hash"] == new_hash

    response = admin_client.get(
        "/device/v1/ota/firmware-hashes",
        headers={"authorization": "Bearer admin-key"},
    )
    assert response.status_code == 200
    assert response.json()["hashes"]["v9.9.9"] == new_hash


def test_admin_register_invalid_hash(admin_client):
    response = admin_client.post(
        "/device/v1/ota/firmware-hashes",
        json={"version": "v1", "hash": "not-a-hash"},
        headers={"authorization": "Bearer admin-key"},
    )
    assert response.status_code == 400


def test_admin_register_missing_version(admin_client):
    response = admin_client.post(
        "/device/v1/ota/firmware-hashes",
        json={"hash": "c" * 64},
        headers={"authorization": "Bearer admin-key"},
    )
    assert response.status_code == 400


# ── helpers ────────────────────────────────────────────────────────────────


def _isolated_verifier() -> AttestationVerifier:
    v = AttestationVerifier()
    v.register("v1.3.0", "sha256:" + "0" * 64)
    v.register("v2.0.0", "sha256:" + "a" * 64)
    return v
