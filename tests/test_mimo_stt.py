"""MiMo STT module tests."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import mimo_stt


def test_disabled_without_key(monkeypatch):
    monkeypatch.delenv("MIMO_TTS_KEY", raising=False)
    monkeypatch.delenv("MIMO_API_KEY", raising=False)
    assert mimo_stt.transcribe_bytes(b"fake", "audio/wav") is None


def test_no_network_without_key(monkeypatch):
    monkeypatch.delenv("MIMO_TTS_KEY", raising=False)
    monkeypatch.delenv("MIMO_API_KEY", raising=False)
    called = False

    class FailClient:
        def __init__(self, *_a, **_k):
            nonlocal called
            called = True

    monkeypatch.setattr(mimo_stt.httpx, "Client", FailClient)
    assert mimo_stt.transcribe_bytes(b"x" * 100, "audio/wav") is None
    assert called is False


def test_extract_transcript_reasoning_field():
    payload = {
        "choices": [{
            "message": {
                "content": "",
                "reasoning_content": "你好世界",
            },
        }],
    }
    assert mimo_stt._extract_transcript(payload) == "你好世界"
