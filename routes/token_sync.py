"""Token sync — receive refreshed API keys from Windows refresh scripts.

Usage:
  POST /internal/v1/token-sync
  Authorization: Bearer <LIMA_ADMIN_TOKEN>
  Body: {"tokens": {"longcat": "ak_new...", "mimo_v2_5": "tp_new..."}}

The server updates backends.py runtime config and validates each token.
"""

from __future__ import annotations

import urllib.error
import urllib.request
import json
import logging

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel

from access_guard import require_private_api_key

_log = logging.getLogger(__name__)
router = APIRouter()

# In-memory token store — overrides backends.py at runtime
_token_overrides: dict[str, str] = {}


class TokenSyncBody(BaseModel):
    tokens: dict[str, str]  # backend_name -> new API key/token


class TokenSyncResult(BaseModel):
    updated: list[str]
    validated: list[str]
    failed: list[str]


def _require_auth(authorization: str = Header(default="")) -> None:
    """Accept admin token or private API key."""
    require_private_api_key(authorization=authorization)


def get_token_override(backend_name: str) -> str | None:
    """Get runtime token override for a backend. Returns None if no override."""
    return _token_overrides.get(backend_name)


def _validate_token(name: str, key: str, url: str, model: str) -> bool:
    """Quick validation: send a minimal request to check if the token works."""
    try:
        body = json.dumps({
            "model": model,
            "messages": [{"role": "user", "content": "hi"}],
            "max_tokens": 3,
        }).encode()
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win6; x64) AppleWebKit/537.36",
            "Authorization": f"Bearer {key}",
        }
        req = urllib.request.Request(url, data=body, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        # Check for valid response
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        return bool(content)
    except urllib.error.HTTPError as e:
        return e.code != 401  # 401 = invalid key, other errors are transient
    except Exception:
        return False


@router.post("/internal/v1/token-sync", dependencies=[Depends(_require_auth)])
async def sync_tokens(body: TokenSyncBody) -> dict:
    """Receive refreshed tokens from Windows, validate, and apply."""
    from backends import BACKENDS

    updated = []
    validated = []
    failed = []

    for name, key in body.tokens.items():
        if not key or key == _token_overrides.get(name):
            continue

        cfg = BACKENDS.get(name, {})
        if not cfg:
            failed.append(f"{name}: unknown backend")
            continue

        url = cfg.get("url", "")
        model = cfg.get("model", "")
        if not url or not model:
            failed.append(f"{name}: no url/model configured")
            continue

        # Validate the new token
        if _validate_token(name, key, url, model):
            _token_overrides[name] = key
            updated.append(name)
            validated.append(name)
            _log.info("Token updated and validated: %s", name)
        else:
            failed.append(f"{name}: validation failed (401 or timeout)")

    return {
        "updated": updated,
        "validated": validated,
        "failed": failed,
        "total_overrides": len(_token_overrides),
    }


@router.get("/internal/v1/token-sync/status", dependencies=[Depends(_require_auth)])
async def token_sync_status() -> dict:
    """Check current token override status."""
    from backends import BACKENDS

    status = {}
    for name, override in _token_overrides.items():
        cfg = BACKENDS.get(name, {})
        status[name] = {
            "has_override": True,
            "key_preview": override[:15] + "..." if len(override) > 15 else override,
            "original_key_preview": (cfg.get("key", "") or "")[:15] + "...",
            "url": cfg.get("url", ""),
        }

    return {
        "overrides": len(_token_overrides),
        "backends": status,
    }
