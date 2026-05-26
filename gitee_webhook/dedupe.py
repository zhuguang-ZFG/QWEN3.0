"""Cross-host push SHA dedupe (GitHub vs Gitee)."""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

_DEFAULT_TTL = 300
_LOCK = threading.Lock()
_MEMORY: dict[str, dict[str, float]] = {"github": {}, "gitee": {}}


def _ttl_seconds() -> int:
    raw = os.environ.get("WEBHOOK_PUSH_DEDUPE_TTL", str(_DEFAULT_TTL)).strip()
    try:
        return max(30, int(raw))
    except ValueError:
        return _DEFAULT_TTL


def _store_path() -> Path:
    root = Path(os.environ.get("LIMA_DATA_DIR", "data"))
    return root / "webhook_push_dedupe.json"


def _prune(bucket: dict[str, float], now: float, ttl: int) -> None:
    stale = [sha for sha, ts in bucket.items() if now - ts > ttl]
    for sha in stale:
        bucket.pop(sha, None)


def _load_file() -> dict[str, dict[str, float]]:
    path = _store_path()
    if not path.is_file():
        return {"github": {}, "gitee": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return {
                "github": {k: float(v) for k, v in (data.get("github") or {}).items()},
                "gitee": {k: float(v) for k, v in (data.get("gitee") or {}).items()},
            }
    except Exception:
        pass
    return {"github": {}, "gitee": {}}


def _save_file(data: dict[str, dict[str, float]]) -> None:
    path = _store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def record_push_shas(shas: list[str], *, source: str = "github") -> None:
    if not shas:
        return
    src = source if source in {"github", "gitee"} else "github"
    now = time.time()
    ttl = _ttl_seconds()
    with _LOCK:
        file_data = _load_file()
        bucket = file_data.setdefault(src, {})
        mem = _MEMORY.setdefault(src, {})
        for sha in shas:
            sha = sha.strip().lower()
            if len(sha) < 7:
                continue
            bucket[sha] = now
            mem[sha] = now
        _prune(bucket, now, ttl)
        _prune(mem, now, ttl)
        _MEMORY[src] = mem
        _save_file(file_data)


def should_skip_gitee_push(shas: list[str]) -> bool:
    """True if any SHA was recently seen from GitHub (dual-push dedupe)."""
    if os.environ.get("GITEE_WEBHOOK_DEDUPE_GITHUB", "1").strip().lower() in {"0", "false", "no"}:
        return False
    if not shas:
        return False
    now = time.time()
    ttl = _ttl_seconds()
    with _LOCK:
        file_data = _load_file()
        github = file_data.get("github") or {}
        _prune(github, now, ttl)
        for sha in shas:
            key = sha.strip().lower()
            ts = github.get(key)
            if ts is not None and now - ts <= ttl:
                return True
    return False


def reset_dedupe_for_tests() -> None:
    with _LOCK:
        _MEMORY["github"].clear()
        _MEMORY["gitee"].clear()
        path = _store_path()
        if path.is_file():
            path.unlink()
