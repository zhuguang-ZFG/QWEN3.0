"""Small stdlib helpers for push_probe_results.py."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

# Heuristic: redact metadata keys whose names contain secret-bearing fragments.
_SENSITIVE_KEY_FRAGMENTS = frozenset(("_key", "api_key", "auth_token", "token", "secret", "password", "credential"))


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    return any(fragment in lowered for fragment in _SENSITIVE_KEY_FRAGMENTS)


def _sanitize_metadata(value: object) -> object:
    """Recursively drop secret-bearing keys from metadata."""
    if isinstance(value, dict):
        return {k: _sanitize_metadata(v) for k, v in value.items() if isinstance(k, str) and not _is_sensitive_key(k)}
    if isinstance(value, list):
        return [_sanitize_metadata(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _load_json(path: Path) -> dict[str, Any] | None:
    """Load a JSON file; return None if missing or malformed."""
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError, ValueError) as exc:
        logging.warning("failed to load %s: %s", path, exc)
        return None


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    """Load a JSONL file; return empty list if missing or malformed."""
    if not path.exists():
        return []
    items: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    if isinstance(obj, dict):
                        items.append(obj)
                except json.JSONDecodeError as exc:
                    logging.warning("invalid JSONL line in %s: %s", path, exc)
    except OSError as exc:
        logging.warning("failed to read %s: %s", path, exc)
    return items
