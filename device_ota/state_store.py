"""Small JSON state store for OTA rollout metadata."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

_log = logging.getLogger(__name__)


def load_state(path: Path | str | None) -> dict[str, Any]:
    if path is None:
        return {}
    file_path = Path(path)
    if not file_path.exists():
        return {}
    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        _log.warning("failed to load OTA state path=%s error=%s", file_path, type(exc).__name__)
        return {}
    return data if isinstance(data, dict) else {}


def save_section(path: Path | str | None, section: str, value: dict[str, Any]) -> None:
    if path is None:
        return
    file_path = Path(path)
    data = load_state(file_path)
    data[section] = value
    file_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = file_path.with_name(file_path.name + ".tmp")
    tmp_path.write_text(json.dumps(data, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    tmp_path.replace(file_path)
