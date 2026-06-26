"""Optional Instructor-patched OpenAI client.

Instructor is not a hard dependency; when absent the router falls back to the
rule-based classifiers and Pydantic validators defined elsewhere.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, TypeVar

import key_pool

if TYPE_CHECKING:
    import openai
    import instructor
    from pydantic import BaseModel

logger = logging.getLogger(__name__)

T = TypeVar("T", bound="BaseModel")

_PROVIDER_BASE_URLS = {
    "groq": "https://api.groq.com/openai/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "cerebras": "https://api.cerebras.ai/v1",
}


def instructor_enabled() -> bool:
    """Whether Instructor-based structured outputs are enabled."""
    import os

    return os.environ.get("LIMA_INSTRUCTOR_ENABLED", "0").strip().lower() in {"1", "true", "on", "yes"}


def try_patch_openai_client(client: "openai.OpenAI") -> "openai.OpenAI | instructor.Instructor":
    """Return an Instructor-patched client if available, else the original."""
    try:
        import instructor as _instructor

        return _instructor.from_openai(client)
    except Exception as exc:  # pragma: no cover - dependency optional
        logger.warning("Instructor patch failed, using plain OpenAI client: %s", exc)
        return client


def create_structured_completion(
    messages: list[dict],
    response_model: type[T],
    *,
    provider: str = "groq",
    model: str = "llama-3.1-8b-instant",
    max_retries: int = 2,
    timeout: float = 10.0,
    temperature: float = 0.0,
    max_tokens: int | None = None,
) -> T | None:
    """Use Instructor to get a structured output from a small backend.

    Returns None if Instructor/openai is missing, no active key is available,
    the provider is unknown, or the call fails.
    """
    try:
        import openai as _openai
        import instructor as _instructor
    except ImportError as exc:
        logger.warning("instructor/openai not installed: %s", exc)
        return None

    api_key = key_pool.get_key(provider)
    if not api_key:
        logger.warning("no active key for provider %s", provider)
        return None

    base_url = _PROVIDER_BASE_URLS.get(provider)
    if not base_url:
        logger.warning("unknown instructor provider %s", provider)
        return None

    client = _instructor.from_openai(_openai.OpenAI(base_url=base_url, api_key=api_key, timeout=timeout))
    try:
        return client.chat.completions.create(
            model=model,
            messages=messages,
            response_model=response_model,
            max_retries=max_retries,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    except Exception as exc:
        logger.warning("instructor structured completion failed for %s/%s: %s", provider, model, exc)
        return None
