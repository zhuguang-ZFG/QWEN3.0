"""Compatibility shim — canonical router lives in routes.ops_metrics.ops_metrics."""

from routes.ops_metrics.ops_metrics import router

__all__ = ["router"]
