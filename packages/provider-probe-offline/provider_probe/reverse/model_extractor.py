"""Model extractor: extract model lists from API endpoints."""

import logging

import httpx

logger = logging.getLogger(__name__)


async def extract_models(base_url: str, api_key: str = "") -> list[dict]:
    """Extract model information from a provider's /v1/models endpoint.

    Returns list of dicts with: id, owned_by, created, context_length, pricing
    """
    url = base_url.rstrip("/") + "/v1/models"
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(url, headers=headers, follow_redirects=True)
            if resp.status_code != 200:
                logger.debug("extract_models %s: HTTP %d", url, resp.status_code)
                return []

            data = resp.json()
            models = data.get("data", data.get("models", []))

            result = []
            for m in models:
                result.append(
                    {
                        "id": m.get("id", ""),
                        "name": m.get("name", m.get("id", "")),
                        "owned_by": m.get("owned_by", ""),
                        "created": m.get("created", 0),
                        "context_length": m.get("context_length", 0),
                        "pricing": m.get("pricing", {}),
                        "is_free": _is_free_model(m),
                    }
                )
            return result
    except Exception as exc:
        logger.warning("extract_models error: %s", exc)
        return []


def _is_free_model(model: dict) -> bool:
    """Heuristic: check if a model appears to be free."""
    pricing = model.get("pricing", {})
    if not pricing:
        return False
    prompt_price = float(pricing.get("prompt", pricing.get("input", -1)))
    completion_price = float(pricing.get("completion", pricing.get("output", -1)))
    if prompt_price == 0 and completion_price == 0:
        return True

    # Check for :free suffix (OpenRouter convention)
    model_id = model.get("id", "")
    if ":free" in model_id:
        return True

    return False


async def probe_models_endpoint(base_url: str) -> dict:
    """Quick probe: check if /v1/models exists and return summary."""
    url = base_url.rstrip("/") + "/v1/models"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, follow_redirects=True)
            return {
                "exists": resp.status_code == 200,
                "status": resp.status_code,
                "response_size": len(resp.content),
                "requires_auth": resp.status_code in (401, 403),
            }
    except Exception as exc:
        return {"exists": False, "error": str(exc)}
