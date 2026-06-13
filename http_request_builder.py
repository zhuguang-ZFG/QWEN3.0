"""HTTP client factory and request builders (CQ-014 slice 8)."""

from __future__ import annotations

import json
import logging
import os
import time

import httpx

import key_pool
from backend_utils import infer_key_pool_provider
from backends_constants import GFW_BACKENDS
from backends_registry import BACKENDS

logger = logging.getLogger(__name__)

GFW_PROXY_URL = os.environ.get("GFW_PROXY", "http://127.0.0.1:7897")
GFW_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


def _needs_proxy(url: str) -> bool:
    """Check if a URL should use the outbound proxy (skip local URLs)."""
    local_hosts = ("127.0.0.1", "localhost", "0.0.0.0")
    for h in local_hosts:
        if h in url:
            return False
    return True


def _build_client(backend: str, timeout: float) -> httpx.Client:
    if backend in GFW_BACKENDS:
        url = BACKENDS.get(backend, {}).get("url", "")
        if _needs_proxy(url):
            return httpx.Client(
                proxy=GFW_PROXY_URL,
                headers={"User-Agent": GFW_USER_AGENT},
                timeout=httpx.Timeout(timeout, connect=10.0),
            )
        return httpx.Client(
            trust_env=False,
            headers={"User-Agent": GFW_USER_AGENT},
            timeout=httpx.Timeout(timeout, connect=10.0),
        )
    # Non-GFW backends: disable env proxy to prevent SOCKS errors
    return httpx.Client(
        trust_env=False,
        timeout=httpx.Timeout(timeout, connect=10.0),
    )


def _build_async_client(backend: str, timeout: float) -> httpx.AsyncClient:
    if backend in GFW_BACKENDS:
        url = BACKENDS.get(backend, {}).get("url", "")
        if _needs_proxy(url):
            return httpx.AsyncClient(
                proxy=GFW_PROXY_URL,
                headers={"User-Agent": GFW_USER_AGENT},
                timeout=httpx.Timeout(timeout, connect=10.0),
            )
        return httpx.AsyncClient(
            trust_env=False,
            headers={"User-Agent": GFW_USER_AGENT},
            timeout=httpx.Timeout(timeout, connect=10.0),
        )
    # Non-GFW backends: disable env proxy to prevent SOCKS errors
    return httpx.AsyncClient(
        trust_env=False,
        timeout=httpx.Timeout(timeout, connect=10.0),
    )


def _build_headers(backend_cfg: dict, key: str | None = None) -> dict:
    fmt = backend_cfg["fmt"]
    auth_style = backend_cfg.get("auth", "x-api-key")
    key = backend_cfg["key"] if key is None else key

    if fmt == "anthropic":
        if auth_style == "bearer":
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {key}",
                "anthropic-version": "2023-06-01",
            }
        else:
            headers = {
                "Content-Type": "application/json",
                "x-api-key": key,
                "anthropic-version": "2023-06-01",
            }
    else:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
            "User-Agent": "LiMa/2.0",
        }

    # Add extra headers (e.g., X-Request-Timestamp for Zhihu)
    extra = backend_cfg.get("extra_headers", {})
    if extra:
        for hk, hv in extra.items():
            if hv == "dynamic" and hk == "X-Request-Timestamp":
                headers[hk] = str(int(time.time()))
            elif hv != "dynamic":
                headers[hk] = hv

    return headers


def _key_pool_provider(backend: str, backend_cfg: dict) -> str:
    return infer_key_pool_provider(backend, backend_cfg)


def _select_key(backend: str, backend_cfg: dict) -> tuple[str, str]:
    # Check runtime token overrides first (from /internal/v1/token-sync)
    try:
        from routes.token_sync import get_token_override
        override = get_token_override(backend)
        if override:
            return override, f"override:{backend}"
    except ImportError:
        pass

    provider = _key_pool_provider(backend, backend_cfg)
    if provider:
        pool_configured = key_pool.ensure_env_pool(provider)
        if pool_configured:
            if key_pool.is_exhausted(provider):
                return "", provider
            selected = key_pool.get_key(provider)
            if selected:
                return selected, provider

    # Dynamic re-read: if key is empty but config has an env var ref, resolve now
    raw_key = backend_cfg.get("key", "")
    if not raw_key or raw_key in ("none", ""):
        # Re-read from env at request time (handles .env loaded after import)
        key_env_var = backend_cfg.get("key_env_var", "")
        if key_env_var:
            raw_key = os.environ.get(key_env_var, "")
        if not raw_key:
            # Scan common env var patterns
            for env_name in [f"{backend.upper()}_API_KEY", f"{backend.upper()}_KEY",
                             f"{backend.replace('-', '_').upper()}_KEY"]:
                raw_key = os.environ.get(env_name, "")
                if raw_key:
                    break

    return raw_key, provider


def _has_key(backend: str, backend_cfg: dict) -> bool:
    selected, _provider = _select_key(backend, backend_cfg)
    return bool(selected)


def _report_key_result(
    provider: str,
    key: str,
    success: bool,
    error_code: int = 0,
    retry_after: int = 0,
) -> None:
    if not provider or not key:
        return
    if success:
        key_pool.report_key_result(provider, key, True)
    else:
        key_pool.report_key_result(
            provider,
            key,
            False,
            error_code=error_code or 0,
            retry_after=retry_after,
        )


def _build_body(
    backend_cfg: dict,
    messages: list[dict],
    max_tokens: int,
    system_prompt: str = "",
    ide: str = "",
    stream: bool = False,
    tools: list[dict] | None = None,
) -> bytes:
    model = backend_cfg["model"]
    fmt = backend_cfg["fmt"]

    sys_text = system_prompt
    if ide and ide not in ("unknown", "未知"):
        from prompt_engineering.layers import compose_system_prompt

        scenario = "coding" if fmt != "anthropic" or ide else "chat"
        sys_text = compose_system_prompt(
            ide=ide,
            scenario=scenario,
            code_context=system_prompt if system_prompt else "",
        )

    try:
        from context_pipeline.cache import optimize_for_prefix_cache

        if sys_text and messages:
            sys_text, messages = optimize_for_prefix_cache(sys_text, messages)
    except ImportError:
        pass
    except Exception as exc:
        logger.warning("prefix cache optimization failed: %s", exc, exc_info=True)

    if fmt == "anthropic":
        if backend_cfg.get("no_system"):
            omni_msgs = [
                {
                    "role": m["role"],
                    "content": [{"type": "text", "text": m["content"]}]
                    if isinstance(m["content"], str)
                    else m["content"],
                }
                for m in messages
            ]
            body = {"model": model, "max_tokens": max_tokens, "messages": omni_msgs}
        else:
            body = {
                "model": model,
                "max_tokens": max_tokens,
                "system": sys_text,
                "messages": messages,
            }
    elif backend_cfg.get("no_system"):
        outgoing = [dict(m) for m in messages]
        if sys_text and outgoing:
            for msg in outgoing:
                if msg.get("role") == "user":
                    content = msg.get("content", "")
                    if isinstance(content, str):
                        msg["content"] = f"{sys_text}\n\n{content}"
                    elif isinstance(content, list):
                        msg["content"] = [{"type": "text", "text": sys_text}] + content
                    break
        body = {"model": model, "max_tokens": max_tokens, "messages": outgoing}
    else:
        body = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": [{"role": "system", "content": sys_text}] + messages,
        }

    extra = backend_cfg.get("extra_body")
    if extra and isinstance(extra, dict):
        body.update(extra)

    if stream or backend_cfg.get("force_stream_param"):
        body["stream"] = bool(stream)

    if tools:
        body["tools"] = tools

    return json.dumps(body).encode()
