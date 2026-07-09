"""Tests for device app voice transcribe and ticket routes."""

from __future__ import annotations

import io
from dataclasses import replace

import pytest
import voice_app_ws_ticket
from fastapi.responses import JSONResponse
from device_app_helpers import client as make_client
from device_app_helpers import fake_wav_bytes, headers, seed_account_and_device, seed_binding


@pytest.fixture
def mock_asr(monkeypatch):
    captured: dict[str, object] = {}

    async def fake_transcribe(audio_data: bytes) -> str:
        captured["audio"] = audio_data
        return "画一只猫"

    monkeypatch.setattr("routes.device_app_voice.transcribe_audio", fake_transcribe)
    return captured


def test_transcribe_draw_intent(tmp_path, monkeypatch, mock_asr):
    client, _store = make_client(tmp_path, monkeypatch)
    seed_account_and_device()
    response = client.post(
        "/device/v1/app/voice/transcribe",
        headers=headers("a-owner"),
        files={"audio": ("clip.wav", io.BytesIO(fake_wav_bytes()), "audio/wav")},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["text"] == "画一只猫"
    assert data["intent"]["capability"] == "draw_generated"
    assert mock_asr["audio"] == fake_wav_bytes()


@pytest.mark.parametrize(
    ("transcript", "capability"),
    [
        ("写你好", "write_text"),
        ("归零", "home"),
    ],
)
def test_transcribe_intent_variants(tmp_path, monkeypatch, transcript, capability):
    async def fake_transcribe(_audio_data: bytes) -> str:
        return transcript

    monkeypatch.setattr("routes.device_app_voice.transcribe_audio", fake_transcribe)
    client, _store = make_client(tmp_path, monkeypatch)
    seed_account_and_device()
    response = client.post(
        "/device/v1/app/voice/transcribe",
        headers=headers("a-owner"),
        files={"audio": ("clip.wav", io.BytesIO(fake_wav_bytes()), "audio/wav")},
    )
    assert response.status_code == 200, response.text
    assert response.json()["intent"]["capability"] == capability


def test_transcribe_persists_audio_for_device(tmp_path, monkeypatch, mock_asr):
    monkeypatch.setenv("LIMA_DATA_DIR", str(tmp_path / "lima-data"))
    client, _store = make_client(tmp_path, monkeypatch)
    seed_account_and_device()
    seed_binding()

    response = client.post(
        "/device/v1/app/voice/transcribe",
        headers=headers("a-owner"),
        data={"device_id": "dev-1"},
        files={"audio": ("clip.wav", io.BytesIO(fake_wav_bytes()), "audio/wav")},
    )
    assert response.status_code == 200, response.text
    audio_id = response.json()["audioId"]
    assert audio_id

    history = client.get("/device/v1/app/devices/dev-1/chat-history", headers=headers("a-owner"))
    assert history.status_code == 200, history.text
    assert any(item["audioId"] == audio_id for item in history.json()["chatHistory"])


def test_transcribe_unauthorized(tmp_path, monkeypatch):
    client, _store = make_client(tmp_path, monkeypatch)
    response = client.post(
        "/device/v1/app/voice/transcribe",
        files={"audio": ("clip.wav", io.BytesIO(fake_wav_bytes()), "audio/wav")},
    )
    assert response.status_code == 401


def test_transcribe_empty_audio(tmp_path, monkeypatch, mock_asr):
    client, _store = make_client(tmp_path, monkeypatch)
    seed_account_and_device()
    response = client.post(
        "/device/v1/app/voice/transcribe",
        headers=headers("a-owner"),
        files={"audio": ("clip.wav", io.BytesIO(b""), "audio/wav")},
    )
    assert response.status_code == 400


def test_transcribe_oversize_audio(tmp_path, monkeypatch):
    from config.voice_settings import VOICE

    monkeypatch.setattr("routes.device_app_voice.VOICE", replace(VOICE, max_audio_bytes=32))
    client, _store = make_client(tmp_path, monkeypatch)
    seed_account_and_device()
    response = client.post(
        "/device/v1/app/voice/transcribe",
        headers=headers("a-owner"),
        files={"audio": ("clip.wav", io.BytesIO(fake_wav_bytes()), "audio/wav")},
    )
    assert response.status_code == 413


def test_transcribe_rate_limited(tmp_path, monkeypatch):
    client, _store = make_client(tmp_path, monkeypatch)
    seed_account_and_device()

    def deny(_key: str, _limit: int, **_kwargs):
        return JSONResponse(
            status_code=429,
            content={"error": {"message": "Rate limit exceeded. Try again later.", "type": "rate_limit_error"}},
        )

    monkeypatch.setattr("routes.device_app_voice.check_key_limit", deny)
    response = client.post(
        "/device/v1/app/voice/transcribe",
        headers=headers("a-owner"),
        files={"audio": ("clip.wav", io.BytesIO(fake_wav_bytes()), "audio/wav")},
    )
    assert response.status_code == 429


def test_transcribe_denies_without_device_control(tmp_path, monkeypatch):
    async def should_not_run(*_args, **_kwargs):
        pytest.fail("ASR must not run when device control is denied")

    monkeypatch.setattr("routes.device_app_voice.transcribe_audio", should_not_run)
    client, _store = make_client(tmp_path, monkeypatch)
    seed_account_and_device()
    seed_binding()

    response = client.post(
        "/device/v1/app/voice/transcribe",
        headers=headers("a-other"),
        data={"device_id": "dev-1"},
        files={"audio": ("clip.wav", io.BytesIO(fake_wav_bytes()), "audio/wav")},
    )
    assert response.status_code == 403


def test_transcribe_asr_not_configured(tmp_path, monkeypatch):
    from device_voice.asr import AsrNotConfiguredError

    async def boom(*_args, **_kwargs):
        raise AsrNotConfiguredError("disabled")

    monkeypatch.setattr("routes.device_app_voice.transcribe_audio", boom)
    client, _store = make_client(tmp_path, monkeypatch)
    seed_account_and_device()
    response = client.post(
        "/device/v1/app/voice/transcribe",
        headers=headers("a-owner"),
        files={"audio": ("clip.wav", io.BytesIO(fake_wav_bytes()), "audio/wav")},
    )
    assert response.status_code == 503


def test_transcribe_asr_runtime_failure(tmp_path, monkeypatch):
    async def boom(*_args, **_kwargs):
        raise RuntimeError("upstream failed")

    monkeypatch.setattr("routes.device_app_voice.transcribe_audio", boom)
    client, _store = make_client(tmp_path, monkeypatch)
    seed_account_and_device()
    response = client.post(
        "/device/v1/app/voice/transcribe",
        headers=headers("a-owner"),
        files={"audio": ("clip.wav", io.BytesIO(fake_wav_bytes()), "audio/wav")},
    )
    assert response.status_code == 503
    assert response.json()["message"] == "ASR failed"


def test_voice_ticket_returns_ticket(tmp_path, monkeypatch):
    voice_app_ws_ticket.reset()
    client, _store = make_client(tmp_path, monkeypatch)
    seed_account_and_device()
    response = client.post("/device/v1/app/voice/ticket", headers=headers("a-owner"))
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["ticket"]
    assert data["expires_in"] == voice_app_ws_ticket.TTL_SECONDS


def test_voice_ticket_binds_account(tmp_path, monkeypatch):
    voice_app_ws_ticket.reset()
    client, _store = make_client(tmp_path, monkeypatch)
    seed_account_and_device()
    response = client.post("/device/v1/app/voice/ticket", headers=headers("a-owner"))
    ticket = response.json()["ticket"]
    assert voice_app_ws_ticket.consume(ticket) == "a-owner"
    assert voice_app_ws_ticket.consume(ticket) is None


def test_voice_ticket_unauthorized(tmp_path, monkeypatch):
    client, _store = make_client(tmp_path, monkeypatch)
    response = client.post("/device/v1/app/voice/ticket")
    assert response.status_code == 401
