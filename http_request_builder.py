"""HTTP client factory and request builders (CQ-014 slice 8)."""

from __future__ import annotations

import json
import logging
import os
import threading
import time as _time

import httpx

import key_pool
from backends import GFW_BACKENDS, infer_key_pool_provider
from opencode_message_normalizer import normalize_messages
from reasoning_variants import apply_variant
from session_options import resolve_session_options

logger = logging.getLogger(__name__)

GFW_PROXY_URL = os.environ.get("GFW_PROXY", "http://127.0.0.1:7897")
GFW_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

# ── Connection pool per backend — reused across requests to eliminate TCP/TLS handshake ──
_async_client_pool: dict[str, httpx.AsyncClient] = {}
_sync_client_pool: dict[str, httpx.Client] = {}
_sync_pool_lock = threading.Lock()
_POOL_MAX_KEEPALIVE = 5
_POOL_MAX_CONNECTIONS = 20
_POOL_RECYCLE_SECONDS = 300


def _build_client(backend: str, timeout: float) -> httpx.Client:
    """Create a new httpx.Client (not pooled). Kept for backward compat."""
    if backend in GFW_BACKENDS:
        return httpx.Client(
            proxy=GFW_PROXY_URL,
            headers={"User-Agent": GFW_USER_AGENT},
            timeout=httpx.Timeout(timeout, connect=10.0),
        )
    return httpx.Client(timeout=httpx.Timeout(timeout, connect=10.0))


def _build_async_client(backend: str, timeout: float) -> httpx.AsyncClient:
    """Create a new httpx.AsyncClient (not pooled). Kept for backward compat."""
    if backend in GFW_BACKENDS:
        return httpx.AsyncClient(
            proxy=GFW_PROXY_URL,
            headers={"User-Agent": GFW_USER_AGENT},
            timeout=httpx.Timeout(timeout, connect=10.0),
        )
    return httpx.AsyncClient(timeout=httpx.Timeout(timeout, connect=10.0))


def _get_client(backend: str, timeout: float) -> httpx.Client:
    """Get a pooled httpx.Client — reuses connections across requests.

    Thread-safe via _sync_pool_lock. Timeout is included in the pool key
    so that callers with different timeout requirements get separate clients.
    Old pool entries are closed on eviction to avoid TCP/FD leaks.
    """
    key = f"{backend}:{int(timeout)}:{int(_time.time() // _POOL_RECYCLE_SECONDS)}"
    with _sync_pool_lock:
        if key not in _sync_client_pool:
            limits = httpx.Limits(
                max_keepalive_connections=_POOL_MAX_KEEPALIVE,
                max_connections=_POOL_MAX_CONNECTIONS)
            if backend in GFW_BACKENDS:
                client = httpx.Client(
                    proxy=GFW_PROXY_URL,
                    headers={"User-Agent": GFW_USER_AGENT},
                    timeout=httpx.Timeout(timeout, connect=10.0),
                    limits=limits)
            else:
                client = httpx.Client(
                    timeout=httpx.Timeout(timeout, connect=10.0),
                    limits=limits)
            # Clean up old pool entries for this backend
            stale = [k for k in _sync_client_pool if k.startswith(f"{backend}:")]
            for sk in stale[:-2]:
                old = _sync_client_pool.pop(sk, None)
                if old is not None:
                    try:
                        old.close()
                    except Exception as exc:
                        logger.debug("pool cleanup: close(%s) failed: %s", sk, type(exc).__name__)
            _sync_client_pool[key] = client
        return _sync_client_pool[key]


def _get_async_client(backend: str, timeout: float) -> httpx.AsyncClient:
    """Get a pooled httpx.AsyncClient — reuses connections across requests.

    Timeout is included in the pool key. Old pool entries are closed on eviction.
    No lock needed — asyncio event loop is single-threaded per context.
    """
    key = f"{backend}:{int(timeout)}:{int(_time.time() // _POOL_RECYCLE_SECONDS)}"
    if key not in _async_client_pool:
        limits = httpx.Limits(
            max_keepalive_connections=_POOL_MAX_KEEPALIVE,
            max_connections=_POOL_MAX_CONNECTIONS)
        if backend in GFW_BACKENDS:
            client = httpx.AsyncClient(
                proxy=GFW_PROXY_URL,
                headers={"User-Agent": GFW_USER_AGENT},
                timeout=httpx.Timeout(timeout, connect=10.0),
                limits=limits)
        else:
            client = httpx.AsyncClient(
                timeout=httpx.Timeout(timeout, connect=10.0),
                limits=limits)
        # Clean up old pool entries for this backend
        stale = [k for k in _async_client_pool if k.startswith(f"{backend}:")]
        for sk in stale[:-2]:
            old = _async_client_pool.pop(sk, None)
            if old is not None:
                try:
                    old.close()
                except Exception as exc:
                    logger.debug("pool cleanup: close(%s) failed: %s", sk, type(exc).__name__)
        _async_client_pool[key] = client
    return _async_client_pool[key]


def _build_headers(backend_cfg: dict, key: str | None = None) -> dict:
    fmt = backend_cfg["fmt"]
    auth_style = backend_cfg.get("auth", "x-api-key")
    key = backend_cfg["key"] if key is None else key

    # 支持后端自定义headers（如免费API需要User-Agent）
    custom_headers = backend_cfg.get("headers", {})

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
    # 合并自定义headers（覆盖默认值）
    headers.update(custom_headers)
    return headers


def _build_headers_with_affinity(
    backend_cfg: dict,
    key: str | None = None,
    backend_name: str = "",
    session_id: str = "",
) -> dict:
    """Build headers with optional x-session-affinity (request.ts:181).

    Non-OpenCode providers get x-session-affinity for load balancer stickiness.
    """
    headers = _build_headers(backend_cfg, key)
    # M-OC21: x-session-affinity for non-opencode providers
    if session_id and backend_name:
        from provider_kind import detect_provider_kind
        pk = detect_provider_kind(backend_name, backend_cfg.get("model", ""))
        if pk not in ("opencode_zen",):
            headers["x-session-affinity"] = session_id
    return headers


def _key_pool_provider(backend: str, backend_cfg: dict) -> str:
    return infer_key_pool_provider(backend, backend_cfg)


def _select_key(backend: str, backend_cfg: dict) -> tuple[str, str]:
    provider = _key_pool_provider(backend, backend_cfg)
    if provider:
        pool_configured = key_pool.ensure_env_pool(provider)
        if pool_configured:
            if key_pool.is_exhausted(provider):
                return "", provider
            selected = key_pool.get_key(provider)
            if selected:
                return selected, provider
    return backend_cfg.get("key", ""), provider


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
    reasoning_effort: str | None = None,
    backend_name: str = "",
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

    # M-OC14: model-family-aware system prompt enhancement (system.ts:19-33)
    try:
        from opencode_system_prompt import enhance_system_prompt
        sys_text = enhance_system_prompt(sys_text, model, backend_name)
    except ImportError:
        pass
    except Exception as exc:
        logger.debug("system prompt enhancement failed: %s", exc)

    # M-OC9: filter unsupported media (image/audio/video/pdf) per model capability
    from opencode_media_detect import filter_unsupported_media
    messages = filter_unsupported_media(messages, backend_name, model)

    # Message normalization (OpenCode 兼容): surrogate 清理、空消息过滤、toolCallId 规范化
    messages = normalize_messages(messages, backend_cfg.get("model", ""))

    # M-OC10: truncate oversized tool outputs (truncate.ts: MAX_LINES=2000, MAX_BYTES=50KB)
    from opencode_truncate import truncate_tool_results_in_messages
    messages = truncate_tool_results_in_messages(messages)

    # M-OC6: prompt caching (Anthropic/OpenRouter/Bedrock/etc. cache control markers)
    from opencode_prompt_cache import apply_prompt_caching
    messages = apply_prompt_caching(messages, backend_name, model)

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
        # M-OC15: normalize tool JSON schemas ($ref inline, allOf flatten, integer bounds)
        try:
            from opencode_tool_schema import normalize_tools_schemas
            tools = normalize_tools_schemas(tools)
        except ImportError:
            pass

        # M-OC7: sanitize tool schemas for Kimi/Gemini (transform.ts:1254-1371)
        from opencode_schema_sanitize import sanitize_tools_for_backend
        tools = sanitize_tools_for_backend(tools, backend_name, model)

        # M-OC16: filter tools by model family (apply_patch vs edit/write)
        try:
            from opencode_tool_routing import filter_tools_for_model
            tools = filter_tools_for_model(tools, model, backend_name)
        except ImportError:
            pass

        # M-OC17: Copilot _noop tool workaround (request.ts:142-158)
        try:
            from opencode_tool_routing import inject_noop_tool_if_needed
            tools = inject_noop_tool_if_needed(tools, messages, backend_name)
        except ImportError:
            pass

        body["tools"] = tools

        # M-OC20: repair tool call names (case-insensitive) + invalid tool routing
        try:
            from opencode_tool_repair import should_inject_invalid_tool
            if should_inject_invalid_tool(tools):
                from opencode_tool_repair import get_invalid_tool_definition
                body["tools"] = list(tools) + [get_invalid_tool_definition()]
        except ImportError:
            pass

    if reasoning_effort:
        variant_opts = apply_variant(backend_name, model, reasoning_effort)
        if variant_opts:
            for k, v in variant_opts.items():
                body[k] = v
        else:
            body["reasoning_effort"] = reasoning_effort

    # M-OC5: sampling parameters (temperature/top_p/top_k per model family)
    from opencode_sampling import resolve_sampling_params
    sampling = resolve_sampling_params(model, backend_name)
    for k, v in sampling.items():
        if k not in body:
            body[k] = v

    # M-OC3: session options (store/enable_thinking/toolStreaming/promptCacheKey)
    if _is_ide_backend_session(backend_name, ide):
        session_opts = resolve_session_options(backend_name, model, session_id=_mk_session_id(backend_name))

        # M-OC18: wrap options in providerOptions namespace keys
        try:
            from opencode_provider_namespace import build_provider_options_for_body
            from provider_kind import detect_provider_kind
            pk = detect_provider_kind(backend_name, model)
            provider_opts = build_provider_options_for_body(session_opts, pk, backend_name, model)
            if provider_opts:
                body["providerOptions"] = provider_opts
        except (ImportError, Exception) as exc:
            logger.debug("provider namespace wrapping failed: %s", exc)

        for k, v in session_opts.items():
            if k not in body:
                body[k] = v

    # M-OC22: doom loop detection — break repeated identical tool calls
    try:
        from opencode_doom_loop import detect_doom_loop, inject_doom_loop_break
        loop_info = detect_doom_loop(messages)
        if loop_info:
            messages = inject_doom_loop_break(messages, loop_info)
    except ImportError:
        pass

    # M-OC19: cap max_tokens at OUTPUT_TOKEN_MAX=32000 (transform.ts:18)
    try:
        from opencode_output_limit import cap_max_tokens_in_body
        cap_max_tokens_in_body(body, backend_name, model)
    except ImportError:
        pass

    return json.dumps(body).encode()


def _is_ide_backend_session(backend_name: str, ide: str) -> bool:
    """Check if this is an IDE-backed session that should receive session-level optimizations."""
    return bool(ide and ide.lower() in ("opencode",))


def _mk_session_id(backend_name: str) -> str:
    """Generate a deterministic session ID for prompt caching.

    Same backend + same day → same session ID, enabling promptCacheKey reuse.
    """
    import hashlib
    day_key = _time.strftime("%Y%m%d")
    raw = f"{backend_name}:{day_key}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]

