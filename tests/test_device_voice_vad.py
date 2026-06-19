"""Unit tests for VAD provider and state management."""

from __future__ import annotations

import pytest


class TestVADProvider:
    """Tests for VAD provider and state management."""

    def test_create_silero(self):
        from device_voice.vad import create_vad_provider

        provider = create_vad_provider("silero")
        from device_voice.providers.vad_silero import SileroVADProvider

        assert isinstance(provider, SileroVADProvider)

    def test_vad_state_defaults(self):
        from device_voice.vad import VADState

        state = VADState()
        assert state.is_speaking is False
        assert len(state.speech_buffer) == 0
        assert state.silence_frames == 0

    def test_silero_detect_empty_without_model(self, monkeypatch):
        """SileroVAD without ONNX model must raise, not silently pass-through."""
        monkeypatch.setenv("LIMA_VOICE_MODEL_DIR", "/nonexistent/path")
        from device_voice.vad import create_vad_provider, VADModelUnavailableError, VADState

        provider = create_vad_provider("silero")
        state = VADState()
        fake_pcm = b"\x00\x00" * 512  # 512 samples of silence
        with pytest.raises(VADModelUnavailableError):
            provider.detect(fake_pcm, state)

    def test_vad_reset_clears_state(self):
        from device_voice.vad import VADState
        from device_voice.providers.vad_silero import SileroVADProvider

        state = VADState(is_speaking=True, silence_frames=100)
        state.speech_buffer.extend(b"test")
        provider = SileroVADProvider()
        provider.reset(state)
        assert state.is_speaking is False
        assert len(state.speech_buffer) == 0
        assert state.silence_frames == 0
