"""Pytest configuration for async test support and test isolation."""

import os
import sys
import tempfile
import uuid
from pathlib import Path

import pytest_asyncio  # noqa: F401

# Allow `from tests.xiaozhi_schema import ...` and sibling helper imports
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "xiaozhi_schema"))

# Enable auto mode so @pytest.mark.asyncio tests run without manual event loop setup
pytest_plugins = ["pytest_asyncio"]

# === Test isolation: set unique temp paths for all test env vars ===
# Runs before any test module imports, so env vars are available at import time.
# Each test session gets its own subdirectory to avoid parallel-run conflicts.

_TEST_RUN_ID = uuid.uuid4().hex[:8]
_TEST_TMP_DIR = Path(tempfile.gettempdir()) / f"lima-test-{_TEST_RUN_ID}"
_TEST_TMP_DIR.mkdir(parents=True, exist_ok=True)

os.environ.setdefault("LIMA_BACKEND_PROFILE_DB", str(_TEST_TMP_DIR / "profiles.db"))
os.environ.setdefault("LIMA_BACKEND_RETIREMENT_DB", str(_TEST_TMP_DIR / "retirement.db"))
os.environ.setdefault("LIMA_SESSION_DB", str(_TEST_TMP_DIR / "session.db"))
os.environ.setdefault("LIMA_SESSION_MEMORY", "1")
os.environ.setdefault("LIMA_LESSONS_DIR", str(_TEST_TMP_DIR / "lessons"))
os.environ.setdefault("LIMA_HEALTH_STATE_DB", str(_TEST_TMP_DIR / "health.db"))
os.environ.setdefault("LIMA_WEIGHTS_PATH", str(_TEST_TMP_DIR / "weights.json"))
os.environ.setdefault("LIMA_TOKEN_HEALTH_DB", str(_TEST_TMP_DIR / "token_health.db"))
os.environ.setdefault("LIMA_PROFILES_DIR", str(_TEST_TMP_DIR / "profiles"))
os.environ.setdefault("LIMA_DATA_DIR", str(_TEST_TMP_DIR / "lima-data"))


def pytest_addoption(parser):
    parser.addoption(
        "--stability-rounds",
        action="store",
        default=0,
        type=int,
        help="Number of stability loop iterations (0 = skip).",
    )


def pytest_sessionfinish(session, exitstatus):
    """Clean up test temp directory after session completes."""
    import shutil

    if _TEST_TMP_DIR.exists():
        shutil.rmtree(_TEST_TMP_DIR, ignore_errors=True)
