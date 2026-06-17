"""External voiceprint API embedding extractor."""

from __future__ import annotations

import logging
from typing import Optional

_log = logging.getLogger(__name__)


async def extract_embedding_api(wav_data: bytes, api_url: str, api_key: str) -> Optional[list[float]]:
    """Extract speaker embedding via an external voiceprint API.

    Args:
        wav_data: WAV-formatted 16kHz mono audio bytes.
        api_url: Base URL of the external voiceprint API.
        api_key: API key for authorization.

    Returns:
        Embedding vector as list of floats, or None on failure.
    """
    try:
        import aiohttp
    except ImportError:
        _log.warning("aiohttp not installed; cannot use API voiceprint mode")
        return None

    try:
        data = aiohttp.FormData()
        data.add_field("file", wav_data, filename="audio.wav", content_type="audio/wav")

        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                f"{api_url}/extract",
                headers={"Authorization": f"Bearer {api_key}"},
                data=data,
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    emb = result.get("embedding")
                    if isinstance(emb, list):
                        return emb
                _log.warning("API embedding extraction failed: HTTP %d", response.status)
                return None
    except Exception:
        _log.warning("API embedding extraction error", exc_info=True)
        return None


__all__ = ["extract_embedding_api"]
