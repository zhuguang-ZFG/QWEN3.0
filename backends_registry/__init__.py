"""Backend provider registry (BACKENDS dict), split by provider family."""

import json as _json
import logging
import os
from pathlib import Path as _Path

from dotenv import load_dotenv

from .cloudflare import BACKENDS as _cf
from .coding_pool import BACKENDS as _coding
from .commercial import BACKENDS as _commercial
from .community_free import BACKENDS as _community
from .free_web import BACKENDS as _free_web
from .github import BACKENDS as _gh
from .google import BACKENDS as _google
from .groq import BACKENDS as _groq
from .kilo import BACKENDS as _kilo
from .misc import BACKENDS as _misc
from .mistral import BACKENDS as _mistral

# Imported for their startup logging side effects only.
from . import community_free as _community_free_module
from .coding_pool import community as _coding_community_module
from .modelscope import BACKENDS as _ms
from .nvidia import BACKENDS as _nvidia
from .openrouter import BACKENDS as _or
from .vps_proxies import BACKENDS as _vps

logger = logging.getLogger(__name__)

load_dotenv()

LM_URL = "http://localhost:1234/v1/chat/completions"

BACKENDS: dict[str, dict] = {}
BACKENDS.update(_ms)
BACKENDS.update(_cf)
BACKENDS.update(_gh)
BACKENDS.update(_or)
BACKENDS.update(_groq)
BACKENDS.update(_nvidia)
BACKENDS.update(_mistral)
BACKENDS.update(_google)
BACKENDS.update(_kilo)
BACKENDS.update(_free_web)
BACKENDS.update(_vps)
BACKENDS.update(_commercial)
BACKENDS.update(_community)
BACKENDS.update(_coding)
BACKENDS.update(_misc)


def add_backend(name: str, cfg: dict) -> None:
    """Register a new backend. Routes layer should use this instead of direct dict mutation."""
    BACKENDS[name] = dict(cfg)


def remove_backend(name: str) -> bool:
    """Unregister a backend. Returns False if not found."""
    return BACKENDS.pop(name, None) is not None


def has_backend(name: str) -> bool:
    """Check if a backend is registered."""
    return name in BACKENDS


def get_backend(name: str) -> dict | None:
    """Get backend config, or None if not found."""
    return BACKENDS.get(name)

# M6: All host-dependent backends migrated to VPS or deleted.
DISABLED_HOST_DEPENDENT_BACKENDS: dict[str, dict] = {}

# Loads data/backend_overrides.json and merges add/update/delete into BACKENDS.
_OVERLAY_PATH = _Path(__file__).resolve().parent.parent / "data" / "backend_overrides.json"


def _load_backend_overlay() -> None:
    """Merge backend overlay JSON into BACKENDS. Idempotent and safe to repeat."""
    if not _OVERLAY_PATH.exists():
        return
    try:
        overlay = _json.loads(_OVERLAY_PATH.read_text(encoding="utf-8"))
    except (_json.JSONDecodeError, OSError) as exc:
        logger.warning("failed to load backend overlay %s: %s", _OVERLAY_PATH, type(exc).__name__)
        return
    for name, cfg in overlay.get("add", {}).items():
        BACKENDS[name] = _normalize_overlay_backend(name, cfg)
    for name in overlay.get("delete", []):
        BACKENDS.pop(name, None)
    for name, cfg in overlay.get("update", {}).items():
        if name in BACKENDS:
            BACKENDS[name].update(_normalize_overlay_backend(name, cfg))


def _normalize_overlay_backend(name: str, cfg: dict) -> dict:
    normalized = dict(cfg)
    normalized.setdefault("fmt", "openai")
    normalized.setdefault("key", "none")
    normalized.setdefault("timeout", 30)
    normalized.setdefault("caps", [])
    if not normalized.get("model"):
        normalized["model"] = name
    return normalized


_load_backend_overlay()

# Emit startup warnings/info for opt-in cleartext backends after logging is configured.
_community_free_module.log_insecure_backend_status()
_coding_community_module.log_insecure_backend_status()
