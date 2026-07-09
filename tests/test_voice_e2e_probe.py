"""Unit tests for production voice E2E probe helpers."""

from __future__ import annotations

import json
import sys
from contextlib import asynccontextmanager
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from voice_e2e_http import fake_wav_bytes
from voice_e2e_probe import (
    exit_code_for_results,
    probe_auth_me,
    probe_voice_ticket,
    probe_voice_transcribe_auth,
    probe_voice_transcribe_unauth,
    resolve_device_app_token,
    run_voice_e2e_probes,
    ProbeResult,
    _probe_voice_ws_path,
)


def test_probe_wav_fixture_exists():
    from voice_e2e_http import DEFAULT_PROBE_WAV, probe_wav_bytes

    assert DEFAULT_PROBE_WAV.is_file(), "run scripts/generate_voice_e2e_fixture_vps.py first"
    wav = probe_wav_bytes()
    assert wav[:4] == b"RIFF"
    assert len(wav) > 1000


def test_transcript_ok_strict():
    from voice_e2e_probe import _transcript_ok

    assert _transcript_ok("画一只猫", strict=True)
    assert not _transcript_ok("", strict=True)
    assert _transcript_ok("hello", strict=False)


def test_fake_wav_bytes_has_riff_header():
    wav = fake_wav_bytes(b"\x01\x02")
    assert wav[:4] == b"RIFF"
    assert wav[8:12] == b"WAVE"


def test_resolve_device_app_token_from_env(monkeypatch):
    monkeypatch.setenv("LIMA_VERIFY_DEVICE_APP_TOKEN", "jwt-test")
    token, source = resolve_device_app_token("chat.example.com")
    assert token == "jwt-test"
    assert "LIMA_VERIFY_DEVICE_APP_TOKEN" in source


def test_resolve_device_app_token_wechat_login(monkeypatch):
    monkeypatch.delenv("LIMA_VERIFY_DEVICE_APP_TOKEN", raising=False)
    monkeypatch.setenv("LIMA_VERIFY_WECHAT_CODE", "wx-code-1")

    calls: list[tuple] = []

    def fake_post(host, path, body=None, *, bearer="", timeout=90):
        calls.append((host, path, body, bearer))
        return 200, {"token": "from-wechat", "accountId": "acc-1"}

    monkeypatch.setattr("voice_e2e_probe.post_json", fake_post)
    token, source = resolve_device_app_token("chat.example.com")
    assert token == "from-wechat"
    assert source.startswith("wechat:")
    assert calls[0][1] == "/device/v1/app/auth/login"


def test_probe_transcribe_unauth(monkeypatch):
    monkeypatch.setattr("voice_e2e_probe.post_multipart", lambda *a, **k: (401, {}))
    result = probe_voice_transcribe_unauth("host")
    assert result.status == "pass"


def test_probe_transcribe_auth_503_warn(monkeypatch):
    monkeypatch.setattr(
        "voice_e2e_probe.post_multipart",
        lambda *a, **k: (503, {"detail": "ASR is not configured"}),
    )
    result = probe_voice_transcribe_auth("host", "jwt", strict=False)
    assert result.status == "warn"


def test_probe_transcribe_auth_503_strict(monkeypatch):
    monkeypatch.setattr(
        "voice_e2e_probe.post_multipart",
        lambda *a, **k: (503, {"detail": "ASR is not configured"}),
    )
    result = probe_voice_transcribe_auth("host", "jwt", strict=True)
    assert result.status == "fail"


def test_probe_auth_me_and_ticket(monkeypatch):
    monkeypatch.setattr("voice_e2e_probe.get_json", lambda host, path, **k: (200, {"accountId": "a1"}))
    assert probe_auth_me("host", "jwt").status == "pass"
    monkeypatch.setattr(
        "voice_e2e_probe.post_json",
        lambda host, path, body=None, **k: (200, {"ticket": "t-1", "expires_in": 60}),
    )
    assert probe_voice_ticket("host", "jwt").status == "pass"


@pytest.mark.asyncio
async def test_probe_voice_ws_transcript(monkeypatch):
    class FakeWs:
        async def send(self, payload):
            self.payloads = getattr(self, "payloads", []) + [payload]

        async def recv(self):
            return json.dumps({"type": "transcript", "text": "hello", "is_final": True})

    @asynccontextmanager
    async def fake_connect(_url):
        yield FakeWs()

    result = await _probe_voice_ws_path(
        "host",
        "ticket-1",
        "/v1/voice",
        strict=False,
        connect_ws=fake_connect,
    )
    assert result.status == "pass"
    assert "transcript" in result.message


@pytest.mark.asyncio
async def test_probe_voice_ws_asr_unconfigured_warn(monkeypatch):
    class Closed1013(Exception):
        code = 1013

    @asynccontextmanager
    async def fake_connect(_url):
        raise Closed1013("try again later")
        yield  # pragma: no cover

    result = await _probe_voice_ws_path(
        "host",
        "ticket-1",
        "/v1/voice",
        strict=False,
        connect_ws=fake_connect,
    )
    assert result.status == "warn"


@pytest.mark.asyncio
async def test_probe_voice_ws_error_frame_warns_when_not_strict():
    class FakeWs:
        async def send(self, _payload):
            return None

        async def recv(self):
            return json.dumps({"type": "error", "message": "ASR failed"})

    @asynccontextmanager
    async def fake_connect(_url):
        yield FakeWs()

    result = await _probe_voice_ws_path(
        "host",
        "ticket-1",
        "/v1/voice",
        strict=False,
        connect_ws=fake_connect,
    )
    assert result.status == "warn"


@pytest.mark.asyncio
async def test_run_voice_e2e_probes_skip_without_token(monkeypatch):
    monkeypatch.delenv("LIMA_VERIFY_DEVICE_APP_TOKEN", raising=False)
    monkeypatch.delenv("LIMA_VERIFY_WECHAT_CODE", raising=False)
    monkeypatch.setattr("voice_e2e_probe.post_multipart", lambda *a, **k: (401, {}))
    results = await run_voice_e2e_probes("host", include_ws=False)
    names = [item.name for item in results]
    assert "voice_transcribe_unauth" in names
    assert "voice_auth_e2e" in names
    assert results[-1].status == "skip"


def test_exit_code_for_results():
    assert exit_code_for_results([ProbeResult("a", "pass", "")]) == 0
    assert exit_code_for_results([ProbeResult("a", "warn", "")]) == 0
    assert exit_code_for_results([ProbeResult("a", "fail", "")]) == 1
