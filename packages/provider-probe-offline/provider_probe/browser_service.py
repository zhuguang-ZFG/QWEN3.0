"""Playwright browser microservice for provider discovery.

Runs on JD Cloud VPS as a standalone FastAPI service (port 8092).
Provides headless browser capabilities: page rendering, JS-aware extraction,
network request interception, and screenshot capture.

Usage:
    python provider_probe/browser_service.py
    # or via systemd: lima-probe-browser.service
"""

from __future__ import annotations

import base64
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Header
from fastapi.responses import JSONResponse

from provider_probe.browser_models import ExtractRequest, ExtractResponse, RenderRequest, RenderResponse
import provider_probe.browser_lifecycle as _lifecycle
from provider_probe.browser_lifecycle import (
    BROWSER_HOST,
    BROWSER_PORT,
    _check_auth,
    _get_browser,
    _close_browser,
    _validate_url,
    _browser_error_detail,
    _redact_headers,
)

logger = logging.getLogger("provider_probe.browser")


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
        status_code = 503 if _lifecycle._browser is None else 502
        phase = "browser_launch" if _lifecycle._browser is None else "render"
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
    logger.info("Browser service listening")
    uvicorn.run(app, host=BROWSER_HOST, port=BROWSER_PORT)
