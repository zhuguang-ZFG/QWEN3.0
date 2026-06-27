"""Admin endpoints for receiving and querying probe results."""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Request

from access_guard import constant_time_equals, extract_bearer_token
from config.env import probe_ingress_enabled, probe_ingress_token
from observability.probe_state import get_probe_snapshot, record_probe_event
from routes.admin_auth import verify_admin

router = APIRouter(prefix="/admin")


def _authenticate_probe(authorization: str) -> None:
    """Verify ingress is enabled and the bearer token matches."""
    if not probe_ingress_enabled():
        raise HTTPException(status_code=503, detail="probe ingress disabled")

    expected_token = probe_ingress_token()
    if not expected_token:
        raise HTTPException(status_code=503, detail="probe ingress token not configured")

    presented = extract_bearer_token(authorization)
    if not presented or not constant_time_equals(presented, expected_token):
        raise HTTPException(status_code=401, detail="Unauthorized")


async def _read_probe_body(request: Request) -> tuple[str, list]:
    """Parse and validate the probe ingress JSON body."""
    try:
        body = await request.json()
    except (json.JSONDecodeError, ValueError, UnicodeDecodeError) as exc:
        # request.json() may raise JSONDecodeError/ValueError for malformed JSON,
        # or UnicodeDecodeError for a body that cannot be decoded as text.
        logging.warning("probe ingress: invalid JSON body: %s", exc)
        raise HTTPException(status_code=400, detail="invalid JSON body") from exc

    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="invalid JSON body")

    source = body.get("source", "")
    if not isinstance(source, str) or not source:
        raise HTTPException(status_code=400, detail="missing or invalid source")

    probes = body.get("probes", [])
    if not isinstance(probes, list):
        raise HTTPException(status_code=400, detail="probes must be a list")

    return source, probes


def _record_probe_items(source: str, probes: list) -> int:
    """Persist each probe item and return the number recorded."""
    recorded = 0
    for item in probes:
        if not isinstance(item, dict):
            logging.warning("probe ingress: skipping non-object probe item from %s", source)
            continue
        provider = item.get("provider")
        if not isinstance(provider, str) or not provider:
            logging.warning("probe ingress: skipping probe item without provider from %s", source)
            continue
        try:
            record_probe_event(
                source=source,
                provider=provider,
                status=str(item.get("status", "")),
                latency_ms=float(item.get("latency_ms", 0.0)),
                price_tier=str(item.get("price_tier", "")),
                checked_at=str(item.get("checked_at", "")),
                metadata=item.get("metadata"),
            )
            recorded += 1
        except Exception as exc:
            logging.warning("probe ingress: failed to record probe %s:%s: %s", source, provider, exc)
    return recorded


@router.post("/api/probe/ingress")
async def probe_ingress(request: Request, authorization: str = Header(default="")) -> dict:
    """Receive probe results from an external probe runner (e.g. JDCloud)."""
    _authenticate_probe(authorization)
    source, probes = await _read_probe_body(request)
    return {"recorded": _record_probe_items(source, probes)}


@router.get("/api/probe/jdcloud", dependencies=[Depends(verify_admin)])
async def probe_jdcloud() -> dict:
    """Return the latest probe snapshot received from JDCloud."""
    return get_probe_snapshot(source="jdcloud")
