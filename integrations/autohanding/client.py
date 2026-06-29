"""Client for autohanding.com free handwriting preview API.

Uses only the public preview endpoint; no API key or login is required.
Output is a raster PNG packaged in a ZIP file.
"""

from __future__ import annotations

import asyncio
import io
import logging
import random
import time
import zipfile

import httpx

from integrations.autohanding import constants

_log = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 30
DEFAULT_MAX_RETRIES = 2
DEFAULT_BACKOFF_BASE_SECONDS = 1.0
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


class AutohandingRateLimitError(Exception):
    """Raised when autohanding reports rate limiting."""


class AutohandingClientError(Exception):
    """Raised for non-2xx responses or malformed payloads."""


def build_client_id() -> str:
    """Build a client fingerprint similar to the autohanding frontend."""
    return f"lima_{random.randint(1000, 9999)}_{int(time.time())}"


def _validate_text(text: str) -> None:
    if not text or not text.strip():
        raise AutohandingClientError("empty text")
    if len(text) > constants.MAX_TEXT_LENGTH:
        raise AutohandingClientError(f"text too long: {len(text)} > {constants.MAX_TEXT_LENGTH}")


def _build_form(
    text: str,
    client_id: str,
    font_type: str,
    paper_bg_type: str,
    mistake_rate: int,
    messy_ratio: int,
    char_random: int,
) -> dict[str, tuple[None, str]]:
    return {
        "fullText": (None, text),
        "fontType": (None, constants.validate_font_type(font_type)),
        "paperBgType": (None, constants.validate_paper_bg_type(paper_bg_type)),
        "mistakeRate": (None, str(constants.validate_rate(mistake_rate))),
        "messyRatio": (None, str(constants.validate_rate(messy_ratio))),
        "charRandom": (None, str(constants.validate_rate(char_random))),
        "clientId": (None, client_id),
    }


def _build_headers() -> dict[str, str]:
    return {
        "User-Agent": DEFAULT_USER_AGENT,
        "Referer": constants.PREVIEW_BASE_URL + "/",
        "Origin": constants.PREVIEW_BASE_URL,
    }


async def _post_preview(
    client: httpx.AsyncClient,
    url: str,
    form: dict[str, tuple[None, str]],
    headers: dict[str, str],
    timeout: float,
) -> httpx.Response:
    try:
        return await client.post(url, files=form, headers=headers)
    except httpx.TimeoutException as exc:
        raise AutohandingClientError(f"request timeout after {timeout}s") from exc
    except httpx.HTTPError as exc:
        raise AutohandingClientError(f"request failed: {exc}") from exc


async def _post_preview_with_retry(
    client: httpx.AsyncClient,
    url: str,
    form: dict[str, tuple[None, str]],
    headers: dict[str, str],
    timeout: float,
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> httpx.Response:
    """Post with exponential backoff. Rate-limit errors are not retried."""
    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            return await _post_preview(client, url, form, headers, timeout)
        except AutohandingRateLimitError:
            raise
        except AutohandingClientError as exc:
            last_exc = exc
            if attempt < max_retries:
                delay = DEFAULT_BACKOFF_BASE_SECONDS * (2**attempt)
                _log.warning("autohanding attempt %d failed, retrying in %.1fs: %s", attempt + 1, delay, exc)
                await asyncio.sleep(delay)
    raise last_exc or AutohandingClientError("all autohanding retry attempts failed")


# AUDIT-11-I1：解压大小上限，防 zip bomb（高压缩比恶意 ZIP 导致 OOM）。
# 单张手写 PNG 不会超过 10MB，50MB 余量足够。
_MAX_DECOMPRESSED_PNG_BYTES = 50 * 1024 * 1024


def _extract_first_png(zip_bytes: bytes) -> bytes:
    """Extract the first PNG found in a ZIP archive."""
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            names = [n for n in zf.namelist() if n.lower().endswith(".png")]
            if not names:
                raise AutohandingClientError("no PNG found in response ZIP")
            names.sort()
            # zip bomb 防护：解压前检查声明大小，超限拒绝（不实际解压）
            info = zf.getinfo(names[0])
            if info.file_size > _MAX_DECOMPRESSED_PNG_BYTES:
                raise AutohandingClientError(
                    f"PNG too large ({info.file_size} bytes), possible zip bomb"
                )
            return zf.read(names[0])
    except zipfile.BadZipFile as exc:
        raise AutohandingClientError("response is not a valid ZIP") from exc


def _handle_status(response: httpx.Response) -> None:
    if response.status_code == 429:
        raise AutohandingRateLimitError("autohanding rate limit")
    if response.status_code != 200:
        body = response.text[:200]
        raise AutohandingClientError(f"unexpected status {response.status_code}: {body}")


def _parse_preview_response(response: httpx.Response) -> bytes:
    _handle_status(response)
    content_type = response.headers.get("content-type", "").lower()
    if "zip" in content_type or response.content[:2] == b"PK":
        return _extract_first_png(response.content)

    body = response.text.strip()[:200]
    if "频率" in body or "请稍后" in body:
        raise AutohandingRateLimitError(body)
    raise AutohandingClientError(f"unexpected response: {body}")


async def convert_text(
    text: str,
    *,
    font_type: str = constants.DEFAULT_FONT_TYPE,
    paper_bg_type: str = constants.DEFAULT_PAPER_BG_TYPE,
    mistake_rate: int = constants.DEFAULT_MISTAKE_RATE,
    messy_ratio: int = constants.DEFAULT_MESSY_RATIO,
    char_random: int = constants.DEFAULT_CHAR_RANDOM,
    client_id: str | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> bytes:
    """Call autohanding preview text endpoint and return the first PNG bytes."""
    _validate_text(text)
    client_id = client_id or build_client_id()
    form = _build_form(text, client_id, font_type, paper_bg_type, mistake_rate, messy_ratio, char_random)
    headers = _build_headers()
    url = constants.PREVIEW_BASE_URL + constants.PREVIEW_TEXT_ENDPOINT

    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        response = await _post_preview_with_retry(client, url, form, headers, timeout, max_retries=max_retries)

    return _parse_preview_response(response)
