"""Deterministic device command parser with grammar rules and confidence scoring.

Upgrades the first-slice keyword mapping to a small pattern-based parser
that extracts structured intents from natural-language commands.

A gated LLM-backed planner (LIMA_DEVICE_LLM_PLANNER=1) can override
low-confidence parses. Until that gate is opened, unknown commands are
rejected (capability="rejected", no motion task) with an explicit
explanation — GW-WH: an unrecognized utterance must never be turned into
pen motion (the old write_text fallback did exactly that).
"""

from __future__ import annotations

import logging
import re
from typing import Any

from config.settings import FLAGS

# LLM replanning subdomain lives in intent_llm_planner (deep-slim T batch).
# Re-exported here for backward compatibility: production prompt_engineering/
# layers.py and tests import DANGEROUS_CAPABILITIES from device_gateway.intent,
# and tests call device_gateway.intent._llm_replan directly.
from device_gateway.intent_llm_planner import (  # noqa: F401  re-export (prod + tests import from here)
    DANGEROUS_CAPABILITIES,
    _REPLAN_BLOCKED_CAPABILITIES,
    _llm_replan,
)

_log = logging.getLogger(__name__)

# ── Emergency stop (GW-WH) ───────────────────────────────────────────────────
# Emergency semantics get absolute priority over every other pattern (and the
# fallback): any utterance containing 急停 / 紧急停止 / the common ASR
# mishearing 估停 / estop / e-stop / emergency [stop] resolves to the estop
# control command. Substring search is intentional — for emergency phrasing,
# stopping is the fail-safe direction.
_EMERGENCY_STOP_RE = re.compile(r"急停|紧急停止|估停|\be[-_ ]?stop\b|\bemergency(?:\s+stop)?\b", re.I)

# ── Command patterns ─────────────────────────────────────────────────────────
# Each pattern is (regex, capability, param_map_fn)
# Patterns are tried in order; first match wins.
# Groups named (?P<kw>) are extracted into params.

_COMMAND_PATTERNS: list[tuple[re.Pattern, str, dict | None]] = [
    # Control commands
    (re.compile(r"^归[零零位]$|^回[零位原点]$|^(?P<kw>home|go\s*home)$", re.I), "home", None),
    (re.compile(r"^暂停$|^(?P<kw>pause|hold)$", re.I), "pause", None),
    (re.compile(r"^继续$|^(?P<kw>resume|continue|go\s*on)$", re.I), "resume", None),
    (re.compile(r"^停止$|^(?P<kw>stop|halt|abort)$", re.I), "stop", None),
    (re.compile(r"^设备信息$|^(?P<kw>device\s*info|status|info)$", re.I), "get_device_info", None),
    # Write text
    (re.compile(r"^写(字?|出?|入?)(?P<text>.{1,40})$"), "write_text", None),
    (re.compile(r"^(?P<kw>write|draw\s*text|print)\s+(?P<text>.{1,40})$", re.I), "write_text", None),
    # Draw
    (re.compile(r"^画(个?|出?|入?)(?P<prompt>.{1,80})$"), "draw_generated", None),
    (re.compile(r"^(?P<kw>draw|sketch|plot)\s+(?P<prompt>.{1,80})$", re.I), "draw_generated", None),
    # Run path (explicit motion path execution)
    (re.compile(r"^运行路径$|^run[_ ]?path$", re.I), "run_path", None),
    (re.compile(r"^执行路径\s*(?P<prompt>.{1,40})$"), "run_path", None),  # Explicit path (SVG-style)
    (re.compile(r"^(?P<kw>path|svg|gcode)\s+(?P<prompt>.{1,200})$", re.I), "draw_generated", None),
    # Move commands
    (
        re.compile(
            r"^(移动|移动到|移到|go\s*to|move\s*to)\s*x\s*(?P<x>-?\d{1,10})\s*y\s*(?P<y>-?\d{1,10})(\s*z\s*(?P<z>-?\d{1,10}))?"
        ),
        "move_abs",
        None,
    ),
    (re.compile(r"^move\s+x\s*(?P<dx>-?\d{1,10})\s*y\s*(?P<dy>-?\d{1,10})", re.I), "move_rel", None),
]

# ── Public API ───────────────────────────────────────────────────────────────


def resolve_direct_device_command(text: str) -> dict[str, Any] | None:
    """Legacy direct-command mapping. Kept for backward compatibility."""
    normalized = (text or "").strip().lower()
    control_map = {
        "归零": "home",
        "回零": "home",
        "home": "home",
        "暂停": "pause",
        "pause": "pause",
        "继续": "resume",
        "resume": "resume",
        "停止": "stop",
        "停": "stop",
        "停下": "stop",
        "停下来": "stop",
        "快停": "stop",
        "stop": "stop",
        # GW-WH: emergency stop variants (估停 = common ASR mishearing of 急停).
        "急停": "estop",
        "紧急停止": "estop",
        "估停": "estop",
        "estop": "estop",
        "e-stop": "estop",
        "emergency": "estop",
        "emergency stop": "estop",
        "设备信息": "get_device_info",
    }
    if normalized in control_map:
        return {"capability": control_map[normalized], "params": {}, "source": "voice"}
    return None


def _extract_pattern_params(m: re.Match, text: str) -> dict[str, Any]:
    """Extract typed params from a regex match groupdict."""
    params: dict[str, Any] = {}
    groupdict = m.groupdict()
    for key in ("text", "prompt", "x", "y", "z", "dx", "dy"):
        val = groupdict.get(key)
        if val is None:
            continue
        if key in ("x", "y", "z", "dx", "dy"):
            try:
                params[key] = float(val)
            except ValueError:
                params[key] = val
        else:
            params[key] = val
    if not params and m.lastgroup:
        params["text"] = text[:40]
    return params


def _make_result(capability: str, params: dict[str, Any], confidence: float, explanation: str) -> dict[str, Any]:
    return {
        "capability": capability,
        "params": params,
        "source": "voice",
        "confidence": confidence,
        "explanation": explanation,
    }


def parse_command(text: str) -> dict[str, Any]:
    """Parse a voice/text command into a structured intent.

    Returns:
        {"capability": "...", "params": {...}, "source": "voice",
         "confidence": 0.0–1.0, "explanation": "..."}

    If no pattern matches, returns a low-confidence "rejected" result (no
    motion task is generated) with an explicit explanation.
    """
    stripped = (text or "").strip()
    if not stripped:
        return _make_result("rejected", {}, 0.0, "empty command: nothing to execute")

    # GW-WH: emergency stop outranks every other pattern, including fallback.
    if _EMERGENCY_STOP_RE.search(stripped):
        return _make_result("estop", {}, 1.0, "emergency stop keyword matched: estop")

    direct = resolve_direct_device_command(stripped)
    if direct:
        direct["confidence"] = 1.0
        direct["explanation"] = f"exact match: {direct['capability']}"
        return direct

    for pattern, capability, _param_map in _COMMAND_PATTERNS:
        m = pattern.match(stripped)
        if m:
            params = _extract_pattern_params(m, stripped)
            return _make_result(
                capability,
                params,
                0.9,
                f"pattern matched: {capability}",
            )

    # GW-WH: low-confidence fallback must NOT generate a motion task — the old
    # write_text fallback turned unknown speech (e.g. an unmatched emergency
    # phrase) into physical pen movement. "rejected" fails capability
    # validation downstream, so the task is refused and needs clarification.
    return _make_result(
        "rejected",
        {},
        0.1,
        f"unknown command '{stripped[:40]}': no pattern matched, rejected (needs clarification)",
    )


def resolve_voice_task(text: str) -> dict[str, Any]:
    """Resolve voice/text to a motion intent.

    Uses pattern-based parser with optional LLM override for ambiguous
    commands (gated behind LIMA_DEVICE_LLM_PLANNER=1).
    """
    result = parse_command(text)

    if result["confidence"] < 0.5 and FLAGS.device_llm_planner:
        llm_result = _llm_replan(text, result)
        if llm_result:
            # GW-R3-8 / GW-R3-12: a "rejected" parse means no pattern matched —
            # an unrecognized (possibly emergency) utterance. GW-WH requires such
            # input never become a DRAWING command (write_text/draw/run_path).
            # Point-to-point move and control caps stay allowed: fuzzy voice
            # positioning is wanted and moves are bounded server-side + firmware.
            if result["capability"] == "rejected" and llm_result["capability"] in _REPLAN_BLOCKED_CAPABILITIES:
                _log.warning(
                    "device llm planner tried to replan rejected command into drawing capability %s; "
                    "refused (GW-R3-8/GW-WH). text=%r",
                    llm_result["capability"],
                    (text or "")[:40],
                )
            else:
                return llm_result

    return {
        "capability": result["capability"],
        "params": result.get("params", {}),
        "source": "voice",
        "explanation": result.get("explanation", ""),
    }
