#!/usr/bin/env python3
"""Check LiMa VPS runtime reproducibility without printing secrets."""

from __future__ import annotations

import importlib.util
import json
import os
import platform
import sys
from pathlib import Path
from typing import Any

ROOT = Path(os.environ.get("LIMA_ROUTER_ROOT", "/opt/lima-router"))

REQUIRED_IMPORTS = {
    "fastapi": "fastapi",
    "uvicorn": "uvicorn",
    "httpx": "httpx",
    "python-dotenv": "dotenv",
    "paramiko": "paramiko",
    "numpy": "numpy",
    "redis": "redis",
    "pybreaker": "pybreaker",
    "python-multipart": "multipart",
    "prometheus_client": "prometheus_client",
}

OPTIONAL_IMPORTS = {
    "paho-mqtt": "paho.mqtt",
    "transformers": "transformers",
}

SECRET_KEYS = [
    "LIMA_API_KEY",
    "LIMA_API_KEYS",
    "GITHUB_WEBHOOK_SECRET",
    "GITEE_WEBHOOK_SECRET",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
    "TELEGRAM_WEBHOOK_SECRET",
]


def _has_module(module: str) -> bool:
    try:
        return importlib.util.find_spec(module) is not None
    except ModuleNotFoundError:
        return False


def _load_env_presence(env_path: Path) -> dict[str, bool]:
    values: dict[str, bool] = {key: bool(os.environ.get(key)) for key in SECRET_KEYS}
    if not env_path.exists():
        return values
    try:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if not line or line.lstrip().startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            if key in values and value.strip():
                values[key] = True
    except OSError:
        return values
    return values


def build_report(root: Path = ROOT) -> dict[str, Any]:
    required = {name: _has_module(module) for name, module in REQUIRED_IMPORTS.items()}
    optional = {name: _has_module(module) for name, module in OPTIONAL_IMPORTS.items()}
    missing_required = [name for name, ok in required.items() if not ok]
    return {
        "ok": not missing_required,
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "root": str(root),
        "root_exists": root.exists(),
        "requirements_server": (root / "requirements_server.txt").exists(),
        "env_file": (root / ".env").exists(),
        "secrets_present": _load_env_presence(root / ".env"),
        "imports": {
            "required": required,
            "optional": optional,
            "missing_required": missing_required,
        },
        "notes": [
            "optional transformers powers local router warmup only; absence must stay explicit in startup logs",
            "secret values are intentionally never printed",
        ],
    }


def main() -> int:
    report = build_report()
    print(json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True))
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
