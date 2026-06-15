"""Shared helpers for provider_automation test modules."""

from __future__ import annotations

from provider_automation.catalog import ProviderModelEntry


def entry(model_id: str, **kwargs) -> ProviderModelEntry:
    return ProviderModelEntry(model_id=model_id, provider=kwargs.pop("provider", "test"), **kwargs)
