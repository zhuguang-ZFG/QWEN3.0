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
    "LIMA_OPENCODE_PREFERRED_BACKEND", "scnet_ds_pro"
)


def _csv_tuple(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


# Preferred backend order for OpenCode requests that carry the full tool list.
# These backends tolerate OpenCode's large tool surface via LiMa's text-tool
# adapter and avoid providers that reject large native tool schemas.
OPENCODE_TOOL_STABLE_BACKENDS = _csv_tuple(
    os.environ.get(
        "LIMA_OPENCODE_TOOL_STABLE_BACKENDS",
        "scnet_ds_pro,scnet_ds_flash,scnet_qwen235b,scnet_qwen30b",
    )
)

# ── Fast path ───────────────────────────────────────────────────────────────
# Pin OpenCode to preferred backend; skip speculative routing / heavy injections.
OPENCODE_DIRECT_STREAM = os.environ.get("LIMA_OPENCODE_DIRECT_STREAM", "1") == "1"

# OpenCode can keep a streaming response open while a coding backend thinks.
# Use this as a floor over per-backend timeouts so direct stream does not cut
# off otherwise healthy IDE responses.
OPENCODE_DIRECT_STREAM_READ_TIMEOUT = float(
    os.environ.get("LIMA_OPENCODE_DIRECT_STREAM_READ_TIMEOUT", "180")
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


# ── Startup summary ────────────────────────────────────────────────────────
def log_config_summary() -> None:
    """Log a compact summary of all OpenCode settings at server startup."""
    lines = [
        f"tool_mode={OPENCODE_TOOL_MODE}",
        f"direct_stream={OPENCODE_DIRECT_STREAM}",
        f"direct_stream_read_timeout={OPENCODE_DIRECT_STREAM_READ_TIMEOUT:g}s",
        f"preferred={OPENCODE_PREFERRED_BACKEND}",
        f"tool_stable={list(OPENCODE_TOOL_STABLE_BACKENDS)}",
        f"fast_boost={OPENCODE_FAST_BOOST}",
        f"fast_backends={sorted(OPENCODE_FAST_BACKENDS)}",
        f"rate_multiplier={OPENCODE_RATE_MULTIPLIER}x",
        f"keep_turns={OPENCODE_KEEP_RECENT_TURNS}",
        f"skip_spec_tools={OPENCODE_SKIP_SPECULATIVE_TOOLS}",
        f"reasoning_variants={OPENCODE_REASONING_VARIANTS}",
        f"session_options={OPENCODE_SESSION_OPTIONS}",
        f"skip_skills={sorted(OPENCODE_SKIPPED_SKILL_CATEGORIES)}",
    ]
    print(f"[opencode-config] {' | '.join(lines)}", flush=True)
