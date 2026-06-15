"""Tests for async MiMo job runner."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from lima_mcp_stdio import job_runner as jr


def test_start_async_run_returns_job_id(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MIMO_MCP_ARTIFACT_DIR", str(tmp_path / "artifacts"))

    mock_proc = MagicMock()
    mock_proc.pid = 12345

    with patch("lima_mcp_stdio.job_runner.subprocess.Popen", return_value=mock_proc) as popen:
        out = jr.start_async_run(task="review foo", scope="foo.py", workspace=str(tmp_path))

    assert out["ok"] is True
    assert out["status"] == "running"
    assert out["job_id"]
    popen.assert_called_once()
    job_dir = Path(out["job_dir"])
    status = json.loads((job_dir / "status.json").read_text(encoding="utf-8"))
    assert status["status"] == "running"
    assert status["pid"] == 12345


def test_job_status_latest(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    art = tmp_path / "artifacts"
    monkeypatch.setenv("MIMO_MCP_ARTIFACT_DIR", str(art))

    job_id = "abc123"
    job_dir = art / "jobs" / job_id
    job_dir.mkdir(parents=True)
    (job_dir / "status.json").write_text(
        json.dumps({"job_id": job_id, "status": "done", "task": "t"}),
        encoding="utf-8",
    )
    (art / "latest_job.json").write_text(json.dumps({"job_id": job_id}), encoding="utf-8")

    out = jr.job_status(workspace=str(tmp_path))
    assert out["status"] == "done"
