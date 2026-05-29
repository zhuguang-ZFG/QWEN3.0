"""TheOldLLM token sync — remote refresh URL or local Windows script."""

from __future__ import annotations

import json
import logging
import os
import platform
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

_log = logging.getLogger(__name__)

DEFAULT_SYNC_SCRIPT = Path(
    os.environ.get("OLDLLM_SYNC_SCRIPT", "D:/ollama_server/sync_oldllm_token_to_cf.js")
)
DEFAULT_REFRESH_URL = os.environ.get("OLDLLM_REFRESH_URL", "").strip().rstrip("/")
REPO_SYNC_PY = Path(__file__).resolve().parent / "scripts" / "sync_oldllm_token_to_cf.py"


def refresh_url_configured() -> bool:
    return bool(DEFAULT_REFRESH_URL)


def trigger_refresh_url(
    url: str = "",
    *,
    timeout: float = 55.0,
) -> dict[str, Any]:
    """GET {OLDLLM_REFRESH_URL}/refresh (Windows token_refresh_server)."""
    base = (url or DEFAULT_REFRESH_URL).rstrip("/")
    if not base:
        return {"ok": False, "method": "refresh_url", "error": "no_refresh_url"}
    target = f"{base}/refresh"
    started = time.monotonic()
    try:
        with urllib.request.urlopen(target, timeout=timeout) as resp:
            raw = resp.read(4096).decode("utf-8", errors="replace")
            elapsed = time.monotonic() - started
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                payload = {"raw": raw[:200]}
            ok = resp.status == 200 and (
                payload.get("ok")
                or payload.get("token_present")
                or bool(payload.get("token"))
            )
            return {
                "ok": bool(ok),
                "method": "refresh_url",
                "status": resp.status,
                "elapsed_sec": round(elapsed, 3),
                "payload": payload,
            }
    except urllib.error.HTTPError as exc:
        elapsed = time.monotonic() - started
        body = exc.read(512).decode("utf-8", errors="replace")
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            payload = {"raw": body[:200]}
        return {
            "ok": False,
            "method": "refresh_url",
            "status": exc.code,
            "elapsed_sec": round(elapsed, 3),
            "payload": payload,
        }
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        elapsed = time.monotonic() - started
        _log.debug("oldllm refresh_url failed: %s", type(exc).__name__)
        return {
            "ok": False,
            "method": "refresh_url",
            "status": None,
            "elapsed_sec": round(elapsed, 3),
            "error": f"{type(exc).__name__}: {exc}",
        }


def run_local_sync(
    *,
    capture: bool = False,
    restart_proxy: bool = True,
    verify: bool = True,
    timeout: float = 120.0,
) -> dict[str, Any]:
    """Run sync_oldllm_token_to_cf on this machine (Windows)."""
    if REPO_SYNC_PY.is_file():
        cmd = [
            sys.executable,
            str(REPO_SYNC_PY),
            "--verify" if verify else "",
            "--restart-proxy" if restart_proxy else "",
            "--capture" if capture else "",
        ]
        cmd = [c for c in cmd if c]
        cwd = str(REPO_SYNC_PY.parent.parent)
    elif DEFAULT_SYNC_SCRIPT.is_file():
        cmd = ["node", str(DEFAULT_SYNC_SCRIPT)]
        if capture:
            cmd.append("--capture")
        if restart_proxy:
            cmd.append("--restart-proxy")
        if verify:
            cmd.append("--verify")
        cwd = str(DEFAULT_SYNC_SCRIPT.parent)
    else:
        return {
            "ok": False,
            "method": "local_sync",
            "error": "sync_script_missing",
        }

    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        tail = (proc.stdout or proc.stderr or "")[-400:]
        return {
            "ok": proc.returncode == 0,
            "method": "local_sync",
            "returncode": proc.returncode,
            "log_tail": tail,
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "method": "local_sync", "error": "timeout"}
    except OSError as exc:
        return {"ok": False, "method": "local_sync", "error": str(exc)}


def try_sync(*, capture: bool = False) -> dict[str, Any]:
    """Best-effort sync: refresh URL first, then local script on Windows."""
    attempts: list[dict[str, Any]] = []

    if refresh_url_configured():
        remote = trigger_refresh_url()
        attempts.append(remote)
        if remote.get("ok"):
            return {"ok": True, "attempts": attempts}

    if platform.system() == "Windows":
        local = run_local_sync(capture=capture)
        attempts.append(local)
        if local.get("ok"):
            return {"ok": True, "attempts": attempts}

    return {
        "ok": False,
        "attempts": attempts,
        "hint": _sync_hint(),
    }


def _sync_hint() -> str:
    if refresh_url_configured():
        return "refresh URL 失败；在 Windows 运行 python scripts/sync_oldllm_token_to_cf.py --restart-proxy --diag"
    return (
        "设置 OLDLLM_REFRESH_URL 指向 Windows :4501 隧道，"
        "或在本机运行 python scripts/sync_oldllm_token_to_cf.py --restart-proxy --diag"
    )


def format_sync_result(result: dict[str, Any]) -> str:
    lines = [f"OldLLM sync: {'ok' if result.get('ok') else 'FAIL'}"]
    for item in result.get("attempts") or []:
        method = item.get("method", "?")
        mark = "ok" if item.get("ok") else "FAIL"
        extra = item.get("status") or item.get("returncode") or item.get("error", "")
        lines.append(f"· [{mark}] {method} {extra}")
    if not result.get("ok") and result.get("hint"):
        lines.append(f"提示: {result['hint']}")
    return "\n".join(lines)
