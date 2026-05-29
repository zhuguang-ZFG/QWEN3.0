"""Optional ops alerts via Apprise (default off)."""

from __future__ import annotations

import logging
import os
from typing import Any

from notify.apprise_bridge import apprise_enabled, notify

_log = logging.getLogger(__name__)


def ops_alerts_enabled() -> bool:
    if not apprise_enabled():
        return False
    return os.environ.get("LIMA_OPS_ALERTS", "0").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def maybe_notify_oldllm_failure(report: dict[str, Any]) -> tuple[bool, str]:
    """Fire Apprise when upstream chat probe fails."""
    if not ops_alerts_enabled():
        return False, "disabled"
    if report.get("upstream_chat_ok", report.get("any_chat_ok")):
        return False, "healthy"

    lines = ["TheOldLLM upstream chat 不可用"]
    for item in report.get("results") or []:
        if item.get("label") != "upstream" or item.get("skipped"):
            continue
        kind = item.get("kind", "?")
        mark = "ok" if item.get("ok") else "FAIL"
        lines.append(f"{kind}: {mark} status={item.get('status')}")

    hints = report.get("hints") or []
    if hints:
        lines.append("修复: " + hints[0][:120])

    body = "\n".join(lines)
    ok, detail = notify(body, title="LiMa OldLLM")
    if ok:
        _log.info("oldllm ops alert sent via apprise")
    else:
        _log.debug("oldllm ops alert skipped: %s", detail)
    return ok, detail
