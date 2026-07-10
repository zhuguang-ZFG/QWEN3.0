#!/usr/bin/env python3
"""Read-only production deploy smoke (health, metrics, L2 rate limit, voice)."""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from voice_e2e_http import fake_wav_bytes, post_multipart
from voice_e2e_probe import (
    exit_code_for_results,
    print_probe_results,
    run_voice_e2e_probes,
    voice_e2e_skipped,
)

try:
    from config import deploy_config, settings

    HOST = deploy_config.VERIFY_HOST
except ImportError:
    print("WARN config module not found; using env defaults (CI mode)")
    HOST = os.environ.get("LIMA_VERIFY_HOST", "chat.donglicao.com")
    settings = None  # type: ignore[assignment]

UA = {"User-Agent": "LiMaDeployVerify/1.0", "Content-Type": "application/json"}


def _get(path: str, *, bearer: str = "", timeout: float = 90) -> tuple[int, str]:
    headers = dict(UA)
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
    req = urllib.request.Request(f"https://{HOST}{path}", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace")


def _post(path: str, body: dict, *, timeout: float = 90) -> tuple[int, str]:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(f"https://{HOST}{path}", data=data, headers=UA, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace")


def _configured_api_key() -> str:
    """Return the deploy-verify API key when configured."""
    if settings is not None:
        return (settings.SECURITY.api_key or "").strip()
    return os.environ.get("LIMA_API_KEY", "").strip()


def _check_health_path(path: str) -> str | None:
    """Probe a health endpoint and return the failure key, or None on success."""
    attempts = 3
    last_exc: Exception | None = None
    api_key = _configured_api_key()
    for attempt in range(attempts):
        started = time.monotonic()
        try:
            status, body = _get(path)
            used_key = False
            if status == 401 and api_key:
                status, body = _get(path, bearer=api_key)
                used_key = True
            elapsed = time.monotonic() - started
            data = json.loads(body)
            ok = status == 200 and data.get("status") == "ok"
            auth_note = " (with API key)" if used_key and ok else ""
            print(
                f"OK  {path} -> {status} status={data.get('status')} ({elapsed:.2f}s){auth_note}"
                if ok
                else f"FAIL {path} -> {status} {body[:120]} ({elapsed:.2f}s)"
            )
            return None if ok else path
        except Exception as exc:
            elapsed = time.monotonic() - started
            last_exc = exc
            print(f"WARN {path} attempt {attempt + 1}/{attempts} -> {type(exc).__name__}: {exc} ({elapsed:.2f}s)")
            if attempt < attempts - 1:
                time.sleep(2)
    print(f"FAIL {path} -> {type(last_exc).__name__}: {last_exc}")
    return path


def _login_rate_limit() -> tuple[int, int]:
    """Return (probe_count, network_failures) after hammering public L2 login."""
    if settings is not None:
        limit = settings.DEVICE.auth_login_per_min
    else:
        limit = int(os.environ.get("LIMA_DEVICE_AUTH_LOGIN_PER_MIN", "5"))
    probe = limit + 1
    network_failures = 0
    for i in range(probe):
        status = 0
        for attempt in range(3):
            try:
                status, _ = _post("/device/v1/app/auth/login", {"phone": "10000000000", "code": "000000"})
                break
            except Exception as exc:
                print(f"WARN L2 login attempt {i + 1}/{probe} retry {attempt + 1}/3 -> {type(exc).__name__}: {exc}")
                if attempt == 2:
                    network_failures += 1
                else:
                    time.sleep(2)
        if status == 429:
            print(f"OK  L2 login rate limit (public) -> 429 on attempt {i + 1}/{probe}")
            return probe, network_failures, status, True
    return probe, network_failures, status, False


def _strict_rate_limit() -> bool:
    """True when Redis-backed cross-worker rate limiting is expected."""
    if settings is not None:
        flag = settings.SECURITY.device_auth_rate_redis
        redis_url = settings.SECURITY.device_auth_rate_redis_url or settings.REDIS.device_redis_url
    else:
        flag = os.environ.get("LIMA_DEVICE_AUTH_RATE_REDIS", "auto")
        redis_url = os.environ.get("LIMA_DEVICE_REDIS_URL", "")
    return flag in {"1", "true", "redis", "on", "yes"} or (flag == "auto" and bool(redis_url))


def _check_l2_rate_limit() -> str | None:
    """Public L2 login probe; returns failure key when strict mode demands a 429."""
    probe, network_failures, last_status, got_429 = _login_rate_limit()
    if got_429:
        return None

    strict = _strict_rate_limit()
    if network_failures and not strict:
        print(f"WARN L2 public probe: skipped due to {network_failures} network failures (last={last_status})")
        return None
    msg = (
        f"FAIL L2 public probe: no 429 after {probe} attempts (last={last_status}, network_failures={network_failures})"
        if strict
        else (
            f"WARN L2 public probe: no 429 after {probe} attempts (last={last_status}, "
            f"network_failures={network_failures}); enable LIMA_DEVICE_AUTH_RATE_REDIS + Redis URL for cross-worker limits"
        )
    )
    print(msg)
    return "l2_rate_limit" if strict else None


def _check_device_app_voice_unauth() -> str | None:
    """POST /device/v1/app/voice/transcribe without auth should be 401."""
    try:
        status, _ = post_multipart(
            HOST,
            "/device/v1/app/voice/transcribe",
            files={"audio": ("clip.wav", fake_wav_bytes(), "audio/wav")},
        )
    except Exception as exc:
        print(f"WARN voice transcribe probe -> {type(exc).__name__}: {exc}")
        return None
    ok = status == 401
    print(f"{'OK' if ok else 'FAIL'}  /device/v1/app/voice/transcribe unauth -> {status}")
    return None if ok else "voice_transcribe_unauth"


def _check_device_app_voice_e2e() -> list[str]:
    """Authenticated voice REST + WS probes when credentials are configured."""
    if voice_e2e_skipped():
        print("SKIP voice auth E2E (LIMA_VOICE_E2E_SKIP=1)")
        return []
    try:
        results = asyncio.run(run_voice_e2e_probes(HOST))
    except Exception as exc:
        print(f"WARN voice auth E2E -> {type(exc).__name__}: {exc}")
        return []
    # unauth probe already ran in main(); drop duplicate
    results = [item for item in results if item.name != "voice_transcribe_unauth"]
    print_probe_results(results)
    if exit_code_for_results(results):
        return ["voice_e2e_auth"]
    return []


def main() -> int:
    failures: list[str] = []

    # /device/v1/health 与 /v1/ops/metrics/prometheus 已随 P4/P5 瘦身退役
    # （WS 设备网关 + ops_metrics 物理删除）；DLC 服务只暴露 /health。
    for path in ("/health",):
        if failure := _check_health_path(path):
            failures.append(failure)

    if failure := _check_l2_rate_limit():
        failures.append(failure)

    if failure := _check_device_app_voice_unauth():
        failures.append(failure)

    failures.extend(_check_device_app_voice_e2e())

    print("---")
    if failures:
        print("RESULT: FAIL", failures)
        return 1
    print("RESULT: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
