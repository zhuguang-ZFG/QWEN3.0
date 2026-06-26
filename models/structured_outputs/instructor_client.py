"""Optional Instructor-patched OpenAI client.

Instructor is not a hard dependency; when absent the router falls back to the
rule-based classifiers and Pydantic validators defined elsewhere.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import instructor
    import openai

logger = logging.getLogger(__name__)


def instructor_enabled() -> bool:
    """Whether Instructor-based structured outputs are enabled."""
    import os

    return os.environ.get("LIMA_INSTRUCTOR_ENABLED", "0").lower() in {"1", "true", "on"}


def try_patch_openai_client(client: "openai.OpenAI") -> "openai.OpenAI | instructor.Instructor":
    """Return an Instructor-patched client if available, else the original."""
    try:
        import instructor as _instructor

        return _instructor.from_openai(client)
    except Exception as exc:  # pragma: no cover - dependency optional
        logger.warning("Instructor patch failed, using plain OpenAI client: %s", exc)
        return client
