#!/usr/bin/env python3
"""Public HTTPS smoke for LiMa Device Gateway (/device/v1/*)."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_CHAT_ROOT = "https://chat.donglicao.com"
DEFAULT_API_KEY = "lima-local"
DEFAULT_DEVICE_ID = "dev-joint-1"


def _request(method: str, url: str, *, headers: dict | None = None, body: dict | None = None, timeout: int = 30):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8", errors="replace"))


def check_health(chat_root: str) -> tuple[bool, dict]:
    status, data = _request("GET", chat_root.rstrip("/") + "/device/v1/health")
    ok = (
        status == 200
        and data.get("status") == "ok"
        and data.get("protocol") == "lima-device-v1"
        and data.get("auth_configured") is True
    )
    return ok, data


def check_tasks(chat_root: str, api_key: str, device_id: str) -> tuple[bool, dict]:
    status, data = _request(
        "POST",
        chat_root.rstrip("/") + "/device/v1/tasks",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        body={"device_id": device_id, "text": "write LiMa", "request_id": "smoke-device-gateway-tasks"},
    )
    task = data.get("task") or {}
    ok = status == 200 and data.get("status") in {"queued", "sent"} and not task.get("error")
    return ok, data


def check_events(chat_root: str, api_key: str, device_id: str, task_id: str) -> tuple[bool, dict]:
    status, data = _request(
        "POST",
        chat_root.rstrip("/") + "/device/v1/events",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        body={
            "type": "motion_event",
            "device_id": device_id,
            "task_id": task_id,
            "phase": "progress",
            "progress": {"percent": 50},
            "request_id": "smoke-device-gateway-events",
        },
    )
    ok = status == 200 and data.get("type") == "motion_event_ack"
    return ok, data


def _load_device_token_from_vps(device_id: str) -> str:
    try:
        import paramiko
    except ImportError as exc:
        raise RuntimeError("paramiko required for VPS token lookup") from exc

    key_path = os.environ.get("LIMA_DEPLOY_KEY_PATH", os.path.expanduser("~/.ssh/id_ed25519"))
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect("47.112.162.80", username="root", key_filename=key_path, timeout=30)
    try:
        for path in ("/opt/lima-router/.env", "/root/secure-service-backups/lima-router.env"):
            _stdin, stdout, _stderr = ssh.exec_command(
                f"test -f {path} && grep -E '^LIMA_DEVICE_TOKENS=' {path} | head -1 || true"
            )
            line = stdout.read().decode().strip()
            if not line or "=" not in line:
                continue
            raw = line.split("=", 1)[1].strip().strip('"').strip("'")
            for chunk in raw.replace(";", ",").split(","):
                if "=" not in chunk:
                    continue
                did, token = chunk.split("=", 1)
                if did.strip() == device_id:
                    return token.strip()
    finally:
        ssh.close()
    raise RuntimeError(f"device token not found for {device_id}")


def _wss_url(chat_root: str) -> str:
    host = chat_root.replace("https://", "wss://").replace("http://", "ws://").rstrip("/")
    return f"{host}/device/v1/ws"


async def _drain_pending_motion_tasks(url: str, token: str, device_id: str) -> int:
    """Complete any queued motion_task frames so fake-u8 can run deterministically."""
    try:
        import websockets
    except ImportError as exc:
        raise RuntimeError("websockets required for WSS drain") from exc

    import inspect

    headers = {"Authorization": f"Bearer {token}"}
    params = inspect.signature(websockets.connect).parameters
    header_key = "additional_headers" if "additional_headers" in params else "extra_headers"
    connect_kwargs = {header_key: headers}

    drained = 0
    async with websockets.connect(url, **connect_kwargs) as websocket:
        await websocket.send(
            json.dumps(
                {
                    "type": "hello",
                    "protocol": "lima-device-v1",
                    "device_id": device_id,
                    "fw_rev": "smoke-drain-0.1.0",
                    "capabilities": ["run_path"],
                },
                ensure_ascii=False,
                separators=(",", ":"),
            )
        )
        while True:
            frame = json.loads(await websocket.recv())
            if frame.get("type") == "hello_ack":
                break

        while True:
            try:
                raw = await asyncio.wait_for(websocket.recv(), timeout=1.0)
            except asyncio.TimeoutError:
                break
            frame = json.loads(raw)
            if frame.get("type") != "motion_task":
                continue
            task_id = str(frame.get("task_id") or "")
            if not task_id:
                continue
            for phase, percent in (("progress", 50), ("done", 100)):
                await websocket.send(
                    json.dumps(
                        {
                            "type": "motion_event",
                            "device_id": device_id,
                            "task_id": task_id,
                            "phase": phase,
                            "progress": {"percent": percent},
                        },
                        ensure_ascii=False,
                        separators=(",", ":"),
                    )
                )
                while True:
                    ack = json.loads(await websocket.recv())
                    if ack.get("type") == "motion_event_ack":
                        break
            drained += 1
    return drained


def check_wss(chat_root: str, device_id: str, token: str) -> tuple[bool, str]:
    repo_root = Path(__file__).resolve().parents[1]
    fake_u8 = repo_root / "esp32S_XYZ" / "tools" / "fake_lima_u8" / "app.py"
    if not fake_u8.is_file():
        raise RuntimeError(f"fake_u8 app missing: {fake_u8}")

    url = _wss_url(chat_root)
    drained = asyncio.run(_drain_pending_motion_tasks(url, token, device_id))

    proc = subprocess.run(
        [
            sys.executable,
            str(fake_u8),
            "--url",
            url,
            "--token",
            token,
            "--device-id",
            device_id,
            "--transcript",
            "write smoke",
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()[:200]
        raise RuntimeError(err or f"fake-u8 exit {proc.returncode}")

    payload = json.loads(proc.stdout)
    frames = payload.get("received") or []
    types = [frame.get("type", "") for frame in frames if isinstance(frame, dict)]
    ok = payload.get("ok") is True and "hello_ack" in types and "motion_task" in types
    detail = f"drained={drained} frames={','.join(types)}"
    return ok, detail


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chat-root", default=DEFAULT_CHAT_ROOT)
    parser.add_argument("--api-key", default=DEFAULT_API_KEY)
    parser.add_argument("--device-id", default=DEFAULT_DEVICE_ID)
    parser.add_argument("--device-token", default="", help="Optional; else load from VPS env")
    parser.add_argument("--skip-wss", action="store_true")
    args = parser.parse_args()

    results: list[tuple[str, bool, str]] = []

    ok, health = check_health(args.chat_root)
    store = health.get("task_store", {})
    bus = health.get("session_bus", {})
    detail = f"backend={store.get('backend')} listener={bus.get('listener_alive')}"
    results.append(("health", ok, detail))

    if not args.skip_wss:
        try:
            token = args.device_token or _load_device_token_from_vps(args.device_id)
            ok, wss_detail = check_wss(args.chat_root, args.device_id, token)
            results.append(("wss", ok, wss_detail))
        except Exception as exc:
            results.append(("wss", False, f"{type(exc).__name__}: {exc}"[:120]))

    ok, tasks = check_tasks(args.chat_root, args.api_key, args.device_id)
    task_id = (tasks.get("task") or {}).get("task_id", "")
    results.append(("tasks", ok, f"status={tasks.get('status')} task_id={task_id}"))

    ok, events = check_events(args.chat_root, args.api_key, args.device_id, task_id or "task-smoke")
    results.append(("events", ok, f"type={events.get('type')} phase={events.get('phase')}"))

    passed = 0
    for name, ok, detail in results:
        print(f"{'OK' if ok else 'FAIL'} {name}: {detail}")
        passed += int(ok)
    print(f"Result: {passed}/{len(results)} checks passed")
    return 0 if all(item[1] for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
