"""OpenCode IDE configuration — centralized settings for OpenCode integration.

All OpenCode-specific tuning knobs live here so callers don't scatter
os.environ.get() calls across the codebase.  Every value is read once at
import time and is therefore constant for the process lifetime.
"""

from __future__ import annotations

import logging
import os
import warnings

_log = logging.getLogger(__name__)

# ── Tool call mode ─────────────────────────────────────────────────────────
# "direct"  → OpenCode tools handled natively in OpenAI format (default)
# "convert" → route through Anthropic conversion pipeline (legacy)
OPENCODE_TOOL_MODE = os.environ.get("LIMA_OPENCODE_TOOL_MODE", "direct")

# Backward compatibility: OPENCODE_OPTIMIZATION_ENABLED=1 → direct mode
if (os.environ.get("OPENCODE_OPTIMIZATION_ENABLED", "0") == "1"
        and "LIMA_OPENCODE_TOOL_MODE" not in os.environ):
    warnings.warn(
        "OPENCODE_OPTIMIZATION_ENABLED is deprecated. "
        "Set LIMA_OPENCODE_TOOL_MODE=direct instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    OPENCODE_TOOL_MODE = "direct"
    _log.info("Legacy OPENCODE_OPTIMIZATION_ENABLED=1 → OPENCODE_TOOL_MODE=direct")

# ── Backend affinity boost ────────────────────────────────────────────────
# Score multiplier applied to fast coding backends for OpenCode requests.
# Set to 1.0 to disable.
OPENCODE_FAST_BOOST = float(os.environ.get("LIMA_OPENCODE_FAST_BOOST", "1.15"))

# Set of backend name prefixes that qualify for the fast boost.
OPENCODE_FAST_BACKENDS: set[str] = {"groq_", "cerebras_", "scnet_ds_flash"}

# ── Rate limiting ─────────────────────────────────────────────────────────
# Multiplier applied to the base rate limit for IDE clients.
OPENCODE_RATE_MULTIPLIER = int(os.environ.get("LIMA_OPENCODE_RATE_MULTIPLIER", "5"))

# ── Preferred backend ─────────────────────────────────────────────────────
# Default backend for OpenCode when no better routing decision is made.
OPENCODE_PREFERRED_BACKEND = os.environ.get(
    "LIMA_OPENCODE_PREFERRED_BACKEND", "scnet_ds_pro"
)

# ── Skills injection ──────────────────────────────────────────────────────
# Categories that OpenCode's built-in system prompt already covers.
# Skills in these categories will be skipped during injection.
OPENCODE_SKIPPED_SKILL_CATEGORIES: set[str] = {"style"}

# ── Context compression ───────────────────────────────────────────────────
# Number of recent message turns to preserve intact during compression.
# OpenCode sends long multi-turn tool-call conversations; keeping more
# turns avoids losing critical tool results.
OPENCODE_KEEP_RECENT_TURNS = int(
    os.environ.get("LIMA_OPENCODE_KEEP_RECENT_TURNS", "8")
)

# ── Speculative execution ─────────────────────────────────────────────────
# Skip speculative calls when OpenCode request contains tools (avoid waste).
OPENCODE_SKIP_SPECULATIVE_TOOLS = (
    os.environ.get("LIMA_OPENCODE_SKIP_SPECULATIVE_TOOLS", "1") == "1"
)
