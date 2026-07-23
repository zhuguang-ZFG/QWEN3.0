import time

from fastapi import FastAPI
from fastapi.testclient import TestClient

from device_gateway.sessions import registry
from device_gateway.store import InMemoryDeviceTaskStore
from device_gateway.tasks import install_task_store_for_tests, reset_tasks_for_tests
from device_logic.activation import reset_activation_store_for_tests
from device_logic.auth import jwt
from device_logic.db import _schema_ready_paths, connect
from device_voice.audio_format import pcm_to_wav_bytes


def token(account_id: str) -> str:
    now = int(time.time())
    payload = {
        "sub": account_id,
        "account_id": account_id,
        "role": "user",
        "iat": now,
        "exp": now + 3600,
    }
    return jwt.encode(payload, "test-secret-minimum-32-bytes-long!!", algorithm="HS256")


def fake_wav_bytes(payload: bytes = b"\x00\x00" * 1600) -> bytes:
    """Minimal mono WAV for transcribe tests (~100 ms @ 16 kHz)."""
    return pcm_to_wav_bytes(payload, sample_rate=16000)


def headers(account_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token(account_id)}"}


def seed_account_and_device(device_id: str = "dev-1", device_sn: str = "SN-APP-01") -> None:
    with connect() as conn:
        conn.execute("INSERT INTO v2_account (id, phone, nickname) VALUES ('a-owner', '13001', 'owner')")
        conn.execute("INSERT INTO v2_account (id, phone, nickname) VALUES ('a-other', '13002', 'other')")
        conn.execute(
            """
            INSERT INTO v2_device (id, device_sn, model, firmware_ver, hardware_ver)
            VALUES (?, ?, 'esp32s3_xyz', '1.0.0', 'rev-a')
            """,
            (device_id, device_sn),
        )
        conn.commit()


def seed_binding(
    device_id: str = "dev-1",
    account_id: str = "a-owner",
    bind_mode: str = "owner",
    binding_id: str = "b-1",
) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO v2_device_binding (id, device_id, account_id, bind_mode, status)
            VALUES (?, ?, ?, ?, 'active')
            """,
            (binding_id, device_id, account_id, bind_mode),
        )
        conn.commit()


def _build_device_app() -> FastAPI:
    """Construct the device-app FastAPI with all routers mounted."""
    from routes.device_app_api import router as app_router
    from routes.device_app_assets import router as assets_router
    from routes.device_app_auth import router as auth_router

    from routes.device_app_chat import router as chat_router
    from routes.device_app_voice import router as voice_router
    from routes.device_app_voice_ws import legacy_router as voice_legacy_ws_router
    from routes.device_app_voice_ws import router as voice_ws_router
    from routes.device_app_provision import router as provision_router
    from routes.device_app_images import router as images_router
    from routes.device_app_members import router as member_router
    from routes.device_app_misc import router as misc_router
    from routes.device_app_notifications import router as notifications_router
    from routes.device_app_stats import router as stats_router
    from routes.device_app_status_ws import router as status_ws_router
    from routes.device_app_task_extras import router as task_extras_router
    from routes.device_app_task_templates import router as template_router
    from routes.device_app_tasks import router as task_router
    from routes.device_app_activity import router as activity_router

    registry.clear()
    app = FastAPI()
    for router in (
        app_router,
        assets_router,
        auth_router,
        chat_router,
        voice_router,
        voice_ws_router,
        voice_legacy_ws_router,
        provision_router,
        images_router,
        member_router,
        misc_router,
        notifications_router,
        stats_router,
        template_router,
        task_router,
        task_extras_router,
        status_ws_router,
        activity_router,
    ):
        app.include_router(router)
    return app


def client(tmp_path, monkeypatch) -> tuple[TestClient, InMemoryDeviceTaskStore]:
    monkeypatch.setenv("LIMA_DB_PATH", str(tmp_path / "device_app.db"))
    monkeypatch.setenv("LIMA_JWT_SECRET", "test-secret-minimum-32-bytes-long!!")
    monkeypatch.setenv("LIMA_XIAOZHI_LOGIN_CODE", "000000")
    monkeypatch.setenv("LIMA_DEVICE_APP_WS_QUERY_AUTH", "1")
    _schema_ready_paths.clear()
    reset_activation_store_for_tests()
    reset_tasks_for_tests()
    store = install_task_store_for_tests(InMemoryDeviceTaskStore())

    app = _build_device_app()
    return TestClient(app), store
