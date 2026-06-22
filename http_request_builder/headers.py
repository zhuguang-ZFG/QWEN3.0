"""Header and key-pool helpers."""

from __future__ import annotations

import os
import time
from typing import Any

import key_pool
from backend_utils import infer_key_pool_provider
from brand_config import USER_AGENT


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
            "User-Agent": USER_AGENT,
        }

    for hk, hv in backend_cfg.get("extra_headers", {}).items():
        if hv == "dynamic" and hk == "X-Request-Timestamp":
            headers[hk] = str(int(time.time()))
        elif hv != "dynamic":
            headers[hk] = hv

    return headers


def _key_pool_provider(backend: str, backend_cfg: dict) -> str:
    return infer_key_pool_provider(backend, backend_cfg)


def _select_key(backend: str, backend_cfg: dict) -> tuple[str, str]:
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

    raw_key = backend_cfg.get("key", "")
    if not raw_key:
        key_env_var = backend_cfg.get("key_env_var", "")
        if key_env_var:
            raw_key = os.environ.get(key_env_var, "")
        if not raw_key:
            for env_name in (
                f"{backend.upper()}_API_KEY",
                f"{backend.upper()}_KEY",
                f"{backend.replace('-', '_').upper()}_KEY",
            ):
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
