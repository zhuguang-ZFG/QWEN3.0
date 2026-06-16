"""API format detection: identify whether a provider uses OpenAI, Anthropic,
or custom API protocol by probing standard endpoints."""

import logging
from dataclasses import dataclass, field
from enum import Enum

import httpx

logger = logging.getLogger(__name__)


class ApiFormat(str, Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    CUSTOM = "custom"
    UNKNOWN = "unknown"


@dataclass
class ApiProfile:
    url: str
    format: ApiFormat = ApiFormat.UNKNOWN
    has_models_endpoint: bool = False
    supports_streaming: bool = False
    supports_tools: bool = False
    requires_auth: bool = False
    auth_type: str = ""
    error: str = ""
    details: dict = field(default_factory=dict)


async def detect_format(base_url: str) -> ApiProfile:
    """Detect API format by probing standard endpoints."""
    url = base_url.rstrip("/")
    profile = ApiProfile(url=url)

    # Step 1: Probe /v1/models (OpenAI signature)
    models_url = f"{url}/v1/models"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(models_url, follow_redirects=True)
            if resp.status_code in (200, 401, 403):
                profile.has_models_endpoint = True
                profile.format = ApiFormat.OPENAI
                if resp.status_code in (401, 403):
                    profile.requires_auth = True
                    profile.auth_type = _detect_auth(resp)
                elif resp.status_code == 200:
                    try:
                        data = resp.json()
                        if "data" in data and isinstance(data["data"], list):
                            profile.details["model_count"] = len(data["data"])
                            profile.details["models_preview"] = [
                                m.get("id", "") for m in data["data"][:20]
                            ]
                    except Exception:
                        logger.debug("models JSON parse failed", exc_info=True)
    except Exception as exc:
        logger.debug("Probe %s: %s", models_url, type(exc).__name__)

    # Step 2: Probe chat completions
    chat_url = f"{url}/v1/chat/completions"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                chat_url,
                json={"model": "x", "messages": [{"role": "user", "content": "hi"}]},
                headers={"Content-Type": "application/json"},
            )
            if resp.status_code not in (404, 405):
                profile.details["chat_accessible"] = True
                if resp.status_code in (401, 403):
                    profile.requires_auth = True
                    profile.auth_type = profile.auth_type or _detect_auth(resp)
    except Exception:
        logger.debug("chat probe failed", exc_info=True)
    anthropic_url = f"{url}/v1/messages"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.head(anthropic_url, follow_redirects=True)
            if resp.status_code not in (404,):
                profile.details["anthropic_endpoint"] = True
                if profile.format == ApiFormat.UNKNOWN:
                    profile.format = ApiFormat.ANTHROPIC
    except Exception:
        logger.debug("anthropic probe failed", exc_info=True)

    if profile.format == ApiFormat.UNKNOWN and profile.has_models_endpoint:
        profile.format = ApiFormat.OPENAI

    return profile


def _detect_auth(resp) -> str:
    """Detect auth type from response."""
    www_auth = resp.headers.get("www-authenticate", "").lower()
    if "bearer" in www_auth:
        return "bearer"
    if "api-key" in www_auth or "apikey" in www_auth:
        return "api-key"
    return "unknown"


async def probe_provider(base_url: str) -> ApiProfile:
    """Full provider probe."""
    profile = await detect_format(base_url)

    # If OpenAI, try actual chat
    if profile.format == ApiFormat.OPENAI and not profile.requires_auth:
        try:
            url = base_url.rstrip("/") + "/v1/chat/completions"
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.post(
                    url,
                    json={
                        "model": "x",
                        "messages": [{"role": "user", "content": "say hi"}],
                        "max_tokens": 5,
                    },
                    headers={"Content-Type": "application/json"},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    profile.details["actual_model"] = data.get("model", "")
                    profile.details["usage"] = data.get("usage", {})
        except Exception as exc:
            profile.error = str(exc)

    return profile
