"""Provider-probe microservice configuration (lazy reads for testability)."""

from __future__ import annotations

import os
from pathlib import Path


def browser_host() -> str:
    return os.environ.get("PROBE_BROWSER_HOST", "127.0.0.1")


def browser_port() -> int:
    try:
        return int(os.environ.get("PROBE_BROWSER_PORT", "8092"))
    except ValueError:
        return 8092


def chromium_executable() -> str | None:
    return os.environ.get("PROBE_CHROMIUM_EXECUTABLE")


def browser_token() -> str | None:
    return os.environ.get("PROBE_BROWSER_TOKEN")


def browser_service_url() -> str:
    return os.environ.get("PROBE_BROWSER_URL", "http://127.0.0.1:8092")


def output_dir() -> Path:
    return Path(os.environ.get("PROBE_OUTPUT_DIR", "/opt/lima-probe/data"))


def searxng_url() -> str | None:
    return os.environ.get("SEARXNG_URL") or os.environ.get("SEARXNG_BASE_URL")
