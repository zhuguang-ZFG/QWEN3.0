"""Optional OpenObserve log export for LiMa events (PE-C-2)."""

from __future__ import annotations

import base64
import json
import logging
import os
import threading
import urllib.error
import urllib.request
from dataclasses import asdict, is_dataclass

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_last_fail_log: float = 0.0
_FAIL_LOG_INTERVAL = 300.0


def openobserve_enabled() -> bool:
    return os.environ.get("OPENOBSERVE_ENABLED", "0").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def _config() -> dict[str, str]:
    return {
        "url": os.environ.get("OPENOBSERVE_URL", "http://127.0.0.1:5080").strip().rstrip("/"),
        "org": os.environ.get("OPENOBSERVE_ORG", "default").strip() or "default",
        "stream": os.environ.get("OPENOBSERVE_STREAM", "lima_events").strip() or "lima_events",
        "user": os.environ.get("OPENOBSERVE_USER", "root@example.com").strip(),
        "password": os.environ.get("OPENOBSERVE_PASSWORD", "").strip(),
    }


def event_to_record(event: object) -> dict:
    if is_dataclass(event):
        raw = asdict(event)
    elif isinstance(event, dict):
        raw = dict(event)
    else:
        raw = {"message": str(event)[:500]}
    return {k: v for k, v in raw.items() if v not in ("", None, [], {})}


def ingest_url(cfg: dict[str, str]) -> str:
    return f"{cfg['url']}/api/{cfg['org']}/{cfg['stream']}/_json"


def post_records(records: list[dict], *, cfg: dict[str, str] | None = None) -> bool:
    if not records:
        return True
    conf = cfg or _config()
    if not conf["password"]:
        _log_failures_throttled("openobserve skipped: OPENOBSERVE_PASSWORD missing")
        return False

    body = json.dumps(records, ensure_ascii=False).encode("utf-8")
    auth = base64.b64encode(f"{conf['user']}:{conf['password']}".encode()).decode()
    req = urllib.request.Request(
        ingest_url(conf),
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Basic {auth}",
            "User-Agent": "LiMa-OpenObserve/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            return 200 <= resp.status < 300
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        _log_failures_throttled(f"openobserve ingest failed: {type(exc).__name__}")
        return False


def maybe_export_event(event: object) -> None:
    if not openobserve_enabled():
        return
    post_records([event_to_record(event)])


def _log_failures_throttled(message: str) -> None:
    global _last_fail_log
    import time

    now = time.monotonic()
    with _lock:
        if now - _last_fail_log < _FAIL_LOG_INTERVAL:
            return
        _last_fail_log = now
    logger.warning(message)
