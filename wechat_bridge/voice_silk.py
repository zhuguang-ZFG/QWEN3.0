"""Encode TTS audio as Tencent SILK for Weixin voice bubbles (not file attachment)."""

from __future__ import annotations

import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Tuple

log = logging.getLogger(__name__)

# iLink outbound voice_item uses 24 kHz in gateway/platforms/weixin.py
SILK_PCM_RATE = int(os.environ.get("LIMA_WEIXIN_SILK_RATE", "24000"))


def _duration_to_ms(duration: object, silk_path: str) -> int:
    try:
        sec = float(duration)
        if sec > 0:
            return max(1000, int(sec * 1000))
    except (TypeError, ValueError):
        pass
    # ~5KB/s rough fallback for tencent silk
    size = Path(silk_path).stat().st_size
    return max(1000, min(60000, int(size / 5)))


def wav_bytes_to_silk_path(wav: bytes) -> Optional[Tuple[str, int]]:
    """Return (path to temp .silk, playtime_ms) or None if encoding failed."""
    if not wav or len(wav) < 44:
        return None
    fd, wav_path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    pcm_path = wav_path + ".pcm"
    silk_path = wav_path + ".silk"
    try:
        Path(wav_path).write_bytes(wav)
        proc = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                wav_path,
                "-vn",
                "-ar",
                str(SILK_PCM_RATE),
                "-ac",
                "1",
                "-f",
                "s16le",
                pcm_path,
            ],
            capture_output=True,
            timeout=20,
        )
        if proc.returncode != 0:
            log.warning("ffmpeg pcm failed: %s", (proc.stderr or b"")[:200])
            return None
        try:
            import pilk
        except ImportError:
            log.warning("pilk not installed — cannot send WeChat voice bubble")
            return None
        duration = pilk.encode(pcm_path, silk_path, pcm_rate=SILK_PCM_RATE, tencent=True)
        if not Path(silk_path).is_file() or Path(silk_path).stat().st_size < 10:
            return None
        play_ms = _duration_to_ms(duration, silk_path)
        return silk_path, play_ms
    except Exception as exc:
        log.warning("silk encode failed: %s", exc)
        return None
    finally:
        for p in (wav_path, pcm_path):
            if p and os.path.isfile(p):
                try:
                    os.unlink(p)
                except OSError:
                    pass
