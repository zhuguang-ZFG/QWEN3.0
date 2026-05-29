"""Data Workbench ingestion policy, artifact manifest, and schema redaction.

Defines rules for dataset and research artifact handling before any upload
or processing code exists. All defaults are local-only and gated.

Policy decisions:
    - Accepted file types: CSV, JSON, JSONL, Markdown, plain text
    - Max file size: 50 MB (dataset), 5 MB (artifact text)
    - Retention: 30 days default, configurable
    - Schema redaction: keys matching PII patterns -> [REDACTED]
    - Export format: JSON manifest + optional summary text
    - Default: local filesystem only, no cloud, no network
"""

from __future__ import annotations

import os
from enum import Enum


class PrivacyClass(str, Enum):
    PUBLIC = "public"
    INTERNAL = "internal"
    SENSITIVE = "sensitive"
    RESTRICTED = "restricted"


class ArtifactKind(str, Enum):
    DATASET = "dataset"
    ANALYSIS_RESULT = "analysis_result"
    GENERATED_CODE = "generated_code"
    SUMMARY = "summary"
    REFERENCE = "reference"


# Ingestion policy

ACCEPTED_EXTENSIONS: frozenset[str] = frozenset({
    ".csv", ".json", ".jsonl", ".md", ".txt", ".yaml", ".yml",
})

MAX_DATASET_BYTES: int = 50 * 1024 * 1024   # 50 MB
MAX_ARTIFACT_TEXT_CHARS: int = 100_000       # ~100K chars per artifact body

DEFAULT_RETENTION_DAYS: int = 30
MAX_RETENTION_DAYS: int = 365
MIN_RETENTION_DAYS: int = 1

_SENSITIVE_SCHEMA_KEYS = (
    "api_key", "apikey", "authorization", "cookie", "key",
    "password", "secret", "token", "credential", "private_key",
    "ssn", "social_security", "credit_card", "passport",
)


def is_accepted_file_type(filename: str) -> bool:
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    return f".{ext}" in ACCEPTED_EXTENSIONS


def is_within_size_limit(size_bytes: int) -> bool:
    return 0 < size_bytes <= MAX_DATASET_BYTES


def validate_retention_days(days: int) -> int:
    return max(MIN_RETENTION_DAYS, min(days, MAX_RETENTION_DAYS))


def is_sensitive_schema_key(key: str) -> bool:
    lowered = key.lower()
    return any(token in lowered for token in _SENSITIVE_SCHEMA_KEYS)


def redact_schema_keys(schema: dict) -> dict:
    """Return a copy with sensitive keys replaced by [REDACTED]."""
    return {
        k: "[REDACTED]" if is_sensitive_schema_key(str(k)) else v
        for k, v in schema.items()
    }


def redact_schema_key_list(schema_keys: list[str]) -> list[str]:
    return [
        "[REDACTED]" if is_sensitive_schema_key(str(key)) else str(key)
        for key in schema_keys
        if key
    ][:50]


def redact_text_body(text: str) -> str:
    """Best-effort text redaction for artifact bodies."""
    try:
        from session_memory.redact import sanitize_for_display
        return sanitize_for_display(text)
    except ImportError:
        import re
        text = re.sub(r"sk-[a-zA-Z0-9]{20,}", "[REDACTED]", text)
        text = re.sub(r"Bearer\s+\S{20,}", "Bearer [REDACTED]", text)
        return text


def artifact_root_dir() -> str:
    return os.environ.get(
        "LIMA_ARTIFACT_ROOT",
        os.path.join(os.getcwd(), "data", "artifacts"),
    )


def normalize_artifact_path(path: str) -> str:
    if not path:
        return ""
    root = os.path.abspath(artifact_root_dir())
    candidate = os.path.abspath(path if os.path.isabs(path) else os.path.join(root, path))
    if candidate == root or candidate.startswith(root + os.sep):
        return candidate
    return ""
