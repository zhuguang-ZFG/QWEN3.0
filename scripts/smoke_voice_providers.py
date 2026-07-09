"""Manual smoke test for device_voice DashScope ASR.

Requires DASHSCOPE_API_KEY or ALIYUN_API_KEY and LIMA_VOICE_ENABLED=1.

Run:
    python scripts/smoke_voice_providers.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

from config.voice_settings import VOICE, VOICE_PROVIDERS
from device_voice.asr import AsrNotConfiguredError, get_asr_provider, transcribe_audio
from device_voice.audio_format import pcm_to_wav_bytes


def _has_credentials() -> bool:
    return bool(VOICE_PROVIDERS.dashscope_asr.api_key)


async def _run() -> None:
    provider_name = (VOICE.asr_provider or "dashscope").strip().lower()
    if provider_name == "dashscope" and not _has_credentials():
        print("Skipping DashScope ASR: DASHSCOPE_API_KEY / ALIYUN_API_KEY not configured.")
        return
    if not VOICE.enabled:
        print("Set LIMA_VOICE_ENABLED=1 to run the smoke test.")
        return

    provider = get_asr_provider()
    print(f"Provider: {provider.__class__.__name__} ({provider_name})")
    wav = pcm_to_wav_bytes(b"\x00\x00" * 800, sample_rate=16000)
    try:
        text = await transcribe_audio(wav)
    except AsrNotConfiguredError as exc:
        print(f"ASR not configured: {exc}")
        return
    except Exception as exc:
        print(f"ASR smoke failed: {type(exc).__name__}: {exc}")
        raise

    print(f"Transcript: {text!r}")


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
