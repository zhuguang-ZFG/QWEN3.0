"""
Enriched context injection — date, location, device awareness.

Injects current date/time, user location (from IP), and device info
(from User-Agent) into the system prompt.  Designed for chatbots that
lack native tool-calling — the model sees this as ambient context.

All sub-operations fail gracefully: if IP lookup or UA parsing fails,
we still inject whatever we can (at minimum the date).
"""

from __future__ import annotations

import logging
import re
from datetime import datetime

_log = logging.getLogger(__name__)

# ── Public API ────────────────────────────────────────────────────────────────

def inject_enriched_context(
    messages: list[dict],
    *,
    client_ip: str = "",
    user_agent: str = "",
) -> list[dict]:
    """Inject date, location, and device context as a system message.

    Returns a new messages list with the enrichment message inserted
    right after the first system message (or at position 0 if none).
    """
    parts: list[str] = []

    # 1. Date / time (always available)
    date_part = _build_date_context()
    if date_part:
        parts.append(date_part)

    # 2. Location (from IP, best-effort)
    if client_ip:
        loc_part = _build_location_context(client_ip)
        if loc_part:
            parts.append(loc_part)

    # 3. Device (from User-Agent, best-effort)
    if user_agent:
        dev_part = _build_device_context(user_agent)
        if dev_part:
            parts.append(dev_part)

    if not parts:
        return list(messages)

    enrichment = "\n".join(parts)
    enriched_msg = {"role": "system", "content": enrichment}

    result = list(messages)
    # Insert after the first existing system message, or at position 0
    insert_pos = 0
    for i, msg in enumerate(result):
        if isinstance(msg, dict) and msg.get("role") == "system":
            insert_pos = i + 1
        else:
            break
    result.insert(insert_pos, enriched_msg)
    return result


# ── Date / time ───────────────────────────────────────────────────────────────

_WEEKDAY_CN = {
    "Monday": "星期一",
    "Tuesday": "星期二",
    "Wednesday": "星期三",
    "Thursday": "星期四",
    "Friday": "星期五",
    "Saturday": "星期六",
    "Sunday": "星期日",
}


def _build_date_context() -> str:
    try:
        now = datetime.now()
        weekday_en = now.strftime("%A")
        weekday_cn = _WEEKDAY_CN.get(weekday_en, weekday_en)
        date_str = now.strftime("%Y年%m月%d日")
        time_str = now.strftime("%H:%M")
        return f"当前时间: {date_str} {weekday_cn} {time_str}"
    except Exception as exc:
        _log.debug("date_context build failed: %s", exc)
        return ""


# ── Location ──────────────────────────────────────────────────────────────────

def _build_location_context(client_ip: str) -> str:
    try:
        from routes.request_tracking import get_ip_location

        location = get_ip_location(client_ip)
        if location and location not in ("本地", "未知", ""):
            return f"用户位置: {location}"
    except ImportError:
        _log.debug("request_tracking not available for location lookup")
    except Exception as exc:
        _log.debug("location lookup failed for ip=%s: %s", client_ip, exc)
    return ""


# ── Device / User-Agent parsing ───────────────────────────────────────────────

# Lightweight UA parsing — no external library needed.
_OS_PATTERNS: list[tuple[str, str]] = [
    (r"Windows NT 10", "Windows 10"),
    (r"Windows NT 11", "Windows 11"),
    (r"Windows NT 6\.3", "Windows 8.1"),
    (r"Windows NT 6\.1", "Windows 7"),
    (r"Mac OS X 10[._]15", "macOS Catalina"),
    (r"Mac OS X 10[._]14", "macOS Mojave"),
    (r"Mac OS X 1[1-9][._]", "macOS"),
    (r"Mac OS X", "macOS"),
    (r"Android (\d+[\d.]*)", "Android"),
    (r"iPhone OS (\d+[_\d]*)", "iOS"),
    (r"iPad.*OS (\d+[_\d]*)", "iPadOS"),
    (r"Linux", "Linux"),
    (r"CrOS", "ChromeOS"),
]

_BROWSER_PATTERNS: list[tuple[str, str]] = [
    (r"EdgA?/", "Edge"),
    (r"Edge/", "Edge"),
    (r"Chrome/", "Chrome"),
    (r"Safari/", "Safari"),
    (r"Firefox/", "Firefox"),
    (r"OPR/|Opera/", "Opera"),
]

_APP_PATTERNS: list[tuple[str, str]] = [
    (r"Claude Code", "Claude Code"),
    (r"cursor-ide", "Cursor"),
    (r"GitHub Copilot", "GitHub Copilot"),
    (r"Codex CLI", "Codex CLI"),
    (r"aider", "Aider"),
    (r"Continue", "Continue"),
    (r"Cline", "Cline"),
    (r"Windsurf", "Windsurf"),
    (r"Kiro", "Kiro"),
    (r"Trae", "Trae"),
    (r"python-requests|Python/|python-httpx|aiohttp", "Python 脚本"),
    (r"curl/", "curl"),
    (r"PostmanRuntime", "Postman"),
]


def _parse_user_agent(ua: str) -> str:
    """Parse User-Agent into a human-readable device description."""
    if not ua or not isinstance(ua, str):
        return ""

    # Detect app / IDE first
    for pattern, label in _APP_PATTERNS:
        if re.search(pattern, ua, re.IGNORECASE):
            return label

    parts: list[str] = []

    # OS
    for pattern, label in _OS_PATTERNS:
        if re.search(pattern, ua):
            parts.append(label)
            break

    # Browser
    for pattern, label in _BROWSER_PATTERNS:
        if re.search(pattern, ua):
            parts.append(label)
            break

    # Mobile marker
    if re.search(r"Mobile|iPhone|Android.*Mobile", ua):
        if "Mobile" not in " ".join(parts):
            parts.append("移动端")

    if not parts:
        return ""

    return " / ".join(parts)


def _build_device_context(user_agent: str) -> str:
    try:
        device = _parse_user_agent(user_agent)
        if device:
            return f"用户设备: {device}"
    except Exception as exc:
        _log.debug("device_context build failed: %s", exc)
    return ""
