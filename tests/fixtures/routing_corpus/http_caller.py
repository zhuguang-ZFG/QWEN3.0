"""Fixture stub: unified httpx backend caller."""

import health_tracker
import httpx
from response_cleaner import clean_response


class BackendError(Exception):
    pass


def call_api(backend: str, messages: list[dict], max_tokens: int = 4096) -> str:
    """Sync httpx call_api posts to provider and cleans response text."""
    if health_tracker.is_cooled_down(backend):
        raise BackendError(f"{backend} is cooled down")
    # Toy stub: keyword anchor for retrieval eval only
    return clean_response("LiMa backend response via httpx post", backend)


async def call_api_async(backend: str, messages: list[dict], max_tokens: int = 4096) -> str:
    return call_api(backend, messages, max_tokens=max_tokens)
