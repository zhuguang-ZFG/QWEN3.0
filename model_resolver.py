"""Resolve client model parameter to LiMa backend name.

Priority:
  1. Exact match in BACKENDS → use that backend
  2. Exact match in MODEL_ALIASES → use mapped backend
  3. No match → return None (caller falls back to auto-routing)

This module is intentionally lightweight (O(1) dict lookups) so it
adds negligible latency to the routing pipeline.
"""

import logging
import os

from backends_constants import MODEL_ALIASES
from backends_registry import BACKENDS

logger = logging.getLogger(__name__)

# Feature gate — default True for personal assistant (not multi-tenant)
_ALLOW_MODEL_OVERRIDE = os.environ.get(
    "LIMA_ALLOW_MODEL_OVERRIDE", "true"
).lower() in ("true", "1", "yes")


def resolve_backend(model: str) -> str | None:
    """Resolve client-specified model to a LiMa backend name.

    Returns:
        Backend name string if resolved, None if auto-routing should apply.
    """
    if not _ALLOW_MODEL_OVERRIDE:
        return None

    if not model or model in ("auto", "lima-1.3", ""):
        return None

    # 1. Strip provider prefix (e.g., "openai/lima-1.3" → "lima-1.3")
    if "/" in model:
        parts = model.split("/", 1)
        if parts[0].lower() in ("openai", "anthropic", "deepseek", "qwen", "meta", "mistral", "google"):
            model = parts[1]
            logger.info("model_resolver: stripped provider prefix → '%s'", model)

    # 2. Exact match: client passed a LiMa backend name directly
    if model in BACKENDS:
        logger.info("model_resolver: exact match → %s", model)
        return model

    # 3. Alias match: human-friendly name → backend name
    alias_target = MODEL_ALIASES.get(model)
    if alias_target and alias_target in BACKENDS:
        logger.info("model_resolver: alias '%s' → %s", model, alias_target)
        return alias_target

    # 4. No match → let auto-routing handle it
    logger.debug("model_resolver: no match for '%s', falling back to auto-route", model)
    return None
