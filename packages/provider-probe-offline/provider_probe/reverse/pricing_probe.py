"""Pricing probe: detect pricing model and free tier from providers."""

import logging
import re

import httpx

logger = logging.getLogger(__name__)

# Common pricing patterns in API documentation and responses
_PRICE_PER_TOKEN = re.compile(
    r"\$?(\d+\.?\d*)\s*/\s*(?:1[Mm]|[Mm]illion)\s*tokens?",
)
_FREE_TIER = re.compile(
    r"(?i)(free\s*tier|no\s*cost|免费|complimentary|zero\s*cost|"
    r"unlimited.*free|free.*unlimited)",
)


async def probe_pricing(base_url: str) -> dict:
    """Probe pricing information from a provider.

    Checks /v1/models response and common pricing pages.
    """
    result = {
        "is_free": False,
        "has_free_tier": False,
        "pricing_detected": False,
        "models_free": 0,
        "models_total": 0,
    }

    # Check /v1/models for pricing data
    url = base_url.rstrip("/") + "/v1/models"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, follow_redirects=True)
            if resp.status_code == 200:
                data = resp.json()
                models = data.get("data", data.get("models", []))
                result["models_total"] = len(models)

                free_count = 0
                for model in models:
                    pricing = model.get("pricing", {})
                    if not pricing:
                        continue
                    prompt = float(pricing.get("prompt", -1))
                    completion = float(pricing.get("completion", -1))
                    if prompt == 0.0 and completion == 0.0:
                        free_count += 1

                result["models_free"] = free_count
                result["is_free"] = free_count > 0
                result["pricing_detected"] = True
    except Exception as exc:
        # Pricing endpoint probe failure is expected for providers without pricing metadata.
        logger.warning("pricing probe HTTP error for %s: %s", base_url, exc)

    # Check pricing page
    pricing_urls = [
        f"{base_url.rstrip('/')}/pricing",
        f"{base_url.rstrip('/')}/docs/pricing",
    ]
    for pricing_url in pricing_urls:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(pricing_url, follow_redirects=True)
                if resp.status_code == 200:
                    text = resp.text.lower()
                    if _FREE_TIER.search(text):
                        result["has_free_tier"] = True
                        result["evidence"] = f"Free tier found on {pricing_url}"
        except Exception as exc:
            logging.debug("pricing probe failed for %s: %s", pricing_url, exc)
            continue

    return result


async def estimate_cost(base_url: str, model_id: str = "") -> dict:
    """Estimate per-token cost by probing the API response for pricing metadata."""
    result = {"prompt_cost": None, "completion_cost": None, "currency": "USD"}

    url = base_url.rstrip("/") + "/v1/models"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, follow_redirects=True)
            if resp.status_code == 200:
                data = resp.json()
                models = data.get("data", [])
                for m in models:
                    m_id = m.get("id", "")
                    if model_id and model_id not in m_id:
                        continue
                    pricing = m.get("pricing", {})
                    if pricing:
                        result["prompt_cost"] = pricing.get("prompt")
                        result["completion_cost"] = pricing.get("completion")
                        result["image_cost"] = pricing.get("image")
                        result["model_id"] = m_id
                        break
    except Exception as exc:
        # Cost estimation failure is expected when pricing metadata is unavailable.
        logger.warning("cost estimation failed for %s: %s", base_url, exc)

    return result
