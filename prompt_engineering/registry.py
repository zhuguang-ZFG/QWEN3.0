"""Runtime prompt template registry with file-mtime cache invalidation."""

from __future__ import annotations

import os
import threading
from pathlib import Path

import yaml

_BASE_DIR = Path(__file__).resolve().parent.parent / "prompts"
_CACHE: dict[Path, tuple[float, dict]] = {}
_LOCK = threading.Lock()


def _load_yaml(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_prompt_template(group: str, name: str) -> str:
    """Load a prompt template from prompts/{group}.yaml by dotted name.

    The file is cached in memory and reloaded automatically when its mtime
    changes, so edits are picked up immediately in development.

    Args:
        group: YAML file basename (e.g. "layers").
        name: Dotted path inside the YAML document (e.g. "role.chat").

    Raises:
        FileNotFoundError: If the YAML file does not exist.
        KeyError: If the dotted path does not exist in the document.
        TypeError: If the resolved value is not a string.
    """
    path = _BASE_DIR / f"{group}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Prompt template file not found: {path}")

    mtime = os.path.getmtime(path)
    with _LOCK:
        cached_mtime, cached_doc = _CACHE.get(path, (None, None))
        if cached_mtime != mtime:
            cached_doc = _load_yaml(path)
            _CACHE[path] = (mtime, cached_doc)
        doc = cached_doc

    node = doc
    for key in name.split("."):
        if not isinstance(node, dict) or key not in node:
            raise KeyError(f"Prompt template not found: {group}.{name}")
        node = node[key]

    if not isinstance(node, str):
        raise TypeError(f"Prompt template {group}.{name} is not a string")

    return node
