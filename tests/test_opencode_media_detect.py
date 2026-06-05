"""Tests for opencode_media_detect.py — unsupported media graceful degradation."""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from opencode_media_detect import (
    mime_to_modality,
    filter_unsupported_media,
)


class TestMimeToModality:
    def test_image(self):
        assert mime_to_modality("image/png") == "image"
        assert mime_to_modality("image/jpeg") == "image"

    def test_audio(self):
        assert mime_to_modality("audio/wav") == "audio"
        assert mime_to_modality("audio/mp3") == "audio"

    def test_video(self):
        assert mime_to_modality("video/mp4") == "video"

    def test_pdf(self):
        assert mime_to_modality("application/pdf") == "pdf"

    def test_unknown(self):
        assert mime_to_modality("text/plain") is None
        assert mime_to_modality("application/json") is None


class TestFilterUnsupportedMedia:
    def test_supported_image_kept(self):
        msgs = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": "data:image/png;base64,abc123"},
                ],
            },
        ]
        result = filter_unsupported_media(msgs, "openai", "gpt-4o", "openai")
        assert result[0]["content"][0]["type"] == "image"

    def test_unsupported_audio_replaced(self):
        msgs = [
            {
                "role": "user",
                "content": [
                    {"type": "file", "mediaType": "audio/wav", "filename": "recording.wav"},
                ],
            },
        ]
        result = filter_unsupported_media(msgs, "anthropic", "claude-3", "anthropic")
        assert result[0]["content"][0]["type"] == "text"
        assert "does not support audio" in result[0]["content"][0]["text"]

    def test_unsupported_pdf_replaced(self):
        msgs = [
            {
                "role": "user",
                "content": [
                    {"type": "file", "mediaType": "application/pdf", "filename": "doc.pdf"},
                ],
            },
        ]
        # qwen only supports image
        result = filter_unsupported_media(msgs, "qwen", "qwen-max", "qwen")
        assert result[0]["content"][0]["type"] == "text"
        assert '"doc.pdf"' in result[0]["content"][0]["text"]
        assert "pdf" in result[0]["content"][0]["text"]

    def test_empty_base64_image(self):
        msgs = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": "data:image/png;base64,"},
                ],
            },
        ]
        result = filter_unsupported_media(msgs, "openai", "gpt-4o", "openai")
        assert result[0]["content"][0]["type"] == "text"
        assert "empty or corrupted" in result[0]["content"][0]["text"]

    def test_non_user_messages_unchanged(self):
        msgs = [
            {"role": "assistant", "content": [{"type": "text", "text": "Hi"}]},
        ]
        result = filter_unsupported_media(msgs, "openai", "gpt-4o", "openai")
        assert result == msgs

    def test_string_content_unchanged(self):
        msgs = [{"role": "user", "content": "Hello"}]
        result = filter_unsupported_media(msgs, "openai", "gpt-4o", "openai")
        assert result == msgs

    def test_deepseek_no_media_support(self):
        msgs = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": "data:image/png;base64,abc123"},
                ],
            },
        ]
        result = filter_unsupported_media(msgs, "deepseek", "DeepSeek-R1", "deepseek_reasoning")
        assert result[0]["content"][0]["type"] == "text"
        assert "does not support image" in result[0]["content"][0]["text"]

    def test_google_supports_all(self):
        msgs = [
            {
                "role": "user",
                "content": [
                    {"type": "file", "mediaType": "application/pdf", "filename": "doc.pdf"},
                    {"type": "file", "mediaType": "audio/wav", "filename": "audio.wav"},
                    {"type": "file", "mediaType": "video/mp4", "filename": "video.mp4"},
                ],
            },
        ]
        result = filter_unsupported_media(msgs, "google_gemini", "gemini-2.5-pro", "google")
        # All should be kept since Google supports all modalities
        assert all(p["type"] == "file" for p in result[0]["content"])

    def test_original_not_mutated(self):
        msgs = [
            {
                "role": "user",
                "content": [
                    {"type": "file", "mediaType": "audio/wav", "filename": "a.wav"},
                ],
            },
        ]
        original_content = list(msgs[0]["content"])
        filter_unsupported_media(msgs, "anthropic", "claude-3", "anthropic")
        assert msgs[0]["content"] == original_content
