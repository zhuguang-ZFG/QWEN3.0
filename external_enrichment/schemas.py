"""Enrichment schemas."""
from typing import Optional
from pydantic import BaseModel


class EnrichmentResult(BaseModel):
    """Result from an enrichment provider."""
    provider: str
    data: dict
    cached: bool
    attribution: str  # e.g., "Data from Open-Meteo.com"
    timestamp: int  # Unix timestamp
