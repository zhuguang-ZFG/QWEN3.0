"""Health preflight and defaults for coding-backend eval runs."""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request

from config import eval_config

_log = logging.getLogger(__name__)


def eval_base_url() -> str:
    return eval_config.eval_base_url()


def quick_backend_list() -> list[str]:
    return eval_config.quick_backend_list()


def full_backend_list() -> list[str]:
    return eval_config.full_backend_list()


def check_eval_health(base_url: str = "") -> tuple[bool, str]:
    """Return (ok, detail) for LiMa /health before live eval."""
    root = (base_url or eval_base_url()).rstrip("/")
    url = f"{root}/health"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "LiMa-EvalPreflight/1.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            body = resp.read(4096).decode("utf-8", errors="replace")
        if resp.status != 200:
            return False, f"health status {resp.status}"
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            return True, "health ok (non-json)"
        status = str(data.get("status", "")).lower()
        if status and status not in {"ok", "healthy", "up"}:
            return False, f"health status={status!r}"
        return True, "health ok"
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        _log.warning("eval preflight failed url=%s err=%s", url, type(exc).__name__)
        return False, f"{type(exc).__name__}: {exc}"
