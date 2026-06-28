"""Tests for the app-facing OTA endpoints."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from device_ota import runtime as ota_runtime
from routes.device_ota import router as device_ota_router
from routes.device_ota_app import router as app_ota_router


def _app_ota_client(monkeypatch):
    monkeypatch.setenv("LIMA_API_KEY", "test-private-token")
    monkeypatch.delenv("LIMA_DEVICE_OTA_STATE_PATH", raising=False)

    # Canonical reset lives in the OTA domain runtime; route modules are now
    # pure adapters and no longer own the singletons.
    ota_runtime.reset_for_tests()

    import routes.device_ota_app as app_ota_mod

    monkeypatch.setattr(
        app_ota_mod,
        "authorize",
        lambda _header: {"id": "acct_1", "role": "user", "phone": "", "email": ""},
    )
    monkeypatch.setattr(
        app_ota_mod,
        "device_access",
        lambda _conn, _account, _device_id: True,
    )
    monkeypatch.setattr(
        app_ota_mod,
        "get_device_row",
        lambda _conn, _device_id: {"firmware_ver": "1.0.0"},
    )
    monkeypatch.setattr(
        app_ota_mod.registry,
        "get",
        lambda _device_id: None,
    )

    app = FastAPI()
    app.include_router(device_ota_router)
    app.include_router(app_ota_router)
    return TestClient(app)


def test_app_ota_check_no_release(monkeypatch):
    """App check returns no_release when nothing is deployed."""
    client = _app_ota_client(monkeypatch)
    response = client.get(
        "/device/v1/ota/check",
        params={"device_id": "dev-1"},
        headers={"Authorization": "Bearer test-token"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "no_release"
    assert data["current_version"] == "1.0.0"


def test_app_ota_check_available_not_selected(monkeypatch):
    """App check shows available firmware when a release is deployed."""
    client = _app_ota_client(monkeypatch)
    for name in ("tests_passing", "canary_verified", "safety_review"):
        r = client.post(
            "/device/v1/ota/release/criteria",
            headers={"Authorization": "Bearer test-private-token"},
            params={"name": name, "passed": "true"},
        )
        assert r.status_code == 200
    client.post(
        "/device/v1/ota/deploy/v2.0.0",
        headers={"Authorization": "Bearer test-private-token"},
        json={
            "url": "https://example.com/fw.bin",
            "sha256": "a" * 64,
            "signature": "c2ln",
        },
    )

    response = client.get(
        "/device/v1/ota/check",
        params={"device_id": "dev-1"},
        headers={"Authorization": "Bearer test-token"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "available_not_selected"
    assert data["available_version"] == "v2.0.0"
    # H1 fix: unselected devices must NOT receive the firmware payload
    # (url/sha256/signature) from an ongoing canary/gradual rollout.
    assert data["firmware"] is None


def test_app_ota_start_selects_device(monkeypatch):
    """App start adds the device to canary and returns selected status."""
    client = _app_ota_client(monkeypatch)
    for name in ("tests_passing", "canary_verified", "safety_review"):
        r = client.post(
            "/device/v1/ota/release/criteria",
            headers={"Authorization": "Bearer test-private-token"},
            params={"name": name, "passed": "true"},
        )
        assert r.status_code == 200
    client.post(
        "/device/v1/ota/deploy/v2.0.0",
        headers={"Authorization": "Bearer test-private-token"},
        json={
            "url": "https://example.com/fw.bin",
            "sha256": "a" * 64,
            "signature": "c2ln",
        },
    )

    response = client.post(
        "/device/v1/ota/start",
        headers={"Authorization": "Bearer test-token"},
        json={"device_id": "dev-1"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["status"] == "available_selected"
    assert data["selected"] is True


def test_app_ota_rollback_removes_device(monkeypatch):
    """App start with rollback=true removes the device from canary."""
    client = _app_ota_client(monkeypatch)
    for name in ("tests_passing", "canary_verified", "safety_review"):
        r = client.post(
            "/device/v1/ota/release/criteria",
            headers={"Authorization": "Bearer test-private-token"},
            params={"name": name, "passed": "true"},
        )
        assert r.status_code == 200
    client.post(
        "/device/v1/ota/deploy/v2.0.0",
        headers={"Authorization": "Bearer test-private-token"},
        json={
            "url": "https://example.com/fw.bin",
            "sha256": "a" * 64,
            "signature": "c2ln",
        },
    )
    client.post(
        "/device/v1/ota/start",
        headers={"Authorization": "Bearer test-token"},
        json={"device_id": "dev-1"},
    )

    response = client.post(
        "/device/v1/ota/start",
        headers={"Authorization": "Bearer test-token"},
        json={"device_id": "dev-1", "rollback": True},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["selected"] is False
    assert data["status"] == "available_not_selected"


# ─── TASK-1: OTA 响应补连接配置（websocket/server_time）───


def test_app_ota_check_includes_connection_config(monkeypatch):
    """固件期望 OTA 响应含 websocket 段（决定走 WS 协议）+ server_time（时钟同步）。"""
    client = _app_ota_client(monkeypatch)
    response = client.get(
        "/device/v1/ota/check",
        params={"device_id": "dev-1"},
        headers={"Authorization": "Bearer test-token"},
    )
    assert response.status_code == 200
    data = response.json()
    # websocket 段必须是非 null 对象（否则固件兜底走 MQTT）
    assert isinstance(data["websocket"], dict)
    assert data["websocket"]["url"].startswith("wss://")
    # server_time 必须含 timestamp（毫秒正整数）
    assert isinstance(data["server_time"], dict)
    assert isinstance(data["server_time"]["timestamp"], int)
    assert data["server_time"]["timestamp"] > 0
    # 不应返回 mqtt 键（固件 HasMqttConfig() 应为 false）
    assert "mqtt" not in data


def test_app_ota_check_no_release_still_has_connection_config(monkeypatch):
    """即便无新版本（no_release 分支），也要返回 websocket 段（固件需它选 WS 协议）。"""
    client = _app_ota_client(monkeypatch)
    response = client.get(
        "/device/v1/ota/check",
        params={"device_id": "dev-1"},
        headers={"Authorization": "Bearer test-token"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "no_release"
    assert isinstance(data["websocket"], dict)
    assert data["websocket"]["url"].startswith("wss://")


# ─── TASK-2a: /check 支持 POST（固件 ota.cc:189 发 POST）───


def test_app_ota_check_post_supported(monkeypatch):
    """固件发 POST（带 system_info body），LiMa /check 必须支持 POST。"""
    client = _app_ota_client(monkeypatch)
    response = client.post(
        "/device/v1/ota/check",
        params={"device_id": "dev-1"},
        headers={"Authorization": "Bearer test-token"},
        json={"chip_model": "esp32s3", "mac": "AA:BB:CC:DD:EE:FF"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "no_release"


# ─── TASK-6: validate_device_token 已注册设备兜底（固件 token 永远为空）───


def test_validate_device_token_registered_device_fallback():
    """固件 NVS 无 token（全代码无写入点），token 空但设备已注册时应放行。"""
    from device_gateway import auth

    # mock _is_registered_device 返回 True（模拟设备已在 v2_device 表注册）
    auth._WS_REGISTERED_DEVICE_FALLBACK = True
    original = auth._is_registered_device
    auth._is_registered_device = lambda _did: True
    try:
        assert auth.validate_device_token("registered-device-id", "") is True
        # 未注册设备 + 空 token → 拒绝
        auth._is_registered_device = lambda _did: False
        assert auth.validate_device_token("unknown-device-id", "") is False
    finally:
        auth._is_registered_device = original


def test_validate_device_token_configured_token_still_works(monkeypatch):
    """配置了 token 的设备仍走原 compare_digest 路径（兜底不影响主路径）。"""
    from device_gateway import auth
    from config.settings import DEVICE

    monkeypatch.setattr(DEVICE, "tokens", "dev_x=secret_x")
    assert auth.validate_device_token("dev_x", "secret_x") is True
    assert auth.validate_device_token("dev_x", "wrong") is False
