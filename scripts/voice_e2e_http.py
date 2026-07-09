"""Shared HTTP helpers for device-app voice production probes."""

from __future__ import annotations

import io
import json
import os
import ssl
import uuid
import wave
import urllib.error
import urllib.request
from pathlib import Path

UA = {"User-Agent": "LiMaVoiceE2E/1.0", "Content-Type": "application/json"}
DEFAULT_PROBE_WAV = Path(__file__).resolve().parent / "fixtures" / "voice_probe_draw_cat.wav"
PROBE_PCM_FRAME_BYTES = 1280


def https_ctx() -> ssl.SSLContext:
    return ssl.create_default_context()


def fake_wav_bytes(payload: bytes = b"\x00\x00" * 160) -> bytes:
    """Minimal mono WAV (44-byte header + PCM) for unauth probes."""
    data_size = len(payload)
    return (
        b"RIFF"
        + (36 + data_size).to_bytes(4, "little")
        + b"WAVE"
        + b"fmt "
        + (16).to_bytes(4, "little")
        + b"\x00" * 16
        + b"data"
        + data_size.to_bytes(4, "little")
        + payload
    )


def probe_wav_bytes() -> bytes:
    """Speech sample for authenticated transcribe / WS probes."""
    override = os.environ.get("LIMA_VOICE_E2E_AUDIO_PATH", "").strip()
    if override:
        return Path(override).read_bytes()
    if DEFAULT_PROBE_WAV.is_file():
        return DEFAULT_PROBE_WAV.read_bytes()
    return fake_wav_bytes()


def probe_pcm_chunks(*, frame_bytes: int = PROBE_PCM_FRAME_BYTES) -> list[bytes]:
    """Split probe WAV into PCM frames (mini-program frameSize=1280)."""
    wav = probe_wav_bytes()
    if len(wav) >= 12 and wav[:4] == b"RIFF" and wav[8:12] == b"WAVE":
        with wave.open(io.BytesIO(wav), "rb") as wav_file:
            pcm = wav_file.readframes(wav_file.getnframes())
    else:
        pcm = wav
    if not pcm:
        return [b"\x00\x00"]
    chunks = [pcm[index : index + frame_bytes] for index in range(0, len(pcm), frame_bytes)]
    return [chunk for chunk in chunks if chunk] or [pcm]


def get_json(host: str, path: str, *, bearer: str = "", timeout: float = 90) -> tuple[int, dict]:
    headers = dict(UA)
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
    req = urllib.request.Request(f"https://{host}{path}", headers=headers)
    try:
        with urllib.request.urlopen(req, context=https_ctx(), timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            return exc.code, json.loads(raw)
        except json.JSONDecodeError:
            return exc.code, {"detail": raw}


def post_json(
    host: str,
    path: str,
    body: dict | None = None,
    *,
    bearer: str = "",
    timeout: float = 90,
) -> tuple[int, dict]:
    headers = dict(UA)
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
    payload = json.dumps(body or {}).encode("utf-8")
    req = urllib.request.Request(
        f"https://{host}{path}",
        data=payload,
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, context=https_ctx(), timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            return exc.code, json.loads(raw)
        except json.JSONDecodeError:
            return exc.code, {"detail": raw}


def post_multipart(
    host: str,
    path: str,
    files: dict[str, tuple[str, bytes, str]],
    *,
    bearer: str = "",
    form: dict[str, str] | None = None,
    timeout: float = 90,
) -> tuple[int, dict]:
    boundary = f"----LiMaVoiceE2E{uuid.uuid4().hex}"
    body = bytearray()
    for key, value in (form or {}).items():
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode())
        body.extend(str(value).encode())
        body.extend(b"\r\n")
    for name, (filename, content, content_type) in files.items():
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(
            f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'.encode(),
        )
        body.extend(f"Content-Type: {content_type}\r\n\r\n".encode())
        body.extend(content)
        body.extend(b"\r\n")
    body.extend(f"--{boundary}--\r\n".encode())
    headers = dict(UA)
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
    headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
    req = urllib.request.Request(
        f"https://{host}{path}",
        data=bytes(body),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, context=https_ctx(), timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            return exc.code, json.loads(raw)
        except json.JSONDecodeError:
            return exc.code, {"detail": raw}
