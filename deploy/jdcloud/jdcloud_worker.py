"""Lightweight FastAPI proxy worker for the JDCloud node.

Forwards OpenAI-compatible chat requests to real providers while injecting
provider-specific API keys. The worker is intended to listen on the Tailscale
interface only and is called by the LiMa Router.
"""

from __future__ import annotations

import hmac
import logging
import os
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import PlainTextResponse, StreamingResponse

load_dotenv()

logger = logging.getLogger("jdcloud_worker")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

DEFAULT_MAX_BODY_BYTES = 10 * 1024 * 1024


class ProviderConfig:
    """Holds a provider's upstream URL and API key."""

    __slots__ = ("url", "key")

    def __init__(self, url: str, key: str) -> None:
        self.url = url
        self.key = key


class Config:
    """Runtime configuration loaded from environment variables."""

    __slots__ = ("worker_token", "host", "port", "providers", "max_body_bytes")

    def __init__(self) -> None:
        self.worker_token = os.environ["JDCLOUD_WORKER_TOKEN"]
        self.host = os.environ.get("JDCLOUD_WORKER_HOST", "100.85.114.65")
        self.port = int(os.environ.get("JDCLOUD_WORKER_PORT", "8700"))
        self.max_body_bytes = int(os.environ.get("JDCLOUD_MAX_BODY_BYTES", str(DEFAULT_MAX_BODY_BYTES)))
        self.providers = _load_providers()


def _load_providers() -> dict[str, ProviderConfig]:
    """Load case-insensitive provider configs from {NAME}_URL / optional {NAME}_KEY."""
    providers: dict[str, ProviderConfig] = {}
    env_ci = {k.lower(): k for k in os.environ}
    for key in os.environ:
        if not key.endswith("_URL"):
            continue
        provider = key[:-4]
        url = os.environ[key]
        api_key_name = env_ci.get(f"{provider}_KEY".lower())
        api_key = os.environ.get(api_key_name) if api_key_name else ""
        if not api_key:
            logger.info("Provider %s loaded without API key (keyless upstream)", provider)
        providers[provider.lower()] = ProviderConfig(url, api_key)
    return providers


def load_config() -> Config:
    """Load configuration from the environment.

    Raises:
        RuntimeError: if the required worker token is missing.
    """
    try:
        return Config()
    except KeyError as exc:
        msg = "Missing required environment variable: JDCLOUD_WORKER_TOKEN"
        logger.error(msg)
        raise RuntimeError(msg) from exc


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage the shared httpx client lifecycle and configuration."""
    app.state.config = load_config()
    app.state.http = httpx.AsyncClient(
        timeout=httpx.Timeout(connect=10.0, read=300.0, write=30.0, pool=10.0),
        limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
    )
    yield
    await app.state.http.aclose()


app = FastAPI(title="LiMa JDCloud Proxy Worker", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    """Return a simple health check."""
    return {"status": "ok"}


@app.post("/proxy/{provider}", response_model=None)
async def proxy(provider: str, request: Request) -> StreamingResponse | PlainTextResponse:
    """Forward the request body to the real provider with its key."""
    start = time.monotonic()

    cfg: Config = request.app.state.config
    _validate_auth(request.headers.get("authorization", ""), cfg.worker_token)
    _check_body_size(request, cfg.max_body_bytes)

    provider_cfg = _resolve_provider(provider, cfg.providers)
    body = await request.body()
    headers = _build_upstream_headers(request, provider_cfg.key)

    try:
        upstream = await request.app.state.http.post(
            provider_cfg.url,
            content=body,
            headers=headers,
        )
    except httpx.RequestError as exc:
        elapsed = int((time.monotonic() - start) * 1000)
        logger.warning("Provider %s request error after %d ms: %s", provider, elapsed, exc)
        raise HTTPException(status_code=502, detail="upstream request failed") from exc

    elapsed = int((time.monotonic() - start) * 1000)
    logger.info(
        "provider=%s upstream_status=%d elapsed_ms=%d",
        provider,
        upstream.status_code,
        elapsed,
    )

    return await _build_response(upstream)


def _validate_auth(auth: str, worker_token: str) -> None:
    """Check the Bearer token against the configured worker token."""
    scheme, sep, token = auth.partition(" ")
    if not sep:
        raise HTTPException(status_code=401, detail="invalid or missing token")
    if not hmac.compare_digest(scheme.lower(), "bearer"):
        raise HTTPException(status_code=401, detail="invalid or missing token")
    if not hmac.compare_digest(token, worker_token):
        raise HTTPException(status_code=401, detail="invalid or missing token")


def _check_body_size(request: Request, max_body_bytes: int) -> None:
    """Reject requests whose Content-Length exceeds the configured limit."""
    content_length = request.headers.get("content-length")
    if content_length is None:
        raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail="content-length required")
    try:
        length = int(content_length)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail="invalid content-length") from None
    if length > max_body_bytes:
        raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail="request body too large")


def _resolve_provider(provider: str, providers: dict[str, ProviderConfig]) -> ProviderConfig:
    """Find provider config by case-insensitive name."""
    cfg = providers.get(provider.lower())
    if cfg is None:
        raise HTTPException(status_code=404, detail=f"unknown provider: {provider}")
    return cfg


def _build_upstream_headers(request: Request, api_key: str) -> dict[str, str]:
    """Build headers for the upstream request, injecting the provider key if present."""
    headers: dict[str, str] = {}
    for name, value in request.headers.items():
        lower = name.lower()
        if lower in ("host", "authorization", "content-length"):
            continue
        headers[name] = value
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    headers["Content-Type"] = request.headers.get("content-type", "application/json")
    return headers


async def _upstream_sse_iterator(upstream: httpx.Response) -> AsyncIterator[str]:
    """Yield upstream SSE chunks and ensure the response is closed."""
    try:
        async for chunk in upstream.aiter_text():
            yield chunk
    finally:
        await upstream.aclose()


async def _build_response(upstream: httpx.Response) -> StreamingResponse | PlainTextResponse:
    """Return streaming or plain response based on upstream headers."""
    content_type = upstream.headers.get("content-type", "application/json")
    is_sse = "text/event-stream" in content_type

    if is_sse:
        return StreamingResponse(
            _upstream_sse_iterator(upstream),
            status_code=upstream.status_code,
            media_type=content_type,
            headers={"Cache-Control": "no-cache"},
        )

    try:
        await upstream.aread()
        content = upstream.content
    finally:
        await upstream.aclose()
    return PlainTextResponse(
        content=content,
        status_code=upstream.status_code,
        media_type=content_type,
    )
