"""Authoritative safety constants for DLC core.

Constants are re-exported from a single source of truth rather than
duplicated, so a change in one place can no longer drift out of sync across
the device_gateway / dlc_core / device_intelligence layers.
"""

from __future__ import annotations

from device_intelligence.schemas import DEFAULT_WORKSPACE_MM  # 300x300x80 product canvas

# MAX_PATH_POINTS lives in device_gateway.path_data (the path-pipeline source
# of truth) — re-export so dlc_core.path_validator does not keep a stale copy.
from device_gateway.path_data import MAX_PATH_POINTS

MAX_TEXT_LENGTH = 5000

__all__ = ["DEFAULT_WORKSPACE_MM", "MAX_PATH_POINTS", "MAX_TEXT_LENGTH"]
