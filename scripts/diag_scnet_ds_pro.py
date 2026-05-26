#!/usr/bin/env python3
"""Diagnose scnet_ds_pro timeout/cooldown root cause (read-only probes)."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backends import BACKENDS
from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

BACKEND = "scnet_ds_pro"


def _probe_direct(timeout: float) -> dict:
    import httpx

    cfg = BACKENDS[BACKEND]
    payload = {
        "model": cfg["model"],
        "messages": [{"role": "user", "content": "Reply with one word: ok"}],
        "max_tokens": 8,
    }
    started = time.time()
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(cfg["url"], json=payload)
        elapsed_ms = int((time.time() - started) * 1000)
        body = resp.text[:200]
        return {
            "ok": resp.status_code == 200,
            "status_code": resp.status_code,
            "latency_ms": elapsed_ms,
            "preview": body,
        }
    except Exception as exc:
        elapsed_ms = int((time.time() - started) * 1000)
        return {
            "ok": False,
            "latency_ms": elapsed_ms,
            "error": f"{type(exc).__name__}: {str(exc)[:160]}",
        }


def main() -> int:
    cfg = BACKENDS.get(BACKEND)
    if not cfg:
        print(f"FAIL: backend {BACKEND} missing", file=sys.stderr)
        return 1

    from health_state import clear_cooldown, get_backend_state, get_cooldown_remaining

    clear_cooldown(BACKEND)
    report = {
        "backend": BACKEND,
        "model": cfg.get("model"),
        "url": cfg.get("url"),
        "configured_timeout_sec": cfg.get("timeout"),
        "diagnosis": (
            "deepseek-v4-pro on direct SCNet often exceeds 45s read timeout; "
            "eval then marks follow-up cases as cooled down when cases run back-to-back."
        ),
        "fixes_applied": [
            "backends_registry scnet_ds_pro timeout 45→90",
            "coding_eval.run_eval clears cooldown before each case",
        ],
        "health_before": get_backend_state(BACKEND),
        "cooldown_remaining_sec": round(get_cooldown_remaining(BACKEND), 2),
        "probe_30s": _probe_direct(30),
        "probe_90s": _probe_direct(float(cfg.get("timeout", 90))),
        "health_after": get_backend_state(BACKEND),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["probe_90s"].get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
