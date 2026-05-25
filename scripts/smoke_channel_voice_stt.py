#!/usr/bin/env python3
"""Smoke: WeChat channel voice STT prerequisites (MiMo + ffmpeg)."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _ok(msg: str) -> None:
    print(f"OK  {msg}")


def _warn(msg: str) -> None:
    print(f"WARN  {msg}")


def _fail(msg: str) -> int:
    print(f"FAIL  {msg}")
    return 1


def main() -> int:
    import mimo_stt
    from channel_gateway.keyword_router import normalize_guest_text

    if normalize_guest_text("菜单") != "/menu":
        return _fail("keyword_router menu")
    _ok("keyword_router")

    key = mimo_stt._api_key()
    if not key:
        _warn("MIMO_TTS_KEY / MIMO_API_KEY unset — MiMo STT will skip")
    else:
        _ok("MiMo API key present")

    if shutil.which("ffmpeg"):
        _ok("ffmpeg on PATH")
    else:
        _warn("ffmpeg missing — WeChat .silk voice may not transcribe")

    if key and shutil.which("ffmpeg"):
        # minimal silent wav header is not valid; skip live API unless LIMA_VOICE_STT_LIVE=1
        if os.environ.get("LIMA_VOICE_STT_LIVE") == "1":
            wav = (
                b"RIFF$\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00"
                b"@\x1f\x00\x00\x80>\x00\x00\x02\x00\x10\x00data\x00\x00\x00\x00"
            )
            text = mimo_stt.transcribe_bytes(wav, "audio/wav", name="smoke.wav")
            if text:
                _ok(f"MiMo STT live returned: {text[:40]}")
            else:
                return _fail("MiMo STT live returned empty")
        else:
            _ok("set LIMA_VOICE_STT_LIVE=1 to run live MiMo STT call")

    try:
        r = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/test_channel_keyword_voice_ux.py", "-q"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=60,
        )
        if r.returncode != 0:
            print(r.stdout, r.stderr)
            return _fail("pytest keyword/voice ux")
        _ok("pytest test_channel_keyword_voice_ux")
    except Exception as exc:
        return _fail(f"pytest: {exc}")

    print("smoke_channel_voice_stt done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
