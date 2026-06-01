"""Run the project Ruff gate over maintained runtime/test paths."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

RUFF_TARGETS = [
    "server.py",
    "routing_engine.py",
    "routing_selector.py",
    "router_v3.py",
    "router_classifier.py",
    "smart_router.py",
    "backends.py",
    "backends_registry.py",
    "agent_runtime",
    "channel_gateway",
    "context_pipeline",
    "developer_skills",
    "reverse_gateway",
    "routes",
    "tests",
    "scripts/run_ruff_check.py",
    "scripts/create_lima_smoke_task.py",
    "scripts/gitee_mirror_status.py",
    "scripts/healthcheck_ping.py",
    "scripts/memory_daemon_ctl.py",
    "scripts/smoke_telegram_outbound.py",
]


def existing_targets(root: Path) -> list[str]:
    return [target for target in RUFF_TARGETS if (root / target).exists()]


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    return subprocess.run(
        [sys.executable, "-m", "ruff", "check", *existing_targets(root)],
        cwd=root,
    ).returncode


if __name__ == "__main__":
    raise SystemExit(main())
