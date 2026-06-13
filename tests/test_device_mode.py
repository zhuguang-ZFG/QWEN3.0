"""Tests for device mode configuration."""
import os
from device_mode import is_device_mode, should_skip_context_pipeline


def test_device_mode_off_by_default():
    """Device mode is off when env var not set."""
    old_val = os.environ.pop("LIMA_DEVICE_MODE", None)
    try:
        assert not is_device_mode()
        assert not should_skip_context_pipeline()
    finally:
        if old_val:
            os.environ["LIMA_DEVICE_MODE"] = old_val


def test_device_mode_enabled_with_env_var(monkeypatch):
    """Device mode is on when LIMA_DEVICE_MODE=1."""
    monkeypatch.setenv("LIMA_DEVICE_MODE", "1")
    assert is_device_mode()
    assert should_skip_context_pipeline()


def test_device_mode_ignores_non_one_values(monkeypatch):
    """Device mode only activates on exactly '1'."""
    for val in ["0", "true", "yes", "on", ""]:
        monkeypatch.setenv("LIMA_DEVICE_MODE", val)
        assert not is_device_mode()
