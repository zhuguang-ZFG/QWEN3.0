"""Key selection helpers extracted from http_request_builder (CQ-014).

Handles: key pool provider detection, key selection, exhaustion checks,
and key result reporting.
"""

from __future__ import annotations

import logging

import key_pool
from backends import infer_key_pool_provider

logger = logging.getLogger(__name__)


def key_pool_provider(backend: str, backend_cfg: dict) -> str:
    """Infer the key pool provider for a backend."""
    return infer_key_pool_provider(backend, backend_cfg)


def select_key(backend: str, backend_cfg: dict) -> tuple[str, str]:
    """Select an API key for the given backend.

    Returns (key, provider). Empty key means the provider's pool is exhausted.
    """
    provider = key_pool_provider(backend, backend_cfg)
    if provider:
        pool_configured = key_pool.ensure_env_pool(provider)
        if pool_configured:
            if key_pool.is_exhausted(provider):
                return "", provider
            selected = key_pool.get_key(provider)
            if selected:
                return selected, provider
    return backend_cfg.get("key", ""), provider


def has_key(backend: str, backend_cfg: dict) -> bool:
    """Check if a usable API key exists for the backend."""
    selected, _provider = select_key(backend, backend_cfg)
    return bool(selected)


def report_key_result(
    provider: str,
    key: str,
    success: bool,
    error_code: int = 0,
    retry_after: int = 0,
) -> None:
    """Report key usage result back to the key pool."""
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
