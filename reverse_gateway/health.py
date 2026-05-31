"""Reverse gateway health aggregation."""

from __future__ import annotations

from reverse_gateway.providers import scnet


PROBES = {
    "scnet_large": scnet.probe,
}


def probe_provider(name: str) -> dict[str, object] | None:
    probe = PROBES.get(name)
    return probe().to_dict() if probe else None


def probe_all() -> dict[str, dict[str, object]]:
    return {name: probe().to_dict() for name, probe in PROBES.items()}
