"""Safe parsing/validation helpers for structured outputs."""

from __future__ import annotations

import json
import logging
from typing import TypeVar

from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


def parse_json(text: str, model: type[T], *, fallback: T | None = None) -> T:
    """Parse a JSON string into ``model``; return fallback on any error.

    Logs a warning instead of swallowing silently (AGENTS.md hard rule).
    """
    try:
        data = json.loads(text)
        return model.model_validate(data)
    except (json.JSONDecodeError, ValidationError) as exc:
        logger.warning("structured_output parse failed: %s", exc)
        if fallback is not None:
            return fallback
        return model()


def validate_value(value: object, model: type[T], *, fallback: T | None = None) -> T:
    """Validate an already-parsed dict/value against ``model``."""
    try:
        return model.model_validate(value)
    except ValidationError as exc:
        logger.warning("structured_output validation failed: %s", exc)
        if fallback is not None:
            return fallback
        return model()
