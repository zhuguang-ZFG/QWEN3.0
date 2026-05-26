"""Unified Capability Evidence — one schema for all production loops.

Records structured evidence for Chat/IDE, LiMa Code Worker, Device Gateway,
Backend Eval, and Ops Learning. Evidence-only — never auto-mutates routing
pools, prompts, worker permissions, or device behavior.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

DEFAULT_PATH = Path("data/capability_evidence.jsonl")
ALLOWED_LOOPS = {
    "chat_ide",
    "limacode_worker",
    "device_gateway",
    "backend_eval",
    "ops_learning",
}


def _store_path() -> Path:
    return Path(os.environ.get("LIMA_CAPABILITY_EVIDENCE_PATH", str(DEFAULT_PATH)))


def _clean(value: Any) -> Any:
    if isinstance(value, str):
        text = value
        # Redact known secret prefixes (only at start or after whitespace)
        for pattern in ("sk-", "gho_", "ghp_", "github_pat_"):
            import re
            text = re.sub(rf"(^|\s)({re.escape(pattern)}\S+)", r"\1[REDACTED]", text)
        # Redact Bearer tokens
        import re
        text = re.sub(r"Bearer\s+\S+", "Bearer [REDACTED]", text)
        return text[:500]
    if isinstance(value, list):
        return [_clean(v) for v in value[:10]]
    if isinstance(value, dict):
        return {str(k)[:80]: _clean(v) for k, v in list(value.items())[:50]}
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return str(value)[:500]


def record_evidence(
    *,
    loop: str,
    request_id: str = "",
    task_id: str = "",
    device_id: str = "",
    entrypoint: str = "",
    selected_backend: str = "",
    fallback_used: bool = False,
    latency_ms: int = 0,
    status: str = "ok",
    evidence: list[str] | None = None,
    artifact_paths: list[str] | None = None,
    rollback: str = "",
) -> dict[str, Any]:
    """Record one capability evidence event to JSONL."""
    if loop not in ALLOWED_LOOPS:
        raise ValueError(f"unsupported capability loop: {loop}")

    row = {
        "schema_version": "lima.capability_evidence.v0",
        "loop": loop,
        "request_id": _clean(request_id),
        "task_id": _clean(task_id),
        "device_id": _clean(device_id),
        "entrypoint": _clean(entrypoint),
        "selected_backend": _clean(selected_backend),
        "fallback_used": bool(fallback_used),
        "latency_ms": max(0, int(latency_ms or 0)),
        "status": _clean(status),
        "evidence": _clean(evidence or []),
        "artifact_paths": _clean(artifact_paths or []),
        "rollback": _clean(rollback),
        "created_at": time.time(),
    }
    path = _store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    return row


def recent_evidence(*, limit: int = 20) -> list[dict[str, Any]]:
    """Return recent evidence rows (newest last)."""
    path = _store_path()
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines()[-max(1, min(limit, 100)):]:
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows
