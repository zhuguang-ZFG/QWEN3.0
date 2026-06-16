"""Quick coding evaluation for discovered AI API providers.

Runs a short coding test to assess whether a provider's models are suitable
for code generation tasks. Uses simple, deterministic test cases.
"""

import logging
import time

import httpx

logger = logging.getLogger(__name__)

# Simple coding test: FizzBuzz (a classic)
CODING_PROMPT = (
    "Write a Python function `fizzbuzz(n)` that returns a list of strings. "
    "For numbers 1 to n: print 'Fizz' if divisible by 3, 'Buzz' if by 5, "
    "'FizzBuzz' if by both, else the number as string. "
    "ONLY output the function code, no explanation."
)

EXPECTED_KEYWORDS = ["fizzbuzz", "def", "return", "Fizz", "Buzz"]


async def run_coding_test(
    base_url: str,
    model: str = "",
    api_key: str = "",
    timeout: float = 60.0,
) -> dict:
    """Run a FizzBuzz coding test against a provider.

    Returns: score, code, model_used, latency_ms, error
    """
    url = base_url.rstrip("/") + "/v1/chat/completions"
    body = {
        "model": model or "gpt-3.5-turbo",
        "messages": [
            {"role": "system", "content": "You are a coding assistant. Output only code."},
            {"role": "user", "content": CODING_PROMPT},
        ],
        "max_tokens": 500,
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

            if resp.status_code != 200:
                return {
                    "score": 0,
                    "code": "",
                    "model_used": model,
                    "latency_ms": round(elapsed, 1),
                    "error": f"HTTP {resp.status_code}",
                }

            data = resp.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")

            # Score: count expected keywords present
            score = sum(1 for kw in EXPECTED_KEYWORDS if kw.lower() in content.lower())
            score = min(score, len(EXPECTED_KEYWORDS))

            return {
                "score": score,
                "max_score": len(EXPECTED_KEYWORDS),
                "code": content[:1000],
                "model_used": data.get("model", model),
                "latency_ms": round(elapsed, 1),
                "tokens": data.get("usage", {}).get("total_tokens", 0),
                "error": None,
            }
    except httpx.TimeoutException:
        return {"score": 0, "error": "timeout", "latency_ms": timeout * 1000}
    except Exception as exc:
        return {"score": 0, "error": str(exc)}


async def quick_eval(base_url: str, model: str = "") -> dict:
    """Quick evaluation: runs coding test and returns summary score.

    Score: 0-5, where 5 = perfect FizzBuzz implementation.
    """
    result = await run_coding_test(base_url, model=model)
    return {
        "coding_score": result.get("score", 0),
        "max_score": result.get("max_score", len(EXPECTED_KEYWORDS)),
        "available": result.get("error") is None,
        "latency_ms": result.get("latency_ms", -1),
        "model_used": result.get("model_used", ""),
        "error": result.get("error"),
    }
