"""Shared helpers for backend registry modules."""

import logging

from config import settings
from runtime_topology import env_truthy

logger = logging.getLogger(__name__)


def legacy_free_enabled(name: str) -> bool:
    """Read opt-in flag for a cleartext HTTP community backend.

    Supports both ``LIMA_FREE_<NAME>_ENABLED`` (preferred) and the legacy
    ``FREE_<NAME>_ENABLED`` form. The legacy form emits a deprecation warning
    when set to a truthy value so operators can migrate.
    """
    lima_name = f"LIMA_FREE_{name}_ENABLED"
    legacy_name = f"FREE_{name}_ENABLED"
    if settings.get_env(lima_name):
        return env_truthy(lima_name)
    if settings.get_env(legacy_name) and env_truthy(legacy_name):
        logger.warning("%s is deprecated; use %s instead", legacy_name, lima_name)
        return True
    return False
