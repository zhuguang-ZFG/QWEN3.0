"""Tests for device app voice routes (M0): transcribe + ticket.

薄端点测试：ASR 转写 + 意图解析（不创建任务），以及实时流 WS ticket 签发。
所有 ASR 调用均 mock，不依赖真实 ASR 服务。
"""

from __future__ import annotations

import types

import pytest

import routes.device_app_voice as device_app_voice
from device_app_helpers import client as make_client
from device_app_helpers import headers, seed_account_and_device


def _fake_wav(payload: bytes = b"\x00\x00" * 160) -> bytes:
    """构造最小 WAV（44 字节 RIFF header + data 块）。ASR 被 mock，header 字段值不影响。"""
    return b"RIFF" + b"\x00" * 36 + b"data" + len(payload).to_bytes(4, "little") + payload


def _mock_asr(monkeypatch, text: str = "画一只猫", capture: dict | None = None) -> None:
    async def fake_transcribe(audio_data: bytes, *, sample_rate: int = 16000) -> str:
        if capture is not None:
            capture["audio_data"] = audio_data
            capture["sample_rate"] = sample_rate
        return text

    monkeypatch.setattr(
        device_app_voice,
        "get_asr_provider",
        lambda: types.SimpleNamespace(transcribe=fake_transcribe),
    )


def _mock_asr_raises(monkeypatch) -> None:
    async def fake_transcribe(audio_data: bytes, *, sample_rate: int = 16000) -> str:
        raise RuntimeError("asr backend unavailable")

    monkeypatch.setattr(
        device_app_voice,
        "get_asr_provider",
        lambda: types.SimpleNamespace(transcribe=fake_transcribe),
    )


@pytest.fixture
def voice_client(tmp_path, monkeypatch):
    client, _store = make_client(tmp_path, monkeypatch)
    seed_account_and_device()
    return client


# ── transcribe：意图分类 ─────────────────────────────────────────────────────


def test_transcribe_draw_intent(voice_client, monkeypatch):
    _mock_asr(monkeypatch, text="画一只猫")
    resp = voice_client.post(
        "/device/v1/app/voice/transcribe",
        files={"audio": ("cmd.wav", _fake_wav(), "audio/wav")},
        headers=headers("a-owner"),
    )
    assert resp.status_code == 200
    data = resp.json()["data"] if "data" in resp.json() else resp.json()
    assert data["text"] == "画一只猫"
    assert data["intent"]["capability"] == "draw_generated"


def test_transcribe_write_intent(voice_client, monkeypatch):
    _mock_asr(monkeypatch, text="写你好")
    resp = voice_client.post(
        "/device/v1/app/voice/transcribe",
        files={"audio": ("cmd.wav", _fake_wav(), "audio/wav")},
        headers=headers("a-owner"),
    )
    assert resp.status_code == 200
    data = resp.json().get("data", resp.json())
    assert data["intent"]["capability"] == "write_text"


def test_transcribe_home_intent(voice_client, monkeypatch):
    _mock_asr(monkeypatch, text="归零")
    resp = voice_client.post(
        "/device/v1/app/voice/transcribe",
        files={"audio": ("cmd.wav", _fake_wav(), "audio/wav")},
        headers=headers("a-owner"),
    )
    assert resp.status_code == 200
    data = resp.json().get("data", resp.json())
    assert data["intent"]["capability"] == "home"


# ── transcribe：鉴权与输入校验 ───────────────────────────────────────────────


def test_transcribe_unauthorized(voice_client, monkeypatch):
    _mock_asr(monkeypatch)
    resp = voice_client.post(
        "/device/v1/app/voice/transcribe",
        files={"audio": ("cmd.wav", _fake_wav(), "audio/wav")},
    )
    assert resp.status_code == 401


def test_transcribe_empty_audio(voice_client, monkeypatch):
    _mock_asr(monkeypatch)
    resp = voice_client.post(
        "/device/v1/app/voice/transcribe",
        files={"audio": ("cmd.wav", b"", "audio/wav")},
        headers=headers("a-owner"),
    )
    assert resp.status_code == 400


def test_transcribe_oversized_audio(voice_client, monkeypatch):
    _mock_asr(monkeypatch)
    oversized = b"\x00" * (device_app_voice.MAX_AUDIO_BYTES + 1)
    resp = voice_client.post(
        "/device/v1/app/voice/transcribe",
        files={"audio": ("cmd.wav", oversized, "audio/wav")},
        headers=headers("a-owner"),
    )
    assert resp.status_code == 413


def test_transcribe_asr_failure(voice_client, monkeypatch):
    _mock_asr_raises(monkeypatch)
    resp = voice_client.post(
        "/device/v1/app/voice/transcribe",
        files={"audio": ("cmd.wav", _fake_wav(), "audio/wav")},
        headers=headers("a-owner"),
    )
    assert resp.status_code == 503
    body = resp.json()
    # 不静默降级：错误信息应可见
    assert "asr" in str(body).lower() or "message" in body


def test_transcribe_strips_wav_header(voice_client, monkeypatch):
    capture: dict = {}
    _mock_asr(monkeypatch, text="画一只猫", capture=capture)
    payload = b"\x11\x22" * 160
    resp = voice_client.post(
        "/device/v1/app/voice/transcribe",
        files={"audio": ("cmd.wav", _fake_wav(payload), "audio/wav")},
        headers=headers("a-owner"),
    )
    assert resp.status_code == 200
    # 传给 ASR 的应是剥掉 RIFF header 的 raw PCM
    assert capture["audio_data"][:4] != b"RIFF"
    assert capture["audio_data"] == payload
    assert capture["sample_rate"] == 16000


# ── voice ticket ─────────────────────────────────────────────────────────────


def test_voice_ticket_returns_ticket(voice_client):
    resp = voice_client.post(
        "/device/v1/app/voice/ticket",
        headers=headers("a-owner"),
    )
    assert resp.status_code == 200
    data = resp.json().get("data", resp.json())
    assert data["ticket"]
    assert data["expires_in"] == 30


def test_voice_ticket_unauthorized(voice_client):
    resp = voice_client.post("/device/v1/app/voice/ticket")
    assert resp.status_code == 401
