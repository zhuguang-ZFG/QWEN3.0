"""Code execution sandbox — run code in isolated Docker containers.

Supported runtimes: Python, JavaScript (Node.js), Shell (bash).

Security constraints:
- Execution timeout (default 30s, max 120s)
- Memory limit (default 256 MB)
- Network disabled by default
- Read-only root filesystem with a writable tmpfs workspace
- No privileged operations
"""

from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

_log = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────────────────
_MAX_TIMEOUT = int(os.environ.get("LIMA_SANDBOX_MAX_TIMEOUT", "120"))
_DEFAULT_TIMEOUT = int(os.environ.get("LIMA_SANDBOX_TIMEOUT", "30"))
_MEMORY_LIMIT = os.environ.get("LIMA_SANDBOX_MEMORY", "256m")
_NETWORK = os.environ.get("LIMA_SANDBOX_NETWORK", "none")  # "none" or "bridge"

# Supported language runtimes
_RUNTIMES: dict[str, dict[str, Any]] = {
    "python": {
        "image": "python:3.11-slim",
        "ext": ".py",
        "cmd": ["python", "{file}"],
    },
    "javascript": {
        "image": "node:20-slim",
        "ext": ".js",
        "cmd": ["node", "{file}"],
    },
    "shell": {
        "image": "bash:5",
        "ext": ".sh",
        "cmd": ["bash", "{file}"],
    },
}


def _docker_available() -> bool:
    """Check if Docker is available."""
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


async def run_code(
    code: str,
    language: str = "python",
    timeout: int = _DEFAULT_TIMEOUT,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Execute *code* in a sandboxed Docker container.

    Returns a dict with keys: ``stdout``, ``stderr``, ``exit_code``,
    ``duration_ms``, ``language``, and ``truncated`` if output was cut.
    """
    runtime = _RUNTIMES.get(language)
    if runtime is None:
        return {"error": f"Unsupported language: {language}", "supported": list(_RUNTIMES.keys())}

    if not _docker_available():
        # Fallback: run locally with basic restrictions (development only)
        return await _run_local_fallback(code, language, timeout, env)

    timeout = min(timeout, _MAX_TIMEOUT)
    suffix = runtime["ext"]

    with tempfile.TemporaryDirectory(prefix="lima_sandbox_") as tmpdir:
        code_file = Path(tmpdir) / f"main{suffix}"
        code_file.write_text(code, encoding="utf-8")

        cmd = [c.format(file=str(code_file)) for c in runtime["cmd"]]
        docker_cmd = [
            "docker", "run",
            "--rm",
            "--network", _NETWORK,
            "--memory", _MEMORY_LIMIT,
            "--cpus", "1",
            "--read-only",
            "--tmpfs", "/tmp:rw,size=64m",
            "-v", f"{tmpdir}:/workspace:ro",
            "-w", "/workspace",
            "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges",
            runtime["image"],
        ] + cmd

        start = time.time()
        try:
            proc = await asyncio.create_subprocess_exec(
                *docker_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(), timeout=timeout
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.communicate()
                return {
                    "stdout": "",
                    "stderr": f"Execution timed out after {timeout}s",
                    "exit_code": -1,
                    "duration_ms": int((time.time() - start) * 1000),
                    "language": language,
                    "timeout": True,
                }

            stdout = stdout_bytes.decode("utf-8", errors="replace")[:10000]
            stderr = stderr_bytes.decode("utf-8", errors="replace")[:5000]
            truncated = len(stdout) >= 10000 or len(stderr) >= 5000
            return {
                "stdout": stdout,
                "stderr": stderr,
                "exit_code": proc.returncode or 0,
                "duration_ms": int((time.time() - start) * 1000),
                "language": language,
                "truncated": truncated,
            }
        except Exception as exc:
            return {
                "stdout": "",
                "stderr": str(exc),
                "exit_code": -1,
                "duration_ms": int((time.time() - start) * 1000),
                "language": language,
                "error": str(exc),
            }


async def _run_local_fallback(
    code: str,
    language: str,
    timeout: int,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Run code locally without Docker (development fallback)."""
    runtime = _RUNTIMES[language]
    with tempfile.TemporaryDirectory(prefix="lima_sandbox_") as tmpdir:
        code_file = Path(tmpdir) / f"main{runtime['ext']}"
        code_file.write_text(code, encoding="utf-8")
        cmd = [c.format(file=str(code_file)) for c in runtime["cmd"]]
        start = time.time()
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={**os.environ, **(env or {})},
            )
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
            stdout = stdout_bytes.decode("utf-8", errors="replace")[:10000]
            stderr = stderr_bytes.decode("utf-8", errors="replace")[:5000]
            return {
                "stdout": stdout,
                "stderr": stderr,
                "exit_code": proc.returncode or 0,
                "duration_ms": int((time.time() - start) * 1000),
                "language": language,
                "truncated": len(stdout) >= 10000,
                "fallback": True,
            }
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            return {
                "stdout": "",
                "stderr": f"Execution timed out after {timeout}s",
                "exit_code": -1,
                "duration_ms": int((time.time() - start) * 1000),
                "language": language,
                "timeout": True,
                "fallback": True,
            }
        except Exception as exc:
            return {
                "stdout": "",
                "stderr": str(exc),
                "exit_code": -1,
                "duration_ms": int((time.time() - start) * 1000),
                "language": language,
                "error": str(exc),
                "fallback": True,
            }
