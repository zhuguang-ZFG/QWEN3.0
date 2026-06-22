"""Shared helpers for chat request handling (CQ-014 slice 4)."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import sys
from datetime import datetime

import asyncio

from backends_constants import THINKING_BACKENDS
from backends_registry import BACKENDS
import health_tracker
import http_caller
import routing_executor

_log = logging.getLogger(__name__)

_DISTILL_QUEUE_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "distill_queue", "pending")
_DEBUG = os.environ.get("LIMA_DEBUG", "") == "1"


def _get_thinking_backend() -> str:
    """Pick an available thinking-capable backend."""
    for name in THINKING_BACKENDS:
        if name in BACKENDS and BACKENDS[name].get("key") and not health_tracker.is_cooled_down(name):
            return name
    return "longcat_thinking"


def _call_thinking_backend(backend: str, msgs: list, max_tokens: int, ide: str) -> str | None:
    _, answer, _ = routing_executor.execute(
        [backend],
        lambda b, m, t: http_caller.call_api(b, m, t, ide=ide),
        msgs,
        max_tokens,
    )
    if not answer:
        return None
    if isinstance(answer, str) and (answer.startswith("[ERR]") or "暂时不可用" in answer):
        return None
    return answer


async def thinking_route(query: str, max_tokens: int = 4096, ide: str = "unknown") -> dict | None:
    """Route to a thinking-capable backend. Returns result dict or None on failure."""
    thinking_backend = _get_thinking_backend()
    msgs = [{"role": "user", "content": query}]
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(_call_thinking_backend, thinking_backend, msgs, max_tokens, ide),
            timeout=90.0,
        )
        if result:
            return {"answer": result, "backend": thinking_backend, "thinking_mode": True}
    except asyncio.TimeoutError:
        _log.warning("thinking backend timeout backend=%s", thinking_backend)
    except Exception as exc:
        _log.warning("thinking backend failed backend=%s: %s", thinking_backend, type(exc).__name__)
    for alt in THINKING_BACKENDS:
        if alt == thinking_backend:
            continue
        if alt not in BACKENDS or not BACKENDS[alt].get("key"):
            continue
        if health_tracker.is_cooled_down(alt):
            continue
        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(_call_thinking_backend, alt, msgs, max_tokens, ide),
                timeout=90.0,
            )
            if result:
                return {"answer": result, "backend": alt, "thinking_mode": True}
        except asyncio.TimeoutError:
            _log.warning("thinking alt backend timeout backend=%s", alt)
        except Exception as exc:
            _log.warning("thinking alt backend failed backend=%s: %s", alt, exc)
    return None


def attach_memory_recall_meta(response: dict, memory_meta: dict) -> dict:
    if memory_meta.get("checked") and isinstance(response, dict):
        response.setdefault("x_lima_meta", {})["memory_recall"] = memory_meta
    return response


def log_sys_prompt(sys_prompt: str) -> None:
    """Record new system prompts with SHA256 dedup."""
    sys_prompt_dir = os.path.join(os.path.dirname(_DISTILL_QUEUE_DIR), "sys_prompts")
    os.makedirs(sys_prompt_dir, exist_ok=True)
    phash = hashlib.sha256(sys_prompt.encode()).hexdigest()[:16]

    existing = os.listdir(sys_prompt_dir) if os.path.exists(sys_prompt_dir) else []
    if any(phash in name for name in existing):
        return

    ide_source = "unknown"
    ide_markers = {
        "Claude Code": "claude_code",
        "Cursor": "cursor",
        "You are Cursor": "cursor",
        "GitHub Copilot": "copilot",
        "Codex": "codex",
        "Windsurf": "windsurf",
    }
    for marker, source in ide_markers.items():
        if marker in sys_prompt:
            ide_source = source
            break

    entry = {
        "ide_source": ide_source,
        "prompt_hash": phash,
        "prompt_preview": sys_prompt[:500],
        "prompt_length": len(sys_prompt),
        "logged_at": datetime.now().isoformat(),
    }
    fname = os.path.join(sys_prompt_dir, f"{ide_source}_{phash}.json")
    with open(fname, "w", encoding="utf-8") as handle:
        json.dump(entry, handle, ensure_ascii=False, indent=2)
    if _DEBUG:
        print(f"[SYS_PROMPT] new: {ide_source} ({len(sys_prompt)} chars)", file=sys.stderr)
