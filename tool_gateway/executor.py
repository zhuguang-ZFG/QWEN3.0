import subprocess
import httpx
from typing import Any, Callable

from .registry import ToolRegistry
from .auth import SecretStore
from .audit import audit_event


class ToolExecutor:
    """Executes registered tools via shell, HTTP, or Python callables."""

    def __init__(self, registry: ToolRegistry, secrets: SecretStore | None = None) -> None:
        self._registry = registry
        self._secrets = secrets or SecretStore()
        self._handlers: dict[str, dict[str, Any]] = {}

    def register_handler(
        self,
        name: str,
        *,
        kind: str,
        target: str | Callable | None = None,
    ) -> None:
        """Register an execution handler for a tool.

        kind: "shell" | "http" | "python"
        target:
          - shell: command template (use {arg} placeholders)
          - http: URL template
          - python: a callable(args: dict) -> Any
        """
        self._handlers[name] = {"kind": kind, "target": target}

    def execute(self, name: str, args: dict) -> dict:
        tool = self._registry.get(name)
        if not tool:
            return {"ok": False, "error": "tool_not_registered"}

        if tool.requires_secret and not self._secrets.has(name.upper() + "_KEY"):
            return {"ok": False, "error": "missing_secret", "tool": tool.name}

        handler = self._handlers.get(name)
        if not handler:
            return {"ok": False, "error": "no_handler_registered", "tool": tool.name}

        kind = handler["kind"]
        target = handler["target"]

        try:
            if kind == "shell":
                return self._exec_shell(name, target, args)
            elif kind == "http":
                return self._exec_http(name, target, args)
            elif kind == "python":
                return self._exec_python(name, target, args)
            else:
                return {"ok": False, "error": f"unknown_kind: {kind}", "tool": name}
        except Exception as exc:
            return {"ok": False, "error": str(exc)[:500], "tool": name}

    def _exec_shell(self, name: str, template: str, args: dict) -> dict:
        """Run a shell command. Template placeholders filled from args."""
        cmd = template.format(**args)
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=30
        )
        ok = result.returncode == 0
        return {
            "ok": ok,
            "tool": name,
            "stdout": result.stdout[:4000],
            "stderr": result.stderr[:2000],
            "returncode": result.returncode,
        }

    def _exec_http(self, name: str, url_template: str, args: dict) -> dict:
        """Make an HTTP POST to the target URL with args as JSON body."""
        url = url_template.format(**args)
        method = args.pop("_method", "POST").upper()
        with httpx.Client(timeout=30) as client:
            resp = client.request(method, url, json=args)
        return {
            "ok": resp.status_code < 400,
            "tool": name,
            "status": resp.status_code,
            "body": resp.text[:4000],
        }

    def _exec_python(self, name: str, fn: Callable, args: dict) -> dict:
        """Call a Python function with args dict."""
        result = fn(args)
        return {"ok": True, "tool": name, "result": result}
