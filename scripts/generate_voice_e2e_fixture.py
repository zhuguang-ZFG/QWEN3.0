#!/usr/bin/env python3
"""Generate scripts/fixtures/voice_probe_draw_cat.wav for production E2E (maintainer-only)."""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import sys
from pathlib import Path

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
OUTPUT_WAV = FIXTURE_DIR / "voice_probe_draw_cat.wav"
PROBE_TEXT = "画一只猫"
VOICE = "zh-CN-XiaoxiaoNeural"


async def _synthesize_mp3(mp3_path: Path) -> None:
    import edge_tts

    communicate = edge_tts.Communicate(PROBE_TEXT, VOICE)
    await communicate.save(str(mp3_path))


def _resolve_ffmpeg() -> str:
    for candidate in (
        os.environ.get("FFMPEG_PATH", "").strip(),
        shutil.which("ffmpeg") or "",
    ):
        if candidate and Path(candidate).exists():
            return candidate
    probe = subprocess.run(
        ["powershell", "-NoProfile", "-Command", "(Get-Command ffmpeg -ErrorAction SilentlyContinue).Source"],
        capture_output=True,
        text=True,
        check=False,
    )
    path = (probe.stdout or "").strip()
    if path and Path(path).exists():
        return path
    raise RuntimeError("ffmpeg not found; set FFMPEG_PATH")


def _convert_to_wav(mp3_path: Path, wav_path: Path) -> None:
    ffmpeg = _resolve_ffmpeg()
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-loglevel",
            "error",
            "-i",
            str(mp3_path),
            "-ar",
            "16000",
            "-ac",
            "1",
            "-sample_fmt",
            "s16",
            str(wav_path),
        ],
        check=True,
    )


def main() -> int:
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    mp3_path = FIXTURE_DIR / "_voice_probe_draw_cat.mp3"
    try:
        asyncio.run(_synthesize_mp3(mp3_path))
        _convert_to_wav(mp3_path, OUTPUT_WAV)
    finally:
        mp3_path.unlink(missing_ok=True)
    size_kb = OUTPUT_WAV.stat().st_size // 1024
    print(f"Wrote {OUTPUT_WAV} ({size_kb} KB) text={PROBE_TEXT!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
