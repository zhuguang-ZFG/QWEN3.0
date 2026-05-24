import json
import subprocess
import sys


def test_memory_daemon_ctl_status_outputs_json():
    result = subprocess.run(
        [sys.executable, "scripts/memory_daemon_ctl.py", "status"],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(result.stdout)
    assert "running" in payload
    assert "inbox_dir" in payload


def test_memory_daemon_ctl_run_once_processes_custom_inbox(tmp_path, monkeypatch):
    monkeypatch.setenv("LIMA_MEMORY_INBOX", str(tmp_path))
    monkeypatch.setenv("LIMA_SESSION_DB", str(tmp_path / "sessions.db"))
    inbox_file = tmp_path / "memory.md"
    inbox_file.write_text("- test passed for memory daemon ctl\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, "scripts/memory_daemon_ctl.py", "run-once"],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(result.stdout)
    assert payload["ingested"] == 1
    assert (tmp_path / ".processed" / "memory.md").exists()
