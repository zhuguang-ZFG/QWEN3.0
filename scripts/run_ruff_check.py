#!/usr/bin/env python3
"""Run ruff check and exit with appropriate code."""
import subprocess
import sys

result = subprocess.run(
    [sys.executable, "-m", "ruff", "check", "."],
    capture_output=True,
    text=True,
)
print(result.stdout)
if result.stderr:
    print(result.stderr, file=sys.stderr)
sys.exit(result.returncode)
