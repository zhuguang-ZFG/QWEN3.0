"""Manual smoke test for cloud ASR/TTS providers.

Requires credentials in environment / .env:
  - DashScope: DASHSCOPE_API_KEY or ALIYUN_API_KEY
  - Aliyun: ALIBABA_CLOUD_ACCESS_KEY_ID, ALIBABA_CLOUD_ACCESS_KEY_SECRET,
            ALIBABA_NLS_APP_KEY
  - Doubao: DOUBAO_TTS_APPID, DOUBAO_TTS_ACCESS_TOKEN,
            DOUBAO_ASR_APPID, DOUBAO_ASR_ACCESS_TOKEN

Flow for each configured provider:
  1. TTS: text -> PCM audio
  2. ASR: PCM audio -> text
  3. Print latency and round-trip text.

Run:
    python scripts/smoke_voice_providers.py
"""

from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path

from dotenv import load_dotenv


def _load_env() -> None:
    env_path = Path(".env")
    if env_path.exists():
        load_dotenv(env_path)


def _has_dashscope_credentials() -> bool:
    return bool(os.environ.get("DASHSCOPE_API_KEY") or os.environ.get("ALIYUN_API_KEY"))


def _has_aliyun_credentials() -> bool:
    return all(
        os.environ.get(k)
        for k in (
            "ALIBABA_CLOUD_ACCESS_KEY_ID",
            "ALIBABA_CLOUD_ACCESS_KEY_SECRET",
            "ALIBABA_NLS_APP_KEY",
        )
    )


def _has_doubao_credentials() -> bool:
    return all(
        os.environ.get(k)
        for k in (
            "DOUBAO_TTS_APPID",
            "DOUBAO_TTS_ACCESS_TOKEN",
            "DOUBAO_ASR_APPID",
            "DOUBAO_ASR_ACCESS_TOKEN",
        )
    )


async def _test_dashscope() -> None:
    from device_voice.providers.asr_dashscope import DashScopeASRProvider
    from device_voice.providers.tts_dashscope import DashScopeTTSProvider

    text = "你好，这是一段测试语音。"
    sample_rate = 16000

    t0 = time.monotonic()
    tts = DashScopeTTSProvider()
    audio = await tts.synthesize(text, sample_rate=sample_rate)
    tts_ms = (time.monotonic() - t0) * 1000

    if not audio:
        print("  DashScope TTS returned empty audio")
        return

    t0 = time.monotonic()
    asr = DashScopeASRProvider()
    recognized = await asr.transcribe(audio, sample_rate=sample_rate)
    asr_ms = (time.monotonic() - t0) * 1000

    print(f"  DashScope TTS: {tts_ms:.0f}ms -> {len(audio)} bytes")
    print(f"  DashScope ASR: {asr_ms:.0f}ms -> '{recognized}'")
    print(f"  Round-trip match: {recognized.strip() == text.strip()}")


async def _test_aliyun() -> None:
    from device_voice.providers.asr_aliyun import AliyunASRProvider
    from device_voice.providers.tts_aliyun import AliyunTTSProvider

    text = "你好，这是一段测试语音。"
    sample_rate = 16000

    t0 = time.monotonic()
    tts = AliyunTTSProvider()
    audio = await tts.synthesize(text, sample_rate=sample_rate)
    tts_ms = (time.monotonic() - t0) * 1000

    if not audio:
        print("  Aliyun TTS returned empty audio")
        return

    t0 = time.monotonic()
    asr = AliyunASRProvider()
    recognized = await asr.transcribe(audio, sample_rate=sample_rate)
    asr_ms = (time.monotonic() - t0) * 1000

    print(f"  Aliyun TTS: {tts_ms:.0f}ms -> {len(audio)} bytes")
    print(f"  Aliyun ASR: {asr_ms:.0f}ms -> '{recognized}'")
    print(f"  Round-trip match: {recognized.strip() == text.strip()}")


async def _test_doubao() -> None:
    from device_voice.providers.asr_doubao import DoubaoASRProvider
    from device_voice.providers.tts_doubao import DoubaoTTSProvider

    text = "你好，这是一段测试语音。"
    sample_rate = 16000

    t0 = time.monotonic()
    tts = DoubaoTTSProvider()
    audio = await tts.synthesize(text, sample_rate=sample_rate)
    tts_ms = (time.monotonic() - t0) * 1000

    if not audio:
        print("  Doubao TTS returned empty audio")
        return

    t0 = time.monotonic()
    asr = DoubaoASRProvider()
    recognized = await asr.transcribe(audio, sample_rate=sample_rate)
    asr_ms = (time.monotonic() - t0) * 1000

    print(f"  Doubao TTS: {tts_ms:.0f}ms -> {len(audio)} bytes")
    print(f"  Doubao ASR: {asr_ms:.0f}ms -> '{recognized}'")
    print(f"  Round-trip match: {recognized.strip() == text.strip()}")


async def main() -> None:
    _load_env()

    tested = False

    if _has_dashscope_credentials():
        print("Testing DashScope ASR/TTS...")
        try:
            await _test_dashscope()
        except Exception as exc:
            print(f"  DashScope test failed: {exc}")
        tested = True
    else:
        print("Skipping DashScope: credentials not configured.")

    if _has_aliyun_credentials():
        print("Testing Alibaba NLS ASR/TTS...")
        try:
            await _test_aliyun()
        except Exception as exc:
            print(f"  Alibaba test failed: {exc}")
        tested = True
    else:
        print("Skipping Alibaba NLS: credentials not configured.")

    if _has_doubao_credentials():
        print("Testing Doubao ASR/TTS...")
        try:
            await _test_doubao()
        except Exception as exc:
            print(f"  Doubao test failed: {exc}")
        tested = True
    else:
        print("Skipping Doubao: credentials not configured.")

    if not tested:
        print("No cloud voice credentials found. Set env vars and retry.")
        print("See requirements_voice.txt and .env.example for details.")


if __name__ == "__main__":
    asyncio.run(main())
