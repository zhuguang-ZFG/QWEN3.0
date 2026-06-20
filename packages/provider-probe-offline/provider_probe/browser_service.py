"""Playwright browser microservice for provider discovery.

Runs on JD Cloud VPS as a standalone FastAPI service (port 8092).
Provides headless browser capabilities: page rendering, JS-aware extraction,
network request interception, and screenshot capture.

Usage:
    python provider_probe/browser_service.py
    # or via systemd: lima-probe-browser.service
"""

import ipaddress
import logging
import os
import re
import socket
from contextlib import asynccontextmanager
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel

logger = logging.getLogger("provider_probe.browser")

BROWSER_HOST = os.environ.get("PROBE_BROWSER_HOST", "127.0.0.1")
BROWSER_PORT = int(os.environ.get("PROBE_BROWSER_PORT", "8092"))
CHROMIUM_EXECUTABLE = os.environ.get("PROBE_CHROMIUM_EXECUTABLE")
BROWSER_TOKEN = os.environ.get("PROBE_BROWSER_TOKEN")

_ALLOWED_SCHEMES = {"http", "https"}
_SENSITIVE_HEADERS = {"authorization", "cookie", "set-cookie", "x-api-key", "api-key"}

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class RenderRequest(BaseModel):
    url: str
    wait_ms: int = 3000
    extract_text: bool = True
    screenshot: bool = False
    extra_http_headers: dict[str, str] | None = None


class RenderResponse(BaseModel):
    url: str
    title: str = ""
    text: str = ""
    html_length: int = 0
    status_code: int | None = None
    network_requests: list[dict] = []
    screenshot_b64: str | None = None


class ExtractRequest(BaseModel):
    url: str
    selector: str | None = None
    wait_ms: int = 2000


class ExtractResponse(BaseModel):
    url: str
    text: str = ""
    items: list[str] = []


# ---------------------------------------------------------------------------
# Browser lifecycle
# ---------------------------------------------------------------------------

_browser = None
_playwright = None


def _check_auth(token: str | None) -> None:
    """Require a bearer token when PROBE_BROWSER_TOKEN is configured."""
    if BROWSER_TOKEN and token != BROWSER_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")


# Common documentation/test domains that should always be allowed for probes.
_TEST_DOMAINS = {"example.com", "example.org", "www.example.com", "www.example.org"}


def _is_public_host(host: str) -> bool:
    """Return True if host is a public IP/hostname, False for private/internal."""
    if not host or host in ("localhost", "localhost."):
        return False
    if host.lower() in _TEST_DOMAINS:
        return True
    try:
        addr = ipaddress.ip_address(host)
        return not (addr.is_private or addr.is_loopback or addr.is_reserved or addr.is_multicast)
    except ValueError:
        pass
    try:
        infos = socket.getaddrinfo(host, None)
        for info in infos:
            addr = ipaddress.ip_address(info[4][0])
            if addr.is_private or addr.is_loopback or addr.is_reserved or addr.is_multicast:
                return False
        return bool(infos)
    except socket.gaierror:
        # DNS unavailable in some test/sandbox environments; assume public and let
        # the actual fetch fail if the host is unreachable.
        return True


def _validate_url(url: str) -> str:
    """Validate a probe URL: public host, http/https only."""
    if not url:
        raise HTTPException(status_code=400, detail="URL is required")
    parsed = urlparse(url)
    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise HTTPException(status_code=400, detail=f"URL scheme must be http or https: {url}")
    if not parsed.hostname:
        raise HTTPException(status_code=400, detail=f"URL has no host: {url}")
    if not _is_public_host(parsed.hostname):
        raise HTTPException(status_code=400, detail=f"URL host is not public: {parsed.hostname}")
    return url


def _sanitize_error(message: str) -> str:
    """Keep operator-visible errors useful without leaking local paths."""
    lines = [line.strip() for line in message.splitlines() if line.strip()]
    first_line = lines[0] if lines else "unknown error"
    first_line = re.sub(
        r"(/root|/home/[^/\s]+|[A-Za-z]:\\Users\\[^\\\s]+)[^\s'\"<]*",
        "<redacted-path>",
        first_line,
    )
    return first_line[:300]


def _browser_error_detail(exc: Exception, *, phase: str) -> dict[str, object]:
    return {
        "ready": False,
        "service": "probe-browser",
        "phase": phase,
        "error_class": type(exc).__name__,
        "error": _sanitize_error(str(exc)),
    }


def _browser_launch_options() -> dict[str, object]:
    options: dict[str, object] = {
        "headless": True,
        "args": [
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
        ],
    }
    executable = os.environ.get("PROBE_CHROMIUM_EXECUTABLE") or CHROMIUM_EXECUTABLE
    if executable:
        options["executable_path"] = executable
    return options


async def _get_browser():
    global _browser, _playwright
    if _browser is None:
        try:
            from playwright.async_api import async_playwright

            _playwright = await async_playwright().start()
            _browser = await _playwright.chromium.launch(**_browser_launch_options())
            logger.info("Browser launched")
        except ImportError:
            raise HTTPException(
                status_code=503,
                detail={
                    "ready": False,
                    "service": "probe-browser",
                    "phase": "import",
                    "error_class": "ImportError",
                    "error": "playwright not installed",
                },
            )
    return _browser


async def _close_browser():
    global _browser, _playwright
    if _browser:
        await _browser.close()
        _browser = None
    if _playwright:
        await _playwright.stop()
        _playwright = None
    logger.info("Browser closed")


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Browser service starting on port %d", BROWSER_PORT)
    yield
    await _close_browser()


app = FastAPI(title="LiMa Provider Probe Browser", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "probe-browser"}


@app.get("/ready")
async def ready():
    try:
        await _get_browser()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=_browser_error_detail(exc, phase="browser_launch"),
        ) from exc
    return {"ready": True, "service": "probe-browser"}


@app.post("/render", response_model=RenderResponse)
async def render_page(
    req: RenderRequest,
    x_probe_token: str | None = Header(None, alias="X-Probe-Token"),
):
    """Render a page and return text content + optional screenshot."""
    _check_auth(x_probe_token)
    _validate_url(req.url)
    context = None

    try:
        browser = await _get_browser()
        context = await browser.new_context(
            extra_http_headers=req.extra_http_headers or {},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/130.0.0.0 Safari/537.36"
            ),
        )
        page = await context.new_page()

        network_requests = []

        async def _on_request(request):
            network_requests.append(
                {
                    "url": request.url,
                    "method": request.method,
                    "resource_type": request.resource_type,
                }
            )

        page.on("request", _on_request)
        response = await page.goto(req.url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(req.wait_ms)

        title = await page.title()
        status_code = response.status if response else None

        text = ""
        if req.extract_text:
            text = await page.evaluate("() => document.body ? document.body.innerText : ''")

        html_length = await page.evaluate("() => document.documentElement.outerHTML.length")

        screenshot_b64 = None
        if req.screenshot:
            import base64

            raw = await page.screenshot(full_page=False, type="png")
            screenshot_b64 = base64.b64encode(raw).decode()

        await context.close()
        return RenderResponse(
            url=req.url,
            title=title,
            text=text[:50000],
            html_length=html_length,
            status_code=status_code,
            network_requests=network_requests[-50:],
            screenshot_b64=screenshot_b64,
        )
    except HTTPException:
        raise
    except Exception as exc:
        if context:
            await context.close()
        status_code = 503 if _browser is None else 502
        phase = "browser_launch" if _browser is None else "render"
        raise HTTPException(
            status_code=status_code,
            detail=_browser_error_detail(exc, phase=phase),
        ) from exc


@app.post("/extract", response_model=ExtractResponse)
async def extract_content(
    req: ExtractRequest,
    x_probe_token: str | None = Header(None, alias="X-Probe-Token"),
):
    """Extract text matching a CSS selector from a page."""
    _check_auth(x_probe_token)
    _validate_url(req.url)
    browser = await _get_browser()
    context = await browser.new_context()
    page = await context.new_page()

    try:
        await page.goto(req.url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(req.wait_ms)

        text = ""
        items = []
        if req.selector:
            locator = page.locator(req.selector)
            raw_items = await locator.all_inner_texts()
            items = [item.strip() for item in raw_items if item.strip()]
        else:
            text = await page.evaluate("() => document.body ? document.body.innerText : ''")

        await context.close()
        return ExtractResponse(url=req.url, text=text[:50000], items=items[:200])
    except Exception as exc:
        await context.close()
        raise HTTPException(status_code=502, detail=f"Extract failed: {exc}")


def _redact_headers(headers: dict[str, str]) -> dict[str, str]:
    """Remove sensitive headers from captured network requests."""
    return {
        k: "<redacted>" if k.lower() in _SENSITIVE_HEADERS else v
        for k, v in headers.items()
    }


@app.post("/network-intercept")
async def network_intercept(
    req: dict,
    x_probe_token: str | None = Header(None, alias="X-Probe-Token"),
):
    """Navigate to URL and collect all network requests (API endpoints, etc.)."""
    _check_auth(x_probe_token)
    url = req.get("url", "")
    _validate_url(url)
    browser = await _get_browser()
    context = await browser.new_context()
    page = await context.new_page()

    requests = []

    async def _capture(request):
        requests.append(
            {
                "url": request.url,
                "method": request.method,
                "headers": _redact_headers(dict(request.headers)),
                "post_data": request.post_data[:1000] if request.post_data else None,
                "resource_type": request.resource_type,
            }
        )

    page.on("request", _capture)

    try:
        await page.goto(url, wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(req.get("wait_ms", 5000))
    except Exception as exc:
        logger.warning("Navigation error (may be ok): %s", exc)

    await context.close()

    api_calls = [r for r in requests if r["resource_type"] in ("fetch", "xhr") and "api" in r["url"].lower()]

    return JSONResponse(
        {
            "total_requests": len(requests),
            "api_calls": api_calls,
            "all_urls": [r["url"] for r in requests],
        }
    )


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    logging.basicConfig(level=logging.INFO)
    logger.info("Browser service listening on %s:%d", BROWSER_HOST, BROWSER_PORT)
    uvicorn.run(app, host=BROWSER_HOST, port=BROWSER_PORT)
