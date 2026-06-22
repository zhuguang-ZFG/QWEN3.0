"""Injectable dependencies for device task creation (test monkeypatch surface).

This module exists to provide a clean monkeypatch surface for tests.
Importing through here instead of directly lets tests replace individual
dependencies without side effects on other importers.

ponytail: kept intentionally despite 18-line size — removes need for
  complex dependency injection framework in test code.
"""

from __future__ import annotations

from device_policy import policy_engine

from .model_routing import resolve_device_route_policy
from .path_validator import validate_capability_params, validate_route_policy
from .profiles import apply_profile_constraints, resolve_profile

__all__ = [
    "apply_profile_constraints",
    "policy_engine",
    "resolve_device_route_policy",
    "resolve_profile",
    "validate_capability_params",
    "validate_route_policy",
]
