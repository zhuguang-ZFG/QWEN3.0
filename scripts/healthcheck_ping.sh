#!/usr/bin/env bash
# Healthchecks.io ping wrapper (INF-B). Prefer scripts/healthcheck_ping.py on Windows.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
exec python3 scripts/healthcheck_ping.py "$@"
