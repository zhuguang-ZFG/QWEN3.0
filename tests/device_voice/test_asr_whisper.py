"""Unit tests for Whisper ASR provider."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


class TestWhisperASRProvider:
    @pytest.mark.asyncio
    async def test_transcribe_success(self, monkeypatch):
        pytest.importorskip("faster_whisper")
        monkeypatch.setenv("WHISPER_MODEL", "tiny")

        from device_voice.providers.asr_whisper import WhisperASRProvider

        provider = WhisperASRProvider()

        fake_segment = MagicMock()
        fake_segment.text = "你好"
        fake_model = MagicMock()
        fake_model.transcribe.return_value = ([fake_segment], None)

        with patch("device_voice.providers.asr_whisper.WhisperModel", return_value=fake_model):
            result = await provider.transcribe(b"\x00\x00" * 1600, sample_rate=16000)

        assert result == "你好"

    @pytest.mark.asyncio
    async def test_transcribe_empty_audio(self):
        pytest.importorskip("faster_whisper")
        from device_voice.providers.asr_whisper import WhisperASRProvider

        provider = WhisperASRProvider()
        result = await provider.transcribe(b"")
        assert result == ""
