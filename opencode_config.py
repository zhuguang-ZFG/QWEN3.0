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
OPENCODE_FAST_BACKENDS: set[str] = {"groq_", "cerebras_", "scnet_", "longcat", "cfai_", "kimi"}

# ── Rate limiting ─────────────────────────────────────────────────────────
# Multiplier applied to the base rate limit for IDE clients.
OPENCODE_RATE_MULTIPLIER = int(os.environ.get("LIMA_OPENCODE_RATE_MULTIPLIER", "5"))

# ── Preferred backend ─────────────────────────────────────────────────────
# Default backend for OpenCode when no better routing decision is made.
OPENCODE_PREFERRED_BACKEND = os.environ.get(
    "LIMA_OPENCODE_PREFERRED_BACKEND", "nvidia_qwen_coder"
)

# ── Fast path ───────────────────────────────────────────────────────────────
# Pin OpenCode to preferred backend; skip speculative routing / heavy injections.
OPENCODE_DIRECT_STREAM = os.environ.get("LIMA_OPENCODE_DIRECT_STREAM", "1") == "1"

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

# ── M-OC3: Reasoning variants ──────────────────────────────────────────────
# Enable reasoning_effort / thinking tier translation per model/provider.
# When enabled, reasoning_effort from client requests is translated into
# provider-specific body parameters (e.g. Anthropic thinking.budgetTokens,
# Google thinkingConfig.thinkingLevel) instead of bare passthrough.
OPENCODE_REASONING_VARIANTS = (
    os.environ.get("LIMA_OPENCODE_REASONING_VARIANTS", "1") == "1"
)

# ── M-OC3: Session options ─────────────────────────────────────────────────
# Enable per-model session-level options injection (store/enable_thinking/
# toolStreaming/promptCacheKey). These options are required by OpenCode for
# correct model behavior (e.g. store=false for GPT-5 stateless reasoning).
OPENCODE_SESSION_OPTIONS = (
    os.environ.get("LIMA_OPENCODE_SESSION_OPTIONS", "1") == "1"
)
