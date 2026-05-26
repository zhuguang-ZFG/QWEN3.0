#!/usr/bin/env python3
"""Wokwi + LiMa Device Gateway smoke test — end-to-end simulation loop.

This script orchestrates the full "product demo" loop:
  1. LiMa Device Gateway is running (VPS or local)
  2. Wokwi simulation has a virtual ESP32 running wokwi_sim.ino
  3. This script injects a motion task via LiMa's task endpoint
  4. The Wokwi device polls, receives, executes, and reports events
  5. This script verifies the full lifecycle: accepted→running→progress→done

Usage:
  python scripts/smoke_wokwi_device_loop.py [--host chat.donglicao.com] [--local]

Requirements:
  LIMA_API_KEY or LIMA_API_KEYS configured (Bearer auth for device endpoints)
  Wokwi simulation running with wokwi_sim.ino (separate process)
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_HOST = os.environ.get("LIMA_DEVICE_HOST", "chat.donglicao.com")
SCHEME = "https"
DEVICE_ID = "wokwi-u1-sim"
API_KEY = os.environ.get("LIMA_API_KEY", "lima-local")
ROOT = Path(__file__).resolve().parent.parent


def _api(method: str, path: str, body: dict | None = None) -> dict:
    url = f"{SCHEME}://{DEFAULT_HOST}{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {API_KEY}")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:500]
        return {"ok": False, "error": f"HTTP {exc.code}", "detail": detail}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def check_health() -> bool:
    result = _api("GET", "/device/v1/health")
    ok = result.get("status") == "ok"
    print(f"[Health] device_gateway={'ok' if ok else 'DOWN'}: {result}")
    return ok


def inject_task(capability: str = "write_text", params: dict | None = None) -> dict:
    body = {
        "device_id": DEVICE_ID,
        "capability": capability,
        "params": params or {"text": "LiMa Wokwi Smoke", "font_size": 24},
        "source": "smoke_wokwi",
    }
    result = _api("POST", "/device/v1/tasks", body)
    print(f"[Task] injected: {result.get('task_id', 'FAILED')} capability={capability}")
    return result


def check_device_events() -> list[dict]:
    result = _api("GET", f"/device/v1/events?device_id={DEVICE_ID}")
    events = result.get("events", [])
    print(f"[Events] {len(events)} events for {DEVICE_ID}")
    return events


def main() -> int:
    host_arg = next((a for a in sys.argv[1:] if not a.startswith("--")), None)
    global DEFAULT_HOST, SCHEME
    if host_arg:
        DEFAULT_HOST = host_arg
    if "--local" in sys.argv:
        DEFAULT_HOST = "127.0.0.1:8080"
        SCHEME = "http"

    print(f"[Smoke] Target: {SCHEME}://{DEFAULT_HOST}")
    print(f"[Smoke] Device: {DEVICE_ID}")

    # 1. Health check
    if not check_health():
        print("[Smoke] FAIL: Device Gateway not healthy. Is lima-router running?")
        return 1

    # 2. Inject a write_text task
    task = inject_task("write_text", {"text": "LiMa", "font_size": 32})
    task_id = task.get("task_id", "")
    if not task_id:
        print("[Smoke] FAIL: No task_id returned. Wokwi device may not be connected.")
        return 1

    # 3. Wait for device to process (Wokwi polls every 2s, motion takes ~3s)
    print("[Smoke] Waiting for device to execute...")
    time.sleep(10)

    # 4. Check events
    events = check_device_events()
    phases = [e.get("phase", "") for e in events if e.get("task_id") == task_id]
    print(f"[Smoke] Task {task_id} phases: {phases}")

    # 5. Verify lifecycle
    required = {"accepted", "running", "done"}
    found = set(phases)
    if required.issubset(found):
        print(f"[Smoke] PASS: Full lifecycle verified {sorted(found)}")
        return 0
    elif found:
        print(f"[Smoke] PARTIAL: Found {sorted(found)}, missing {required - found}")
        return 1
    else:
        print("[Smoke] FAIL: No lifecycle events received. Is Wokwi running wokwi_sim.ino?")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
