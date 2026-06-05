#!/usr/bin/env python3
"""VPS deployment verification for LiMa + OpenCode.

Usage:
  python scripts/verify_opencode_vps.py              # quick health + models check
  python scripts/verify_opencode_vps.py --full       # health + models + sample chat
  python scripts/verify_opencode_vps.py --deploy     # deploy then verify
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

# ── Config ──────────────────────────────────────────────────────────────────
VPS_IP = "47.112.162.80"
VPS_DOMAIN = "https://chat.donglicao.com"
HEALTH_URL = f"{VPS_DOMAIN}/health"
MODELS_URL = f"{VPS_DOMAIN}/v1/models"
CHAT_URL = f"{VPS_DOMAIN}/v1/chat/completions"
API_KEY = os.environ.get("LIMA_API_KEY", "")
SSH_KEY = os.path.expanduser("~/.ssh/id_ed25519")
REMOTE_DIR = "/opt/lima-router"

# ── Terminal colors ─────────────────────────────────────────────────────────
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"


def ok(msg: str) -> str:
    return f"{GREEN}✓{RESET} {msg}"


def fail(msg: str) -> str:
    return f"{RED}✗{RESET} {msg}"


def warn(msg: str) -> str:
    return f"{YELLOW}⚠{RESET} {msg}"


def info(msg: str) -> str:
    return f"{BLUE}→{RESET} {msg}"


# ── Health check ────────────────────────────────────────────────────────────
def _make_request(url: str, **kwargs) -> Request:
    """Create a request with browser-like headers to avoid WAF blocks."""
    headers = kwargs.pop("headers", {})
    headers.setdefault("User-Agent", "Mozilla/5.0 (compatible; LiMa-Verify/1.0)")
    return Request(url, headers=headers, **kwargs)


def check_health() -> bool:
    print(info("Checking /health ..."), end=" ")
    try:
        req = _make_request(HEALTH_URL)
        resp = urlopen(req, timeout=10)
        body = resp.read().decode()
        print(ok(f"HTTP {resp.status} — {body[:80]}"))
        return True
    except URLError as e:
        print(fail(f"unreachable: {e.reason}"))
        return False
    except Exception as e:
        print(fail(str(e)))
        return False


# ── Models endpoint ─────────────────────────────────────────────────────────
def check_models() -> bool:
    print(info("Checking /v1/models ..."), end=" ")
    if not API_KEY:
        print(warn("no LIMA_API_KEY set — skipped"))
        return False
    try:
        req = _make_request(MODELS_URL, headers={"Authorization": f"Bearer {API_KEY}"})
        resp = urlopen(req, timeout=15)
        data = json.loads(resp.read().decode())
        model_count = len(data.get("data", []))
        print(ok(f"{model_count} models available"))
        return True
    except HTTPError as e:
        body = e.read().decode()[:200] if e.fp else ""
        print(fail(f"HTTP {e.code}: {body}"))
        return False
    except Exception as e:
        print(fail(str(e)))
        return False


# ── Sample chat request ─────────────────────────────────────────────────────
def check_chat() -> bool:
    print(info("Testing /v1/chat/completions (lima-1.3, 'hi', max_tokens=10) ..."), end=" ")
    if not API_KEY:
        print(warn("no LIMA_API_KEY set — skipped"))
        return False
    payload = json.dumps({
        "model": "lima-1.3",
        "messages": [{"role": "user", "content": "hi"}],
        "max_tokens": 10,
    }).encode()
    try:
        req = _make_request(
            CHAT_URL,
            data=payload,
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json",
            },
        )
        resp = urlopen(req, timeout=60)
        data = json.loads(resp.read().decode())
        content = data["choices"][0]["message"]["content"][:60]
        print(ok(f"reply: '{content}'"))
        return True
    except HTTPError as e:
        body = e.read().decode()[:200] if e.fp else ""
        print(fail(f"HTTP {e.code}: {body}"))
        return False
    except Exception as e:
        print(fail(str(e)))
        return False


# ── SSH server status ───────────────────────────────────────────────────────
def check_server_status() -> bool:
    print(info("Checking server process on VPS via SSH ..."))
    if not os.path.exists(SSH_KEY):
        print(warn(f"SSH key not found: {SSH_KEY} — skipping SSH check"))
        return False
    try:
        result = subprocess.run(
            [
                "ssh",
                "-i", SSH_KEY,
                "-o", "StrictHostKeyChecking=accept-new",
                "-o", "ConnectTimeout=5",
                f"root@{VPS_IP}",
                "ss -tlnp | grep 8080; echo '---'; uptime",
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode == 0:
            print(result.stdout.strip())
            return True
        return False
    except subprocess.TimeoutExpired:
        print(fail("SSH timed out"))
        return False
    except Exception as e:
        print(fail(str(e)))
        return False


# ── Deploy ──────────────────────────────────────────────────────────────────
def run_deploy() -> bool:
    print(info("Running deploy_opencode.py ..."))
    deploy_script = Path(__file__).parent.parent / "deploy_opencode.py"
    if not deploy_script.exists():
        print(fail(f"deploy script not found: {deploy_script}"))
        return False
    result = subprocess.run(
        [sys.executable, str(deploy_script)],
        capture_output=False,
        timeout=120,
    )
    return result.returncode == 0


# ── Main ────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Verify LiMa + OpenCode VPS deployment")
    parser.add_argument("--full", action="store_true", help="Full check including chat test")
    parser.add_argument("--deploy", action="store_true", help="Deploy before verifying")
    args = parser.parse_args()

    print(f"\n{'='*60}")
    print(f"  LiMa + OpenCode VPS Verification")
    print(f"  Target: {VPS_DOMAIN} ({VPS_IP}:8080)")
    print(f"{'='*60}\n")

    if args.deploy:
        run_deploy()
        print()
        time.sleep(3)

    results = {
        "health": check_health(),
    }

    if API_KEY:
        results["models"] = check_models()
        if args.full:
            results["chat"] = check_chat()
    else:
        print(warn("\nSet LIMA_API_KEY environment variable to test authenticated endpoints."))
        print(warn("  $env:LIMA_API_KEY='your-key'   (PowerShell)"))
        print(warn("  export LIMA_API_KEY='your-key'  (Bash)\n"))

    results["ssh"] = check_server_status()

    print(f"\n{'─'*60}")
    total = len(results)
    passed = sum(1 for v in results.values() if v)
    if passed == total:
        print(ok(f"All {total}/{total} checks passed"))
    else:
        print(warn(f"{passed}/{total} checks passed"))
    print(f"{'─'*60}\n")


if __name__ == "__main__":
    main()
