"""Topology-aware eval routing for Windows local-proxy backends (P2-25)."""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request

from config.settings import EVAL, SECURITY
from eval_preflight import check_eval_health
from runtime_topology import BACKEND_PORT_ENV, LOCAL_ONLY_BACKENDS, backend_available, local_port_open

_log = logging.getLogger(__name__)

TRUTHY = {"1", "true", "yes", "on"}
DEFAULT_FRP_ROUTER = "http://127.0.0.1:8088"


def eval_via_router_enabled() -> bool:
    return EVAL.via_router_enabled


def eval_via_router_url() -> str:
    """FRP/Windows router base URL for proxy-backend eval (e.g. VPS :8088 → Windows :8080)."""
    explicit = EVAL.via_router_url or EVAL.windows_router_url
    if explicit:
        return explicit.rstrip("/")
    if not eval_via_router_enabled():
        return ""
    if _auto_frp_router_available():
        return DEFAULT_FRP_ROUTER.rstrip("/")
    return ""


def _auto_frp_router_available() -> bool:
    """Use FRP loopback when local proxy port is down but :8088 /health is ok."""
    if local_port_open(4505) or local_port_open(4504):
        return False
    ok, _detail = check_eval_health(DEFAULT_FRP_ROUTER)
    return ok


def needs_via_router(backend: str) -> bool:
    if backend not in LOCAL_ONLY_BACKENDS:
        return False
    if backend_available(backend):
        return False
    return bool(eval_via_router_url())


def eval_api_key() -> str:
    return SECURITY.api_key.strip()


def call_via_router(
    backend: str,
    messages: list[dict],
    max_tokens: int,
    *,
    router_url: str = "",
    timeout: float = 120.0,
) -> str:
    """POST /internal/v1/eval/call on Windows router (via FRP from VPS)."""
    base = (router_url or eval_via_router_url()).rstrip("/")
    if not base:
        raise OSError("local proxy unreachable; set LIMA_EVAL_VIA_ROUTER_URL=http://127.0.0.1:8088")
    key = eval_api_key()
    if not key:
        raise OSError("LIMA_API_KEY required for eval via router")

    payload = {
        "backend": backend,
        "messages": messages,
        "max_tokens": max_tokens,
    }
    req = urllib.request.Request(
        f"{base}/internal/v1/eval/call",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
            "User-Agent": "LiMa-EvalTopology/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read(65536).decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as exc:
        detail = exc.read(512).decode("utf-8", errors="replace")
        raise OSError(f"eval router HTTP {exc.code}: {detail[:200]}") from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise OSError(f"eval router failed: {type(exc).__name__}: {exc}") from exc

    if not body.get("ok"):
        raise OSError(str(body.get("error") or body.get("detail") or "eval router not ok"))
    answer = str(body.get("answer") or "")
    if not answer.strip():
        raise OSError("eval router returned empty answer")
    return answer


def topology_status_lines() -> list[str]:
    url = eval_via_router_url()
    lines = [f"eval_via_router={'1' if url else '0'}"]
    if url:
        lines.append(f"via_router_url={url}")
    proxy_ports = sorted({port for port, _env in BACKEND_PORT_ENV.values()})
    closed = [str(p) for p in proxy_ports if not local_port_open(p)]
    if closed:
        lines.append(f"local_proxy_closed={','.join(closed)}")
    return lines
