#!/usr/bin/env bash
# Push origin then gitee (GI-G-1 wrapper)
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
exec python3 scripts/push_dual_remotes.py "$@"
