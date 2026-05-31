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

# M1: oldllm_* now CF Workers on llm.zhuguang.ccwu.cc. No local proxy needed.
DEFAULT_UPSTREAM = os.environ.get(
    "OLDLLM_UPSTREAM_URL", "https://llm.zhuguang.ccwu.cc"
).rstrip("/")
DEFAULT_CHAT_MODEL = os.environ.get("OLDLLM_DIAG_MODEL", "gpt-4.1-nano")
DEFAULT_CHAT_TIMEOUT = float(os.environ.get("OLDLLM_DIAG_CHAT_TIMEOUT", "30"))


def _parse_sse_chat(raw: str) -> str:
    parts: list[str] = []
    for line in raw.splitlines():
        if not line.startswith("data:"):
            continue
        chunk = line[5:].strip()
        if not chunk or chunk == "[DONE]":
            continue
        try:
            payload = json.loads(chunk)
        except json.JSONDecodeError:
            continue
        delta = payload.get("choices", [{}])[0].get("delta", {})
        piece = delta.get("content") or payload.get("content")
        if piece:
            parts.append(str(piece))
        try:
            msg = payload["choices"][0]["message"]["content"]
            if msg:
                parts.append(str(msg))
        except (KeyError, IndexError, TypeError):
            pass
    return "".join(parts).strip()[:120]

# M1: oldllm_* now CF Workers (no Windows proxy). Hints updated.
REFRESH_HINTS = (
    "502 Bad Gateway → check CF Worker token sync (scripts/sync_oldllm_token_to_cf.py --diag)",
    "Turnstile → sync script pushes token to CF Worker; retry refresh if needed",
    "chat timeout → 增大 OLDLLM_DIAG_CHAT_TIMEOUT 或换 gpt-5.1 / gpt-4.1-nano",
    "models ok chat fail → check CF Worker Bearer key and upstream health",
)


def failure_hints(report: dict[str, Any]) -> list[str]:
    """Actionable remediation from probe results."""
    hints: list[str] = []
    for item in report.get("results", []):
        if item.get("ok"):
            continue
        status = item.get("status")
        label = item.get("label", "?")
        kind = item.get("kind", "?")
        if status == 502:
            hints.append(f"[{label}/{kind}] HTTP 502 → 刷新 TheOldLLM token / 检查上游代理")
        elif status in (401, 403):
            hints.append(f"[{label}/{kind}] HTTP {status} → 检查 API key / Bearer")
        elif item.get("skipped"):
            hints.append(
                f"[{label}/{kind}] 跳过 → {item.get('skip_reason', 'local proxy 不在本机')}"
            )
        elif item.get("timed_out"):
            hints.append(f"[{label}/{kind}] 超时 → 检查隧道或增大 timeout")
        elif status is None and kind == "chat":
            hints.append(f"[{label}/{kind}] 连接失败 → 确认 {label} 地址可达")
    if not report.get("any_chat_ok") and report.get("any_models_ok"):
        hints.append("models 通 chat 不通 → 优先查 token 刷新与 Windows oldllm_proxy")
    if not report.get("any_models_ok"):
        hints.append("models 也不通 → 查 DNS/FRP/Cloudflare 入口是否变更")
    deduped: list[str] = []
    for hint in hints + list(REFRESH_HINTS[:2]):
        if hint not in deduped:
            deduped.append(hint)
    return deduped[:6]


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
    content = _extract_chat_content(payload)
    if isinstance(payload, str) and not content:
        content = _parse_sse_chat(payload)
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


def _extract_chat_content(payload: dict[str, Any] | str) -> str:
    if not isinstance(payload, dict):
        return ""
    try:
        return str(payload["choices"][0]["message"]["content"])[:120]
    except (KeyError, IndexError, TypeError):
        return ""


# M1: oldllm_* now CF Workers. Simplified diag — upstream only.
def run_diag(
    *,
    upstream: str = DEFAULT_UPSTREAM,
    chat_timeout: float = DEFAULT_CHAT_TIMEOUT,
    skip_chat: bool = False,
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    models = probe_models(upstream)
    models["label"] = "upstream"
    results.append(models)

    if not skip_chat:
        chat = probe_chat(upstream, model=DEFAULT_CHAT_MODEL, timeout=chat_timeout)
        chat["label"] = "upstream"
        results.append(chat)

    any_models = any(r.get("kind") == "models" and r.get("ok") for r in results)
    any_chat = any(r.get("kind") == "chat" and r.get("ok") for r in results)
    report = {
        "upstream": upstream,
        "chat_model": DEFAULT_CHAT_MODEL,
        "chat_timeout_sec": chat_timeout,
        "any_models_ok": any_models,
        "any_chat_ok": any_chat,
        "upstream_chat_ok": any_chat,
        "results": results,
    }
    report["hints"] = failure_hints(report)
    return report
