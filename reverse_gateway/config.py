"""Configuration helpers for reverse sidecars."""

from __future__ import annotations

import os
from dataclasses import dataclass


TRUTHY = {"1", "true", "yes", "on"}


def env_truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in TRUTHY


@dataclass(frozen=True)
class ProviderConfig:
    enabled: bool
    upstream_url: str
    max_concurrency: int
    timeout_seconds: float
    file_context_enabled: bool
    file_context_threshold_chars: int
    file_context_chunk_chars: int
    file_context_max_files: int
    file_context_max_total_chars: int


def int_env(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return max(1, int(raw))
    except ValueError:
        return default


def float_env(name: str, default: float) -> float:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return max(0.1, float(raw))
    except ValueError:
        return default


def scnet_config() -> ProviderConfig:
    return ProviderConfig(
        enabled=env_truthy("SCNET_REVERSE_ENABLED"),
        upstream_url=os.environ.get("SCNET_REVERSE_UPSTREAM_URL", "").strip(),
        max_concurrency=int_env("SCNET_REVERSE_MAX_CONCURRENCY", 1),
        timeout_seconds=float_env("SCNET_REVERSE_TIMEOUT_SECONDS", 60.0),
        file_context_enabled=env_truthy("SCNET_REVERSE_ENABLE_FILE_CONTEXT"),
        file_context_threshold_chars=int_env("SCNET_REVERSE_FILE_CONTEXT_THRESHOLD_CHARS", 10000),
        file_context_chunk_chars=int_env("SCNET_REVERSE_FILE_CONTEXT_CHUNK_CHARS", 45000),
        file_context_max_files=int_env("SCNET_REVERSE_FILE_CONTEXT_MAX_FILES", 30),
        file_context_max_total_chars=int_env("SCNET_REVERSE_FILE_CONTEXT_MAX_TOTAL_CHARS", 50000),
    )
