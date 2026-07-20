"""Gated LLM-backed device command replanner.

Extracted from ``device_gateway.intent`` (deep-slim T batch): the LLM
replanning subdomain — capability whitelist/blacklist, prompt construction,
code-fence stripping, plan interpretation, and the gated HTTP call — lives here
as pure functions. ``device_gateway.intent`` re-exports
``DANGEROUS_CAPABILITIES`` and ``_llm_replan`` for backward compatibility
(production ``prompt_engineering/layers.py`` and tests import them from the
original module path).
"""

from __future__ import annotations

import logging
from typing import Any

_log = logging.getLogger(__name__)

# ── Safety: capabilities whitelist and dangerous blacklist ────────────────────
_ALLOWED_CAPABILITIES = frozenset(
    {
        "home",
        "pause",
        "resume",
        "stop",
        "get_device_info",
        "write_text",
        "draw_generated",
        "run_path",
        "move_abs",
        "move_rel",
        "rejected",
    }
)

DANGEROUS_CAPABILITIES = frozenset(
    {
        "spindle_on",
        "laser_on",
        "heater_on",
        "gpio_high",
        "m3",
        "m4",
        "m8",
        "spindle_cw",
        "spindle_ccw",
    }
)

# GW-R3-8: capabilities that produce physical pen/gantry motion. When the
# pattern parser already resolved a command to "rejected" (unrecognized
# utterance), the LLM replanner must NOT be allowed to turn it into one of
# these — that would undo GW-WH ("unrecognized speech must never become pen
# motion") and could route an unmatched emergency-stop variant into drawing
# instead of stopping. Replanning a rejected command into a control capability
# (home/pause/resume/stop/estop/get_device_info) is still permitted.
MOTION_CAPABILITIES = frozenset(
    {
        "run_path",
        "write_text",
        "draw_generated",
        "move_abs",
        "move_rel",
    }
)


def _build_llm_planner_prompt(text: str) -> str:
    """Build the system/user prompt instructing the LLM to output a capability JSON."""
    return (
        "You are a device command parser for a CNC writing machine. "
        "Given a user command, output ONLY a JSON object with keys: "
        "capability (one of: run_path, write_text, draw_generated, "
        "home, pause, resume, stop, get_device_info, move_abs, move_rel, rejected), "
        "params (object with text/prompt/x/y/z as needed). "
        "If the command doesn't make sense for a CNC machine, set "
        "capability to 'rejected' and include a 'reason' key.\n\n"
        f"NEVER output any of these dangerous capabilities: "
        f"{', '.join(sorted(DANGEROUS_CAPABILITIES))}.\n\n"
        f"Command: {text}\n\nJSON:"
    )


def _strip_code_fence(text: str) -> str:
    """Strip a leading/trailing markdown code fence (```json or ```) from a string."""
    s = text.strip()
    if s.startswith("```json"):
        s = s.removeprefix("```json").strip()
    elif s.startswith("```"):
        s = s.removeprefix("```").strip()
    if s.endswith("```"):
        s = s.removesuffix("```").strip()
    return s


def _interpret_llm_plan(parsed: Any) -> dict[str, Any] | None:
    """Validate a parsed LLM plan dict against the whitelist; returns normalized result or None."""
    if not (isinstance(parsed, dict) and "capability" in parsed):
        return None
    capability = parsed["capability"]
    if capability not in _ALLOWED_CAPABILITIES:
        _log.warning("device llm planner returned unapproved capability: %s", capability)
        return None
    return {
        "capability": capability,
        "params": parsed.get("params", {}),
        "source": "llm",
        "explanation": f"LLM planned: {parsed.get('reason', capability)}",
    }


def _llm_replan(text: str, _fallback: dict[str, Any]) -> dict[str, Any] | None:
    """Gated LLM replanning for ambiguous commands. Returns None if unavailable."""
    try:
        import http_caller
        import json as _json

        answer = http_caller.call_api(
            "longcat_lite",
            [{"role": "user", "content": _build_llm_planner_prompt(text)}],
            max_tokens=200,
        )
        parsed = _json.loads(_strip_code_fence(answer))
        return _interpret_llm_plan(parsed)
    except Exception as exc:
        _log.warning("device llm planner parse failed: %s", exc, exc_info=True)
    return None
