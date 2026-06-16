"""Fleet agent — runs on worker nodes (e.g. Windows GPU box).

Polls VPS for tasks, executes them locally, reports results.

Usage:
    python -m fleet.agent --node-id windows-gpu --vps http://47.112.162.80:8080
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
from safe_command import UnsafeCommandError, run_safe_command

_log = logging.getLogger("fleet.agent")

POLL_INTERVAL = 30  # seconds
EXEC_TIMEOUT = 60    # seconds
DEFAULT_FLEET_COMMAND_ALLOWLIST = {
    "python",
    "python.exe",
    "pytest",
    "pytest.exe",
    "ruff",
    "ruff.exe",
    "pyright",
    "pyright.exe",
    "npm",
    "npm.cmd",
    "node",
    "node.exe",
    "git",
    "git.exe",
}


def _detect_gpu(caps: dict) -> None:
    """Detect GPU via nvidia-smi."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            line = result.stdout.strip().split("\n")[0]
            parts = line.split(",")
            caps["gpu"] = True
            caps["gpu_model"] = parts[0].strip()
            if len(parts) > 1:
                vram_str = parts[1].strip().replace("MiB", "").replace("GB", "")
                try:
                    caps["gpu_vram_gb"] = round(float(vram_str) / 1024, 1)
                except ValueError:
                    pass
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass


def _detect_ollama(caps: dict) -> None:
    """Detect Ollama models."""
    try:
        result = subprocess.run(
            ["curl", "-s", "http://127.0.0.1:11434/api/tags"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            caps["models"] = [
                f"ollama:{m['name']}" for m in data.get("models", [])
            ]
    except Exception as exc:
        _log.debug("fleet/agent.py: {}", type(exc).__name__)


def _detect_ram(caps: dict) -> None:
    """Detect system RAM."""
    try:
        if platform.system() == "Windows":
            import ctypes
            kernel32 = ctypes.windll.kernel32
            c_ulonglong = ctypes.c_ulonglong
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", c_ulonglong),
                    ("ullAvailPhys", c_ulonglong),
                    ("ullTotalPageFile", c_ulonglong),
                    ("ullAvailPageFile", c_ulonglong),
                    ("ullTotalVirtual", c_ulonglong),
                    ("ullAvailVirtual", c_ulonglong),
                    ("ullAvailExtendedVirtual", c_ulonglong),
                ]
            mem = MEMORYSTATUSEX()
            mem.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            kernel32.GlobalMemoryStatusEx(ctypes.byref(mem))
            caps["ram_gb"] = round(mem.ullTotalPhys / (1024**3), 1)
        else:
            with open("/proc/meminfo") as f:
                for line in f:
                    if "MemTotal" in line:
                        caps["ram_gb"] = round(int(line.split()[1]) / (1024**2), 1)
                        break
    except Exception as exc:
        _log.debug("fleet/agent.py: {}", type(exc).__name__)


def detect_capabilities() -> dict:
    """Auto-detect node capabilities."""
    caps = {
        "gpu": False, "gpu_model": "", "gpu_vram_gb": 0.0,
        "cpu_cores": os.cpu_count() or 1, "ram_gb": 0.0,
        "shell": True, "workspace": True, "models": [],
    }
    _detect_gpu(caps)
    _detect_ollama(caps)
    _detect_ram(caps)
    return caps


def register(vps_url: str, node_id: str, caps: dict) -> bool:
    """Register this node with the VPS."""
    try:
        resp = httpx.post(
            f"{vps_url}/fleet/register",
            json={"node_id": node_id, "role": "worker", **caps},
            timeout=10,
        )
        data = resp.json()
        _log.info("registered: %s", data.get("ok"))
        return data.get("ok", False)
    except Exception as exc:
        _log.warning("register failed: %s", exc)
        return False


def heartbeat(vps_url: str, node_id: str, load_avg: float = 0.0) -> bool:
    """Send heartbeat to VPS."""
    try:
        resp = httpx.post(
            f"{vps_url}/fleet/heartbeat",
            json={"node_id": node_id, "load_avg": load_avg},
            timeout=5,
        )
        return resp.json().get("ok", False)
    except Exception:
        return False


def fleet_command_allowlist() -> set[str]:
    raw = os.environ.get("LIMA_FLEET_ALLOWED_COMMANDS", "")
    configured = {item.strip().lower() for item in raw.split(",") if item.strip()}
    return configured or DEFAULT_FLEET_COMMAND_ALLOWLIST


def run_shell_task(command: str) -> tuple[str, str]:
    """Run a fleet shell task through the reviewed command boundary."""
    try:
        proc = run_safe_command(
            command,
            allowed_commands=fleet_command_allowlist(),
            timeout=EXEC_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return "", f"timeout after {EXEC_TIMEOUT}s"
    except UnsafeCommandError as exc:
        return "", f"unsafe command rejected: {exc}"
    except Exception as exc:
        return "", str(exc)[:1024]

    result = proc.stdout[:65536]
    error = ""
    if proc.returncode != 0:
        error = f"exit {proc.returncode}: {proc.stderr[:2048]}"
    return result, error


def poll_and_execute(vps_url: str, node_id: str) -> bool:
    """Poll VPS for tasks, execute, report result."""
    try:
        resp = httpx.get(f"{vps_url}/fleet/poll/{node_id}", timeout=10)
        data = resp.json()
        if not data.get("ok") or not data.get("task"):
            return False

        task = data["task"]
        task_id = task["task_id"]
        command = task.get("command", "")
        task_type = task.get("task_type", "shell")

        _log.info("executing task %s: %s", task_id, command[:80])

        result = ""
        error = ""

        if task_type == "shell":
            result, error = run_shell_task(command)
        elif task_type == "inference":
            # Route to Ollama or local model
            error = "inference tasks not yet implemented"
        else:
            error = f"unknown task_type: {task_type}"

        # Report result
        httpx.post(
            f"{vps_url}/fleet/complete",
            json={"task_id": task_id, "result": result, "error": error},
            timeout=10,
        )
        return True

    except Exception as exc:
        _log.warning("poll/execute failed: %s", exc)
        return False


def run_agent(vps_url: str, node_id: str) -> None:
    """Main agent loop."""
    _log.info("fleet agent starting: node=%s vps=%s", node_id, vps_url)

    caps = detect_capabilities()
    _log.info("capabilities: gpu=%s gpu_model=%s vram=%.1fGB models=%d",
              caps["gpu"], caps["gpu_model"], caps["gpu_vram_gb"], len(caps["models"]))

    register(vps_url, node_id, caps)

    while True:
        try:
            import psutil
            load = psutil.getloadavg()[0] if hasattr(psutil, "getloadavg") else 0.0
        except Exception:
            load = 0.0

        heartbeat(vps_url, node_id, load)
        poll_and_execute(vps_url, node_id)
        time.sleep(POLL_INTERVAL)


def main() -> None:
    parser = argparse.ArgumentParser(description="LiMa Fleet Agent")
    parser.add_argument("--node-id", default=f"node-{platform.node()}", help="Node identifier")
    parser.add_argument("--vps", default="http://47.112.162.80:8080", help="VPS URL")
    parser.add_argument("--once", action="store_true", help="Run one poll cycle and exit")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")

    if args.once:
        caps = detect_capabilities()
        register(args.vps, args.node_id, caps)
        heartbeat(args.vps, args.node_id)
        poll_and_execute(args.vps, args.node_id)
    else:
        run_agent(args.vps, args.node_id)


if __name__ == "__main__":
    main()
