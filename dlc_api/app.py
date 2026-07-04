"""Minimal FastAPI app for dlc_api P0 validation."""

from __future__ import annotations

from fastapi import FastAPI

from dlc_api.routes import router as dlc_router

app = FastAPI(title="DLC Drawing Service", version="0.1.0-p0")
app.include_router(dlc_router)
