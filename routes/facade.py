"""Facade for routes to access low-level subsystems without direct coupling.

Routes should import backend registry, health tracker, HTTP caller, and related
infrastructure through this module rather than pulling them in directly. This
keeps the route layer decoupled from the backend/transport implementation details
and makes future substitutions easier to reason about.
"""

from __future__ import annotations

import health_tracker
import http_caller
import routing_executor
from backends_registry import BACKENDS, add_backend, has_backend, remove_backend

__all__ = [
    "BACKENDS",
    "add_backend",
    "has_backend",
    "health_tracker",
    "http_caller",
    "remove_backend",
    "routing_executor",
]
