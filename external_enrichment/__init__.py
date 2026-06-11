"""External enrichment: optional non-AI public context with offline tests.

Provides weather, holidays, and other public data with:
- Cache TTL and fallback
- Rate limiting and attribution
- No dependency on external APIs for dispatch
"""
from external_enrichment.cache import EnrichmentCache
from external_enrichment.schemas import EnrichmentResult

__all__ = ["EnrichmentCache", "EnrichmentResult"]
