"""Helpers for asserting registered HTTP paths (FastAPI 0.139+ wraps routers)."""

from __future__ import annotations

from fastapi import FastAPI


def openapi_paths(app: FastAPI) -> set[str]:
    """Return all path templates exposed by *app* (from OpenAPI schema)."""
    return set(app.openapi()["paths"].keys())
