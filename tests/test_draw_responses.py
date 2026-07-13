"""Tests for device_gateway/draw_responses.py — sanitized error messages."""

from __future__ import annotations

from device_gateway.draw_responses import (
    PUBLIC_DRAW_MODEL_LABEL,
    _sanitize_error,
    build_failed_response,
    build_partial_response,
)


class TestSanitizeError:
    def test_plain_message_preserved(self):
        assert _sanitize_error("Something went wrong") == "Something went wrong"

    def test_removes_http_url(self):
        result = _sanitize_error("failed: http://internal.donglicao.com/x")
        assert "[URL]" in result
        assert "donglicao" not in result

    def test_removes_https_url(self):
        result = _sanitize_error("error at https://api.secret.com/v1/call")
        assert "[URL]" in result
        assert "secret.com" not in result

    def test_removes_file_path(self):
        result = _sanitize_error("crash in /home/user/file.py")
        assert "[PATH]" in result
        assert "/home/user" not in result

    def test_removes_windows_path(self):
        result = _sanitize_error("error C:\\Users\\test\\file.txt")
        assert "[PATH]" in result

    def test_truncates_long_message(self):
        result = _sanitize_error("x" * 500)
        assert len(result) <= 200

    def test_empty_message_fallback(self):
        assert _sanitize_error("") == "An error occurred"


class TestBuildFailedResponse:
    def test_sanitizes_error(self):
        result = build_failed_response("model-x", "http://internal/x")
        assert result["status"] == "failed"
        assert result["model"] == PUBLIC_DRAW_MODEL_LABEL
        assert "[URL]" in result["error"]
        assert "internal" not in result["error"]

    def test_plain_error_preserved(self):
        result = build_failed_response("model-x", "device offline")
        assert result["error"] == "device offline"


class TestBuildPartialResponse:
    def test_sanitizes_error(self):
        result = build_partial_response("https://cdn/img.png", 100, 200, "model-x", "/home/user/crash")
        assert result["status"] == "partial"
        assert "[PATH]" in result["error"]
        assert "/home/user" not in result["error"]
