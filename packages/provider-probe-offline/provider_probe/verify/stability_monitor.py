"""Stability monitor: track provider uptime and reliability over time."""

import json
import logging
import time
from datetime import datetime, timezone

import httpx

from provider_probe import config as probe_config

logger = logging.getLogger(__name__)

STORAGE_DIR = probe_config.OUTPUT_DIR
STABILITY_FILE = STORAGE_DIR / "stability.json"


def _load_stability() -> dict:
    """Load stability data from disk."""
    if STABILITY_FILE.exists():
        try:
            return json.loads(STABILITY_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_stability(data: dict):
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    STABILITY_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


async def check_provider(url: str, provider_id: str) -> dict:
    """Check a single provider and record stability data."""
    stability = _load_stability()
    entry = stability.get(
        provider_id,
        {
            "url": url,
            "checks": 0,
            "successes": 0,
            "last_success": None,
            "last_failure": None,
            "latencies": [],
        },
    )

    entry["checks"] += 1

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            start = time.monotonic()
            resp = await client.get(url.rstrip("/") + "/v1/models", follow_redirects=True)
            elapsed = (time.monotonic() - start) * 1000

            if resp.status_code == 200:
                entry["successes"] += 1
                entry["last_success"] = datetime.now(timezone.utc).isoformat()
                entry["latencies"].append(round(elapsed, 1))
                # Keep last 100 latency samples
                if len(entry["latencies"]) > 100:
                    entry["latencies"] = entry["latencies"][-100:]
            else:
                entry["last_failure"] = datetime.now(timezone.utc).isoformat()
                entry.setdefault("failures", []).append(
                    {
                        "time": datetime.now(timezone.utc).isoformat(),
                        "status": resp.status_code,
                    }
                )
    except Exception as exc:
        entry["last_failure"] = datetime.now(timezone.utc).isoformat()
        entry.setdefault("failures", []).append(
            {
                "time": datetime.now(timezone.utc).isoformat(),
                "error": str(exc),
            }
        )

    stability[provider_id] = entry
    _save_stability(stability)

    # Calculate uptime percentage
    uptime = (entry["successes"] / entry["checks"]) * 100 if entry["checks"] > 0 else 0

    return {
        "provider_id": provider_id,
        "checks": entry["checks"],
        "successes": entry["successes"],
        "uptime_pct": round(uptime, 1),
        "avg_latency_ms": (
            round(sum(entry["latencies"][-20:]) / len(entry["latencies"][-20:]), 1) if entry["latencies"] else -1
        ),
    }


def get_stability_report() -> list[dict]:
    """Get a summary report of all monitored providers."""
    stability = _load_stability()
    report = []

    for pid, data in stability.items():
        checks = data.get("checks", 0)
        if checks == 0:
            continue
        uptime = (data["successes"] / checks) * 100
        latencies = data.get("latencies", [])
        report.append(
            {
                "provider_id": pid,
                "url": data.get("url", ""),
                "uptime_pct": round(uptime, 1),
                "checks": checks,
                "avg_latency_ms": (round(sum(latencies[-10:]) / len(latencies[-10:]), 1) if latencies else -1),
                "last_success": data.get("last_success", "never"),
            }
        )

    report.sort(key=lambda x: x["uptime_pct"], reverse=True)
    return report
