"""Reverse gateway status endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from reverse_gateway.health import probe_all, probe_provider
from reverse_gateway.registry import list_provider_status, provider_status

router = APIRouter(prefix="/reverse-gateway", tags=["reverse-gateway"])


@router.get("/health")
def reverse_gateway_health() -> dict[str, object]:
    providers = list_provider_status()
    return {
        "status": "ok",
        "routing_policy": "disabled_until_adapter_health_and_eval",
        "providers": providers,
        "probes": probe_all(),
    }


@router.get("/providers/{name}")
def reverse_gateway_provider(name: str) -> dict[str, object]:
    status = provider_status(name)
    if status is None:
        raise HTTPException(status_code=404, detail="unknown reverse provider")
    probe = probe_provider(name)
    if probe:
        status["probe"] = probe
    return status


@router.get("/providers/{name}/probe")
def reverse_gateway_probe(name: str) -> dict[str, object]:
    probe = probe_provider(name)
    if probe is None:
        raise HTTPException(status_code=404, detail="unknown reverse provider probe")
    return probe
