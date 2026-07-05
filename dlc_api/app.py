"""Minimal FastAPI app for dlc_api P0 validation."""

from __future__ import annotations

from fastapi import FastAPI

from dlc_api.routes import router as dlc_router

# P1: disable interactive docs on the public entrypoint so the API surface
# cannot be enumerated. SEC-05.
app = FastAPI(
    title="DLC Drawing Service",
    version="0.1.0-p0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
app.include_router(dlc_router)
