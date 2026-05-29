"""Health preflight and defaults for coding-backend eval runs."""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request

_log = logging.getLogger(__name__)

DEFAULT_EVAL_BASE_URL = os.environ.get(
    "LIMA_EVAL_BASE_URL", "http://127.0.0.1:8080"
).rstrip("/")

DEFAULT_QUICK_BACKENDS = os.environ.get(
    "LIMA_EVAL_QUICK_BACKENDS",
    "scnet_qwen30b,scnet_ds_flash,kimi",
)

# SCNet/Kimi 11-backend pool (FREE_MODEL_ROUTING_STATUS Re-eval C)
DEFAULT_FULL_BACKENDS = os.environ.get(
    "LIMA_EVAL_FULL_BACKENDS",
    "scnet_large_ds_pro,scnet_qwen30b,scnet_large_ds_flash,scnet_qwen235b,"
    "scnet_ds_flash,scnet_ds_pro,cf_kimi_k26,kimi_search,kimi_thinking,kimi,"
    "stock_kimi_k2",
)


def eval_base_url() -> str:
    return DEFAULT_EVAL_BASE_URL


def quick_backend_list() -> list[str]:
    return [b.strip() for b in DEFAULT_QUICK_BACKENDS.split(",") if b.strip()]


def full_backend_list() -> list[str]:
    return [b.strip() for b in DEFAULT_FULL_BACKENDS.split(",") if b.strip()]


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
