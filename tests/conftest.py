"""Pytest configuration for async test support and test isolation."""

import os
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any

from ._env_sync import _EnvSyncMonkeyPatch

import pytest
import pytest_asyncio  # noqa: F401

# Allow `from tests.xiaozhi_schema import ...` and sibling helper imports
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "xiaozhi_schema"))

# Enable auto mode so @pytest.mark.asyncio tests run without manual event loop setup
pytest_plugins = ["pytest_asyncio"]

# === Test isolation: set unique temp paths for all test env vars ===
# Runs before any test module imports, so env vars are available at import time.
# Each test session gets its own subdirectory to avoid parallel-run conflicts.
# Original values are captured and restored in pytest_sessionfinish to prevent
# cross-session leakage (P1-7).

_TEST_RUN_ID = uuid.uuid4().hex[:8]
_TEST_TMP_DIR = Path(tempfile.gettempdir()) / f"lima-test-{_TEST_RUN_ID}"
_TEST_TMP_DIR.mkdir(parents=True, exist_ok=True)

_TEST_ENV_KEYS = [
    "LIMA_BACKEND_PROFILE_DB",
    "LIMA_BACKEND_RETIREMENT_DB",
    "LIMA_SESSION_DB",
    "LIMA_SESSION_MEMORY",
    "LIMA_LESSONS_DIR",
    "LIMA_HEALTH_STATE_DB",
    "LIMA_WEIGHTS_PATH",
    "LIMA_TOKEN_HEALTH_DB",
    "LIMA_PROFILES_DIR",
    "LIMA_DATA_DIR",
    "LIMA_DEVICE_TASK_STORE",
]
_TEST_ENV_ORIGINAL: dict[str, str | None] = {}

_TEST_ENV_DEFAULTS: dict[str, str] = {
    "LIMA_BACKEND_PROFILE_DB": str(_TEST_TMP_DIR / "profiles.db"),
    "LIMA_BACKEND_RETIREMENT_DB": str(_TEST_TMP_DIR / "retirement.db"),
    "LIMA_SESSION_DB": str(_TEST_TMP_DIR / "session.db"),
    "LIMA_SESSION_MEMORY": "1",
    "LIMA_LESSONS_DIR": str(_TEST_TMP_DIR / "lessons"),
    "LIMA_HEALTH_STATE_DB": str(_TEST_TMP_DIR / "health.db"),
    "LIMA_WEIGHTS_PATH": str(_TEST_TMP_DIR / "weights.json"),
    "LIMA_TOKEN_HEALTH_DB": str(_TEST_TMP_DIR / "token_health.db"),
    "LIMA_PROFILES_DIR": str(_TEST_TMP_DIR / "profiles"),
    "LIMA_DATA_DIR": str(_TEST_TMP_DIR / "lima-data"),
    "LIMA_DEVICE_TASK_STORE": "memory",
}

for _key in _TEST_ENV_KEYS:
    _TEST_ENV_ORIGINAL[_key] = os.environ.get(_key)
    os.environ.setdefault(_key, _TEST_ENV_DEFAULTS[_key])


def pytest_addoption(parser):
    parser.addoption(
        "--stability-rounds",
        action="store",
        default=0,
        type=int,
        help="Number of stability loop iterations (0 = skip).",
    )


def pytest_configure(config):
    """Make access_guard API keys react to per-test os.environ changes."""
    import access_guard

    def _dynamic_configured_api_keys() -> set[str]:
        # Combine any explicit module-level patches with current environment so
        # per-test monkeypatch.setenv continues to work after centralization.
        keys: set[str] = set(access_guard._API_KEYS)
        primary = os.environ.get("LIMA_API_KEY", "").strip()
        if primary:
            keys.add(primary)
        for raw in os.environ.get("LIMA_API_KEYS", "").split(","):
            key = raw.strip()
            if key:
                keys.add(key)
        return keys

    access_guard.configured_api_keys = _dynamic_configured_api_keys

    def _dynamic_anonymous_env_enabled() -> bool:
        return os.environ.get("LIMA_ALLOW_ANONYMOUS", "").strip().lower() in {"1", "true", "yes", "on"}

    access_guard._anonymous_access_env_enabled = _dynamic_anonymous_env_enabled


@pytest.fixture
def monkeypatch():
    """Provide a MonkeyPatch wrapper that keeps config singletons in sync with os.environ."""
    from _pytest.monkeypatch import MonkeyPatch

    mp = MonkeyPatch()
    wrapper = _EnvSyncMonkeyPatch(mp)
    yield wrapper
    wrapper.undo()


@pytest.fixture(autouse=True)
def bypass_default_attestation_in_legacy_tests(request, monkeypatch):
    """Legacy device-gateway tests do not configure firmware hashes.

    The default global verifier only knows v1.3.0, so any hello with a different
    firmware would be quarantined. This fixture makes the default verifier allow
    full access during tests, except for `test_device_attestation.py` which
    explicitly tests attestation behavior with its own isolated verifier.
    """
    if "test_device_attestation" in request.node.module.__name__:
        return

    from device_gateway.attestation import ACTION_FULL_ACCESS, AttestationResult
    from routes import device_gateway_ws_handlers as handlers

    original_verify = handlers.attestation_verifier.verify

    def _test_verify(device_id: str, firmware_hash: str, firmware_version: str):
        version = (firmware_version or "").strip()
        hashes = handlers.attestation_verifier.list_hashes()
        actual = (firmware_hash or "").strip()
        # Legacy tests do not provide a firmwareHash. If the device reports a
        # missing hash or a version that is NOT in the current verifier's
        # whitelist, treat it as if attestation is not configured for that
        # device. This keeps legacy tests working while still honoring explicit
        # full_access matches in test_device_attestation.py.
        if not actual or not hashes or version not in hashes:
            return AttestationResult(
                action=ACTION_FULL_ACCESS,
                version=version,
                expected_hash=hashes.get(version, ""),
                actual_hash=actual,
                reason="attestation bypass in legacy test",
            )
        return original_verify(device_id, firmware_hash, firmware_version)

    monkeypatch.setattr(handlers.attestation_verifier, "verify", _test_verify)


def pytest_sessionfinish(session, exitstatus):
    """Clean up test temp directory and restore original env vars after session completes."""
    import shutil

    for _key in _TEST_ENV_KEYS:
        _original = _TEST_ENV_ORIGINAL.get(_key)
        if _original is None:
            os.environ.pop(_key, None)
        else:
            os.environ[_key] = _original

    if _TEST_TMP_DIR.exists():
        shutil.rmtree(_TEST_TMP_DIR, ignore_errors=True)
