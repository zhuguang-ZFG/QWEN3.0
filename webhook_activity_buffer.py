"""Ring buffer for GitHub/Gitee webhook activity (TG-GH-3)."""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

_MAX_EVENTS = 50
_LOCK = threading.Lock()


def _store_path() -> Path:
    root = Path(os.environ.get("LIMA_DATA_DIR", "data"))
    return root / "webhook_activity.json"


def _load() -> list[dict]:
    path = _store_path()
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data[-_MAX_EVENTS:]
    except Exception:
        pass
    return []


def _save(events: list[dict]) -> None:
    path = _store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(events[-_MAX_EVENTS:], indent=2), encoding="utf-8")


def record_webhook_event(
    *,
    source: str,
    kind: str,
    repo: str = "",
    detail: str = "",
) -> None:
    """Append one webhook summary event."""
    entry = {
        "ts": time.time(),
        "source": source,
        "kind": kind,
        "repo": repo,
        "detail": (detail or "")[:200],
    }
    with _LOCK:
        events = _load()
        events.append(entry)
        _save(events)


def summarize_last_hours(hours: float = 24.0) -> dict[str, dict[str, int]]:
    cutoff = time.time() - hours * 3600
    totals: dict[str, dict[str, int]] = {
        "github": {"push": 0, "pr": 0, "ci_fail": 0, "issue": 0, "release": 0, "other": 0},
        "gitee": {"push": 0, "mr": 0, "other": 0},
    }
    for event in _load():
        if float(event.get("ts") or 0) < cutoff:
            continue
        src = str(event.get("source") or "github")
        kind = str(event.get("kind") or "other")
        bucket = totals.setdefault(src, {})
        bucket[kind] = bucket.get(kind, 0) + 1
    return totals


def format_activity_lines(hours: float = 24.0) -> list[str]:
    totals = summarize_last_hours(hours)
    lines: list[str] = []
    gh = totals.get("github", {})
    if any(gh.values()):
        parts = [
            f"{gh.get('push', 0)} push",
            f"{gh.get('pr', 0)} PR",
            f"{gh.get('ci_fail', 0)} CI fail",
        ]
        if gh.get("issue"):
            parts.append(f"{gh.get('issue', 0)} issue")
        if gh.get("release"):
            parts.append(f"{gh.get('release', 0)} release")
        lines.append(f"GitHub {int(hours)}h: {', '.join(parts)}")
    gt = totals.get("gitee", {})
    if any(gt.values()):
        lines.append(
            f"Gitee {int(hours)}h: {gt.get('push', 0)} push, "
            f"{gt.get('mr', 0)} MR"
        )
    if not lines:
        lines.append(f"Git hosts {int(hours)}h: (no webhook events recorded)")
    return lines


def reset_for_tests() -> None:
    with _LOCK:
        path = _store_path()
        if path.is_file():
            path.unlink()
