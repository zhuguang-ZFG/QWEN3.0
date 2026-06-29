"""Tests for device_ota.state_store."""

from pathlib import Path
from unittest.mock import patch

from device_ota.state_store import load_state, save_section


def test_save_section_retries_on_windows_permission_error(tmp_path):
    """save_section retries replace() on transient Windows file locking."""
    path = tmp_path / "state.json"
    original_replace = Path.replace
    calls: list[str] = []

    def _fake_replace(self: Path, target: str) -> Path:
        calls.append(str(target))
        if len(calls) == 1:
            raise PermissionError(13, "Permission denied")
        return original_replace(self, target)

    with patch.object(Path, "replace", _fake_replace):
        save_section(path, "gate", {"ok": True})

    assert len(calls) == 2
    assert load_state(path).get("gate", {}).get("ok") is True
