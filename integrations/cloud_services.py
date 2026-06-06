"""Post-route integrations: Supabase + LangSmith logging.

Called after each routing decision to persist data.
Fire-and-forget: never blocks the main response path.
Uses urllib (no proxy dependency) for reliability.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request

_log = logging.getLogger(__name__)

_SUPABASE_URL = ""
_SUPABASE_KEY = ""
_LANGSMITH_KEY = ""


def _get_supabase_url():
    return os.environ.get("SUPABASE_URL", "") or _SUPABASE_URL


def _get_supabase_key():
    return os.environ.get("SUPABASE_SECRET", "") or _SUPABASE_KEY


def _get_langsmith_key():
    return os.environ.get("LANGSMITH_API_KEY", "") or _LANGSMITH_KEY


_opener = None


def _get_opener():
    global _opener
    if _opener is None:
        import urllib.request as _urllib
        _opener = _urllib.build_opener(_urllib.ProxyHandler({}))
    return _opener


def _post_json(url: str, data: dict, headers: dict | None = None) -> bool:
    """POST JSON via urllib (bypasses proxy)."""
    try:
        body = json.dumps(data).encode("utf-8")
        hdrs = {"Content-Type": "application/json"}
        if headers:
            hdrs.update(headers)
        req = urllib.request.Request(url, data=body, headers=hdrs, method="POST")
        with _get_opener().open(req, timeout=10) as resp:
            ok = resp.status in (200, 201)
            if not ok:
                import logging
                logging.warning("cloud_services: POST %s returned %d", url, resp.status)
            return ok
    except Exception as e:
        import logging
        logging.warning("cloud_services: POST %s failed: %s", url, e)
        return False


def log_routing_decision(
    backend: str, request_type: str, scenario: str,
    latency_ms: int, fallback_used: bool = False,
) -> None:
    """Log routing decision to Supabase."""
    url = _get_supabase_url()
    key = _get_supabase_key()
    if not url or not key:
        return
    _post_json(f"{url}/rest/v1/routing_logs", {
        "backend": backend, "request_type": request_type,
        "scenario": scenario, "latency_ms": latency_ms,
    }, {"apikey": key, "Authorization": f"Bearer {key}", "Prefer": "return=minimal"})


def log_llm_run(
    backend: str, model: str, latency_ms: int,
    input_tokens: int = 0, output_tokens: int = 0, scenario: str = "",
) -> None:
    """Log LLM run to LangSmith."""
    key = _get_langsmith_key()
    if not key:
        return
    _post_json("https://api.smith.langchain.com/runs", {
        "session_name": "lima-router", "run_type": "llm",
        "name": f"{backend}/{model}",
        "inputs": {"backend": backend, "model": model, "scenario": scenario},
        "outputs": {"latency_ms": latency_ms, "input_tokens": input_tokens, "output_tokens": output_tokens},
    }, {"x-api-key": key})


