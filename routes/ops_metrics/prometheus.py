"""Ops Prometheus scrape endpoint."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from access_guard import require_private_api_key

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/metrics/prometheus", dependencies=[Depends(require_private_api_key)])
def ops_metrics_prometheus(request: Request):
    """Prometheus / OpenMetrics scrape endpoint (default-off).

    Enable with LIMA_PROMETHEUS_METRICS=1.
    Requires prometheus_client package installed.
    """
    try:
        from observability import prometheus_metrics
    except ImportError as exc:
        logger.warning("Prometheus metrics module unavailable: %s", exc)
        return JSONResponse({"error": "Prometheus metrics unavailable"}, status_code=503)

    if not prometheus_metrics.is_enabled():
        return JSONResponse(
            {"error": "Prometheus metrics disabled"},
            status_code=404,
        )

    try:
        body = prometheus_metrics.generate_metrics()
    except RuntimeError as exc:
        logger.warning("Prometheus metrics generation failed: %s", exc)
        return JSONResponse({"error": "Prometheus metrics unavailable"}, status_code=503)
    return PlainTextResponse(body, media_type="text/plain; version=0.0.4")
