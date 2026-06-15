"""Shared helpers for ops_metrics test modules."""

from __future__ import annotations

import importlib


def reload_prometheus_metrics():
    import observability.prometheus_metrics as prometheus_metrics

    return importlib.reload(prometheus_metrics)
