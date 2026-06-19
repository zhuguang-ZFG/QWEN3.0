"""Runtime environment helpers."""

from __future__ import annotations

import os


def is_production_runtime() -> bool:
    return os.environ.get("LIMA_RUNTIME_ENV", "").strip().lower() in {"prod", "production"}
