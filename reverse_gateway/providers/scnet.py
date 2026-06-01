"""SCNet large-context reverse adapter."""

from __future__ import annotations

import time

import httpx

from reverse_gateway.config import ProviderConfig, scnet_config
from reverse_gateway.errors import classify_error
from reverse_gateway.models import ProbeResult
from reverse_gateway.providers.scnet_adapter import attach_text_files, build_headers, build_payload, latest_user_content, normalize_response

FILE_CONTEXT_BRIDGE_PROMPT = "?" * 32
from reverse_gateway.providers.scnet_cookie import cookie_path, load_cookie_state
from reverse_gateway.providers.scnet_file_context import should_bridge_text, upload_text_context_chunks
from reverse_gateway.providers.scnet_protocol import load_template, protocol_path
from reverse_gateway.rate_limit import ConcurrencyGate


PROVIDER_NAME = "scnet_large"
PORT = 4505
BACKENDS = ("scnet_large_ds_flash", "scnet_large_ds_pro")
_gate = ConcurrencyGate(scnet_config().max_concurrency)


def probe() -> ProbeResult:
    cfg = scnet_config()
    template = load_template()
    cookies = load_cookie_state()
    if not cfg.enabled:
        reason = "SCNet reverse adapter is disabled."
        if template:
            reason = "SCNet protocol template is present but SCNET_REVERSE_ENABLED is not set."
        return ProbeResult(
            provider=PROVIDER_NAME,
            healthy=False,
            status="disabled_no_adapter",
            reason=reason,
            error_class="disabled_no_adapter",
        )
    if cfg.upstream_url:
        return ProbeResult(
            provider=PROVIDER_NAME,
            healthy=True,
            status="ready_proxy_shell",
            reason="SCNet reverse sidecar is enabled with an explicit upstream shell.",
        )
    if not template:
        return ProbeResult(
            provider=PROVIDER_NAME,
            healthy=False,
            status="disabled_missing_protocol",
            reason="SCNET_REVERSE_PROTOCOL_PATH must point to a SCNet Web Chat protocol template.",
            error_class="protocol_error",
        )
    if not cookies or not cookies.cookie_header():
        return ProbeResult(
            provider=PROVIDER_NAME,
            healthy=False,
            status="disabled_missing_cookies",
            reason="SCNET_REVERSE_COOKIE_PATH must contain a valid SCNet login cookie export.",
            error_class="auth_expired",
        )
    return ProbeResult(
        provider=PROVIDER_NAME,
        healthy=True,
        status="ready_protocol_adapter",
        reason="SCNet Web Chat protocol adapter is enabled with protocol template and login cookies.",
    )


def config_status() -> dict[str, object]:
    cfg = scnet_config()
    gate = _gate.state
    template = load_template()
    cookies = load_cookie_state()
    return {
        "enabled": cfg.enabled,
        "upstream_configured": bool(cfg.upstream_url),
        "protocol_path": str(protocol_path()),
        "protocol_template_loaded": template is not None,
        "protocol_template": template.redacted() if template else None,
        "cookie_path": str(cookie_path()),
        "cookie_state_loaded": cookies is not None,
        "cookie_count": len(cookies.cookies) if cookies else 0,
        "cookies": cookies.redacted() if cookies else [],
        "max_concurrency": cfg.max_concurrency,
        "in_flight": gate.in_flight,
        "timeout_seconds": cfg.timeout_seconds,
        "file_context_enabled": cfg.file_context_enabled,
        "file_context_threshold_chars": cfg.file_context_threshold_chars,
        "file_context_chunk_chars": cfg.file_context_chunk_chars,
        "file_context_max_files": cfg.file_context_max_files,
        "file_context_max_total_chars": cfg.file_context_max_total_chars,
    }


def sidecar_health() -> dict[str, object]:
    result = probe()
    return {
        "provider": PROVIDER_NAME,
        "port": PORT,
        "backends": list(BACKENDS),
        "probe": result.to_dict(),
        "config": config_status(),
    }


def forward_chat(body: dict, cfg: ProviderConfig | None = None) -> tuple[int, dict]:
    active_config = cfg or scnet_config()
    if not active_config.enabled:
        return 503, {
            "error": {
                "message": "SCNet reverse adapter disabled_no_adapter",
                "type": "disabled_no_adapter",
            }
        }
    if active_config.upstream_url:
        return _forward_upstream_shell(body, active_config)

    template = load_template()
    if not template:
        return 503, {
            "error": {
                "message": "SCNET_REVERSE_PROTOCOL_PATH is required",
                "type": "protocol_error",
            }
        }
    cookies = load_cookie_state()
    if not cookies or not cookies.cookie_header():
        return 503, {
            "error": {
                "message": "SCNET_REVERSE_COOKIE_PATH is required",
                "type": "auth_expired",
            }
        }

    headers = build_headers(template, cookies)
    payload = build_payload(template, body)
    content = latest_user_content(body)
    try:
        if active_config.file_context_enabled and should_bridge_text(
            content, active_config.file_context_threshold_chars
        ):
            uploaded = upload_text_context_chunks(
                content,
                headers,
                active_config.timeout_seconds,
                active_config.file_context_chunk_chars,
                active_config.file_context_max_files,
                active_config.file_context_max_total_chars,
            )
            # Bridge prompt: tell the model to read the uploaded text files.
            # Matches the Node.js proxy behaviour (scnet_large_proxy.js).
            attach_text_files(
                payload,
                [item.as_payload() for item in uploaded],
                FILE_CONTEXT_BRIDGE_PROMPT,
            )
    except httpx.HTTPError as exc:
        return 502, {"error": {"message": str(exc), "type": classify_error(str(exc))}}
    started = time.time()
    try:
        with _gate.acquire():
            response = httpx.post(
                template.endpoint,
                headers=headers,
                json=payload,
                timeout=active_config.timeout_seconds,
            )
    except RuntimeError as exc:
        return 429, {"error": {"message": str(exc), "type": "rate_limited"}}
    except httpx.TimeoutException as exc:
        return 504, {"error": {"message": str(exc), "type": "timeout"}}
    except httpx.HTTPError as exc:
        return 502, {"error": {"message": str(exc), "type": classify_error(str(exc))}}

    latency_ms = int((time.time() - started) * 1000)
    try:
        payload: object = response.json()
    except ValueError:
        payload = response.text
    if response.status_code >= 400:
        return _error_response(response.status_code, {"message": str(payload)[:500]}, latency_ms)
    if isinstance(payload, dict) and _looks_like_error(payload):
        return _error_response(response.status_code, payload, latency_ms)
    model = str(body.get("model") or "")
    return response.status_code, normalize_response(payload, model)


def _forward_upstream_shell(body: dict, active_config: ProviderConfig) -> tuple[int, dict]:
    started = time.time()
    try:
        with _gate.acquire():
            response = httpx.post(
                active_config.upstream_url,
                json=body,
                timeout=active_config.timeout_seconds,
            )
    except RuntimeError as exc:
        return 429, {"error": {"message": str(exc), "type": "rate_limited"}}
    except httpx.TimeoutException as exc:
        return 504, {"error": {"message": str(exc), "type": "timeout"}}
    except httpx.HTTPError as exc:
        return 502, {"error": {"message": str(exc), "type": classify_error(str(exc))}}

    latency_ms = int((time.time() - started) * 1000)
    try:
        payload = response.json()
    except ValueError:
        return response.status_code, {
            "error": {
                "message": response.text[:500],
                "type": classify_error(response.text),
                "latency_ms": latency_ms,
            }
        }
    if response.status_code >= 400:
        return _error_response(response.status_code, payload, latency_ms)
    return response.status_code, payload


def _looks_like_error(payload: dict) -> bool:
    code = str(payload.get("code") or "")
    if code and code != "0":
        return True
    return isinstance(payload.get("error"), dict)


def _error_response(status_code: int, payload: dict, latency_ms: int) -> tuple[int, dict]:
    text = str(payload)
    payload.setdefault("error", {})
    if isinstance(payload["error"], dict):
        payload["error"].setdefault("type", classify_error(text))
        payload["error"].setdefault("latency_ms", latency_ms)
    return status_code, payload
