"""Deterministic device command parser with grammar rules and confidence scoring.

Upgrades the first-slice keyword mapping to a small pattern-based parser
that extracts structured intents from natural-language commands.

A gated LLM-backed planner (LIMA_DEVICE_LLM_PLANNER=1) can override
low-confidence parses. Until that gate is opened, unknown commands fall
back to write_text with an explicit explanation.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from config.settings import FLAGS

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
            r"^(移动|移动到|移到|go\s*to|move\s*to)\s*x\s*(?P<x>-?\d+)\s*y\s*(?P<y>-?\d+)(\s*z\s*(?P<z>-?\d+))?"
        ),
        "move_abs",
        None,
    ),
    (re.compile(r"^move\s+x\s*(?P<dx>-?\d+)\s*y\s*(?P<dy>-?\d+)", re.I), "move_rel", None),
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
        "stop": "stop",
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

    If no pattern matches, returns a low-confidence fallback with an
    explicit explanation of why the command was rejected.
    """
    stripped = (text or "").strip()
    if not stripped:
        return _make_result(
            "write_text",
            {"text": "hello"},
            0.0,
            "empty command, falling back to write_text",
        )

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

    return _make_result(
        "write_text",
        {"text": stripped[:40]},
        0.1,
        f"unknown command '{stripped[:40]}', falling back to write_text",
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
            return llm_result

    return {
        "capability": result["capability"],
        "params": result.get("params", {}),
        "source": "voice",
        "explanation": result.get("explanation", ""),
    }


def _llm_replan(text: str, _fallback: dict[str, Any]) -> dict[str, Any] | None:
    """Gated LLM replanning for ambiguous commands. Returns None if unavailable."""
    try:
        import http_caller

        answer = http_caller.call_api(
            "longcat_lite",
            [
                {
                    "role": "user",
                    "content": (
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
                    ),
                }
            ],
            max_tokens=200,
        )
        import json as _json

        json_text = answer.strip()
        if json_text.startswith("```json"):
            json_text = json_text.removeprefix("```json").strip()
        elif json_text.startswith("```"):
            json_text = json_text.removeprefix("```").strip()
        if json_text.endswith("```"):
            json_text = json_text.removesuffix("```").strip()
        parsed = _json.loads(json_text)
        if isinstance(parsed, dict) and "capability" in parsed:
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
    except Exception as exc:
        _log.warning("device llm planner parse failed: %s", exc, exc_info=True)
    return None
