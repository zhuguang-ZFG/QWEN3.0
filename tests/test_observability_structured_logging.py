"""Tests for structured logging configuration defaults.

These use subprocesses to avoid reloading the config singletons in the test
process, which would reset secrets and break authentication in later tests.
"""

from __future__ import annotations

import os
import subprocess
import sys

import pytest


def _run_default_check(env_overrides: dict[str, str] | None = None) -> str:
    env = os.environ.copy()
    env.pop("LIMA_STRUCTURED_LOGGING", None)
    if env_overrides:
        env.update(env_overrides)
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from config.settings import OBSERVABILITY; print(OBSERVABILITY.structured_logging)",
        ],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    return result.stdout.strip()


def test_structured_logging_default_enabled():
    assert _run_default_check() == "True"


def test_structured_logging_can_be_disabled():
    assert _run_default_check({"LIMA_STRUCTURED_LOGGING": "0"}) == "False"


def test_structured_logging_respects_explicit_on():
    assert _run_default_check({"LIMA_STRUCTURED_LOGGING": "1"}) == "True"
