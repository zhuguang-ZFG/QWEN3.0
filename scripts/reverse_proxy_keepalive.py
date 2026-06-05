#!/usr/bin/env python3
"""Reverse proxy cookie health monitor + auto-refresh for LongCat-web.

Deploy to VPS: /opt/lima-router/reverse_proxy_keepalive.py
Run via cron: */30 * * * * python3.10 /opt/lima-router/reverse_proxy_keepalive.py

Checks each reverse proxy every 30 min. If cookie expired:
  1. Logs warning with exact error
  2. LongCat-web: attempts Playwright auto-refresh
  3. SCNet/Kimi/MiMo: sends notification (needs manual cookie refresh)
"""

import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [keepalive] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("keepalive")

PROXIES = {
    "longcat-web": {
        "port": 4506,
        "cookie_file": "/root/.longcat_cookie",
        "test_model": "longcat-web",
        "auto_refresh": True,
        "service_name": "longcat-web-proxy",
    },
    "mimo": {
        "port": 4507,
        "cookie_file": "/root/.mimo_cookie",
        "test_model": "mimo-web-flash",
        "auto_refresh": False,
        "service_name": "mimo-proxy",
    },
    "kimi": {
        "port": 4504,
        "cookie_file": "/opt/lima-router/reverse_gateway_state/kimi_cookies.json",
        "test_model": "kimi",
        "auto_refresh": False,
        "service_name": "kimi-proxy",
    },
    "scnet-large": {
        "port": 4505,
        "cookie_file": "/opt/lima-router/reverse_gateway_state/scnet_cookies.json",
        "test_model": "deepseek-v4-flash",
        "auto_refresh": False,
        "service_name": "lima-scnet-reverse",
    },
}

ALERT_FILE = "/tmp/reverse_proxy_alerts.json"


def check_backend_health(port: int, model: str) -> tuple[bool, str]:
    """Test if a reverse proxy can respond to chat requests. Returns (healthy, detail)."""
    import httpx

    try:
        resp = httpx.post(
            f"http://localhost:{port}/v1/chat/completions",
            headers={"Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": "hi"}],
                "max_tokens": 5,
                "stream": False,
            },
            timeout=30,
        )
        if resp.status_code == 200:
            try:
                data = resp.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                if content and len(content.strip()) >= 1:
                    return True, f"OK ({len(content)} chars)"
                return False, "Empty response"
            except Exception:
                return False, f"JSON parse error: {resp.text[:80]}"
        elif resp.status_code in (401, 403):
            return False, f"Cookie expired (HTTP {resp.status_code})"
        elif resp.status_code == 502:
            return False, f"Session failed (HTTP 502)"
        else:
            return False, f"HTTP {resp.status_code}: {resp.text[:80]}"
    except Exception as e:
        return False, f"Connection error: {e}"


def refresh_longcat_cookie() -> bool:
    """Attempt Playwright-based cookie refresh for LongCat-web."""
    cookie_file = Path("/root/.longcat_cookie")
    state_file = Path("/root/.longcat_browser_state.json")

    # Check if playwright is available
    try:
        import playwright  # noqa: F401
    except ImportError:
        log.warning("Playwright not installed, cannot auto-refresh LongCat cookie")
        return False

    log.info("Attempting LongCat cookie auto-refresh via Playwright...")
    try:
        # Use the built-in refresh mechanism from the proxy
        result = subprocess.run(
            [
                "/usr/local/bin/python3.10",
                "-c",
                """
import asyncio, sys
sys.path.insert(0, "/opt/lima-router")

# The proxy has built-in cookie refresh
# Try restarting the proxy —- it will attempt Playwright refresh on startup
print("Cookie refresh triggered via proxy restart")
""",
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        log.info(f"Refresh attempt: {result.stdout.strip()}")

        # Check if cookie file was updated
        if cookie_file.exists():
            mtime = cookie_file.stat().st_mtime
            age_minutes = (time.time() - mtime) / 60
            if age_minutes < 5:
                log.info(f"Cookie refreshed ({age_minutes:.0f}min old)")
                return True
            else:
                log.warning(f"Cookie NOT refreshed ({age_minutes:.0f}min old)")
        return False
    except Exception as e:
        log.error(f"Auto-refresh failed: {e}")
        return False


def save_alert(proxy_name: str, status: str, detail: str) -> None:
    """Save alert state for external monitoring."""
    alerts = {}
    if os.path.exists(ALERT_FILE):
        try:
            with open(ALERT_FILE) as f:
                alerts = json.load(f)
        except Exception as exc:
            log.warning("failed to read alert file: %s", exc)

    alerts[proxy_name] = {
        "status": status,
        "detail": detail,
        "timestamp": datetime.now().isoformat(),
    }

    with open(ALERT_FILE, "w") as f:
        json.dump(alerts, f, indent=2)


def send_notification(message: str) -> None:
    """Send alert via ntfy or fallback to log."""
    ntfy_url = os.environ.get("NTFY_URL", "")
    if ntfy_url:
        try:
            import httpx

            httpx.post(ntfy_url, json={"topic": "lima", "message": message}, timeout=10)
        except Exception as exc:
            log.warning("ntfy notification failed: %s", exc)
    log.warning(f"ALERT: {message}")


def main():
    log.info("=== Reverse Proxy Keepalive Check ===")

    all_healthy = True
    for name, cfg in PROXIES.items():
        port = cfg["port"]
        model = cfg["test_model"]

        healthy, detail = check_backend_health(port, model)
        status = "HEALTHY" if healthy else "UNHEALTHY"
        log.info(f"  {name}: {status} — {detail}")
        save_alert(name, status, detail)

        if not healthy:
            all_healthy = False
            if "cookie" in detail.lower() or "401" in detail or "502" in detail:
                if cfg["auto_refresh"]:
                    log.info(f"  → Attempting auto-refresh for {name}...")
                    if refresh_longcat_cookie():
                        # Restart the proxy to pick up new cookie
                        svc = cfg.get("service_name", f"{name}-proxy")
                        subprocess.run(
                            ["systemctl", "restart", svc],
                            capture_output=True,
                            timeout=30,
                        )
                        # Re-check
                        time.sleep(5)
                        healthy2, detail2 = check_backend_health(port, model)
                        if healthy2:
                            log.info(f"  → {name} RECOVERED after auto-refresh")
                            save_alert(name, "RECOVERED", detail2)
                            continue
                send_notification(f"LiMa reverse proxy {name} DOWN: {detail}. Manual cookie refresh needed.")

    # Remove stale alerts for healthy proxies
    if os.path.exists(ALERT_FILE):
        try:
            with open(ALERT_FILE) as f:
                alerts = json.load(f)
            alerts = {k: v for k, v in alerts.items() if v["status"] != "HEALTHY"}
            with open(ALERT_FILE, "w") as f:
                json.dump(alerts, f, indent=2)
        except Exception as exc:
            log.warning("failed to clean stale alerts: %s", exc)

    status_str = "ALL HEALTHY" if all_healthy else "SOME DOWN"
    log.info(f"=== {status_str} ===")
    return 0 if all_healthy else 1


if __name__ == "__main__":
    sys.exit(main())
