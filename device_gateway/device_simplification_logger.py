"""Simplification logger for recording profile constraint decisions."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_log = logging.getLogger(__name__)

# ── Configuration ───────────────────────────────────────────────────────────────

ARTIFACT_DIR = Path("device_artifacts")

# ── Public API ────────────────────────────────────────────────────────────────


def record_simplification(
    device_id: str,
    task_id: str,
    simplification_type: str,
    reason: str,
    original: dict[str, Any],
    constrained: dict[str, Any],
) -> None:
    """Record a profile simplification decision to artifact log.

    This must be called whenever apply_profile_constraints() makes a change
    (downgrade, cap, gate) to the task. Silent geometry repair is FORBIDDEN.
    """
    if not device_id or not task_id:
        _log.warning("Cannot record simplification: missing device_id or task_id")
        return

    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    record = {
        "timestamp": now,
        "device_id": device_id,
        "task_id": task_id,
        "simplification_type": simplification_type,
        "reason": reason,
        "original": original,
        "constrained": constrained,
    }

    log_path = ARTIFACT_DIR / f"simplification_{device_id}.log"

    try:
        log_path.parent.mkdir(exist_ok=True)
        with log_path.open("a", encoding="utf-8") as f:
            f.write(f"{json.dumps(record, ensure_ascii=False)}\n")
        _log.debug("Recorded simplification: device=%s, type=%s", device_id, simplification_type)
    except (OSError, ValueError) as e:
        _log.warning("Failed to record simplification to artifact log: %s", e)
