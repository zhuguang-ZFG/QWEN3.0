#!/usr/bin/env python3
"""Smoke LiMa public online distributions without printing secrets."""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request


DEFAULT_TIMEOUT = 15


def _request(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    body: bytes | None = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> tuple[int, str, int]:
    req = urllib.request.Request(url, data=body, headers=headers or {}, method=method)
    start = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read()
        elapsed_ms = int((time.time() - start) * 1000)
        return resp.status, data.decode("utf-8", errors="replace"), elapsed_ms


def _check_http(name: str, url: str, *, expect: int = 200) -> bool:
    try:
        status, body, elapsed_ms = _request("GET", url)
        ok = status == expect and bool(body)
        print(f"{'OK' if ok else 'FAIL'} {name}: HTTP {status} {elapsed_ms}ms")
        return ok
    except Exception as exc:
        print(f"FAIL {name}: {type(exc).__name__}: {str(exc)[:120]}")
        return False


def _check_models(base_url: str, api_key: str) -> bool:
    try:
        status, body, elapsed_ms = _request(
            "GET",
            base_url.rstrip("/") + "/models",
            headers={"Authorization": "Bearer " + api_key},
        )
        data = json.loads(body)
        models = data.get("data", [])
        ok = status == 200 and isinstance(models, list) and bool(models)
        print(f"{'OK' if ok else 'FAIL'} chat models: HTTP {status} {elapsed_ms}ms count={len(models) if isinstance(models, list) else 0}")
        return ok
    except Exception as exc:
        print(f"FAIL chat models: {type(exc).__name__}: {str(exc)[:120]}")
        return False


def _check_device_health(chat_root: str) -> bool:
    try:
        status, body, elapsed_ms = _request("GET", chat_root.rstrip("/") + "/device/v1/health")
        data = json.loads(body)
        store = data.get("task_store", {})
        ok = (
            status == 200
            and data.get("status") == "ok"
            and data.get("protocol") == "lima-device-v1"
            and isinstance(store, dict)
        )
        backend = store.get("backend") if isinstance(store, dict) else "unknown"
        print(f"{'OK' if ok else 'FAIL'} device gateway health: HTTP {status} {elapsed_ms}ms backend={backend}")
        return ok
    except Exception as exc:
        print(f"FAIL device gateway health: {type(exc).__name__}: {str(exc)[:120]}")
        return False


def _check_exact_chat(base_url: str, api_key: str, token: str) -> bool:
    payload = {
        "model": "lima-1.3",
        "messages": [{"role": "user", "content": "Return exactly: " + token}],
        "temperature": 0,
        "max_tokens": 24,
    }
    try:
        status, body, elapsed_ms = _request(
            "POST",
            base_url.rstrip("/") + "/chat/completions",
            headers={
                "Authorization": "Bearer " + api_key,
                "Content-Type": "application/json",
            },
            body=json.dumps(payload).encode("utf-8"),
            timeout=45,
        )
        content = json.loads(body)["choices"][0]["message"]["content"].strip()
        ok = status == 200 and content == token
        print(f"{'OK' if ok else 'FAIL'} chat exact: HTTP {status} {elapsed_ms}ms content={content!r}")
        return ok
    except Exception as exc:
        print(f"FAIL chat exact: {type(exc).__name__}: {str(exc)[:120]}")
        return False


def _check_internal_port_guarded(host: str, port: int, timeout: int = 5) -> bool:
    url = f"http://{host}:{port}/health"
    try:
        status, _body, elapsed_ms = _request("GET", url, timeout=timeout)
        print(f"FAIL public internal-port guard: {host}:{port} returned HTTP {status} {elapsed_ms}ms")
        return False
    except (TimeoutError, OSError, urllib.error.URLError) as exc:
        print(f"OK public internal-port guard: {host}:{port} blocked ({type(exc).__name__})")
        return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chat-base", default="https://chat.donglicao.com/v1")
    parser.add_argument("--chat-root", default="https://chat.donglicao.com")
    parser.add_argument("--official-root", default="https://www.donglicao.com")
    parser.add_argument("--open-platform-root", default="https://api.donglicao.com")
    parser.add_argument("--frp-root", default="http://47.112.162.80:8088")
    parser.add_argument("--public-host", default="47.112.162.80")
    parser.add_argument("--api-key", default="lima-local")
    parser.add_argument("--chat-exact", default="", help="Optional exact-output token for /v1/chat/completions")
    parser.add_argument("--skip-port-guard", action="store_true")
    args = parser.parse_args()

    checks = [
        _check_http("official website", args.official_root),
        _check_http("open platform", args.open_platform_root),
        _check_http("chat interface", args.chat_root),
        _check_http("chat health", args.chat_root.rstrip("/") + "/health"),
        _check_device_health(args.chat_root),
        _check_http("frp health", args.frp_root.rstrip("/") + "/health"),
        _check_models(args.chat_base, args.api_key),
    ]
    if args.chat_exact:
        checks.append(_check_exact_chat(args.chat_base, args.api_key, args.chat_exact))
    if not args.skip_port_guard:
        for port in (8080, 3003, 8091, 6379):
            checks.append(_check_internal_port_guarded(args.public_host, port))

    passed = sum(1 for item in checks if item)
    print(f"Result: {passed}/{len(checks)} checks passed")
    return 0 if all(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
