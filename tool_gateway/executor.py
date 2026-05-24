import subprocess
import shlex
import json
import httpx
from typing import Any, Callable

from .registry import ToolRegistry, requires_approval
from .auth import SecretStore
from .audit import audit_event


class ToolExecutor:
    """Executes registered tools via shell, HTTP, or Python callables.

    Enforces authority-based tool access: tools require explicit authorization
    matching their AuthorityClass. Dangerous authorities require approval.
    """

    def __init__(self, registry: ToolRegistry, secrets: SecretStore | None = None) -> None:
        self._registry = registry
        self._secrets = secrets or SecretStore()
        self._handlers: dict[str, dict[str, Any]] = {}
        self._allowed_tools: set[str] | None = None

    def set_allowed_tools(self, allowed: set[str] | list[str] | None) -> None:
        """Restrict execution to the given tool names. None = allow all."""
        if allowed is None:
            self._allowed_tools = None
        else:
            self._allowed_tools = set(allowed)

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
          - shell: command as list template (use {arg} placeholders)
          - http: URL template
          - python: a callable(args: dict) -> Any
        """
        self._handlers[name] = {"kind": kind, "target": target}

    def execute(self, name: str, args: dict) -> dict:
        tool = self._registry.get(name)
        if not tool:
            audit_event("execute_rejected", tool=name, reason="not_registered")
            return {"ok": False, "error": "tool_not_registered"}

        # ── Authority enforcement (M7) ─────────────────────────────────────
        if self._allowed_tools is not None and name not in self._allowed_tools:
            audit_event("execute_rejected", tool=name, reason="not_allowed")
            return {"ok": False, "error": "tool_not_allowed", "tool": name}

        if tool.requires_approval or requires_approval(tool.authority):
            audit_event("execute_rejected", tool=name, reason="requires_approval")
            return {"ok": False, "error": "tool_requires_approval", "tool": name}

        if len(args) > tool.max_args:
            audit_event("execute_rejected", tool=name, reason="too_many_args")
            return {"ok": False, "error": "too_many_args", "tool": name}

        if tool.requires_secret and not self._secrets.has(name.upper() + "_KEY"):
            audit_event("execute_rejected", tool=name, reason="missing_secret")
            return {"ok": False, "error": "missing_secret", "tool": tool.name}

        handler = self._handlers.get(name)
        if not handler:
            audit_event("execute_rejected", tool=name, reason="no_handler")
            return {"ok": False, "error": "no_handler_registered", "tool": tool.name}

        kind = handler["kind"]
        target = handler["target"]


        try:
            audit_event("execute_start", tool=name, kind=kind, args_keys=list(args.keys()))
            if kind == "shell":
                result = self._exec_shell(name, target, args, timeout_sec=tool.timeout_sec)
            elif kind == "http":
                result = self._exec_http(name, target, args, timeout_sec=tool.timeout_sec)
            elif kind == "python":
                result = self._exec_python(name, target, args)
            else:
                result = {"ok": False, "error": f"unknown_kind: {kind}", "tool": name}
            audit_event("execute_done", tool=name, ok=result.get("ok", False))
            return result
        except Exception as exc:
            audit_event("execute_error", tool=name, error=str(exc)[:200])
            return {"ok": False, "error": str(exc)[:500], "tool": name}

    def _exec_shell(
        self, name: str, template: str, args: dict, *, timeout_sec: float
    ) -> dict:
        """Run a shell command safely — no shell=True, args passed as list."""
        import re
        _SAFE_ARG = re.compile(r'^[\w\-./=:@]+$')
        sanitized = {}
        for k, v in args.items():
            v_str = str(v)
            if not _SAFE_ARG.match(v_str):
                return {"ok": False, "error": f"unsafe_arg: {k}", "tool": name}
            sanitized[k] = v_str
        cmd_str = template.format(**sanitized)
        cmd_list = shlex.split(cmd_str)
        result = subprocess.run(
            cmd_list, shell=False, capture_output=True, text=True, timeout=timeout_sec
        )
        return {
            "ok": result.returncode == 0,
            "tool": name,
            "stdout": result.stdout[:4000],
            "stderr": result.stderr[:2000],
            "returncode": result.returncode,
        }

    def _exec_http(
        self, name: str, url_template: str, args: dict, *, timeout_sec: float
    ) -> dict:
        """Make an HTTP request. Does not mutate caller's args dict."""
        args_copy = dict(args)
        method = args_copy.pop("_method", "POST").upper()
        url = url_template.format(**args_copy)
        with httpx.Client(timeout=timeout_sec) as client:
            resp = client.request(method, url, json=args_copy)
        return {
            "ok": resp.status_code < 400,
            "tool": name,
            "status": resp.status_code,
            "body": resp.text[:4000],
        }

    def _exec_python(self, name: str, fn: Callable, args: dict) -> dict:
        """Call a Python function with args dict."""
        result = fn(dict(args))
        return {"ok": True, "tool": name, "result": result}
