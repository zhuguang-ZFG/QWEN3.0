"""Connectivity test: latency measurement and availability check."""

import logging
import time

import httpx

logger = logging.getLogger(__name__)


async def measure_latency(url: str, samples: int = 3) -> dict:
    """Measure API latency with multiple samples.

    Returns: avg_ms, min_ms, max_ms, samples, success_rate
    """
    latencies: list[float] = []
    success = 0

    for _ in range(samples):
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                start = time.monotonic()
                resp = await client.get(url, follow_redirects=True)
                elapsed = (time.monotonic() - start) * 1000
                if resp.status_code < 500:
                    latencies.append(elapsed)
                    success += 1
        except Exception:
            latencies.append(-1)

    valid = [l for l in latencies if l >= 0]

    return {
        "avg_ms": round(sum(valid) / len(valid), 1) if valid else -1,
        "min_ms": round(min(valid), 1) if valid else -1,
        "max_ms": round(max(valid), 1) if valid else -1,
        "samples": samples,
        "success": success,
        "success_rate": round(success / samples, 2),
    }


async def probe_chat_completion(base_url: str, model: str = "", api_key: str = "", timeout: float = 30.0) -> dict:
    """Test actual chat completion with a simple query.

    Returns: status, latency_ms, model_used, tokens, error
    """
    url = base_url.rstrip("/") + "/v1/chat/completions"
    body = {
        "model": model or "gpt-3.5-turbo",
        "messages": [{"role": "user", "content": "Reply with exactly: OK"}],
        "max_tokens": 5,
        "temperature": 0,
    }
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            start = time.monotonic()
            resp = await client.post(url, json=body, headers=headers)
            elapsed = (time.monotonic() - start) * 1000

            if resp.status_code == 200:
                data = resp.json()
                return {
                    "status": "ok",
                    "latency_ms": round(elapsed, 1),
                    "model_used": data.get("model", ""),
                    "tokens": data.get("usage", {}).get("total_tokens", 0),
                    "error": None,
                }
            return {
                "status": "failed",
                "latency_ms": round(elapsed, 1),
                "http_status": resp.status_code,
                "error": resp.text[:500],
            }
    except httpx.TimeoutException:
        return {"status": "timeout", "latency_ms": timeout * 1000, "error": "timeout"}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


async def probe_availability(base_url: str) -> dict:
    """Quick availability check: models endpoint + chat completion."""
    chat_result = await probe_chat_completion(base_url)

    # Also check models
    models_url = base_url.rstrip("/") + "/v1/models"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(models_url, follow_redirects=True)
            models_ok = resp.status_code == 200
    except Exception:
        models_ok = False

    return {
        "available": chat_result["status"] == "ok",
        "models_endpoint": models_ok,
        "chat_test": chat_result["status"],
        "latency_ms": chat_result.get("latency_ms", -1),
        "model_used": chat_result.get("model_used", ""),
    }
