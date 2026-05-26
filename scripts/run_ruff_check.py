#!/usr/bin/env python3
"""Run Ruff lint gate (F + E9) using repo ruff.toml."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    config = ROOT / "ruff.toml"
    if not config.is_file():
        print("ruff: missing ruff.toml", file=sys.stderr)
        return 2
    cmd = [sys.executable, "-m", "ruff", "check", str(ROOT), "--config", str(config)]
    print("+", " ".join(cmd), flush=True)
    return subprocess.call(cmd, cwd=ROOT)


if __name__ == "__main__":
    sys.exit(main())
