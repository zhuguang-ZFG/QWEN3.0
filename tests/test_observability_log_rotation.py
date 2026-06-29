"""Tests for AUDIT-5-O9: size-limited rotating file logging.

All tests run in subprocesses to avoid mutating the test process's root logger
and to verify env-driven configuration end-to-end.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


def _run_in_tmp(tmp_path: Path, script: str, env_overrides: dict[str, str]) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])
    env.pop("LIMA_LOG_FILE_PATH", None)
    env.pop("LIMA_LOG_FILE_MAX_MB", None)
    env.pop("LIMA_LOG_FILE_BACKUPS", None)
    env.pop("LIMA_STRUCTURED_LOGGING", None)
    env.update(env_overrides)
    return subprocess.run(
        [sys.executable, "-c", script],
        cwd=str(tmp_path),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_default_log_file_path():
    script = "from config.settings import OBSERVABILITY; print(OBSERVABILITY.log_file_path)"
    result = _run_in_tmp(Path.cwd(), script, {})
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "logs/lima-router.log"


def test_log_file_created_and_rotated(tmp_path: Path):
    log_path = tmp_path / "app.log"
    script = """
import logging, sys
try:
    from observability.structured_logging import setup_structured_logging, stop_file_listener
except ImportError as e:
    print(f"IMPORT_ERROR: {e}", file=sys.stderr)
    sys.exit(1)
setup_structured_logging()
log = logging.getLogger("test.rotation")
for i in range(20):
    log.info("x" * 200)
stop_file_listener()
print("done")
"""
    result = _run_in_tmp(
        tmp_path,
        script,
        {
            "LIMA_LOG_FILE_PATH": str(log_path),
            "LIMA_LOG_FILE_MAX_MB": "0",
            "LIMA_LOG_FILE_BACKUPS": "2",
            "LIMA_STRUCTURED_LOGGING": "1",
        },
    )
    assert result.returncode == 0, result.stderr
    assert "done" in result.stdout, f"unexpected stdout: {result.stdout!r}"
    files = sorted(tmp_path.iterdir())
    assert any(f.name.startswith("app.log") for f in files)
    backups = [f for f in files if f.name.startswith("app.log.")]
    assert len(backups) <= 2, f"expected at most 2 backups, got {backups}"


def test_log_file_disabled_when_path_empty(tmp_path: Path):
    script = """
import logging
import os
from observability.structured_logging import setup_structured_logging
setup_structured_logging()
log = logging.getLogger("test.disabled")
log.info("should not create file")
print("done")
"""
    result = _run_in_tmp(
        tmp_path,
        script,
        {
            "LIMA_LOG_FILE_PATH": "",
            "LIMA_STRUCTURED_LOGGING": "1",
        },
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "done"
    assert list(tmp_path.iterdir()) == []


def test_structured_file_log_format_is_json(tmp_path: Path):
    log_path = tmp_path / "app.log"
    script = """
import logging
from observability.structured_logging import setup_structured_logging, stop_file_listener
setup_structured_logging()
log = logging.getLogger("test.json")
log.info("hello")
stop_file_listener()
print("done")
"""
    result = _run_in_tmp(
        tmp_path,
        script,
        {
            "LIMA_LOG_FILE_PATH": str(log_path),
            "LIMA_STRUCTURED_LOGGING": "1",
        },
    )
    assert result.returncode == 0, result.stderr
    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    assert lines
    record = json.loads(lines[-1])
    assert record["message"] == "hello"
    assert record["level"] == "INFO"


def test_plain_file_log_format_when_structured_disabled(tmp_path: Path):
    log_path = tmp_path / "app.log"
    script = """
import logging
from observability.structured_logging import setup_structured_logging, stop_file_listener
setup_structured_logging()
log = logging.getLogger("test.plain")
log.warning("plain")
stop_file_listener()
print("done")
"""
    result = _run_in_tmp(
        tmp_path,
        script,
        {
            "LIMA_LOG_FILE_PATH": str(log_path),
            "LIMA_STRUCTURED_LOGGING": "0",
        },
    )
    assert result.returncode == 0, result.stderr
    text = log_path.read_text(encoding="utf-8")
    assert "plain" in text
    assert "WARNING" in text
