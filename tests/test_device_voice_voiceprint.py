"""Unit tests for voiceprint.py stub."""

from __future__ import annotations

import asyncio


class TestVoiceprintProvider:
    """Tests for voiceprint.py stub."""

    def test_speaker_identity_defaults(self):
        from device_voice.voiceprint import SpeakerIdentity

        sid = SpeakerIdentity()
        assert sid.member_id == ""
        assert sid.is_known is False
        assert sid.confidence == 0.0

    def test_identify_speaker_without_model(self):
        from device_voice.voiceprint import VoiceprintProvider

        provider = VoiceprintProvider()
        result = asyncio.run(provider.identify_speaker(b"", "dev-1"))
        assert result.member_id == ""
        assert result.is_known is False
        assert result.reason == "extraction_failed"
