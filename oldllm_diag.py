"""TheOldLLM proxy/upstream health probes (NEXT_MILESTONES P1)."""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.request
from typing import Any

_log = logging.getLogger(__name__)

DEFAULT_UPSTREAM = os.environ.get(
    "OLDLLM_UPSTREAM_URL", "https://llm.zhuguang.ccwu.cc"
).rstrip("/")
DEFAULT_LOCAL_PROXY = os.environ.get(
    "OLDLLM_LOCAL_PROXY_URL", "http://127.0.0.1:4502"
).rstrip("/")
DEFAULT_CHAT_MODEL = os.environ.get("OLDLLM_DIAG_MODEL", "gpt-4.1-nano")
DEFAULT_CHAT_TIMEOUT = float(os.environ.get("OLDLLM_DIAG_CHAT_TIMEOUT", "30"))


def _http_json(
    url: str,
    *,
    method: str = "GET",
    body: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 8.0,
) -> tuple[int | None, dict[str, Any] | str, float]:
    started = time.monotonic()
    data = None
    req_headers = {"User-Agent": "LiMa-OldLLMDiag/1.0", **(headers or {})}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        req_headers.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=data, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read(65536).decode("utf-8", errors="replace")
            elapsed = time.monotonic() - started
            try:
                return resp.status, json.loads(raw), elapsed
            except json.JSONDecodeError:
                return resp.status, raw[:500], elapsed
    except urllib.error.HTTPError as exc:
        elapsed = time.monotonic() - started
        raw = exc.read(4096).decode("utf-8", errors="replace")
        try:
            payload: dict[str, Any] | str = json.loads(raw)
        except json.JSONDecodeError:
            payload = raw[:500]
        return exc.code, payload, elapsed
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        elapsed = time.monotonic() - started
        _log.debug("oldllm probe failed url=%s err=%s", url, type(exc).__name__)
        return None, f"{type(exc).__name__}: {exc}", elapsed


def probe_models(base_url: str, *, timeout: float = 8.0) -> dict[str, Any]:
    url = f"{base_url.rstrip('/')}/v1/models"
    status, payload, elapsed = _http_json(url, timeout=timeout)
    model_ids: list[str] = []
    if isinstance(payload, dict):
        for item in payload.get("data", []):
            if isinstance(item, dict) and item.get("id"):
                model_ids.append(str(item["id"]))
    ok = status == 200 and bool(model_ids)
    return {
        "target": base_url,
        "kind": "models",
        "ok": ok,
        "status": status,
        "elapsed_sec": round(elapsed, 3),
        "model_count": len(model_ids),
        "models_sample": model_ids[:5],
        "error": None if ok else (payload if not ok else "no models"),
    }


def probe_chat(
    base_url: str,
    *,
    model: str = DEFAULT_CHAT_MODEL,
    timeout: float = DEFAULT_CHAT_TIMEOUT,
    api_key: str = "1",
) -> dict[str, Any]:
    url = f"{base_url.rstrip('/')}/v1/chat/completions"
    body = {
        "model": model,
        "messages": [{"role": "user", "content": "Reply with exactly: pong"}],
        "max_tokens": 8,
        "stream": False,
    }
    status, payload, elapsed = _http_json(
        url,
        method="POST",
        body=body,
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=timeout,
    )
    content = ""
    if isinstance(payload, dict):
        try:
            content = str(payload["choices"][0]["message"]["content"])[:120]
        except (KeyError, IndexError, TypeError):
            content = ""
    ok = status == 200 and bool(content.strip())
    timed_out = isinstance(payload, str) and "timed out" in payload.lower()
    return {
        "target": base_url,
        "kind": "chat",
        "model": model,
        "ok": ok,
        "status": status,
        "elapsed_sec": round(elapsed, 3),
        "timed_out": timed_out,
        "content_sample": content,
        "error": None if ok else payload,
    }


def run_diag(
    *,
    upstream: str = DEFAULT_UPSTREAM,
    local_proxy: str = DEFAULT_LOCAL_PROXY,
    chat_timeout: float = DEFAULT_CHAT_TIMEOUT,
    skip_chat: bool = False,
) -> dict[str, Any]:
    targets = [
        ("upstream", upstream),
        ("local_proxy", local_proxy),
    ]
    results: list[dict[str, Any]] = []
    for label, base in targets:
        models = probe_models(base)
        models["label"] = label
        results.append(models)
        if skip_chat:
            continue
        chat = probe_chat(base, timeout=chat_timeout)
        chat["label"] = label
        results.append(chat)

    any_models = any(r.get("kind") == "models" and r.get("ok") for r in results)
    any_chat = any(r.get("kind") == "chat" and r.get("ok") for r in results)
    return {
        "upstream": upstream,
        "local_proxy": local_proxy,
        "chat_model": DEFAULT_CHAT_MODEL,
        "chat_timeout_sec": chat_timeout,
        "any_models_ok": any_models,
        "any_chat_ok": any_chat,
        "results": results,
    }
