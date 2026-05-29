"""Portable admin path resolution."""

import os
from pathlib import Path

from routes import request_tracking
from routes.admin_api import REPO_ROOT
from routes.admin_state import FALLBACK_LOG


def test_admin_state_shares_request_tracking_fallback_log():
    assert FALLBACK_LOG == request_tracking.FALLBACK_LOG
    assert FALLBACK_LOG.endswith("fallback_log.jsonl")


def test_fallback_log_default_lives_under_data_dir():
    normalized = FALLBACK_LOG.replace("\\", "/")
    assert normalized.endswith("/data/fallback_log.jsonl") or normalized.endswith("data/fallback_log.jsonl")


def test_admin_repo_root_points_at_project_root():
    assert REPO_ROOT == Path(__file__).resolve().parent.parent
    assert (REPO_ROOT / "server.py").is_file()


def test_lima_data_dir_env_pattern(monkeypatch, tmp_path):
    monkeypatch.setenv("LIMA_DATA_DIR", str(tmp_path))
    data_dir = os.environ.get(
        "LIMA_DATA_DIR",
        os.path.join(os.path.dirname(__file__), "..", "data"),
    )
    expected = os.path.join(data_dir, "fallback_log.jsonl")
    assert expected == str(tmp_path / "fallback_log.jsonl")
