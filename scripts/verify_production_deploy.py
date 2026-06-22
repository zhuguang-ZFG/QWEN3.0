#!/usr/bin/env python3
"""Read-only production deploy smoke (health, metrics, L2 rate limit)."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOST = os.environ.get("LIMA_VERIFY_HOST", "chat.donglicao.com").strip()
UA = {"User-Agent": "LiMaDeployVerify/1.0", "Content-Type": "application/json"}


def _load_key() -> str:
    env_path = ROOT / ".env"
    if env_path.is_file():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("LIMA_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return os.environ.get("LIMA_API_KEY", "").strip()


def _load_redis_url() -> str:
    env_path = ROOT / ".env"
    if env_path.is_file():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("LIMA_DEVICE_AUTH_RATE_REDIS_URL="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
            if line.startswith("LIMA_DEVICE_REDIS_URL="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return (
        os.environ.get("LIMA_DEVICE_AUTH_RATE_REDIS_URL", "").strip()
        or os.environ.get("LIMA_DEVICE_REDIS_URL", "").strip()
    )


def _get(path: str, *, bearer: str = "") -> tuple[int, str]:
    headers = dict(UA)
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
    req = urllib.request.Request(f"https://{HOST}{path}", headers=headers)
    with urllib.request.urlopen(req, timeout=45) as resp:
        return resp.status, resp.read().decode("utf-8", errors="replace")


def _post(path: str, body: dict) -> tuple[int, str]:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(f"https://{HOST}{path}", data=data, headers=UA, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace")


def _check_health_path(path: str) -> str | None:
    """Probe a health endpoint and return the failure key, or None on success."""
    try:
        status, body = _get(path)
        data = json.loads(body)
        ok = status == 200 and data.get("status") == "ok"
        print(f"OK  {path} -> {status} status={data.get('status')}" if ok else f"FAIL {path} -> {status} {body[:120]}")
        return None if ok else path
    except Exception as exc:
        print(f"FAIL {path} -> {type(exc).__name__}: {exc}")
        return path


def _check_metrics(bearer: str) -> str | None:
    """Probe Prometheus metrics endpoint and return the failure key, or None."""
    try:
        status, text = _get("/v1/ops/metrics/prometheus", bearer=bearer)
        needles = (
            "lima_backend_retired_count",
            "lima_backend_retirement_events_total",
            "lima_backend_retired",
        )
        missing = [n for n in needles if n not in text]
        ok = status == 200 and not missing
        print(
            f"OK  /v1/ops/metrics/prometheus -> {status} lines={len(text.splitlines())}"
            if ok
            else f"FAIL metrics -> {status} missing={missing}"
        )
        if ok:
            for line in text.splitlines():
                if line.startswith("lima_backend_retired_count "):
                    print(f"    {line.strip()}")
                    break
            return None
        return "metrics"
    except Exception as exc:
        print(f"FAIL metrics -> {type(exc).__name__}: {exc}")
        return "metrics"


def _check_l2_rate_limit() -> str | None:
    """Public L2 login probe; returns failure key when strict mode demands a 429."""
    limit = int(os.environ.get("LIMA_DEVICE_AUTH_LOGIN_PER_MIN", "20"))
    probe = limit + 1
    got_429 = False
    last_status = 0
    for i in range(probe):
        last_status, _body = _post("/device/v1/app/auth/login", {"phone": "10000000000", "code": "000000"})
        if last_status == 429:
            got_429 = True
            print(f"OK  L2 login rate limit (public) -> 429 on attempt {i + 1}/{probe}")
            break
    if got_429:
        return None

    flag = os.environ.get("LIMA_DEVICE_AUTH_RATE_REDIS", "auto").strip().lower()
    redis_url = _load_redis_url()
    strict = flag in {"1", "true", "redis", "on", "yes"} or (flag == "auto" and bool(redis_url))
    msg = (
        f"FAIL L2 public probe: no 429 after {probe} attempts (last={last_status})"
        if strict
        else (
            f"WARN L2 public probe: no 429 after {probe} attempts (last={last_status}); "
            "enable LIMA_DEVICE_AUTH_RATE_REDIS + Redis URL for cross-worker limits"
        )
    )
    print(msg)
    return "l2_rate_limit" if strict else None


def main() -> int:
    key = _load_key()
    failures: list[str] = []

    for path in ("/health", "/device/v1/health"):
        if failure := _check_health_path(path):
            failures.append(failure)

    if not key:
        print("SKIP /v1/ops/metrics/prometheus (no LIMA_API_KEY)")
        failures.append("metrics_no_key")
    elif failure := _check_metrics(key):
        failures.append(failure)

    if failure := _check_l2_rate_limit():
        failures.append(failure)

    print("---")
    if failures:
        print("RESULT: FAIL", failures)
        return 1
    print("RESULT: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
