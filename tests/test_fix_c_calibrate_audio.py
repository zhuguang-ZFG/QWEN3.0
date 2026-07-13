"""Tests for fix-c: calibrate unmapping + audio_store path traversal."""

from __future__ import annotations

import pytest

from device_logic.audio_store import (
    _sanitize_id,
    resolve_storage_path,
    write_audio_file,
)
from device_logic.gateway import gateway_capability


# ── Fix 1: calibrate intent 误映射为 home ────────────────────────


class TestGatewayCapabilityCalibrate:
    def test_calibrate_returns_unsupported(self):
        """calibrate must fall through to unsupported-capability error."""
        _cap, _params, error = gateway_capability("calibrate", {})
        assert error is not None
        assert "unsupported" in error.lower()

    def test_home_still_works(self):
        """home intent must remain unaffected."""
        cap, params, error = gateway_capability("home", {})
        assert error is None
        assert cap == "home"

    def test_run_path_still_works(self):
        """run_path intent must remain unaffected."""
        cap, params, error = gateway_capability("run_path", {"foo": 1})
        assert error is None
        assert cap == "run_path"

    def test_unsupported_intent_returns_error(self):
        """random intent must return error."""
        _cap, _params, error = gateway_capability("nonexistent", {})
        assert error is not None
        assert "unsupported" in error.lower()


# ── Fix 2: audio_store 路径穿越 ──────────────────────────────────


class TestAudioStoreSanitizeId:
    def test_normal_id_passes(self):
        assert _sanitize_id("abc123._-") == "abc123._-"

    def test_single_dot_allowed(self):
        """a.b is a legal filename and must not be caught."""
        assert _sanitize_id("a.b") == "a.b"

    def test_leading_trailing_spaces_removed(self):
        assert _sanitize_id("  hello  ") == "hello"

    def test_empty_raises(self):
        with pytest.raises(ValueError, match="audio id is required"):
            _sanitize_id("")

    def test_dotdot_alone_rejected(self):
        """A value of exactly '..' would produce a path-traversal component."""
        with pytest.raises(ValueError, match="path traversal|traversal"):
            _sanitize_id("..")


class TestAudioStoreWriteAudioFile:
    def test_write_valid_id_succeeds(self, tmp_path, monkeypatch):
        monkeypatch.setattr("device_logic.audio_store.get_lima_data_dir", lambda: str(tmp_path))
        result = write_audio_file("dev-1", "audio-1", b"hello", ext="mp3")
        assert isinstance(result, str)
        expected = tmp_path / "device-app-audio" / "dev-1" / "audio-1.mp3"
        assert expected.exists()
        assert expected.read_bytes() == b"hello"

    def test_traversal_device_id_rejected(self, tmp_path, monkeypatch):
        """device_id='..' must be rejected and no file written outside root."""
        monkeypatch.setattr("device_logic.audio_store.get_lima_data_dir", lambda: str(tmp_path))
        with pytest.raises(ValueError):
            write_audio_file("..", "safe-audio", b"evil", ext="mp3")
        # No file should exist under device-app-audio
        root = tmp_path / "device-app-audio"
        assert not root.exists() or not any(root.iterdir())

    def test_symmetry_with_resolve_storage_path(self, tmp_path, monkeypatch):
        """A file written via write_audio_file must be resolvable."""
        monkeypatch.setattr("device_logic.audio_store.get_lima_data_dir", lambda: str(tmp_path))
        result = write_audio_file("dev-1", "audio-1", b"data", ext="mp3")
        resolved = resolve_storage_path(result)
        assert resolved is not None
        assert resolved.exists()
