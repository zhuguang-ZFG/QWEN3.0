"""Network HTTP executor with domain allowlist enforcement.

Uses httpx for HTTP calls with timeout and domain validation.
All execution gated behind LIMA_DRY_RUN=0 + LIMA_ALLOW_NETWORK=1.
"""

from __future__ import annotations

import logging
import time

from agent_runtime.contract import redact
from agent_runtime.feature_flags import ExecutionFeatureFlags, is_network_allowed
from agent_runtime.tool_exec import ToolResult

_log = logging.getLogger(__name__)

_DEFAULT_TIMEOUT_SEC = 15.0
_MAX_RESPONSE_BYTES = 64 * 1024


def network_execute(
    url: str,
    *,
    flags: ExecutionFeatureFlags,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    timeout_sec: float = _DEFAULT_TIMEOUT_SEC,
) -> ToolResult:
    t0 = time.time()

    if not is_network_allowed(url, flags):
        return ToolResult(
            ok=False,
            error="network not allowed or domain not in allowlist",
            evidence=["network_gate_blocked"],
            duration_ms=(time.time() - t0) * 1000,
            executed=False,
        )

    try:
        import httpx
    except ImportError:
        return ToolResult(
            ok=False,
            error="httpx not installed",
            evidence=["network_httpx_missing"],
            duration_ms=(time.time() - t0) * 1000,
            executed=False,
        )

    timeout = min(timeout_sec, _DEFAULT_TIMEOUT_SEC)
    _log.info("network_execute: %s %s (timeout=%s)", method, redact(url[:120]), timeout)

    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            resp = client.request(method, url, headers=headers or {})
            body = resp.content[:_MAX_RESPONSE_BYTES].decode(errors="replace")
            duration = (time.time() - t0) * 1000

            return ToolResult(
                ok=resp.is_success,
                output=body,
                error="" if resp.is_success else f"http {resp.status_code}",
                evidence=[
                    f"network_status:{resp.status_code}",
                    f"network_duration:{duration:.0f}ms",
                ],
                duration_ms=duration,
                executed=True,
            )

    except httpx.TimeoutException:
        duration = (time.time() - t0) * 1000
        return ToolResult(
            ok=False,
            error=f"timeout after {timeout}s",
            evidence=["network_timeout", f"network_duration:{duration:.0f}ms"],
            duration_ms=duration,
            executed=True,
        )

    except httpx.RequestError as exc:
        duration = (time.time() - t0) * 1000
        return ToolResult(
            ok=False,
            error=f"request error: {type(exc).__name__}",
            evidence=["network_request_error"],
            duration_ms=duration,
            executed=True,
        )
