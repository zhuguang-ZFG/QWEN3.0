"""Shared project root detection for context pipeline."""

from __future__ import annotations

import os


def _detect_project_root() -> str:
    env_root = os.environ.get("LIMA_PROJECT_ROOT", "")
    if env_root and os.path.isdir(env_root):
        return env_root
    cwd = os.getcwd()
    candidates = [cwd, "/opt/lima-router", "D:/GIT"]
    for p in candidates:
        if os.path.isdir(p) and os.path.exists(os.path.join(p, "routing_engine.py")):
            return p
    return cwd
