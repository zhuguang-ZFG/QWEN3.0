"""Offline provider probe batch CLI (Cold path only).

Requires LIMA_PROVIDER_AUTOMATION_RUN=1. Never imported from server.py or routing hot path.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from provider_automation.openrouter import fetch_live, parse_fixture
from provider_automation.runner import ProbeRunner, ProbeRunnerConfig, format_batch_results


def _require_run_gate() -> None:
    if os.environ.get("LIMA_PROVIDER_AUTOMATION_RUN", "").strip() != "1":
        raise SystemExit("Refusing to run: set LIMA_PROVIDER_AUTOMATION_RUN=1 (offline ops / CI only).")


def _load_models(*, fixture: Path | None, live_openrouter: bool) -> list:
    if live_openrouter:
        import asyncio

        snapshot = asyncio.run(fetch_live())
    else:
        path = str(fixture) if fixture else ""
        snapshot = parse_fixture(path)
    return list(snapshot.models)


def main(argv: list[str] | None = None) -> int:
    _require_run_gate()

    parser = argparse.ArgumentParser(description="Run provider_automation metadata/smoke probe batch")
    parser.add_argument("--fixture", type=Path, help="OpenRouter fixture JSON path")
    parser.add_argument(
        "--live-openrouter", action="store_true", help="Fetch live catalog (needs LIMA_OPENROUTER_LIVE_FETCH=1)"
    )
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="Enable completion smoke (requires configured callable; default metadata-only)",
    )
    parser.add_argument("--limit", type=int, default=0, help="Max models to probe (0 = all)")
    args = parser.parse_args(argv)

    models = _load_models(fixture=args.fixture, live_openrouter=args.live_openrouter)
    if args.limit > 0:
        models = models[: args.limit]

    config = ProbeRunnerConfig(
        run_metadata=True,
        run_completion_smoke=bool(args.smoke),
        run_stream_smoke=False,
        run_coding_fixture=False,
        run_quality_gate=False,
    )
    runner = ProbeRunner(config)
    results = runner.run(models)
    print(format_batch_results(results))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
