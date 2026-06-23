"""Runtime environment helpers."""

from __future__ import annotations

from config import settings


def is_production_runtime() -> bool:
    return settings.FLAGS.runtime_env in {"prod", "production"}
